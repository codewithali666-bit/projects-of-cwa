import os
import math
import wave
import struct
import tempfile
import threading
import pygame
from pathlib import Path
from cwa_agent.config import DATA_DIR

SOUNDS_DIR = DATA_DIR / "sounds"
SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

class StarkAudioFX:
    """
    Programmatic Stark Industries Sci-Fi Sound FX Engine.
    Generates harmonic electronic frequencies using mathematical waveforms
    so no external audio assets or downloads are required.
    """
    def __init__(self):
        self._sound_cache = {}
        self._ensure_mixer()
        self._generate_all_sounds()

    def _ensure_mixer(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=24000, size=-16, channels=2, buffer=512)
        except Exception as e:
            print(f"[AudioFX Notice] Pygame mixer init warning: {e}")

    def _generate_wav(self, filename: str, generator_fn, duration_sec: float = 1.0, sample_rate: int = 24000):
        filepath = SOUNDS_DIR / filename
        if filepath.exists():
            return str(filepath)

        num_samples = int(sample_rate * duration_sec)
        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            val = generator_fn(t, duration_sec)
            val = max(-1.0, min(1.0, val))
            sample_val = int(val * 32767.0)
            samples.append(sample_val)

        with wave.open(str(filepath), 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_data = struct.pack(f'<{len(samples)}h', *samples)
            wav_file.writeframes(wav_data)

        return str(filepath)

    def _generate_all_sounds(self):
        # 1. Boot Sound: Arc Reactor power-up harmonic sweep
        def _boot_gen(t, dur):
            env = min(1.0, t * 2.5) if t < 0.4 else max(0.0, 1.0 - (t - 0.4) / (dur - 0.4))
            freq = 220 + 660 * (t / dur) ** 1.8
            harm1 = 0.6 * math.sin(2 * math.pi * freq * t)
            harm2 = 0.3 * math.sin(2 * math.pi * (freq * 2) * t)
            harm3 = 0.1 * math.sin(2 * math.pi * (freq * 3) * t)
            mod = 1.0 + 0.15 * math.sin(2 * math.pi * 30 * t)
            return (harm1 + harm2 + harm3) * env * mod * 0.7

        # 2. Listen Beep: Dual-tone high-tech activation chime
        def _listen_gen(t, dur):
            if t < 0.08:
                f = 880
                env = math.sin(math.pi * (t / 0.08))
            elif 0.09 < t < 0.18:
                f = 1320
                env = math.sin(math.pi * ((t - 0.09) / 0.09))
            else:
                return 0.0
            return math.sin(2 * math.pi * f * t) * env * 0.5

        # 3. Processing Beep: Quick high-frequency pulse
        def _process_gen(t, dur):
            env = math.exp(-12 * t)
            f = 1046.5  # C6
            return (0.7 * math.sin(2 * math.pi * f * t) + 0.3 * math.sin(2 * math.pi * f * 1.5 * t)) * env * 0.4

        # 4. Alert Chime: Futuristic harmonic alert pulse
        def _alert_gen(t, dur):
            if t < 0.15:
                f = 784  # G5
                env = math.sin(math.pi * (t / 0.15))
            elif 0.16 < t < 0.35:
                f = 1046.5  # C6
                env = math.sin(math.pi * ((t - 0.16) / 0.19))
            else:
                return 0.0
            return (0.8 * math.sin(2 * math.pi * f * t) + 0.2 * math.sin(2 * math.pi * f * 2 * t)) * env * 0.6

        try:
            self.boot_path = self._generate_wav("cwa_boot.wav", _boot_gen, duration_sec=1.4)
            self.listen_path = self._generate_wav("cwa_listen.wav", _listen_gen, duration_sec=0.25)
            self.process_path = self._generate_wav("cwa_process.wav", _process_gen, duration_sec=0.2)
            self.alert_path = self._generate_wav("cwa_alert.wav", _alert_gen, duration_sec=0.45)
        except Exception as e:
            print(f"[AudioFX Warning] Audio generation error: {e}")

    def _play_file(self, filepath: str):
        if not filepath or not os.path.exists(filepath):
            return
        try:
            self._ensure_mixer()
            if pygame.mixer.get_init():
                if filepath not in self._sound_cache:
                    self._sound_cache[filepath] = pygame.mixer.Sound(filepath)
                self._sound_cache[filepath].play()
        except Exception as e:
            pass

    def play_boot(self):
        threading.Thread(target=lambda: self._play_file(getattr(self, 'boot_path', None)), daemon=True).start()

    def play_listen(self):
        threading.Thread(target=lambda: self._play_file(getattr(self, 'listen_path', None)), daemon=True).start()

    def play_process(self):
        threading.Thread(target=lambda: self._play_file(getattr(self, 'process_path', None)), daemon=True).start()

    def play_alert(self):
        threading.Thread(target=lambda: self._play_file(getattr(self, 'alert_path', None)), daemon=True).start()

# Global Audio FX Singleton
audio_fx = StarkAudioFX()
