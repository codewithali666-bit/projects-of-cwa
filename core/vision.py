import os
import time
import cv2
import pyautogui
from PIL import Image
from pathlib import Path
from cwa_agent.config import CAMERA_INDEX, CAMERA_URL, VISION_SNAPS_DIR, SCREENSHOTS_DIR, GEMINI_API_KEY, GEMINI_MODEL

class VisionSystem:
    def __init__(self, camera_index=CAMERA_INDEX):
        self.camera_index = camera_index
        self._cap = None
        self._mp_face = None

    def _open_camera_source(self, source):
        """Attempts to open a camera source (index or stream URL) with multiple backends."""
        if isinstance(source, str) and source.strip():
            # URL stream (e.g. DroidCam: http://192.168.1.5:4747/video or mjpegfeed)
            try:
                cap = cv2.VideoCapture(source)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        return cap
                    cap.release()
            except Exception:
                pass
            return None

        # Numeric index: try DirectShow, MSMF, and default backend
        for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
            try:
                cap = cv2.VideoCapture(int(source), backend)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        return cap
                    cap.release()
            except Exception:
                continue
        return None

    def release_camera(self):
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def capture_camera_frame(self, save=True) -> tuple[bool, str, any]:
        """
        Captures a frame from the webcam, DroidCam client, or IP camera.
        Tries configured source first, then auto-probes all available camera indices (0..4).
        Returns (success, filepath_if_saved, frame_bgr).
        """
        candidates = []
        # Priority 1: Configured stream URL (e.g. DROIDCAM_URL / CAMERA_URL)
        if CAMERA_URL:
            candidates.append(CAMERA_URL)

        # Priority 2: Configured index
        if self.camera_index is not None:
            candidates.append(self.camera_index)

        # Priority 3: Fallback indices (0, 1, 2, 3, 4)
        for idx in [0, 1, 2, 3, 4]:
            if idx not in candidates:
                candidates.append(idx)

        cap = None
        working_source = None
        for src in candidates:
            cap = self._open_camera_source(src)
            if cap is not None and cap.isOpened():
                working_source = src
                break

        if cap is None or not cap.isOpened():
            print("[Vision Error] Could not connect to any camera/DroidCam. "
                  "Please ensure DroidCam Client is 'Started' on PC or set CAMERA_URL/DROIDCAM_URL.")
            return False, "", None

        # Flush a couple frames for auto-exposure & sensor stabilization
        for _ in range(2):
            cap.read()

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            print("[Vision Error] Camera source connected but returned an empty frame.")
            return False, "", None

        filepath = ""
        if save:
            filename = f"cam_snap_{int(time.time())}.jpg"
            filepath = str(VISION_SNAPS_DIR / filename)
            cv2.imwrite(filepath, frame)
            print(f"[Vision 📸] Camera snapshot captured (source: {working_source}): {filepath}")

        return True, filepath, frame

    def capture_screen(self, auto_open=False) -> tuple[bool, str]:
        """
        Captures the current desktop screen using multi-engine fallbacks (ImageGrab, mss, pyautogui).
        Returns (success, filepath).
        """
        filename = f"screen_snap_{int(time.time())}.png"
        filepath = str(SCREENSHOTS_DIR / filename)


        # Engine 1: PIL ImageGrab
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab(all_screens=True)
            screenshot.save(filepath)
            print(f"[Vision 🖥️] Screenshot captured via ImageGrab: {filepath}")
            if auto_open:
                try:
                    os.startfile(filepath)
                except Exception:
                    pass
            return True, filepath
        except Exception as e1:
            print(f"[Vision Notice] ImageGrab engine note: {e1}")

        # Engine 2: mss (Fast multi-monitor capture)
        try:
            import mss
            with mss.mss() as sct:
                sct.shot(output=filepath)
            print(f"[Vision 🖥️] Screenshot captured via MSS: {filepath}")
            if auto_open:
                try:
                    os.startfile(filepath)
                except Exception:
                    pass
            return True, filepath
        except Exception as e2:
            print(f"[Vision Notice] MSS engine note: {e2}")

        # Engine 3: pyautogui
        try:
            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)
            print(f"[Vision 🖥️] Screenshot captured via PyAutoGUI: {filepath}")
            if auto_open:
                try:
                    os.startfile(filepath)
                except Exception:
                    pass
            return True, filepath
        except Exception as e3:
            print(f"[Vision Error] All screenshot engines failed: {e3}")
            return False, ""

    def analyze_image_with_gemini(self, image_path: str, prompt: str = "Describe what you see in detail and answer any specific questions.") -> str:
        """
        Sends the image to Gemini multimodal model for deep visual comprehension.
        """
        if not os.path.exists(image_path):
            return "Image file not found."

        try:
            from google import genai
            from google.genai import types
            from cwa_agent.config import GEMINI_API_KEY, GEMINI_MODEL

            api_k = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
            client = genai.Client(api_key=api_k)
            
            # Open image with PIL
            img = Image.open(image_path)
            
            from cwa_agent.config import USER_NAME
            from cwa_agent.core.speaker import speaker
            from cwa_agent.core.ignore_words import ignore_words_manager

            active_persona = getattr(speaker, 'persona', 'CWA')
            user_title = USER_NAME or "Sir"

            persona_context = (
                f"You are MJ (female), a warm, brilliant, proactive AI friend to {user_title}."
                if active_persona == "MJ" else
                f"You are CWA (male), a witty, sharp, JARVIS-grade AI companion to {user_title}."
            )

            system_instruction = (
                f"{persona_context} Examine the provided image / screenshot thoroughly. "
                f"Identify all code, error traces, UI elements, text, or visual details with 100% precision. "
                f"Provide a clear, direct, step-by-step solution and explanation for {user_title}. "
                f"Prompt from {user_title}: {prompt}"
            )

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[img, system_instruction]
            )
            raw_result = response.text.strip() if response.text else f"I looked at the image, {user_title}, but could not deduce details."
            return ignore_words_manager.filter_and_replace_text(raw_result, persona=active_persona)

        except Exception as e:
            return f"Vision analysis error: {str(e)}"

# Global Singleton instance
vision = VisionSystem()
