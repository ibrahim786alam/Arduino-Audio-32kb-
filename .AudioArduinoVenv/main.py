import numpy as np
import soundfile as sf
import sounddevice as sd
import time
from scipy.fft import rfft, rfftfreq
from scipy.signal import find_peaks

Chunk_Duration = 0.2
Freq_Offset = 0
Start_Time = 6.0
Rms_Threshold = 0.01


data, fs = sf.read("C:\\Users\\PC\\Desktop\\stuff\\Audio_To_Arduino\\.AudioArduinoVenv\\TestAudio2.wav", dtype='float32')
Frequencies = []

num_samples = int(fs * Chunk_Duration)

Current_Time = Start_Time



while Current_Time < (data.shape[0] / fs):
    chunk_start = int(Current_Time * fs)
    chunk = data[chunk_start:chunk_start + num_samples,0]  # Assuming mono audio, take the first channel

    rms = np.sqrt(np.mean(chunk ** 2))

    if rms < Rms_Threshold:
        print("noTone(9);")

        Current_Time += Chunk_Duration
        continue

    window = np.hanning(len(chunk))

    windowed_chunk = chunk * window

    fft_values = rfft(windowed_chunk)
    fft_values = np.abs(fft_values)
    freqs = rfftfreq(num_samples,d = 1/fs)

    freq_mask = (freqs >= 80) & (freqs <= 5000)

    filtered_freq = freqs[freq_mask]
    filtered_fft_values = fft_values[freq_mask]

    peaks, properties = find_peaks(
        filtered_fft_values,
        prominence=np.max(filtered_fft_values) * 0.05
    )

    if len(peaks) == 0:

        print("no peak")

        Current_Time += Chunk_Duration
        continue

    peak_index = peaks[
        np.argmax(filtered_fft_values[peaks])
    ]

    #peak_index = np.argmax(filtered_fft_values[1:]) + 1 
    
    if peak_index < len(filtered_freq):
        dominant_freq = filtered_freq[peak_index]
        if dominant_freq > 20 and dominant_freq < 20000:
            Frequencies.append(dominant_freq + Freq_Offset)
            
               
               

    Current_Time += Chunk_Duration

    time.sleep(0)


repeat_count = 1

for freqi in range(len(Frequencies)):
    freq = Frequencies[freqi]
    if freqi + 1 < len(Frequencies) and freq == Frequencies[freqi + 1]:
        repeat_count += 1
    else:
        
        print(f"tone(9, {int(freq)},{int(repeat_count*Chunk_Duration*1000)});")
        print(f"delay({int(repeat_count*Chunk_Duration*1000)});")
        repeat_count = 1


print(f"Sampling Rate: {fs} Hz")
print(f"Total array shape: {data.shape}")
#print(f"0.1s chunk array shape: {first_chunk.shape}")


# Play the raw numpy array data
#sd.play(data, fs)

# Block execution until the audio completely finishes playing
#sd.wait()


