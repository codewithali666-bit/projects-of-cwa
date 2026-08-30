"""
CWA Autonomous Agent — AI Background Removal & Studio Portrait Engine
Powered by Remove.bg API with dynamic multi-source image ingestion (Local Files, URLs, Clipboard, Screen Snips).
Zero hardcoding — fully dynamic color mapping, format selection, and Telegram delivery.
"""
import os
import sys
import time
import requests
from pathlib import Path
from PIL import Image, ImageGrab

# Fix Windows cp1252 encoding — allow emojis in print() on all Windows terminals
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
os.environ.setdefault('PYTHONUTF8', '1')

from cwa_agent.config import (
    REMOVE_BG_API_KEY, BG_REMOVED_DIR, SCREENSHOTS_DIR, DOWNLOADS_DIR, USER_NAME
)

COLOR_PRESETS = {
    "transparent": "",
    "white": "white",
    "pure white": "white",
    "id white": "white",
    "blue": "#1e3a8a",
    "navy blue": "#0f172a",
    "passport blue": "#2563eb",
    "studio grey": "#475569",
    "black": "black",
    "red": "#dc2626",
    "green": "#16a34a",
    "yellow": "#facc15",
    "cyan": "#06b6d4"
}


class BackgroundRemover:
    """
    High-Precision AI Background Removal & Studio Portrait Generation Engine.
    """
    def __init__(self):
        self.api_url = "https://api.remove.bg/v1.0/removebg"
        BG_REMOVED_DIR.mkdir(parents=True, exist_ok=True)

    def _get_api_key(self) -> str:
        key = REMOVE_BG_API_KEY or os.getenv("REMOVE_BG_API_KEY", "")
        if not key:
            # Check .env directly if loaded late
            try:
                from dotenv import get_key
                from cwa_agent.config import ENV_PATH
                key = get_key(str(ENV_PATH), "REMOVE_BG_API_KEY") or ""
            except Exception:
                pass
        return key.strip()

    def remove_background(
        self,
        image_input: str = "",
        bg_color: str = "transparent",
        output_name: str = "",
        auto_open: bool = True
    ) -> tuple[bool, str, str]:
        """
        Removes background from an image file, URL, clipboard, or screen snapshot.
        
        Parameters:
        - image_input: Local file path, URL, 'clipboard', 'screen', or empty (auto-detects clipboard/recent screenshot).
        - bg_color: 'transparent', 'white' (passport/resume), 'blue', 'navy blue', 'studio grey', or custom HEX '#FFFFFF'.
        - output_name: Custom file name (optional).
        - auto_open: Whether to open output image in Windows Photo Viewer immediately.

        Returns: (success: bool, output_path: str, message: str)
        """
        api_key = self._get_api_key()
        u_name = USER_NAME or "Sir"

        if not api_key:
            return (
                False,
                "",
                f"{u_name}, Remove.bg API key is not configured yet. Please add REMOVE_BG_API_KEY in .env or HUD settings!"
            )

        # 1. Resolve source image
        source_path = ""
        is_url = False
        img_url = ""

        clean_input = str(image_input).strip() if image_input else ""

        if clean_input.startswith("http://") or clean_input.startswith("https://"):
            is_url = True
            img_url = clean_input
        elif clean_input.lower() in ["clipboard", "paste", "copy"]:
            # Grab from clipboard
            cb = ImageGrab.grabclipboard()
            if isinstance(cb, Image.Image):
                temp_cb = SCREENSHOTS_DIR / f"cb_for_bg_{int(time.time())}.png"
                cb.save(str(temp_cb))
                source_path = str(temp_cb)
            elif isinstance(cb, list) and len(cb) > 0 and os.path.exists(str(cb[0])):
                source_path = str(cb[0])
            else:
                return (False, "", f"{u_name}, clipboard par koi image ya screenshot nahi mila.")
        elif clean_input.lower() in ["screen", "screenshot", "snip"]:
            # Capture active screen
            from cwa_agent.core.vision import vision
            success, path = vision.capture_screen(auto_open=False)
            if success and path:
                source_path = path
            else:
                return (False, "", f"{u_name}, screen capture nahi ho paya.")
        elif clean_input and os.path.exists(clean_input):
            source_path = clean_input
        else:
            # Auto-detect: check clipboard first, then most recent download/screenshot
            cb = ImageGrab.grabclipboard()
            if isinstance(cb, Image.Image):
                temp_cb = SCREENSHOTS_DIR / f"cb_for_bg_{int(time.time())}.png"
                cb.save(str(temp_cb))
                source_path = str(temp_cb)
            else:
                # Check most recent image in screenshots or downloads
                recent_files = []
                for folder in [SCREENSHOTS_DIR, DOWNLOADS_DIR, Path.cwd()]:
                    if folder.exists():
                        for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
                            recent_files.extend(folder.glob(ext))
                if recent_files:
                    recent_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    source_path = str(recent_files[0])
                else:
                    return (False, "", f"{u_name}, background remove karne ke liye koi image specify karein ya clipboard par copy karein.")

        # 2. Resolve background color
        color_val = COLOR_PRESETS.get(bg_color.lower().strip(), bg_color.strip())
        if color_val == "transparent" or not color_val:
            color_val = None

        # 3. Call Remove.bg API
        timestamp = int(time.time())
        safe_name = "".join(c for c in output_name if c.isalnum() or c in ['_', '-']).strip() if output_name else f"cutout_{timestamp}"
        out_filename = f"{safe_name}.png"
        out_filepath = str(BG_REMOVED_DIR / out_filename)

        headers = {"X-Api-Key": api_key}
        data_payload = {
            "size": "auto",
            "format": "png"
        }
        if color_val:
            data_payload["bg_color"] = color_val

        try:
            print(f"[Remove.bg ✂️] Processing background removal (Color: {bg_color})...")
            if is_url:
                data_payload["image_url"] = img_url
                resp = requests.post(self.api_url, headers=headers, data=data_payload, timeout=30)
            else:
                with open(source_path, "rb") as f_in:
                    files_payload = {"image_file": f_in}
                    resp = requests.post(self.api_url, headers=headers, files=files_payload, data=data_payload, timeout=30)

            if resp.status_code == 200:
                with open(out_filepath, "wb") as f_out:
                    f_out.write(resp.content)

                print(f"[Remove.bg ✅] Success! Saved to: {out_filepath}")

                if auto_open and os.name == "nt":
                    try:
                        os.startfile(out_filepath)
                    except Exception:
                        pass

                color_desc = f"with {bg_color} background" if color_val else "transparent PNG"
                msg = f"Done {u_name}! Image ka background successfully remove karke {color_desc} ready kar diya hai. File saved at `{out_filepath}`."
                try:
                    from cwa_agent.core.ignore_words import ignore_words_manager
                    from cwa_agent.core.speaker import speaker
                    msg = ignore_words_manager.filter_and_replace_text(msg, persona=getattr(speaker, 'persona', 'CWA'))
                except Exception:
                    pass

                return (True, out_filepath, msg)

            elif resp.status_code == 402:
                err_msg = f"{u_name}, Remove.bg account credits khatam ho gaye hain (Payment/Plan required)."
                return (False, "", err_msg)
            elif resp.status_code == 403:
                err_msg = f"{u_name}, Remove.bg API key invalid ya unauthorized hai. Kripya check karein."
                return (False, "", err_msg)
            else:
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("errors", [{}])[0].get("title", resp.text)
                except Exception:
                    err_detail = resp.text[:120]
                return (False, "", f"Remove.bg API Error ({resp.status_code}): {err_detail}")

        except requests.exceptions.RequestException as e:
            return (False, "", f"Network error contacting Remove.bg API: {e}")
        except Exception as ex:
            return (False, "", f"Failed to process background removal: {ex}")


# Global Singleton Instance
bg_remover = BackgroundRemover()
