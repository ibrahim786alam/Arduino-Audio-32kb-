import os
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

# ============================================================
# SETTINGS
# ============================================================

TARGET_SAMPLE_RATE = 1600
INPUT_FILE = r".AudioArduinoVenv\Aria math FINAL.wav"
OUTPUT_FILE = "audio_data.h"

# Set True if you want to hear the decoded compressed audio
PREVIEW = True

# Keep some room for the Arduino program itself
MAX_AUDIO_BYTES = 32000


# ============================================================
# IMA ADPCM TABLES
# ============================================================

STEP_TABLE = [
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17,
    19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
    50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
    130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
    337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
    876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878,
    2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026,
    4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630,
    9493, 10442, 11487, 12635, 13899, 15289, 16818,
    18500, 20350, 22385, 24623, 27086, 29794, 32767
]

INDEX_TABLE = [
    -1, -1, -1, -1,
     2,  4,  6,  8,
    -1, -1, -1, -1,
     2,  4,  6,  8
]


# ============================================================
# ENCODER
# ============================================================

def encode_ima_adpcm(samples):
    predictor = int(samples[0])
    index = 0

    encoded = bytearray()
    current_byte = 0
    high_nibble = False

    for sample in samples[1:]:
        sample = int(sample)

        step = STEP_TABLE[index]
        difference = sample - predictor

        code = 0

        if difference < 0:
            code = 8
            difference = -difference

        temp = step

        if difference >= temp:
            code |= 4
            difference -= temp

        temp >>= 1

        if difference >= temp:
            code |= 2
            difference -= temp

        temp >>= 1

        if difference >= temp:
            code |= 1

        # Calculate reconstructed difference
        diffq = step >> 3

        if code & 1:
            diffq += step >> 2

        if code & 2:
            diffq += step >> 1

        if code & 4:
            diffq += step

        if code & 8:
            predictor -= diffq
        else:
            predictor += diffq

        predictor = max(-32768, min(32767, predictor))

        index += INDEX_TABLE[code]
        index = max(0, min(88, index))

        # Pack two 4-bit samples into one byte
        if not high_nibble:
            current_byte = code & 0x0F
            high_nibble = True
        else:
            current_byte |= (code & 0x0F) << 4
            encoded.append(current_byte)
            high_nibble = False

    # If odd number of nibbles
    if high_nibble:
        encoded.append(current_byte)

    return bytes(encoded), predictor


# ============================================================
# DECODER
# ============================================================

def decode_ima_adpcm(encoded, initial_predictor):
    predictor = int(initial_predictor)
    index = 0

    decoded = [predictor]

    for byte in encoded:

        for code in (byte & 0x0F, (byte >> 4) & 0x0F):

            step = STEP_TABLE[index]

            diffq = step >> 3

            if code & 1:
                diffq += step >> 2

            if code & 2:
                diffq += step >> 1

            if code & 4:
                diffq += step

            if code & 8:
                predictor -= diffq
            else:
                predictor += diffq

            predictor = max(-32768, min(32767, predictor))

            index += INDEX_TABLE[code]
            index = max(0, min(88, index))

            decoded.append(predictor)

    return np.array(decoded, dtype=np.int16)


# ============================================================
# FIND INPUT FILE
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

input_path = os.path.join(SCRIPT_DIR, INPUT_FILE)
output_path = os.path.join(SCRIPT_DIR, OUTPUT_FILE)

if not os.path.exists(input_path):
    print()
    print("ERROR: Could not find:")
    print(input_path)
    print()
    print("Put TestSound.wav in the same folder as this Python file.")
    input("Press Enter to exit...")
    raise SystemExit


# ============================================================
# LOAD AUDIO
# ============================================================

print("Loading:", input_path)

audio, sample_rate = sf.read(input_path)

# Convert stereo -> mono
if audio.ndim > 1:
    audio = np.mean(audio, axis=1)

# Convert to float
audio = audio.astype(np.float32)

