import sounddevice as sd
import numpy as np

def play_single_tone():
    fs = 44100  # Sample rate
    duration = 3.0  # 1 second
    frequency = 440  # 440 Hz tone
    t = np.linspace(0, duration, int(fs * duration), False)
    tone = 0.5 * np.sin(2 * np.pi * frequency * t)

    print("Playing single tone...")
    sd.play(tone, fs)
    sd.wait()
    print("Tone finished.")

if __name__ == "__main__":
    play_single_tone()


# Testing playback and recording

# import sounddevice as sd
# import numpy as np

# fs = 44100  # Sample rate
# duration = 1  # seconds
# frequency = 440  # Hz

# t = np.linspace(0, duration, int(fs * duration), False)
# tone = 0.5 * np.sin(2 * np.pi * frequency * t)

# print("Playing test tone...")
# sd.play(tone, fs)
# sd.wait()
# print("Test tone playback complete.")



# import sounddevice as sd
# import numpy as np
# import time
# from repp import RhythmExperimentGUI
# from tap_detector import TapDetector


# # Example rhythm sequence (e.g., simple rhythm)
# rhythm_sequence = [0, 520, 520, 520, 260, 260, 520, 520]  # in ms

# # Generate a simple audio tone for each rhythm beat
# def generate_tone(frequency=440, duration=0.1, fs=44100):
#     t = np.linspace(0, duration, int(fs * duration), False)
#     tone = 0.5 * np.sin(2 * np.pi * frequency * t)
#     return tone

# # Play the rhythm sequence
# def play_rhythm(rhythm_sequence):
#     fs = 44100  # Sample rate
#     tone = generate_tone()  # A 440Hz tone for each beat
#     silence = np.zeros(int(fs * 0.1))  # 100 ms of silence between tones

#     for beat in rhythm_sequence:
#         sd.play(tone, fs)
#         sd.wait()
#         time.sleep(beat / 1000.0)  # Convert ms to seconds

# # Record participant taps in sync with rhythm
# def record_taps(duration=5, fs=44100):
#     print("Recording taps...")
#     recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
#     sd.wait()  # Wait until recording is finished
#     print("Recording complete.")
#     return recording

# # Combine playback and recording
# def play_and_record():
#     play_rhythm(rhythm_sequence)
#     recording = record_taps(duration=5)
#     return recording

# def process_taps(recording, fs=44100):
#     detector = TapDetector(fs)
#     taps = detector.detect_taps(recording)
#     print("Detected taps:", taps)
#     return taps


# # Run playback and recording together
# if __name__ == "__main__":
#     recording = play_and_record()
#     detected_taps = process_taps(recording)
