import time
import threading
import datetime
import speech_recognition as sr
from collections import deque


class AmbientRoomListener:
    """
    Ambient Room Intelligence Listener for CWA-JARVIS.
    Continuously transcribes all room conversation in the background
    into a rolling time-stamped buffer without saving anything to disk.
    Allows instant recall of what was said in the last N minutes
    when anyone asks: "Jarvis, abhi kya baat ho rahi thi?"
    """

    def __init__(self, buffer_minutes: int = 15, language: str = "en-IN"):
        self.buffer_minutes = buffer_minutes
        self.language = language
        self._buffer: deque = deque()  # Each entry: {"time": str, "text": str}
        self._running = False
        self._thread = None
        self._recognizer = sr.Recognizer()
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.energy_threshold = 120
        self._recognizer.pause_threshold = 0.8
        self._lock = threading.Lock()


    def start(self):
        """Starts the background ambient room listener thread."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            print("[Ambient Listener 👂] Room Intelligence Listener active — monitoring ambient conversation.")

    def stop(self):
        """Stops the background ambient room listener."""
        self._running = False

    def _prune_old_entries(self):
        """Removes buffer entries older than buffer_minutes from RAM."""
        cutoff = time.time() - (self.buffer_minutes * 60)
        with self._lock:
            while self._buffer and self._buffer[0].get("epoch", 0) < cutoff:
                self._buffer.popleft()

    def _add_to_buffer(self, text: str):
        """Adds a transcribed line to the rolling RAM buffer."""
        entry = {
            "epoch": time.time(),
            "time": datetime.datetime.now().strftime("%I:%M:%S %p"),
            "text": text.strip()
        }
        with self._lock:
            self._buffer.append(entry)
        self._prune_old_entries()

    def _listen_loop(self):
        """Continuously listens to ambient room audio and transcribes into rolling buffer."""
        while self._running:
            try:
                with sr.Microphone() as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    try:
                        audio = self._recognizer.listen(source, timeout=4, phrase_time_limit=15)
                    except sr.WaitTimeoutError:
                        continue

                    # Try Indian English first, fallback to Hindi
                    text = ""
                    try:
                        text = self._recognizer.recognize_google(audio, language=self.language)
                    except sr.UnknownValueError:
                        try:
                            text = self._recognizer.recognize_google(audio, language="hi-IN")
                        except Exception:
                            pass
                    except sr.RequestError:
                        pass

                    if text and text.strip():
                        self._add_to_buffer(text)
                        print(f"[Ambient 🎤 {datetime.datetime.now().strftime('%I:%M %p')}]: {text}")

            except Exception as e:
                time.sleep(1)

    def get_recent_transcript(self, minutes: int = None) -> str:
        """
        Returns a clean formatted string of all room conversation
        captured in the last `minutes` minutes from the RAM buffer.
        """
        if minutes is None:
            minutes = self.buffer_minutes

        cutoff = time.time() - (minutes * 60)
        self._prune_old_entries()

        with self._lock:
            entries = [e for e in self._buffer if e.get("epoch", 0) >= cutoff]

        if not entries:
            return f"No conversation captured in the last {minutes} minute(s)."

        lines = [f"[{e['time']}] {e['text']}" for e in entries]
        return "\n".join(lines)

    def clear_buffer(self):
        """Clears the entire in-RAM conversation buffer."""
        with self._lock:
            self._buffer.clear()
        return "Room conversation buffer cleared."

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._buffer)


# Global Ambient Room Listener Singleton
ambient = AmbientRoomListener(buffer_minutes=15, language="en-IN")
