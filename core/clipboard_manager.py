"""
CWA Autonomous Agent — Smart Clipboard History Manager
Monitors system clipboard in real-time and maintains a dynamic history of copied items.
Zero hardcoding — fully dynamic, max_items configurable at runtime.
"""
import threading
import time
import datetime


class ClipboardManager:
    """
    Live clipboard history tracker.
    Stores up to max_items unique entries with timestamps.
    Runs in background daemon thread — zero UI blocking.
    """
    def __init__(self, max_items: int = 20):
        self.max_items = max_items
        self.history: list[dict] = []
        self._last_content = ""
        self._running = False
        self._thread = None
        self._on_update_callback = None

    def start(self, on_update=None):
        """Start clipboard polling daemon."""
        self._on_update_callback = on_update
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _poll_loop(self):
        """Background loop — polls clipboard every 0.8s."""
        import tkinter as tk
        try:
            root = tk.Tk()
            root.withdraw()
            while self._running:
                try:
                    content = root.clipboard_get()
                    if content and content != self._last_content and len(content.strip()) > 0:
                        self._last_content = content
                        entry = {
                            "text": content[:800],  # Cap very long items
                            "preview": content[:60].replace("\n", " ").strip(),
                            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                            "length": len(content)
                        }
                        # Avoid exact duplicates at top
                        if not self.history or self.history[0]["text"] != content:
                            self.history.insert(0, entry)
                            self.history = self.history[:self.max_items]
                            if self._on_update_callback:
                                try:
                                    self._on_update_callback(entry)
                                except Exception:
                                    pass
                except Exception:
                    pass
                time.sleep(0.8)
            root.destroy()
        except Exception:
            pass

    def copy_item(self, index: int) -> str:
        """Copies a history item back to clipboard by index."""
        if 0 <= index < len(self.history):
            return self.history[index]["text"]
        return ""

    def clear_history(self):
        """Clears all clipboard history."""
        self.history.clear()
        self._last_content = ""

    def get_summary(self) -> str:
        """Returns a text summary of clipboard history."""
        if not self.history:
            return "Clipboard history is empty."
        lines = [f"📋 Smart Clipboard History ({len(self.history)} items):"]
        for i, item in enumerate(self.history[:10]):
            lines.append(f"  [{i+1}] {item['preview'][:50]}{'...' if len(item['preview']) >= 50 else ''} ({item['timestamp']})")
        return "\n".join(lines)


# Global singleton
clipboard_manager = ClipboardManager(max_items=20)