# Resample
if sample_rate != TARGET_SAMPLE_RATE:

    print(
        f"Resampling {sample_rate} Hz -> "
        f"{TARGET_SAMPLE_RATE} Hz..."
    )

    audio = resample_poly(
        audio,
        TARGET_SAMPLE_RATE,
        sample_rate
    )


# ============================================================
# CONVERT TO 16-BIT PCM
# ============================================================

audio = np.clip(audio, -1.0, 1.0)

samples = np.round(audio * 32767).astype(np.int16)

if len(samples) == 0:
    raise RuntimeError("Audio file contains no samples.")


# ============================================================
# COMPRESS
# ============================================================

print("Compressing using 4-bit IMA ADPCM...")

initial_predictor = int(samples[0])

encoded, final_predictor = encode_ima_adpcm(samples)

print()
print("Original samples:", len(samples))
print("Compressed bytes:", len(encoded))
print("Audio duration:  ", len(samples) / TARGET_SAMPLE_RATE, "seconds")


# ============================================================
# IMPORTANT SAFETY CHECK
# ============================================================

if len(encoded) > MAX_AUDIO_BYTES:
    print()
    print("ERROR:")
    print(
        f"Compressed audio is {len(encoded)} bytes, "
        f"but the safe limit is {MAX_AUDIO_BYTES} bytes."
    )
    print()
    print("Use a shorter audio file.")
    input("Press Enter to exit...")
    raise SystemExit


# ============================================================
# VERIFY DECODER
# ============================================================

decoded = decode_ima_adpcm(
    encoded,
    initial_predictor
)

# The last nibble may decode one extra sample
decoded = decoded[:len(samples)]


print()
print("Decoder verification:")
print("Decoded samples:", len(decoded))

if len(decoded) != len(samples):
    print("WARNING: decoded sample count does not match!")


# ============================================================
# OPTIONAL PREVIEW
# ============================================================

if PREVIEW:

    try:

        import sounddevice as sd

        print()
        print("Playing decoded ADPCM audio...")
        print("Press Ctrl+C to stop.")

        decoded_float = decoded.astype(np.float32) / 32768.0

        sd.play(
            decoded_float,
            TARGET_SAMPLE_RATE
        )

        sd.wait()

    except ImportError:

        print()
        print("sounddevice is not installed.")
        print("Install it with:")
        print("pip install sounddevice")


# ============================================================
# GENERATE ARDUINO HEADER
# ============================================================

print()
print("Generating:", output_path)

with open(output_path, "w", encoding="ascii") as f:

    f.write("#ifndef AUDIO_DATA_H\n")
    f.write("#define AUDIO_DATA_H\n\n")

    f.write("#include <Arduino.h>\n")
    f.write("#include <avr/pgmspace.h>\n\n")

    f.write(f"#define AUDIO_SAMPLE_RATE {TARGET_SAMPLE_RATE}UL\n")
    f.write(f"#define AUDIO_SAMPLES {len(samples)}UL\n")
    f.write(f"#define AUDIO_COMPRESSED_SIZE {len(encoded)}UL\n")
    f.write(f"#define AUDIO_INITIAL_PREDICTOR {initial_predictor}\n")
    f.write("#define AUDIO_INITIAL_INDEX 0\n\n")

    # IMPORTANT:
    # NO [6836] OR ANY OTHER ARRAY SIZE
    f.write("const uint8_t audio_data[] PROGMEM = {\n")

    for i, byte in enumerate(encoded):

        if i % 16 == 0:
            f.write("    ")

        f.write(f"0x{byte:02X}")

        if i != len(encoded) - 1:
            f.write(", ")

        if i % 16 == 15:
            f.write("\n")

    if len(encoded) % 16 != 0:
        f.write("\n")

    f.write("};\n\n")
    f.write("#endif\n")


# ============================================================
# FINAL VERIFICATION
# ============================================================

# Count actual generated byte values
with open(output_path, "r", encoding="ascii") as f:
    header_text = f.read()

expected = len(encoded)

print()
print("========================================")
print("DONE")
print("========================================")
print("Compressed bytes:", expected)
print("Header:", output_path)
print()
print("The array has NO explicit size.")
print("This prevents the 'too many initializers' error.")
print()