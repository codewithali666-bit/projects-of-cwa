"""
CWA Autonomous Agent — Real-Time Windows System & App Notification Sentry
Monitors all incoming Windows toast notifications across WhatsApp, Telegram, Chrome, Mail, VS Code, System Alerts, etc.
Zero hardcoding — dynamically parses Windows Notification SQLite subsystem in real-time.
"""
import os
import time
import shutil
import sqlite3
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

class NotificationSentry:
    """
    Real-time Windows Notification Monitor Daemon.
    Detects new incoming notifications, triggers GUI card updates, voice alerts,
    and handles interactive Open/Close actions.
    """
    def __init__(self):
        self._running = False
        self._thread = None
        self._last_seen_id = 0
        self.active_notification = None
        self.on_notification_callback = None
        self.on_voice_alert_callback = None
        self.on_decision_callback = None

        # Resolve wpndatabase.db path
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        self.db_path = Path(local_app_data) / "Microsoft" / "Windows" / "Notifications" / "wpndatabase.db"

    def is_supported(self) -> bool:
        return self.db_path.exists()

    def start(self, on_notification=None, on_voice_alert=None, on_decision=None):
        """Starts the notification monitor background daemon."""
        if on_notification:
            self.on_notification_callback = on_notification
        if on_voice_alert:
            self.on_voice_alert_callback = on_voice_alert
        if on_decision:
            self.on_decision_callback = on_decision

        if not self.is_supported():
            print("[Notification Sentry ⚠️] Windows Notification database not found. Sentry standby.")
            return False

        if not self._running:
            self._running = True
            # Initialize baseline ID to ignore old historical notifications
            self._init_baseline_id()
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()
            print("[Notification Sentry 🔔] Live Windows notification monitor daemon active.")
            return True

    def stop(self):
        """Stops the monitoring daemon."""
        self._running = False

    def _init_baseline_id(self):
        """Initializes baseline ID so we catch new incoming notifications without re-alerting ancient history."""
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(Id) FROM Notification;")
            row = cursor.fetchone()
            if row and row[0] is not None:
                self._last_seen_id = int(row[0])
            conn.close()
        except Exception:
            self._last_seen_id = 0

    def _clean_app_name(self, raw_app_id: str) -> str:
        """Dynamically parses any Windows app ID into a clean human-readable name. Zero hardcoding — works with any app automatically."""
        if not raw_app_id:
            return "Windows System"
        
        raw = str(raw_app_id).strip()

        # Step 1: For UWP apps like "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App" or "Microsoft.WindowsStore_8wekyb3d8bbwe!App"
        if "!" in raw:
            package_part = raw.split("!")[0]
            if "_" in package_part:
                package_part = package_part.split("_")[0]
            raw = package_part

        # Step 2: Remove GUID/SID prefixes like {GUID} or S-1-... 
        if "}" in raw:
            raw = raw.split("}")[-1]

        # Step 3: Remove common file extensions
        for ext in [".exe", ".lnk", ".Root"]:
            raw = raw.replace(ext, "")

        # Step 4: Remove common platform prefixes
        raw = raw.strip().strip("\\").strip("/")

        # Step 5: Extract last meaningful segment from dot-separated IDs
        if "." in raw:
            segments = [s for s in raw.split(".") if s.strip()]
            generic_words = {"windows", "microsoft", "google", "mozilla", "com", "app", "desktop", "client"}
            meaningful = [s for s in segments if s.lower() not in generic_words]
            raw = meaningful[-1] if meaningful else segments[-1]

        # Step 6: Extract from backslash paths
        if "\\" in raw:
            raw = raw.split("\\")[-1]
        if "/" in raw:
            raw = raw.split("/")[-1]

        # Step 7: Convert CamelCase or underscores to spaced title
        import re
        spaced = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', raw)
        spaced = spaced.replace("_", " ").replace("-", " ")
        cleaned = " ".join(spaced.split()).strip().title()

        # Polish known spaced words
        cleaned = cleaned.replace("Whats App", "WhatsApp").replace("Screen Sketch", "Snipping Tool")

        return cleaned if cleaned else "Windows System"

    def _parse_payload(self, payload_data) -> tuple:
        """Extracts Title and Body text from Windows toast XML payload."""
        if not payload_data:
            return ("", "")

        payload_str = payload_data.decode("utf-8", errors="ignore") if isinstance(payload_data, bytes) else str(payload_data)
        title = ""
        body = ""

        try:
            root = ET.fromstring(payload_str)
            texts = [elem.text.strip() for elem in root.iter("text") if elem.text and elem.text.strip()]
            if texts:
                title = texts[0]
                body = " | ".join(texts[1:]) if len(texts) > 1 else ""
        except Exception:
            # Fallback regex extraction
            import re
            m = re.findall(r'<text[^>]*>([^<]+)</text>', payload_str)
            if m:
                title = m[0].strip()
                body = " | ".join(m[1:]).strip() if len(m) > 1 else ""

        return (title, body)

    def _monitor_loop(self):
        """Continuous live polling loop scanning for new Windows toast notifications with WAL support."""
        seen_ids = set()
        if self._last_seen_id > 0:
            seen_ids.add(self._last_seen_id)

        while self._running:
            try:
                if self.db_path.exists():
                    conn = None
                    try:
                        # Direct read-only URI connection with live WAL reading
                        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
                    except Exception:
                        # Fallback: copy db + wal files together
                        temp_dir = Path("./temp_sentry_dir")
                        temp_dir.mkdir(exist_ok=True)
                        temp_db = temp_dir / "wpndatabase.db"
                        shutil.copy2(self.db_path, temp_db)
                        wal_src = self.db_path.parent / "wpndatabase.db-wal"
                        if wal_src.exists():
                            shutil.copy2(wal_src, temp_dir / "wpndatabase.db-wal")
                        conn = sqlite3.connect(str(temp_db))

                    cursor = conn.cursor()
                    query = """
                    SELECT n.Id, h.PrimaryId, n.Payload, n.ArrivalTime
                    FROM Notification n
                    LEFT JOIN NotificationHandler h ON n.HandlerId = h.RecordId
                    WHERE n.Id > ?
                    ORDER BY n.Id ASC;
                    """
                    cursor.execute(query, (self._last_seen_id,))
                    rows = cursor.fetchall()

                    for row in rows:
                        nid, raw_app, payload, arr_time = row
                        int_id = int(nid)
                        self._last_seen_id = max(self._last_seen_id, int_id)

                        if int_id in seen_ids:
                            continue
                        seen_ids.add(int_id)
                        if len(seen_ids) > 1000:
                            seen_ids.clear()
                            seen_ids.add(int_id)

                        title, body = self._parse_payload(payload)
                        if not title and not body:
                            continue

                        clean_app = self._clean_app_name(raw_app)
                        time_str = time.strftime("%H:%M:%S")

                        notif_data = {
                            "id": int_id,
                            "app": clean_app,
                            "raw_app": raw_app,
                            "title": title,
                            "body": body,
                            "time": time_str
                        }

                        self.active_notification = notif_data
                        print(f"\n[Notification Alert 🔔] App: {clean_app} | Title: {title} | Body: {body[:60]} ({time_str})")

                        # 1. Trigger HUD GUI Update
                        if self.on_notification_callback:
                            try:
                                self.on_notification_callback(notif_data)
                            except Exception as ex_gui:
                                print(f"[Notification GUI Update Error]: {ex_gui}")

                        # 2. Trigger Vocal Speech Alert
                        if self.on_voice_alert_callback:
                            try:
                                self.on_voice_alert_callback(notif_data)
                            except Exception as ex_v:
                                print(f"[Notification Voice Alert Error]: {ex_v}")

                    conn.close()

            except Exception as e:
                pass

            time.sleep(0.6)

    def handle_user_decision(self, decision: str) -> str:
        """
        Executes Open or Close action on the active notification.
        - decision: 'open' / 'close' / 'dismiss'
        """
        if not self.active_notification:
            return "Sir, there are currently no active notifications to open or dismiss."

        notif = self.active_notification
        app_name = notif.get("app", "App")
        dec = str(decision).lower().strip()

        if any(w in dec for w in ["open", "kholo", "show", "launch", "chalao"]):
            # Open / Focus the app
            from cwa_agent.core.tools import app_control
            res = app_control(action="open", app_name=app_name)
            self.active_notification = None
            if self.on_decision_callback:
                try:
                    self.on_decision_callback("open")
                except Exception:
                    pass
            return f"Opening {app_name}, Sir! {res}"

        elif any(w in dec for w in ["close", "dismiss", "band", "ignore", "hatao", "rehne"]):
            self.active_notification = None
            if self.on_decision_callback:
                try:
                    self.on_decision_callback("close")
                except Exception:
                    pass
            return f"Notification from {app_name} dismissed, Sir."

        return f"Unknown decision: '{decision}'. Please say 'open' or 'close'."


# Global Singleton Notification Sentry
notification_sentry = NotificationSentry()
