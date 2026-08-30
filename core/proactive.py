import os
import sys
import time
import random
import datetime
import threading
import psutil
from cwa_agent.core.audio_fx import audio_fx

# Fix Windows cp1252 encoding
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


class ProactiveSentinel:
    """
    Autonomous Proactive Background Brain for CWA-JARVIS.
    Monitors hardware battery thresholds, screen-time wellness intervals,
    dispatches voice-scheduled reminders, and initiates organic companion check-ins
    after 1 to 5 minutes of silence.
    """
    def __init__(self, on_proactive_alert=None):
        self.on_proactive_alert = on_proactive_alert
        self.reminders = []
        self._running = False
        self._sentinel_thread = None
        self._battery_warned = False
        self._start_time = time.time()
        self._last_health_break = time.time()
        self.last_interaction_time = time.time()
        self.next_idle_interval = random.randint(90, 240)  # Random 1.5 to 4 mins
        self.whatsapp_auto_reply_enabled = False
        self.whatsapp_busy_reason = "Sir is currently busy working"
        self.whatsapp_reply_history = {}

    def toggle_whatsapp_autoreply(self, enable: bool, busy_reason: str = "Sir is currently busy working") -> str:
        """Toggles the autonomous background WhatsApp AI auto-responder."""
        self.whatsapp_auto_reply_enabled = bool(enable)
        if busy_reason and busy_reason.strip():
            self.whatsapp_busy_reason = busy_reason.strip()
        status_str = "ACTIVE" if self.whatsapp_auto_reply_enabled else "DISABLED"
        print(f"[Proactive Sentinel 📱] WhatsApp AI Auto-Responder: {status_str} | Note: '{self.whatsapp_busy_reason}'")
        return f"WhatsApp AI Auto-Responder is now {status_str}. Busy status: '{self.whatsapp_busy_reason}', Sir."


    def start(self, on_proactive_alert=None):
        if on_proactive_alert:
            self.on_proactive_alert = on_proactive_alert
        if not self._running:
            self._running = True
            self._sentinel_thread = threading.Thread(target=self._sentinel_loop, daemon=True)
            self._sentinel_thread.start()
            print("[Proactive Sentinel ⚡] Autonomous background sentry active with 1-5 min Companion Check-ins.")

    def stop(self):
        self._running = False

    def touch_interaction(self):
        """Resets the idle timer whenever user or agent interacts."""
        self.last_interaction_time = time.time()
        self.next_idle_interval = random.randint(90, 240)

    def add_reminder(self, minutes: float, message: str) -> str:
        """Schedules a voice reminder to be spoken autonomously in X minutes."""
        if minutes <= 0 or not message:
            return "Invalid reminder duration or message, Sir."

        due_time = time.time() + (minutes * 60)
        due_str = datetime.datetime.fromtimestamp(due_time).strftime("%I:%M %p")
        
        self.reminders.append({
            "due_time": due_time,
            "due_str": due_str,
            "message": message.strip()
        })
        print(f"[Proactive Sentinel ⏰] Reminder scheduled for {due_str}: '{message}'")
        return f"Reminder set for {due_str}: '{message}', Sir."

    def _sentinel_loop(self):
        while self._running:
            try:
                now = time.time()

                # --- 1. Check Scheduled Reminders ---
                due_reminders = [r for r in self.reminders if r["due_time"] <= now]
                for rem in due_reminders:
                    self.reminders.remove(rem)
                    try:
                        from cwa_agent.core.brain import brain
                        from cwa_agent.config import USER_NAME
                        dynamic_rem = brain.process_query(
                            f"SCHEDULED REMINDER: The timer is up! Remind {USER_NAME} about their scheduled reminder: '{rem['message']}'. "
                            f"Deliver this in a crisp, natural 1-sentence JARVIS style. Do NOT call any tools."
                        )
                        self._dispatch_alert(
                            dynamic_rem,
                            emotion=dynamic_rem.emotion or "ALERT",
                            intensity=dynamic_rem.intensity or 85
                        )
                    except Exception as e:
                        print(f"[Proactive Reminder Error]: {e}")

                # --- 2. Check Critical Battery Threshold (< 20% unplugged) ---
                battery = psutil.sensors_battery()
                if battery:
                    if not battery.power_plugged and battery.percent <= 20:
                        if not self._battery_warned:
                            self._battery_warned = True
                            try:
                                from cwa_agent.core.brain import brain
                                from cwa_agent.config import USER_NAME
                                dynamic_batt = brain.process_query(
                                    f"CRITICAL HARDWARE ALERT: Battery level has dropped to {battery.percent}% and AC adapter is unplugged. "
                                    f"Warn {USER_NAME} urgently to plug in the charger in 1 concise JARVIS sentence. Do NOT call any tools."
                                )
                                self._dispatch_alert(
                                    dynamic_batt,
                                    emotion=dynamic_batt.emotion or "ANGRY",
                                    intensity=dynamic_batt.intensity or 90
                                )
                            except Exception as e:
                                print(f"[Proactive Battery Error]: {e}")
                    elif battery.power_plugged:
                        self._battery_warned = False

                # --- 3. Screen-Time Health Sentinel (Every 90 mins) ---
                if now - self._last_health_break >= 5400:  # 90 minutes
                    self._last_health_break = now
                    try:
                        from cwa_agent.core.brain import brain
                        from cwa_agent.config import USER_NAME
                        dynamic_health = brain.process_query(
                            f"WELLNESS SENTINEL: {USER_NAME} has been working continuously at the workstation for 90 minutes. "
                            f"Give a warm, caring 1-sentence recommendation to stretch, rest eyes, or drink water. Do NOT call any tools."
                        )
                        self._dispatch_alert(
                            dynamic_health,
                            emotion=dynamic_health.emotion or "CARING",
                            intensity=dynamic_health.intensity or 80
                        )
                    except Exception as e:
                        print(f"[Proactive Health Error]: {e}")

                # --- 4. Autonomous 1-5 Min Idle Companion Check-In ---
                from cwa_agent.core.speaker import speaker
                if not speaker.is_speaking:
                    if now - self.last_interaction_time >= self.next_idle_interval:
                        self.last_interaction_time = now
                        self.next_idle_interval = random.randint(90, 240)
                        
                        try:
                            from cwa_agent.core.brain import brain
                            checkin_resp = brain.generate_idle_checkin()
                            if checkin_resp and checkin_resp.text:
                                self._dispatch_alert(
                                    checkin_resp,
                                    emotion=checkin_resp.emotion or "FOCUSED",
                                    intensity=checkin_resp.intensity or 75
                                )
                        except Exception as ex:
                            print(f"[Proactive Check-In Exception]: {ex}")

                # --- 5. Background WhatsApp AI Auto-Responder Monitor ---
                if getattr(self, 'whatsapp_auto_reply_enabled', False):
                    try:
                        self._check_whatsapp_auto_reply()
                    except Exception as ex_wa:
                        print(f"[Proactive WhatsApp Monitor Error]: {ex_wa}")

            except Exception as e:
                print(f"[Proactive Sentinel Exception]: {e}")

            time.sleep(10)  # Check every 10 seconds

    def _check_whatsapp_auto_reply(self):
        """Monitors for unread WhatsApp desktop notifications and dispatches AI auto-reply."""
        try:
            import pygetwindow as gw
            wa_wins = [w for w in gw.getAllWindows() if "whatsapp" in w.title.lower()]
            if wa_wins:
                win = wa_wins[0]
                # If window title indicates unread messages (e.g. "(2) WhatsApp")
                if win.title and "(" in win.title:
                    now_ts = time.time()
                    last_ts = getattr(self, 'whatsapp_reply_history', {}).get(win.title, 0)
                    if now_ts - last_ts > 45:  # Rate limit 45s per contact
                        self.whatsapp_reply_history[win.title] = now_ts
                        print(f"[Proactive WhatsApp 📱] Detected unread notification: {win.title}")
                        from cwa_agent.core.tools import auto_reply_whatsapp_chat
                        auto_reply_whatsapp_chat(contact_name="", custom_busy_note=self.whatsapp_busy_reason)
        except Exception as ex:
            pass

    def _dispatch_alert(self, text_or_obj, emotion: str = "ALERT", intensity: int = 80):
        audio_fx.play_alert()
        if self.on_proactive_alert:
            try:
                self.on_proactive_alert(text_or_obj, emotion=emotion, intensity=intensity)
            except Exception as e:
                print(f"[Proactive Dispatch Error]: {e}")

# Global Proactive Sentinel Singleton
proactive = ProactiveSentinel()

