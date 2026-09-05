#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/pgmspace.h>
#include "audio_data.h"

// --- ADD THIS LINE IF THE COMPILER STILL CANNOT FIND IT ---
extern const uint32_t audio_data_len;

// ADPCM Tables
const int16_t stepTable[89] PROGMEM = {
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17,
    19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
    50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
    130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
    337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
    876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
    2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358,
    5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
    15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767
};

const int8_t indexTable[16] PROGMEM = {
    -1, -1, -1, -1, 2, 4, 6, 8,
    -1, -1, -1, -1, 2, 4, 6, 8
};

// Global Decoder & Playback State Variables
volatile int32_t predictor = 0;
volatile uint8_t adpcmIndex = 0;
volatile uint32_t byteNumber = 0;
volatile bool highNibble = false;
volatile bool isPlaying = false;

// Decode a single 4-bit ADPCM nibble
int16_t decodeNibble(uint8_t nibble) {
    uint16_t step = pgm_read_word(&stepTable[adpcmIndex]);
    int32_t diff = step >> 3;

    if (nibble & 1) diff += step >> 2;
    if (nibble & 2) diff += step >> 1;
    if (nibble & 4) diff += step;

    if (nibble & 8) {
        predictor -= diff;
    } else {
        predictor += diff;
    }

    // Clamp predictor to 16-bit signed PCM range
    if (predictor > 32767) predictor = 32767;
    if (predictor < -32768) predictor = -32768;

    // Update step index with signed index calculation to avoid underflow
    int8_t indexChange = (int8_t)pgm_read_byte(&indexTable[nibble]);
    int16_t newIndex = (int16_t)adpcmIndex + indexChange;

    if (newIndex < 0) newIndex = 0;
    if (newIndex > 88) newIndex = 88;

    adpcmIndex = (uint8_t)newIndex;

    return (int16_t)predictor;
}

// Map 16-bit signed PCM (-32768 to 32767) to 8-bit unsigned PWM duty cycle (0 to 255)
inline uint8_t audioToPWM(int16_t sample) {
    // Multiply sample by 2 (bitshift >> 7 instead of >> 8) to increase volume
    int16_t scaled = (sample >> 7) + 128; 
    
    // Hard clipping guard
    if (scaled < 0) scaled = 0;
    if (scaled > 255) scaled = 255;
    
    return (uint8_t)scaled;
}

// Timer1 CTC ISR: Triggered at 8000 Hz
ISR(TIMER1_COMPA_vect) {
    if (!isPlaying) return;

    if (byteNumber >= sizeof(audio_data)) {
        isPlaying = false;
        OCR2B = 128; // Reset PWM output to midpoint (silence)
        return;
    }

    uint8_t currentByte = pgm_read_byte(&audio_data[byteNumber]);
    uint8_t nibble;

    if (highNibble) {
        nibble = (currentByte >> 4) & 0x0F;
        byteNumber++;
        highNibble = false;
    } else {
        nibble = currentByte & 0x0F;
        highNibble = true;
    }

    int16_t sample = decodeNibble(nibble);
    OCR2B = audioToPWM(sample);
}

// Setup Timer2 for Fast PWM on Pin 3 (OC2B)
void setupPWM() {
    pinMode(3, OUTPUT);

    // Fast PWM mode, non-inverting output on OC2B (Pin 3)
    TCCR2A = (1 << COM2B1) | (1 << WGM21) | (1 << WGM20);
    // Prescaler = 1 (31.25 kHz PWM carrier frequency)
    TCCR2B = (1 << CS20);

    OCR2B = 128; // Center voltage at 2.5V
}

// Setup Timer1 for 8000 Hz sample clock interrupts
void setupSampleTimer() {
    cli(); // Disable interrupts

    TCCR1A = 0;
    TCCR1B = 0;
    TCNT1  = 0;

    // CTC mode (Clear Timer on Compare match)
    TCCR1B |= (1 << WGM12);
    // Prescaler = 1
    TCCR1B |= (1 << CS10);

    // Set compare match value for 8 kHz: (16 MHz / (1 * 8000 Hz)) - 1 = 1999
    OCR1A = 9999;

    // Enable Timer1 compare interrupt A
    TIMSK1 |= (1 << OCIE1A);

    sei(); // Enable interrupts
}

void startAudio() {
    predictor = 0;
    adpcmIndex = 0;
    byteNumber = 0;
    highNibble = false;
    isPlaying = true;
}

void setup() {
    setupPWM();
    setupSampleTimer();
    startAudio();
}

void loop() {
    // Loop audio indefinitely when finished
    if (!isPlaying) {
        delay(1000);
        startAudio();
    }
}