import os
import time
import json
import threading
import requests
from pathlib import Path
from cwa_agent.config import BASE_DIR, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, USER_NAME

class TelegramRemoteBridge:
    """
    Stark Industries Autonomous Phone Remote Control Bridge.
    Connects CWA-JARVIS directly to Telegram on the user's phone.
    Allows full remote workstation control (screenshots, lock, system scan, camera, wallpaper, AI chat)
    from anywhere in the world using standard HTTP polling — zero hardcoding.
    """
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.authorized_chat_id = str(chat_id or TELEGRAM_CHAT_ID).strip()
        self._running = False
        self._thread = None
        self._last_update_id = 0
        self.on_remote_activity = None

    def start(self, on_remote_activity=None):
        """Starts the background Telegram polling daemon."""
        if on_remote_activity:
            self.on_remote_activity = on_remote_activity

        if not self.token:
            print("[Telegram Bridge 📱] Token not configured. Remote bridge standby.")
            return False

        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()
            print("[Telegram Bridge 📱] Connected! Remote phone control active.")
            return True

    def stop(self):
        """Stops the polling daemon."""
        self._running = False

    def is_configured(self) -> bool:
        return bool(self.token and self.token.strip())

    def set_credentials(self, token: str, chat_id: str = "") -> bool:
        """Dynamically updates and saves Telegram Bot Token & Chat ID into .env file."""
        self.token = token.strip()
        if chat_id:
            self.authorized_chat_id = str(chat_id).strip()

        env_path = BASE_DIR / ".env"
        env_lines = []
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                env_lines = f.readlines()

        token_set = False
        chat_id_set = False
        new_lines = []
        for line in env_lines:
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                new_lines.append(f"TELEGRAM_BOT_TOKEN={self.token}\n")
                token_set = True
            elif line.startswith("TELEGRAM_CHAT_ID="):
                new_lines.append(f"TELEGRAM_CHAT_ID={self.authorized_chat_id}\n")
                chat_id_set = True
            else:
                new_lines.append(line)

        if not token_set:
            new_lines.append(f"TELEGRAM_BOT_TOKEN={self.token}\n")
        if not chat_id_set and self.authorized_chat_id:
            new_lines.append(f"TELEGRAM_CHAT_ID={self.authorized_chat_id}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        print("[Telegram Bridge 📱] Credentials saved to .env")
        if self._running:
            self.stop()
            time.sleep(0.5)
        return self.start(self.on_remote_activity)

    def send_message(self, chat_id: str, text: str) -> bool:
        """Sends a text message to the specified Telegram chat."""
        if not self.token or not chat_id or not text:
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code != 200:
                # Retry without markdown if parsing fails
                payload.pop("parse_mode", None)
                requests.post(url, json=payload, timeout=15)
            return True
        except Exception as e:
            print(f"[Telegram Bridge Send Error]: {e}")
            return False

    def send_photo(self, chat_id: str, photo_path: str, caption: str = "") -> bool:
        """Uploads and sends a photo file to the Telegram chat."""
        if not self.token or not chat_id or not photo_path or not os.path.exists(photo_path):
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        try:
            with open(photo_path, "rb") as photo_file:
                files = {"photo": photo_file}
                data = {"chat_id": chat_id, "caption": caption}
                r = requests.post(url, data=data, files=files, timeout=45)
                return r.status_code == 200
        except Exception as e:
            print(f"[Telegram Bridge Photo Error]: {e}")
            return False

    def send_audio(self, chat_id: str, audio_path: str, caption: str = "", title: str = "", performer: str = "") -> bool:
        """Uploads and sends an audio/music file (MP3) to the Telegram chat."""
        if not self.token or not chat_id or not audio_path or not os.path.exists(audio_path):
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendAudio"
        try:
            with open(audio_path, "rb") as audio_file:
                files = {"audio": audio_file}
                data = {
                    "chat_id": chat_id,
                    "caption": caption,
                    "title": title or Path(audio_path).stem,
                    "performer": performer or "CWA Media Studio"
                }
                r = requests.post(url, data=data, files=files, timeout=60)
                return r.status_code == 200
        except Exception as e:
            print(f"[Telegram Bridge Audio Error]: {e}")
            return False

    def send_video(self, chat_id: str, video_path: str, caption: str = "") -> bool:
        """Uploads and sends a video file (MP4) to the Telegram chat."""
        if not self.token or not chat_id or not video_path or not os.path.exists(video_path):
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendVideo"
        try:
            with open(video_path, "rb") as video_file:
                files = {"video": video_file}
                data = {"chat_id": chat_id, "caption": caption}
                r = requests.post(url, data=data, files=files, timeout=120)
                return r.status_code == 200
        except Exception as e:
            print(f"[Telegram Bridge Video Error]: {e}")
            return False

    def send_document(self, chat_id: str, doc_path: str, caption: str = "") -> bool:
        """Uploads and sends any document or file to the Telegram chat."""
        if not self.token or not chat_id or not doc_path or not os.path.exists(doc_path):
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendDocument"
        try:
            with open(doc_path, "rb") as doc_file:
                files = {"document": doc_file}
                data = {"chat_id": chat_id, "caption": caption}
                r = requests.post(url, data=data, files=files, timeout=90)
                return r.status_code == 200
        except Exception as e:
            print(f"[Telegram Bridge Document Error]: {e}")
            return False

    def _poll_loop(self):
        """Long-polling loop receiving incoming commands from user's phone."""
        while self._running:
            try:
                url = f"https://api.telegram.org/bot{self.token}/getUpdates"
                params = {"offset": self._last_update_id + 1, "timeout": 20}
                r = requests.get(url, params=params, timeout=25)
                
                if r.status_code == 200:
                    data = r.json()
                    for update in data.get("result", []):
                        self._last_update_id = update.get("update_id", self._last_update_id)
                        message = update.get("message", {})
                        text = message.get("text", "").strip()
                        chat = message.get("chat", {})
                        chat_id = str(chat.get("id", ""))
                        sender_name = message.get("from", {}).get("first_name", "Sir")

                        if text and chat_id:
                            self._handle_incoming_message(chat_id, text, sender_name)

            except Exception as e:
                time.sleep(2)

            time.sleep(1)

    def _handle_incoming_message(self, chat_id: str, user_text: str, sender_name: str):
        """Processes and responds to messages sent from the user's phone."""
        # Security: Bind first user as authorized chat ID if empty
        if not self.authorized_chat_id:
            self.authorized_chat_id = chat_id
            self.set_credentials(self.token, chat_id)
            print(f"[Telegram Bridge 🔐] Authorized Phone Chat ID bound to: {chat_id}")

        # Reject unauthorized chat IDs
        if str(chat_id) != str(self.authorized_chat_id):
            self.send_message(chat_id, "⚠️ Access Denied: Unauthorized workstation remote connection.")
            return

        print(f"[Telegram 📲 {sender_name}]: {user_text}")
        if self.on_remote_activity:
            try:
                self.on_remote_activity(f"[Telegram 📲 {sender_name}]: {user_text}")
            except Exception:
                pass

        low = user_text.lower().strip()

        # --- 1. Quick Remote Photo: Desktop Screenshot ---
        if any(w in low for w in ["screenshot", "/screenshot", "screen photo", "desktop photo", "screen bhej"]):
            from cwa_agent.core.vision import vision
            self.send_message(chat_id, "📸 Capturing desktop screen, Sir...")
            success, path = vision.capture_screen(auto_open=False)
            if success and os.path.exists(path):
                self.send_photo(chat_id, path, caption="🖥️ Current Desktop Screen Snapshot")
            else:
                self.send_message(chat_id, "Could not capture desktop screen at this moment, Sir.")
            return

        # --- 2. Quick Remote Photo: Webcam Snapshot ---
        if any(w in low for w in ["camera", "/cam", "/camera", "webcam", "camera photo", "cam photo"]):
            from cwa_agent.core.vision import vision
            self.send_message(chat_id, "👁️ Capturing camera snapshot, Sir...")
            success, path, _ = vision.capture_camera_frame(save=True)
            if success and os.path.exists(path):
                self.send_photo(chat_id, path, caption="📷 Live Workstation Camera Snapshot")
            else:
                self.send_message(chat_id, "Could not access workstation camera, Sir.")
            return

        # --- 3. Dynamic Neural AI Evaluation for all other commands/queries ---
        from cwa_agent.core.brain import brain
        try:
            # Let Gemini execute any tools (lock, volume, scan, wallpaper, code, apps) dynamically!
            prompt = (
                f"[REMOTE TELEGRAM COMMAND from {USER_NAME}'s phone]: '{user_text}'. "
                f"Execute any requested workstation tools or answer clearly in natural Hinglish/English. Keep response concise for phone view."
            )
            response = brain.process_query(prompt)
            resp_text = response.text if hasattr(response, 'text') else str(response)
            
            # Send clean result back to phone
            self.send_message(chat_id, resp_text)
            
            if self.on_remote_activity:
                try:
                    self.on_remote_activity(f"[CWA 🤖 → Phone]: {resp_text}")
                except Exception:
                    pass

        except Exception as e:
            self.send_message(chat_id, f"Neural execution error: {str(e)}")

# Global Singleton Remote Bridge
remote_bridge = TelegramRemoteBridge()
