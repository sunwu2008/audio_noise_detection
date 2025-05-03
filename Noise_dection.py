import os
import shutil
import webrtcvad
from pydub import AudioSegment
import contextlib
import wave

# Convert any audio format to mono 16kHz WAV for VAD analysis
def convert_to_wav_mono_16k(input_path, output_path):
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(output_path, format="wav")

# Read the WAV file as raw PCM data
def read_wave(path):
    with contextlib.closing(wave.open(path, 'rb')) as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        pcm_data = wf.readframes(wf.getnframes())
        return pcm_data, wf.getframerate()

# Break the audio into 30ms frames
def frame_generator(frame_duration_ms, audio, sample_rate):
    frame_size = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
    for i in range(0, len(audio) - frame_size + 1, frame_size):
        yield audio[i:i + frame_size]

# Use WebRTC VAD to calculate % of speech
def vad_speech_ratio(wav_path, aggressiveness=2):
    audio, sample_rate = read_wave(wav_path)
    vad = webrtcvad.Vad(aggressiveness)
    frames = list(frame_generator(30, audio, sample_rate))
    if not frames:
        return 0.0
    speech_frames = sum(1 for f in frames if vad.is_speech(f, sample_rate))
    return speech_frames / len(frames)

# Determine if file is mostly noise (< 10% speech)
def is_mostly_noise(input_path, tmp_wav="temp.wav", threshold=0.1):
    try:
        convert_to_wav_mono_16k(input_path, tmp_wav)
        ratio = vad_speech_ratio(tmp_wav)
        os.remove(tmp_wav)
        return ratio < threshold
    except Exception as e:
        print(f"Failed to process {input_path}: {e}")
        return False

# Recursively scan a folder and filter noisy audio files
def scan_and_filter_audio(input_folder, output_folder="filtered_noise", threshold=0.1):
    os.makedirs(output_folder, exist_ok=True)
    supported_exts = (".mp3", ".wav", ".flac", ".m4a")

    for root, _, files in os.walk(input_folder):
        for fname in files:
            if not fname.lower().endswith(supported_exts):
                continue
            full_path = os.path.join(root, fname)
            print(f"Scanning: {full_path}")
            if is_mostly_noise(full_path, tmp_wav="temp.wav", threshold=threshold):
                # Preserve relative path in output
                rel_path = os.path.relpath(full_path, input_folder)
                dest_path = os.path.join(output_folder, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.move(full_path, dest_path)
                print(f"Moved (mostly noise): {rel_path}")

# === Example usage ===
if __name__ == "__main__":
    input_directory = "audio_files"        # Replace with your input folder
    output_directory = "filtered_noise"    # Folder to store noisy files
    scan_and_filter_audio(input_directory, output_directory, threshold=0.1)