import sys
import os
import threading
import time
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cwa_agent.config import ASSISTANT_NAME, USER_NAME, GEMINI_API_KEY
from cwa_agent.core.brain import brain
from cwa_agent.core.speaker import speaker
from cwa_agent.core.listener import listener
from cwa_agent.core.vision import vision
from cwa_agent.core.audio_fx import audio_fx
from cwa_agent.core.memory import memory
from cwa_agent.core.proactive import proactive
from cwa_agent.core.system_scanner import scanner
from cwa_agent.core.ambient_listener import ambient
from cwa_agent.core.remote_bridge import remote_bridge
from cwa_agent.core.notification_sentry import notification_sentry
from cwa_agent.ui.hud_gui import CWAHUD

class CWAOrchestrator:
    def __init__(self):
        self.gui = None
        self.is_busy = False
        self.hands_free_active = False
        self._hands_free_thread = None

    def start_gui(self):
        # Play Stark Arc Reactor Boot Sound
        audio_fx.play_boot()

        # Run Full System Scan at Boot (populates scanner cache for brain context)
        print("[System Scanner 🔍] Performing full boot scan...")
        threading.Thread(target=self._boot_scan, daemon=True).start()

        # Ambient Room Intelligence is handled inside the Master Mic Loop
        print("[Ambient Intelligence 🎤] Room awareness active via Master Mic Loop.")

        # Start Proactive Background Sentinel (Battery, Reminders, Health)
        proactive.start(on_proactive_alert=self._on_proactive_alert)

        # Start Phone Remote Control Bridge (Telegram Daemon)
        remote_bridge.start(
            on_remote_activity=lambda msg: self.gui.after(0, lambda: self.gui.log("system", f"{msg}\n")) if self.gui else None
        )

        # Create HUD GUI
        self.gui = CWAHUD(
            on_user_query=self.process_query,
            on_mic_toggle=self.trigger_voice_input,
            on_vision_trigger=self.trigger_vision_sight,
            on_always_listen_toggle=self.toggle_hands_free
        )


        # Register UI callbacks
        brain.register_clear_callback(lambda: self.gui.after(0, self.gui.clear_logs_ui) if self.gui else None)
        from cwa_agent.core.tools import register_download_callback, register_translation_callback, register_ttt_expand_callback, register_route_modal_callback
        register_download_callback(
            lambda title, pct, spd, sz, eta, st: self.gui.after(0, lambda: self.gui.update_download_progress(title, pct, spd, sz, eta, st)) if self.gui else None
        )
        register_translation_callback(
            lambda src_txt, res_txt, src, tgt: self.gui.after(0, lambda: self.gui._on_manual_trans_done(res_txt)) if self.gui else None
        )
        register_ttt_expand_callback(
            lambda: self.gui.after(0, self.gui.expand_ttt_panel) if self.gui else None
        )
        register_route_modal_callback(
            lambda r_data: self.gui.after(0, lambda: self.gui.show_route_modal(r_data)) if self.gui else None
        )

        # Start Live Notification Sentry Daemon (monitors all Windows toast notifications)
        notification_sentry.start(
            on_notification=self._on_system_notification,
            on_voice_alert=self._on_notification_voice_alert,
            on_decision=lambda dec: self.gui.after(0, self.gui._reset_notification_card) if self.gui else None
        )

        # Start Smart Clipboard History Manager Daemon
        from cwa_agent.core.clipboard_manager import clipboard_manager
        clipboard_manager.start(
            on_update=lambda entry: self.gui.update_clipboard_history(entry) if self.gui else None
        )

        # Start Network & WiFi Monitor Daemon
        from cwa_agent.core.network_monitor import network_monitor
        network_monitor.start(
            on_update=lambda stats: self.gui.update_network_stats(stats) if self.gui else None
        )

        # Enable Hands-Free Master Mic Loop automatically on boot
        self.toggle_hands_free(True)

        # Dynamic AI Greeting in background (after scan completes)
        threading.Thread(target=self._greeting, daemon=True).start()

        # Start GUI main loop
        self.gui.mainloop()


    def _boot_scan(self):
        """Runs the full system scan at boot and logs results into HUD."""
        try:
            report = scanner.full_scan()
            scan_summary = scanner.get_system_context_string()
            print(f"[System Scanner ✅] Boot scan complete:\n{scan_summary}")
            if self.gui:
                self.gui.after(0, lambda: self.gui.log("system", f"[System Boot Scan ✅]\n{scan_summary}\n"))
        except Exception as e:
            print(f"[System Scanner Error] {e}")

    def _on_proactive_alert(self, text_or_obj, emotion: str = "ALERT", intensity: int = 85):
        """Dispatches autonomous proactive background alerts to speech and HUD."""
        text = text_or_obj.text if hasattr(text_or_obj, 'text') else str(text_or_obj)
        if self.gui:
            self.gui.log("system", f"[Proactive Sentry ⚡] {text}\n")
        self._speak_and_display(text_or_obj, speak=True)

    def _on_system_notification(self, notif_data: dict):
        """Called by NotificationSentry daemon when a new Windows notification arrives. Updates HUD card via thread-safe after()."""
        if self.gui:
            self.gui.after(0, lambda: self.gui.update_notification_card(notif_data))

    def _on_notification_voice_alert(self, notif_data: dict):
        """Speaks a short voice alert when a new notification arrives so Sir is immediately informed."""
        try:
            app_name = notif_data.get("app", "App")
            title = notif_data.get("title", "")
            body = notif_data.get("body", "")

            # Build concise spoken alert
            alert_parts = [f"Sir, {app_name} se notification aaya hai"]
            if title:
                alert_parts.append(title[:80])
            if body:
                alert_parts.append(body[:60])
            alert_text = ". ".join(alert_parts) + ". Kya open karun ya dismiss karun?"

            # Speak alert (non-blocking)
            speaker.speak(alert_text)
        except Exception as e:
            print(f"[Notification Voice Alert Error]: {e}")

    def _greeting(self):
        time.sleep(1.2)
        greet_text = brain.generate_greeting()
        self._speak_and_display(greet_text, speak=True)

    def toggle_hands_free(self, enabled: bool):
        self.hands_free_active = enabled
        if enabled:
            if self._hands_free_thread is None or not self._hands_free_thread.is_alive():
                self._hands_free_thread = threading.Thread(target=self._master_mic_loop, daemon=True)
                self._hands_free_thread.start()

    def _master_mic_loop(self):
        """
        Unified Master Mic Intelligence Loop.
        When 'Always Listen' is ON:
          - Every phrase spoken in the room is saved to the ambient buffer.
          - Everything is also processed as a direct command/query by CWA —
            no wake word required. User can say ANYTHING directly.
          - If multiple people are in the room and someone says something unrelated,
            CWA will respond only to audible speech it picks up.
        """
        while self.hands_free_active:
            if not self.is_busy and not speaker.is_speaking:
                if self.gui:
                    self.gui.set_reactor_state("LISTENING")

                # Single mic listen — one thread, no conflicts
                spoken_text = listener.listen(phrase_time_limit=8)

                if spoken_text and spoken_text.strip():
                    low = spoken_text.lower()

                    # 1. Always save to ambient room conversation buffer (for recall)
                    ambient._add_to_buffer(spoken_text)
                    ambient._prune_old_entries()

                    # 2. Check for MJ persona switch
                    if "mj" in low.split() and "jarvis" not in low and "cwa" not in low:
                        speaker.set_persona("MJ", "female")

                    # 3. Process ALL speech as a direct query — no wake word needed
                    if self.hands_free_active and not self.is_busy:
                        audio_fx.play_process()
                        if self.gui:
                            self.gui.log("user", f"You (Voice): {spoken_text}\n")
                        self.process_query(spoken_text, speak=True)

            else:
                time.sleep(0.3)


    def process_query(self, user_text: str, speak: bool = True):
        if not user_text or self.is_busy:
            return

        proactive.touch_interaction()
        self.is_busy = True
        if self.gui:
            self.gui.set_reactor_state("THINKING")


        # Proactively check if user calls MJ or CWA
        low_query = user_text.lower()
        if "mj" in low_query.split() or "female voice" in low_query or "ladki ki awaz" in low_query or "ladki ban jao" in low_query:
            speaker.set_persona("MJ", "female")
        elif "cwa" in low_query.split() or "male voice" in low_query or "ladke ki awaz" in low_query or "ladka ban jao" in low_query:
            speaker.set_persona("CWA", "male")

        try:
            # Send query to Gemini Brain (executes tools dynamically)
            response_text = brain.process_query(user_text)
            self._speak_and_display(response_text, speak=speak)
        except Exception as e:
            err = f"Neural exception encountered: {str(e)}"
            self._speak_and_display(err, speak=speak)
        finally:
            if self.gui:
                if self.hands_free_active:
                    self.gui.set_reactor_state("LISTENING")
                else:
                    self.gui.set_reactor_state("IDLE")
            self.is_busy = False

    def trigger_voice_input(self):
        if self.is_busy:
            return

        def _voice_worker():
            self.is_busy = True
            audio_fx.play_listen()
            if self.gui:
                self.gui.set_reactor_state("LISTENING")
                self.gui.log("system", "[Listening to microphone... Speak now]\n")

            recognized_text = listener.listen(
                on_listen_start=lambda: self.gui.set_reactor_state("LISTENING") if self.gui else None,
                on_listen_end=lambda: self.gui.set_reactor_state("THINKING") if self.gui else None
            )

            if recognized_text:
                if self.gui:
                    self.gui.log("user", f"You (Voice): {recognized_text}\n")
                self.process_query(recognized_text, speak=True)
            else:
                if self.gui:
                    self.gui.log("system", "[No audible speech detected]\n")
                    self.gui.set_reactor_state("IDLE")
                self.is_busy = False

        threading.Thread(target=_voice_worker, daemon=True).start()

    def trigger_vision_sight(self):
        if self.is_busy:
            return

        def _vision_worker():
            self.is_busy = True
            if self.gui:
                self.gui.set_reactor_state("VISION")
                self.gui.log("system", "[Activating Camera Perception...]\n")

            success, path, _ = vision.capture_camera_frame(save=True)
            if not success:
                try:
                    dyn_cam_err = brain.process_query(
                        f"The camera hardware sensor could not be accessed on this machine. Inform {USER_NAME} in 1 short, polite JARVIS sentence. Do NOT call tools."
                    )
                    self._speak_and_display(dyn_cam_err, speak=True)
                except Exception:
                    self._speak_and_display("Camera hardware is unavailable, Sir.", speak=True)
                if self.gui:
                    self.gui.set_reactor_state("IDLE")
                self.is_busy = False
                return


            if self.gui:
                self.gui.log("system", "[Analyzing Camera Snapshot with Gemini Vision...]\n")

            analysis = vision.analyze_image_with_gemini(
                path, 
                prompt="Tell the user in natural Hinglish or English what is in front of the camera, what objects or actions you see, and greet them."
            )
            self._speak_and_display(analysis, speak=True)
            if self.gui:
                self.gui.set_reactor_state("IDLE")
            self.is_busy = False

        threading.Thread(target=_vision_worker, daemon=True).start()


    def _speak_and_display(self, response, speak: bool = True):
        text = response.text if hasattr(response, 'text') else str(response)
        emotion = getattr(response, 'emotion', 'CALM')
        intensity = getattr(response, 'intensity', 50)
        emoji_char = getattr(response, 'emoji', '')
        reason = getattr(response, 'reason', '')

        if self.gui:
            self.gui.set_emotion(emotion, intensity, reason, emoji_char=emoji_char)
            self.gui.log("cwa", f"CWA: {text}\n\n", emotion=emotion, intensity=intensity, emoji_char=emoji_char)


        if speak:
            if self.gui:
                self.gui.set_reactor_state("SPEAKING")
            speaker.speak(
                text,
                emotion=emotion,
                intensity=intensity,
                on_start=lambda: self.gui.set_reactor_state("SPEAKING") if self.gui else None,
                on_finish=lambda: self.gui.set_reactor_state("LISTENING" if self.hands_free_active else "IDLE") if self.gui else None
            )

    def start_cli(self):
        """Interactive Terminal / Console Chat Mode with Dynamic Neural Emotions"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 60)
        print("     CWA // AUTONOMOUS JARVIS AGENT (EMOTIONAL CONSCIOUSNESS)")
        print("     Type your message, or type 'voice' to speak, 'exit' to quit.")
        print("=" * 60)
        
        greet = brain.generate_greeting()
        print(f"\n[CWA 👨 {greet.emotion} ({greet.intensity}%)]: {greet.text}")
        speaker.speak_async(greet.text, emotion=greet.emotion, intensity=greet.intensity)

        while True:
            try:
                user_input = input("\n[You] > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ["exit", "quit", "bye", "shutdown"]:
                    farewell = brain.generate_shutdown()
                    print(f"\n[CWA 👨 {farewell.emotion}]: {farewell.text}")
                    speaker.speak(farewell.text, emotion=farewell.emotion, intensity=farewell.intensity)
                    break
                elif user_input.lower() in ["voice", "speak", "mic"]:
                    print("[CWA 👂]: Listening...")
                    spoken = listener.listen()
                    if spoken:
                        print(f"[You (Voice)] > {spoken}")
                        resp = brain.process_query(spoken)
                        print(f"\n[CWA 👨 {resp.emotion} ({resp.intensity}%)]: {resp.text}")
                        speaker.speak(resp.text, emotion=resp.emotion, intensity=resp.intensity)
                    else:
                        print("[CWA]: No speech detected.")
                elif user_input.lower() in ["vision", "camera", "see"]:
                    print("[CWA 👁️]: Capturing webcam snapshot...")
                    success, path, _ = vision.capture_camera_frame(save=True)
                    if success:
                        analysis = vision.analyze_image_with_gemini(path, prompt="Describe what you see in front of the camera in Hinglish or English.")
                        print(f"\n[CWA Vision]: {analysis}")
                        speaker.speak(analysis, emotion="SURPRISED", intensity=75)
                    else:
                        print("[CWA]: Could not access camera.")
                else:
                    resp = brain.process_query(user_input)
                    print(f"\n[CWA 👨 {resp.emotion} ({resp.intensity}%)]: {resp.text}")
                    speaker.speak(resp.text, emotion=resp.emotion, intensity=resp.intensity)

            except KeyboardInterrupt:
                farewell = brain.generate_shutdown()
                print(f"\n[CWA]: {farewell.text}")
                speaker.speak(farewell.text, emotion=farewell.emotion, intensity=farewell.intensity)
                break


def run():
    parser = argparse.ArgumentParser(description="CWA AI Assistant")
    parser.add_argument("--cli", action="store_true", help="Run in Terminal / CLI mode instead of GUI")
    args = parser.parse_args()

    app = CWAOrchestrator()
    if args.cli:
        app.start_cli()
    else:
        app.start_gui()

if __name__ == "__main__":
    run()
