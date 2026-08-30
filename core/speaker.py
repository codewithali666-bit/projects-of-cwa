import os
import sys
import re
import asyncio
import tempfile
import threading
import edge_tts
import pygame
import pyttsx3
from pathlib import Path

# Fix Windows cp1252 encoding — allow emojis in print() on all Windows terminals
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
os.environ.setdefault('PYTHONUTF8', '1')

from cwa_agent.config import (
    VOICE_NAME, VOICE_RATE, VOICE_PITCH, MALE_VOICE, FEMALE_VOICE,
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_MALE, ELEVENLABS_VOICE_FEMALE, ELEVENLABS_MODEL_ID
)
import requests


class Speaker:
    def __init__(self, voice: str = VOICE_NAME, rate: str = VOICE_RATE, pitch: str = VOICE_PITCH):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.persona = "CWA"
        self.is_speaking = False
        self._stop_requested = False
        self._offline_engine = None

        # ✅ Initialize pygame mixer at startup — 44100Hz CD quality
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            print("[Speaker 🔊] Audio engine initialized at 44100Hz (CD quality)")
        except Exception as e:
            print(f"[Speaker Warning] Pygame mixer init failed at startup: {e}")

    def set_persona(self, persona: str, gender: str = None):
        p = persona.upper().strip()
        if p == "MJ" or (gender and gender.lower() in ["female", "girl", "ladki"]):
            self.persona = "MJ"
            self.voice = FEMALE_VOICE
            print(f"[Speaker 👩] Persona switched to MJ (Female Voice: {self.voice})")
        else:
            self.persona = "CWA"
            self.voice = MALE_VOICE
            print(f"[Speaker 👨] Persona switched to CWA (Male Voice: {self.voice})")
        
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        except Exception as e:
            print(f"[Speaker Init Warning] Pygame mixer init failed: {e}")

    def _get_offline_engine(self):
        if self._offline_engine is None:
            try:
                self._offline_engine = pyttsx3.init()
                self._offline_engine.setProperty('rate', 165)
                self._offline_engine.setProperty('volume', 1.0)
            except Exception as e:
                print(f"[Speaker] pyttsx3 init error: {e}")
        return self._offline_engine

    def _generate_elevenlabs(self, text: str, output_file: str) -> bool:
        """
        Generates hyper-realistic human voice via ElevenLabs API.
        """
        api_key = ELEVENLABS_API_KEY or os.getenv("ELEVENLABS_API_KEY", "")
        if not api_key:
            return False

        voice_id = ELEVENLABS_VOICE_FEMALE if self.persona == "MJ" else ELEVENLABS_VOICE_MALE
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        data = {
            "text": text,
            "model_id": ELEVENLABS_MODEL_ID,
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.80,
                "style": 0.20,
                "use_speaker_boost": True
            }
        }

        try:
            print(f"[Speaker 🎙️] Generating ElevenLabs ultra-realistic audio for {self.persona}...")
            resp = requests.post(url, json=data, headers=headers, timeout=12)
            if resp.status_code == 200 and resp.content:
                with open(output_file, "wb") as f:
                    f.write(resp.content)
                return True
            else:
                print(f"[Speaker Notice] ElevenLabs returned status {resp.status_code}: {resp.text[:100]}")
                return False
        except Exception as err:
            print(f"[Speaker Notice] ElevenLabs connection failed ({err}), using Edge-TTS fallback.")
            return False

    def _get_emotion_acoustic_profile(self, emotion: str, intensity: int = 50) -> tuple:
        """
        Dynamically calculates speech rate (+/- %) and pitch (+/- Hz)
        based on active emotion state and intensity (0-100).
        """
        emo = emotion.upper().strip() if emotion else "CALM"
        norm_intensity = max(0, min(100, intensity)) / 100.0

        if emo in ["HAPPY", "JOYFUL"]:
            rate_val = int(2 + 6 * norm_intensity)
            pitch_val = int(2 + 6 * norm_intensity)
            offline_rate = int(170 + 15 * norm_intensity)

        elif emo in ["EXCITED", "ENERGETIC"]:
            rate_val = int(4 + 8 * norm_intensity)
            pitch_val = int(4 + 8 * norm_intensity)
            offline_rate = int(175 + 20 * norm_intensity)

        elif emo in ["SAD", "EMPATHETIC"]:
            rate_val = -int(3 + 6 * norm_intensity)
            pitch_val = -int(2 + 4 * norm_intensity)
            offline_rate = int(155 - 15 * norm_intensity)

        elif emo in ["ANGRY", "STERN"]:
            rate_val = int(2 + 5 * norm_intensity)
            pitch_val = -int(2 + 4 * norm_intensity)
            offline_rate = int(165 + 10 * norm_intensity)

        elif emo in ["WITTY", "SARCASTIC"]:
            rate_val = int(2 + 4 * norm_intensity)
            pitch_val = int(2 + 4 * norm_intensity)
            offline_rate = int(168 + 8 * norm_intensity)

        elif emo in ["SURPRISED", "CURIOUS"]:
            rate_val = int(3 + 6 * norm_intensity)
            pitch_val = int(4 + 6 * norm_intensity)
            offline_rate = int(170 + 12 * norm_intensity)

        elif emo in ["CARING", "LOVING"]:
            rate_val = -int(2 + 4 * norm_intensity)
            pitch_val = int(2 + 4 * norm_intensity)
            offline_rate = int(158 - 8 * norm_intensity)

        else:
            rate_val = 0
            pitch_val = 0
            offline_rate = 165

        rate_str  = f"{'+' if rate_val  >= 0 else ''}{rate_val}%"
        pitch_str = f"{'+' if pitch_val >= 0 else ''}{pitch_val}Hz"
        return rate_str, pitch_str, offline_rate

    async def _generate_edge_tts(self, text: str, output_file: str, rate: str, pitch: str):
        communicate = edge_tts.Communicate(text, self.voice, rate=rate, pitch=pitch)
        await communicate.save(output_file)

    def speak(self, text: str, emotion: str = "CALM", intensity: int = 50, on_start=None, on_finish=None):
        """
        Speaks text synchronously with dynamic emotion modulation.
        Prioritizes ElevenLabs if key present, else Edge-TTS neural models, else pyttsx3.
        """
        if not text or not text.strip():
            return

        cleaned_text = re.sub(r"\[(?:MOOD|EMOTION|INTENSITY|EMOJI|REASON):[^\]]*\]", "", str(text), flags=re.IGNORECASE)
        cleaned_text = re.sub(r"\[[^\]]*\|[^\]]*\]", "", cleaned_text).replace("*", "").replace("#", "").replace("`", "").strip()
        try:
            from cwa_agent.core.ignore_words import ignore_words_manager
            cleaned_text = ignore_words_manager.filter_and_replace_text(cleaned_text, persona=self.persona)
        except Exception:
            pass
        try:
            from cwa_agent.core.memory import memory
            cleaned_text = memory.filter_forbidden_words(cleaned_text, persona=self.persona)
        except Exception:
            pass

        speech_text = re.sub(r'[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50]', '', cleaned_text).strip()
        if not speech_text:
            speech_text = cleaned_text

        rate_str, pitch_str, offline_rate = self._get_emotion_acoustic_profile(emotion, intensity)
        print(f"\n[CWA 🗣️ Mood: {emotion.upper()} ({intensity}%) | Rate: {rate_str} | Pitch: {pitch_str}]: {cleaned_text}")

        self.is_speaking = True
        self._stop_requested = False
        if on_start:
            try:
                on_start()
            except Exception:
                pass

        temp_audio = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_audio = f.name

            # 1. Try ElevenLabs API first if key configured
            success = self._generate_elevenlabs(speech_text, temp_audio)

            # 2. Fallback to Edge-TTS Neural voice
            if not success:
                asyncio.run(self._generate_edge_tts(speech_text, temp_audio, rate_str, pitch_str))

            # Play audio using Pygame (44100Hz CD quality)
            if pygame.mixer.get_init():
                pygame.mixer.music.load(temp_audio)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy() and not self._stop_requested:
                    pygame.time.Clock().tick(20)
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()

        except Exception as e:
            print(f"[Speaker Notice] Playback fallback ({e}). Using offline engine...")
            engine = self._get_offline_engine()
            if engine:
                try:
                    engine.setProperty('rate', offline_rate)
                    engine.say(speech_text)
                    engine.runAndWait()
                except Exception as ex:
                    print(f"[Speaker Error] pyttsx3 failed: {ex}")

        finally:
            if temp_audio and os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                except Exception:
                    pass
            self.is_speaking = False
            if on_finish:
                try:
                    on_finish()
                except Exception:
                    pass

    def speak_async(self, text: str, emotion: str = "CALM", intensity: int = 50, on_start=None, on_finish=None):
        """Speaks in a background thread with dynamic emotion modulation."""
        t = threading.Thread(target=self.speak, args=(text, emotion, intensity, on_start, on_finish), daemon=True)
        t.start()
        return t

    def _apply_vocal_studio_fx(self, input_audio_path: str, output_wav_path: str) -> bool:
        """
        Transforms flat TTS speech audio into a lush studio vocal track:
        1. Organic Vibrato Modulation (4.8 - 5.5 Hz pitch LFO on sustained notes)
        2. Studio Reverb & Multi-Tap Spatial Echo (Early reflections + warm room decay)
        3. Vocal Warmth EQ & Dynamic Compression
        """
        try:
            import numpy as np
            from scipy.io import wavfile

            if not os.path.exists(input_audio_path):
                return False

            # Decode raw PCM audio using Pygame mixer sound
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)

            snd = pygame.mixer.Sound(input_audio_path)
            raw_bytes = snd.get_raw()
            if not raw_bytes:
                return False

            samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
            sample_rate = 44100

            # Convert stereo to mono if needed
            if len(samples) % 2 == 0:
                stereo = samples.reshape(-1, 2)
                mono = np.mean(stereo, axis=1)
            else:
                mono = samples

            n_samples = len(mono)
            if n_samples < 1000:
                return False

            t = np.arange(n_samples) / float(sample_rate)

            # 1. Apply Natural Organic Vocal Vibrato
            vibrato_rate = 5.2  # 5.2 Hz human vocal vibrato frequency
            vibrato_depth = 0.0025  # 0.25% dynamic pitch LFO
            mod_wave = 1.0 + vibrato_depth * np.sin(2 * np.pi * vibrato_rate * t)
            sample_indices = np.clip(np.cumsum(mod_wave), 0, n_samples - 1)
            vocal_vibrato = np.interp(sample_indices, np.arange(n_samples), mono)

            # 2. Apply Studio Reverb & Spatial Echo Matrix
            reverb_audio = np.copy(vocal_vibrato)
            reflections = [(0.038, 0.24), (0.072, 0.18), (0.115, 0.12), (0.160, 0.08)]
            for delay_sec, decay_gain in reflections:
                d_samples = int(sample_rate * delay_sec)
                if d_samples < n_samples:
                    delay_signal = np.pad(vocal_vibrato[:-d_samples], (d_samples, 0), 'constant')
                    reverb_audio += delay_signal * decay_gain

            # 3. Soft Dynamic Compressor / Vocal Warmth Normalization
            max_val = np.max(np.abs(reverb_audio))
            if max_val > 0:
                norm_audio = (reverb_audio / max_val) * 0.95
            else:
                norm_audio = reverb_audio

            # Soft knee warmth saturation
            saturated = np.tanh(norm_audio * 1.1)
            out_pcm = (saturated * 32767.0).astype(np.int16)

            # Convert back to stereo for lush spatial audio width
            stereo_out = np.column_stack((out_pcm, out_pcm))

            wavfile.write(output_wav_path, sample_rate, stereo_out)
            return True
        except Exception as e:
            print(f"[Speaker Notice] Studio vocal FX fallback ({e})")
            return False

    def _generate_backing_track(self, duration_sec: float = 20.0, output_path: str = None, style: str = "acoustic") -> str:
        """
        Generates a rich multi-instrument studio backing track (Piano/Guitar Timbre + Sub Bass + Soft Rhythm Beat)
        with physical harmonic ADSR synthesis tailored to the requested song style.
        """
        try:
            import numpy as np
            from scipy.io import wavfile

            sample_rate = 44100
            total_samples = int(sample_rate * duration_sec)
            audio_left = np.zeros(total_samples, dtype=np.float32)
            audio_right = np.zeros(total_samples, dtype=np.float32)

            st = str(style).lower().strip()
            if "sad" in st or "emotional" in st:
                chords = [[220.0, 261.6, 329.6], [174.6, 220.0, 261.6], [261.6, 329.6, 392.0], [196.0, 246.9, 293.6]] # Am - F - C - G
                bass_notes = [110.0, 87.3, 130.8, 98.0]
                bpm = 70
            elif "pop" in st or "upbeat" in st:
                chords = [[261.6, 329.6, 392.0], [196.0, 246.9, 293.6], [220.0, 261.6, 329.6], [174.6, 220.0, 261.6]] # C - G - Am - F
                bass_notes = [130.8, 98.0, 110.0, 87.3]
                bpm = 92
            elif "rock" in st or "energetic" in st:
                chords = [[164.8, 207.6, 246.9], [196.0, 246.9, 293.6], [220.0, 277.1, 329.6], [261.6, 329.6, 392.0]] # E - G - A - C
                bass_notes = [82.4, 98.0, 110.0, 130.8]
                bpm = 98
            else: # acoustic / romantic / ballad default
                chords = [[261.6, 329.6, 392.0], [220.0, 261.6, 329.6], [174.6, 220.0, 261.6], [196.0, 246.9, 293.6]] # C - Am - F - G
                bass_notes = [130.8, 110.0, 87.3, 98.0]
                bpm = 76

            chord_duration = (60.0 / bpm) * 4.0  # 4 beats per chord measure
            measure_samples = int(sample_rate * chord_duration)
            t_meas = np.linspace(0, chord_duration, measure_samples, False)

            # Plucked instrument ADSR envelope
            adsr_piano = np.exp(-1.4 * t_meas) * (1.0 - np.exp(-15.0 * t_meas))

            # Rhythm beat soft pulse envelope (brush snare on beat 2 and 4)
            beat_sec = 60.0 / bpm
            t_beat = np.linspace(0, beat_sec, int(sample_rate * beat_sec), False)
            snare_env = np.exp(-25.0 * t_beat)

            num_measures = int(np.ceil(duration_sec / chord_duration))
            for i in range(num_measures):
                start_idx = int(i * measure_samples)
                end_idx = min(start_idx + measure_samples, total_samples)
                actual_len = end_idx - start_idx
                if actual_len <= 0:
                    break

                chord_freqs = chords[i % len(chords)]
                bass_freq = bass_notes[i % len(bass_notes)]
                meas_left = np.zeros(actual_len, dtype=np.float32)
                meas_right = np.zeros(actual_len, dtype=np.float32)

                # 1. Multi-Harmonic Acoustic Guitar / Piano Timbre
                for note_idx, freq in enumerate(chord_freqs):
                    pan = 0.3 if note_idx == 0 else (0.7 if note_idx == 1 else 0.5)
                    wave = (
                        0.45 * np.sin(2 * np.pi * freq * t_meas[:actual_len]) +
                        0.25 * np.sin(2 * np.pi * (freq * 2.0) * t_meas[:actual_len]) +
                        0.12 * np.sin(2 * np.pi * (freq * 3.0) * t_meas[:actual_len]) +
                        0.06 * np.sin(2 * np.pi * (freq * 4.0) * t_meas[:actual_len])
                    )
                    meas_left += wave * adsr_piano[:actual_len] * (1.0 - pan)
                    meas_right += wave * adsr_piano[:actual_len] * pan

                # 2. Warm Sub-Bass Note
                bass_wave = (
                    0.4 * np.sin(2 * np.pi * bass_freq * t_meas[:actual_len]) +
                    0.2 * np.sin(2 * np.pi * (bass_freq * 2.0) * t_meas[:actual_len])
                )
                bass_env = np.exp(-0.8 * t_meas[:actual_len])
                meas_left += bass_wave * bass_env * 0.45
                meas_right += bass_wave * bass_env * 0.45

                # 3. Soft Acoustic Rhythm Pulse (Beats 2 and 4)
                for b_idx in [1, 3]:  # 2nd and 4th beat
                    b_start = int(b_idx * sample_rate * beat_sec)
                    b_len = min(len(snare_env), actual_len - b_start)
                    if b_start < actual_len and b_len > 0:
                        noise = np.random.uniform(-0.15, 0.15, b_len)
                        meas_left[b_start:b_start + b_len] += noise * snare_env[:b_len] * 0.25
                        meas_right[b_start:b_start + b_len] += noise * snare_env[:b_len] * 0.25

                audio_left[start_idx:end_idx] += meas_left
                audio_right[start_idx:end_idx] += meas_right

            # Master Normalization
            max_left = np.max(np.abs(audio_left))
            max_right = np.max(np.abs(audio_right))
            max_val = max(max_left, max_right)
            if max_val > 0:
                audio_left = (audio_left / max_val) * 0.30
                audio_right = (audio_right / max_val) * 0.30

            stereo_audio = np.column_stack(((audio_left * 32767).astype(np.int16), (audio_right * 32767).astype(np.int16)))

            if not output_path:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    output_path = f.name

            wavfile.write(output_path, sample_rate, stereo_audio)
            return output_path
        except Exception as e:
            print(f"[Speaker Warning] Studio backing track generation notice: {e}")
            return ""

    def _preprocess_lyrics_for_singing(self, lyrics: str) -> list:
        """
        Transforms plain raw lyrics text into expressive vocal singing phrases
        with melodic vowel extensions, legato breath pauses, and pitch scale contours.
        """
        lines = [line.strip() for line in lyrics.strip().split("\n") if line.strip()]
        phrased_lines = []

        # Melodic scale pitch contours (Sa-Re-Ga-Ma pentatonic scale pitch intervals)
        melodic_pitches = ["+10Hz", "+18Hz", "+6Hz", "+14Hz", "+22Hz", "+12Hz", "+8Hz", "+16Hz"]

        vowel_map = {
            'a': 'aaa~', 'e': 'eee~', 'i': 'iii~', 'o': 'ooo~', 'u': 'uuu~',
            'A': 'aaa~', 'E': 'eee~', 'I': 'iii~', 'O': 'ooo~', 'U': 'uuu~'
        }

        for idx, line in enumerate(lines):
            clean_line = str(line).replace("*", "").replace("#", "").strip()
            if not clean_line:
                continue

            # Extend end vowel of the last word for melodic holding note
            words = clean_line.split()
            if words:
                last_word = words[-1]
                if len(last_word) > 1 and last_word[-1].isalpha():
                    last_char = last_word[-1].lower()
                    if last_char in vowel_map:
                        words[-1] = last_word[:-1] + vowel_map[last_char]
                    else:
                        words[-1] = last_word + "..."

            phrased_text = " ".join(words)
            pitch_val = melodic_pitches[idx % len(melodic_pitches)]

            phrased_lines.append({
                "text": phrased_text,
                "pitch": pitch_val,
                "rate": "-12%"  # Slightly relaxed vocal speed for musical emotion
            })

        return phrased_lines

    def sing_song(self, lyrics: str, title: str = "JARVIS Song", style: str = "acoustic", on_start=None, on_finish=None) -> str:
        """
        Synthesizes and performs lyrics like a professional singer with vocal pitch vibrato,
        studio reverb, melodic phrasing, and a multi-instrument acoustic backing track.
        """
        import time
        if not lyrics or not lyrics.strip():
            return "No lyrics provided to sing, Sir."

        phrased_lines = self._preprocess_lyrics_for_singing(lyrics)
        if not phrased_lines:
            return "No valid lyrics lines found."

        print(f"\n[Speaker 🎵 Professional Singer Engine]: Performing '{title}' ({len(phrased_lines)} lines | Style: {style})...")

        self.is_speaking = True
        self._stop_requested = False

        if on_start:
            try:
                on_start()
            except Exception:
                pass

        temp_files = []
        try:
            # 1. Generate multi-instrument studio backing track
            est_duration = max(14.0, len(phrased_lines) * 4.8)
            backing_wav = self._generate_backing_track(duration_sec=est_duration, style=style)
            if backing_wav:
                temp_files.append(backing_wav)

            # 2. Synthesize line-by-line vocal audio with studio FX & vibrato
            vocal_files = []
            for item in phrased_lines:
                if self._stop_requested:
                    break

                clean_text = item["text"]
                try:
                    from cwa_agent.core.memory import memory
                    clean_text = memory.filter_forbidden_words(clean_text, persona=self.persona)
                except Exception:
                    pass

                if not clean_text:
                    continue

                # Temporary file for raw TTS output
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    raw_vocal_path = f.name
                    temp_files.append(raw_vocal_path)

                # Temporary file for studio FX vocal output
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f2:
                    fx_vocal_path = f2.name
                    temp_files.append(fx_vocal_path)

                # Synthesize TTS vocal audio
                asyncio.run(self._generate_edge_tts(clean_text, raw_vocal_path, rate=item["rate"], pitch=item["pitch"]))

                # Apply Studio Vocal FX (Vibrato + Reverb + Compression)
                fx_success = self._apply_vocal_studio_fx(raw_vocal_path, fx_vocal_path)
                vocal_path_to_play = fx_vocal_path if (fx_success and os.path.exists(fx_vocal_path)) else raw_vocal_path
                vocal_files.append(vocal_path_to_play)

            # 3. Perform Live Mix: Backing Track + Studio Vocals in Pygame
            if pygame.mixer.get_init():
                backing_sound = None
                if backing_wav and os.path.exists(backing_wav):
                    try:
                        backing_sound = pygame.mixer.Sound(backing_wav)
                        backing_sound.set_volume(0.35)  # Perfect acoustic mix level
                        backing_sound.play()
                    except Exception as ex:
                        print(f"[Speaker Notice] Backing track playback notice: {ex}")

                # Sing each line in rhythm with backing track
                for vocal_path in vocal_files:
                    if self._stop_requested:
                        break
                    if os.path.exists(vocal_path):
                        pygame.mixer.music.load(vocal_path)
                        pygame.mixer.music.play()
                        while pygame.mixer.music.get_busy() and not self._stop_requested:
                            pygame.time.Clock().tick(20)
                        pygame.mixer.music.stop()
                        pygame.mixer.music.unload()
                        time.sleep(0.12)  # Natural vocal breathing pause

                if backing_sound:
                    try:
                        backing_sound.stop()
                    except Exception:
                        pass

            return f"Singing performance of '{title}' completed like a professional singer, Sir."

        except Exception as e:
            print(f"[Singing Engine Notice] Vocal performance notice: {e}")
            return f"Singing performance completed with notice: {e}"

        finally:
            for fpath in temp_files:
                if os.path.exists(fpath):
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
            self.is_speaking = False
            if on_finish:
                try:
                    on_finish()
                except Exception:
                    pass

    def stop(self):
        """Interrupts current speech playback."""
        self._stop_requested = True
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
        self.is_speaking = False

# Global Singleton instance
speaker = Speaker()

