import speech_recognition as sr
import time

class Listener:
    def __init__(self, language="en-IN"):
        self.recognizer = sr.Recognizer()
        # High sensitivity: lower energy threshold so normal/soft voice is captured easily
        self.recognizer.energy_threshold = 120
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.3
        self.recognizer.pause_threshold = 0.6
        self.recognizer.non_speaking_duration = 0.4
        self.language = language
        self.is_listening = False
        self._calibrated = False

    def calibrate(self):
        """Quick calibration with high sensitivity cap."""
        if not self._calibrated:
            try:
                with sr.Microphone() as source:
                    print("[Listener] Tuning high-sensitivity microphone...")
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.4)
                    # Cap threshold so it never becomes too hard to trigger
                    if self.recognizer.energy_threshold > 200:
                        self.recognizer.energy_threshold = 180
                    self._calibrated = True
                    print(f"[Listener] High Sensitivity Ready (Threshold: {self.recognizer.energy_threshold:.0f})")
            except Exception as e:
                print(f"[Listener Warning] Calibration failed: {e}")


    def listen(self, phrase_time_limit=10, on_listen_start=None, on_listen_end=None) -> str:
        """
        Listens to the microphone and returns recognized text.
        Returns empty string if speech is unintelligible or timeout occurs.
        """
        self.calibrate()
        self.is_listening = True
        if on_listen_start:
            try:
                on_listen_start()
            except Exception:
                pass

        query = ""
        try:
            with sr.Microphone() as source:
                print("\n[CWA 👂]: Listening...")
                audio = self.recognizer.listen(source, timeout=6, phrase_time_limit=phrase_time_limit)
                
                print("[CWA ⚡]: Processing audio...")
                # First try Indian English / Hinglish
                try:
                    query = self.recognizer.recognize_google(audio, language=self.language)
                except sr.UnknownValueError:
                    # Fallback to Hindi if en-IN missed it
                    try:
                        query = self.recognizer.recognize_google(audio, language="hi-IN")
                    except Exception:
                        query = ""

                if query and len(query.strip()) >= 2:
                    print(f"[User 🎙️]: {query}")
                else:
                    query = ""

        except sr.WaitTimeoutError:
            pass
        except sr.RequestError as e:
            print(f"[Listener Error] Speech Recognition service unavailable: {e}")
        except Exception as e:
            print(f"[Listener Error]: {e}")
        finally:
            self.is_listening = False
            if on_listen_end:
                try:
                    on_listen_end()
                except Exception:
                    pass

        return query.strip()

    def listen_for_wake_word(self, phrase_time_limit=4) -> tuple:
        """
        Listens for hands-free wake words: 'jarvis', 'cwa', 'mj', 'hey jarvis', 'hey cwa', 'hey mj', 'wake up'.
        Returns (is_detected: bool, full_query: str, detected_persona: str).
        """
        query = self.listen(phrase_time_limit=phrase_time_limit)
        if not query:
            return False, "", ""

        low = query.lower()
        words = low.split()

        if "mj" in words or "hey mj" in low or "ladki" in low:
            return True, query, "MJ"

        if "jarvis" in words or "cwa" in words or "hey jarvis" in low or "hey cwa" in low or "wake up" in low or "jarvis" in low:
            return True, query, "CWA"

        return False, query, ""

# Global Singleton instance
listener = Listener()

