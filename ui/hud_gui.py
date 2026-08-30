import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import threading
import math
import time
import datetime
import random
import re
import psutil
from PIL import Image, ImageTk, ImageDraw, ImageFont
from cwa_agent.core.speaker import speaker
from cwa_agent.config import DOWNLOADS_DIR

# Universal Unicode Emoji Regex pattern supporting ALL Unicode emoji standards:
# - All Planes (0x1F300 to 0x1FAFF, 0x1F000 to 0x1F2FF, Dingbats, Misc Symbols)
# - ZWJ (Zero Width Joiner) composite sequences (e.g. 🧑🏽‍💻, 🫱🏼‍🫲🏾)
# - Fitzpatrick Skin Tone modifiers (0x1F3FB to 0x1F3FF)
# - Country flags (Regional Indicator Pairs 0x1F1E6 to 0x1F1FF)
# - Variation Selectors & Keycaps (❤️, #️⃣, 1️⃣)
EMOJI_REGEX = re.compile(
    r'('
    r'[\U0001F1E6-\U0001F1FF]{2}'
    r'|[0-9#*]\uFE0F?\u20E3'
    r'|(?:[\U0001F300-\U0001FAFF]|[\U0001F000-\U0001F2FF]|[\u2600-\u27BF]|[\u2300-\u23FF]|\u2B50|\u2B55|\u203C|\u2049|\u00A9|\u00AE)'
    r'(?:[\U0001F3FB-\U0001F3FF]|\uFE0E|\uFE0F)*'
    r'(?:\u200D(?:[\U0001F300-\U0001FAFF]|[\U0001F000-\U0001F2FF]|[\u2600-\u27BF]|[\u2300-\u23FF]|\u2B50|\u2B55|\u203C|\u2049|\u00A9|\u00AE)(?:[\U0001F3FB-\U0001F3FF]|\uFE0E|\uFE0F)*)*'
    r')',
    flags=re.UNICODE
)

class JarvisIronManHologram(tk.Canvas):
    """
    Animated GIF Avatar for the CWA HUD center panel.
    Loads agent.gif from the project root and loops it frame-by-frame.
    Overlays dynamic state text, dynamic emotion matrix pill, persona-aware subtitle, and mic pill button.
    """
    EMOTION_PALETTES = {
        "HAPPY": {"neon": "#10b981", "bright": "#6ee7b7", "icon": "😊", "bg": "#064e3b", "label": "HAPPY // JOYFUL"},
        "EXCITED": {"neon": "#f59e0b", "bright": "#fde68a", "icon": "⚡", "bg": "#78350f", "label": "EXCITED // ENERGIZED"},
        "SAD": {"neon": "#6366f1", "bright": "#a5b4fc", "icon": "🥺", "bg": "#312e81", "label": "SAD // EMPATHETIC"},
        "EMPATHETIC": {"neon": "#38bdf8", "bright": "#bae6fd", "icon": "💙", "bg": "#075985", "label": "EMPATHETIC // COMPASSION"},
        "ANGRY": {"neon": "#ef4444", "bright": "#fca5a5", "icon": "😠", "bg": "#7f1d1d", "label": "ANGRY // HIGH ALERT"},
        "WITTY": {"neon": "#a855f7", "bright": "#e9d5ff", "icon": "😏", "bg": "#581c87", "label": "WITTY // SARCASTIC"},
        "SURPRISED": {"neon": "#ec4899", "bright": "#fbcfe8", "icon": "😲", "bg": "#831843", "label": "SURPRISED // CURIOUS"},
        "CARING": {"neon": "#f43f5e", "bright": "#fecdd3", "icon": "💖", "bg": "#881337", "label": "CARING // WARMTH"},
        "CALM": {"neon": "#00f0ff", "bright": "#67e8f9", "icon": "🤖", "bg": "#0c2340", "label": "CALM // BALANCED"}
    }

    def __init__(self, parent, width=390, height=450, on_mic_click=None, **kwargs):
        super().__init__(parent, width=width, height=height, bg="#01040a", highlightthickness=0, **kwargs)
        self.w = width
        self.h = height
        self.cx = width // 2
        self.on_mic_click = on_mic_click
        self.state = "IDLE"
        self.emotion = "CALM"
        self.intensity = 50
        self.emoji = ""
        self.emotion_reason = "balanced baseline"
        self._running = True
        self._frames = []
        self._frame_idx = 0
        self._is_mj_mode = False
        self._mj_photo = None
        self._mj_frames = []       # mp4 video frames
        self._mj_frame_idx = 0
        self._glow_phase = 0.0     # for pulsating glow animation

        # Resolve paths dynamically — same dir as run_cwa.py / project root
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        gif_path = os.path.join(base_dir, "agent.gif")
        if not os.path.exists(gif_path):
            gif_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "agent.gif")

        # Resolve mj.png & mj.mp4 from same candidate dirs
        mj_candidates = [
            os.path.join(base_dir, "mj.png"),
            os.path.join(base_dir, "cwa_agent", "mj.png"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mj.png"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mj.png"),
        ]
        mj_path = next((p for p in mj_candidates if os.path.exists(p)), None)
        self._load_mj_image(mj_path, width, height)

        # Try mp4 video in same dir as png (same name, different ext)
        if mj_path:
            mp4_path = mj_path.replace(".png", ".mp4")
            if os.path.exists(mp4_path):
                self._load_mj_video(mp4_path, width, height)

        self._load_gif(gif_path, width, height)
        self.bind("<Button-1>", self._on_canvas_click)
        self.after(40, self._animate)

    def _load_gif(self, path, w, h):
        """Load all GIF frames and loop them forward as-is."""
        try:
            gif = Image.open(path)
            n = getattr(gif, "n_frames", 1)
            for i in range(n):
                gif.seek(i)
                frame = gif.copy().convert("RGBA").resize((w, h), Image.BILINEAR)
                self._frames.append(ImageTk.PhotoImage(frame))
        except Exception as e:
            print(f"[HUD] agent.gif load error: {e}")

    def _load_mj_image(self, path, w, h):
        """Load mj.png using cover-crop: scale to fill canvas while maintaining
        aspect ratio, then center-crop to fit exactly. No stretching."""
        if not path:
            print("[HUD] mj.png not found — MJ mode will use text-only avatar.")
            return
        try:
            img = Image.open(path).convert("RGBA")
            img_w, img_h = img.size

            # Scale factor: fill canvas (cover mode — like CSS background-size: cover)
            scale = max(w / img_w, h / img_h)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)

            # Center-crop to exact canvas size
            left = (new_w - w) // 2
            top  = (new_h - h) // 2
            img  = img.crop((left, top, left + w, top + h))

            self._mj_photo = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"[HUD] mj.png load error: {e}")

    def _load_mj_video(self, path, w, h):
        """Load mj.mp4 frames for animated avatar loop. Skips frames to limit RAM."""
        try:
            import cv2
            cap = cv2.VideoCapture(path)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 9999
            # Keep max 90 frames to stay memory-friendly
            skip = max(1, total // 90)
            idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if idx % skip == 0:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(frame_rgb).convert("RGBA")
                    img_w, img_h = pil_img.size
                    scale = max(w / img_w, h / img_h)
                    nw, nh = int(img_w * scale), int(img_h * scale)
                    pil_img = pil_img.resize((nw, nh), Image.BILINEAR)
                    left = (nw - w) // 2
                    top  = (nh - h) // 2
                    pil_img = pil_img.crop((left, top, left + w, top + h))
                    self._mj_frames.append(ImageTk.PhotoImage(pil_img))
                idx += 1
            cap.release()
            print(f"[HUD] MJ video avatar: {len(self._mj_frames)} frames loaded")
        except Exception as e:
            print(f"[HUD] mj.mp4 load error: {e}")

    def set_persona_mode(self, is_mj: bool):
        """Called by CWAHUD when persona switches; toggles avatar image."""
        self._is_mj_mode = is_mj
        self._mj_frame_idx = 0  # restart video loop on switch

    def set_state(self, new_state: str):
        state_clean = new_state.upper()
        if self.state != state_clean:
            self.state = state_clean

    def set_emotion(self, emotion: str, intensity: int = 50, reason: str = "", emoji_char: str = ""):
        self.emotion = emotion.upper().strip() if emotion else "CALM"
        self.intensity = max(0, min(100, intensity))
        self.emoji = emoji_char.strip() if emoji_char else ""
        self.emotion_reason = reason.strip() if reason else "neural perception"

    def _on_canvas_click(self, event):
        btn_y = self.h - 26
        if abs(event.x - self.cx) <= 115 and abs(event.y - btn_y) <= 16:
            if self.on_mic_click:
                self.on_mic_click()

    def _animate(self):
        if not self._running:
            return

        self.delete("all")

        # Draw current avatar frame — MJ video/image or animated JARVIS GIF
        if self._is_mj_mode:
            if self._mj_frames:
                # Animated mp4 video loop
                self.create_image(0, 0, anchor="nw", image=self._mj_frames[self._mj_frame_idx])
                self._mj_frame_idx = (self._mj_frame_idx + 1) % len(self._mj_frames)
            elif self._mj_photo:
                # Static PNG fallback
                self.create_image(0, 0, anchor="nw", image=self._mj_photo)
        elif self._frames:
            self.create_image(0, 0, anchor="nw", image=self._frames[self._frame_idx])
            self._frame_idx = (self._frame_idx + 1) % len(self._frames)

        # Get emotion palette
        emo_palette = self.EMOTION_PALETTES.get(self.emotion, self.EMOTION_PALETTES["CALM"])
        is_mj = (getattr(speaker, 'persona', 'CWA') == 'MJ')
        active_icon = self.emoji if self.emoji else emo_palette["icon"]

        # --- Top Hologram Dynamic Mood Matrix Pill ---
        mood_y = 22
        pill_w, pill_h = 135, 12
        pill_bg = emo_palette["bg"]
        pill_neon = emo_palette["neon"]
        self.create_oval(self.cx - pill_w, mood_y - pill_h, self.cx - pill_w + 24, mood_y + pill_h, fill=pill_bg, outline=pill_neon, width=1)
        self.create_oval(self.cx + pill_w - 24, mood_y - pill_h, self.cx + pill_w, mood_y + pill_h, fill=pill_bg, outline=pill_neon, width=1)
        self.create_rectangle(self.cx - pill_w + 12, mood_y - pill_h, self.cx + pill_w - 12, mood_y + pill_h, fill=pill_bg, outline=pill_neon, width=1)
        
        mood_text = f"{active_icon} MOOD: {self.emotion} ({self.intensity}%)"
        self.create_text(self.cx, mood_y, text=mood_text, fill=emo_palette["bright"], font=("Consolas", 8, "bold"))

        # --- Persona & state-based overlay text ---
        if is_mj:
            c_neon   = "#ff007f" if self.emotion == "CALM" else emo_palette["neon"]
            c_bright = "#f472b6" if self.emotion == "CALM" else emo_palette["bright"]
            persona_title = "M  J"
            default_sub   = f"I'm MJ. Feeling {self.emotion.lower()} & standing by."
        else:
            c_neon   = "#00f0ff" if self.emotion == "CALM" else emo_palette["neon"]
            c_bright = "#67e8f9" if self.emotion == "CALM" else emo_palette["bright"]
            persona_title = "J  A  R  V  I  S"
            default_sub   = f"JARVIS active. Emotional matrix: {self.emotion.lower()}."

        # State overrides
        if self.state == "LISTENING":
            c_neon   = "#10b981"
            c_bright = "#6ee7b7"
            sub_text = "● LISTENING TO YOUR VOICE... SPEAK NOW"
            btn_text = "🎙️ Listening to you..."
            btn_bg   = "#065f46"
        elif self.state == "THINKING":
            c_neon   = "#f59e0b"
            c_bright = "#fde68a"
            sub_text = f"● REASONING & SYNTHESIZING ({self.emotion})..."
            btn_text = "⚡ Processing command..."
            btn_bg   = "#78350f"
        elif self.state == "SPEAKING":
            sub_text = f"● TRANSMITTING [{self.emotion} // {self.intensity}%]"
            btn_text = "🔊 Speaking to you..."
            btn_bg   = "#1e3a8a" if not is_mj else "#831843"
        elif self.state == "VISION":
            c_neon   = "#ec4899"
            c_bright = "#f472b6"
            sub_text = "● OPTICAL VISION & ANALYSIS ACTIVE"
            btn_text = "👁️ Vision analysis..."
            btn_bg   = "#701a75"
        else:
            sub_text = default_sub
            btn_text = "🎙️ Click here to speak"
            btn_bg   = "#1e293b"

        # --- Lip-sync animation overlay when MJ is speaking ---
        if is_mj and self.state == "SPEAKING":
            self._draw_lip_sync(c_neon)

        # --- Persona title + subtitle (bottom overlay) ---
        text_y = self.h - 94
        self.create_text(self.cx + 1, text_y + 1, text=persona_title, fill="#000000", font=("Consolas", 18, "bold"))
        self.create_text(self.cx, text_y, text=persona_title, fill=c_neon, font=("Consolas", 18, "bold"))

        self.create_text(self.cx + 1, text_y + 25, text=sub_text, fill="#000000", font=("Consolas", 8))
        self.create_text(self.cx, text_y + 24, text=sub_text, fill=c_bright, font=("Consolas", 8))

        # --- Glowing pill mic button ---
        btn_y  = self.h - 26
        btn_w, btn_h = 110, 14
        self.create_oval(self.cx - btn_w, btn_y - btn_h, self.cx - btn_w + 28, btn_y + btn_h, fill=btn_bg, outline=c_neon, width=1)
        self.create_oval(self.cx + btn_w - 28, btn_y - btn_h, self.cx + btn_w, btn_y + btn_h, fill=btn_bg, outline=c_neon, width=1)
        self.create_rectangle(self.cx - btn_w + 14, btn_y - btn_h, self.cx + btn_w - 14, btn_y + btn_h, fill=btn_bg, outline=c_neon, width=1)
        self.create_text(self.cx, btn_y, text=btn_text,
                         fill="#ffffff" if self.state != "IDLE" else "#cbd5e1",
                         font=("Consolas", 8, "bold"))

        self.after(85, self._animate)

    def _draw_lip_sync(self, color):
        """Animated talking wave overlay near MJ's mouth area when speaking."""
        t = time.time()
        cx = self.cx
        lip_y = int(self.h * 0.62)   # approximate mouth region
        bar_count = 9
        bar_w = 5
        spacing = 7
        total_w = bar_count * (bar_w + spacing)
        start_x = cx - total_w // 2
        for i in range(bar_count):
            amp = 3 + int(9 * abs(math.sin(t * 10 + i * 0.7)))
            x = start_x + i * (bar_w + spacing)
            self.create_rectangle(
                x, lip_y - amp, x + bar_w, lip_y + amp,
                fill=color, outline=""
            )

    def destroy(self):
        self._running = False
        super().destroy()


class LiveWaveformGraph(tk.Canvas):
    """Live Fluctuating Sci-Fi Waveform & Audio Spectrum Bar with dynamic color adaptation"""
    def __init__(self, parent, width=330, height=75, color="#00f0ff", **kwargs):
        super().__init__(parent, width=width, height=height, bg="#030814", highlightthickness=0, **kwargs)
        self.w = width
        self.h = height
        self.color = color
        self.history = [30 + random.randint(-15, 15) for _ in range(35)]
        self._running = True
        self.after(140, self._update_graph)

    def set_color(self, new_color: str):
        """Dynamically updates waveform accent glow color according to emotions."""
        self.color = new_color

    def _update_graph(self):
        if not self._running:
            return
        self.delete("all")
        
        # Grid lines
        for y in range(15, self.h, 20):
            self.create_line(0, y, self.w, y, fill="#091b2e", width=1, dash=(2, 4))
        for x in range(0, self.w, 30):
            self.create_line(x, 0, x, self.h, fill="#091b2e", width=1, dash=(2, 4))

        # Add new point with smooth noise
        new_val = 35 + math.sin(time.time() * 4) * 20 + random.randint(-8, 8)
        new_val = max(10, min(self.h - 10, new_val))
        self.history.pop(0)
        self.history.append(new_val)

        step = self.w / (len(self.history) - 1)
        coords = []
        for i, val in enumerate(self.history):
            x = i * step
            y = self.h - val
            coords.extend([x, y])
            # Draw vertical visualizer bar
            self.create_line(x, self.h, x, y, fill="#072b4a", width=3)

        if len(coords) >= 4:
            self.create_line(coords, fill=self.color, width=2, smooth=True)

        self.after(140, self._update_graph)

    def destroy(self):
        self._running = False
        super().destroy()


class CWAHUD(tk.Tk):
    def __init__(self, on_user_query=None, on_mic_toggle=None, on_vision_trigger=None, on_always_listen_toggle=None, on_persona_switch=None):
        super().__init__()
        self.title("JARVIS OS // STARK INDUSTRIES MARK-VII")
        self.geometry("1180x780")
        self.configure(bg="#01040a")
        self.minsize(1050, 680)

        self.on_user_query = on_user_query
        self.on_mic_toggle = on_mic_toggle
        self.on_vision_trigger = on_vision_trigger
        self.on_always_listen_toggle = on_always_listen_toggle
        self.on_persona_switch = on_persona_switch

        self.voice_output_enabled = tk.BooleanVar(value=True)
        # Always listen is ACTIVE by default for seamless hands-free room intelligence
        self.always_listen_enabled = tk.BooleanVar(value=True)
        self.current_persona = tk.StringVar(value=getattr(speaker, 'persona', 'CWA'))
        self.is_dark_theme = True

        # Dynamic Full-Color Emoji Rendering Engine (Pillow Embedded Color)
        self._emoji_cache = {}
        self._emoji_font = None
        self._init_emoji_engine()

        self._build_stark_hud()
        self._start_clock_and_telemetry()

    def _init_emoji_engine(self):
        """Loads the Windows Segoe UI Emoji font dynamically for full-color rendering."""
        font_candidates = [
            os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', 'seguiemj.ttf'),
            r"C:\Windows\Fonts\seguiemj.ttf",
            r"C:\Windows\Fonts\seguisym.ttf"
        ]
        for fp in font_candidates:
            if os.path.exists(fp):
                try:
                    self._emoji_font = ImageFont.truetype(fp, 18)
                    break
                except Exception:
                    pass

    def _get_emoji_photo(self, emoji_char: str):
        """Renders any emoji (single or complex multi-char sequence) into a full-color PhotoImage with dynamic bounding box."""
        if emoji_char in self._emoji_cache:
            return self._emoji_cache[emoji_char]
        if not self._emoji_font:
            return None
        try:
            bbox = self._emoji_font.getbbox(emoji_char)
            w = max(22, (bbox[2] - bbox[0]) + 4) if bbox else 22
            h = max(22, (bbox[3] - bbox[1]) + 4) if bbox else 22
            img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.text((1, 1), emoji_char, font=self._emoji_font, embedded_color=True)
            photo = ImageTk.PhotoImage(img)
            self._emoji_cache[emoji_char] = photo
            return photo
        except Exception:
            return None

    def _insert_rich_text(self, text: str, tag: str = None):
        """Inserts text into log_text, rendering any Unicode emojis as vibrant full-color inline images."""
        if not text:
            return
        tokens = EMOJI_REGEX.split(text)
        for tok in tokens:
            if not tok:
                continue
            if EMOJI_REGEX.fullmatch(tok):
                photo = self._get_emoji_photo(tok)
                if photo:
                    self.log_text.image_create(tk.END, image=photo)
                    continue
            if tag:
                self.log_text.insert(tk.END, tok, tag)
            else:
                self.log_text.insert(tk.END, tok)

    def _build_stark_hud(self):
        # --- 1. TOP STARK SCI-FI STATUS BAR ---
        top_bar = tk.Frame(self, bg="#040b17", height=50, bd=1, relief="solid")
        top_bar.pack(fill="x", side="top")

        # Top Left: Stark Industries Header
        tl_frame = tk.Frame(top_bar, bg="#040b17")
        tl_frame.pack(side="left", padx=15, pady=6)

        logo_lbl = tk.Label(tl_frame, text="STARK INDUSTRIES // JARVIS OS v7.2", fg="#00f0ff", bg="#040b17", font=("Consolas", 12, "bold"))
        logo_lbl.pack(side="left")

        sub_tag = tk.Label(tl_frame, text="[SECURE AI QUANTUM CORE]", fg="#94a3b8", bg="#0e1f38", font=("Consolas", 8, "bold"), padx=6, pady=2)
        sub_tag.pack(side="left", padx=10)

        # Top Right: Live Clock & Location Telemetry
        tr_frame = tk.Frame(top_bar, bg="#040b17")
        tr_frame.pack(side="right", padx=15)

        self.emotion_lbl = tk.Label(tr_frame, text="MOOD: 🤖 CALM (50%)", fg="#00f0ff", bg="#040b17", font=("Consolas", 9, "bold"))
        self.emotion_lbl.pack(side="left", padx=10)

        self.weather_lbl = tk.Label(tr_frame, text="30°C // FAIR  |  SYS: 100%", fg="#38bdf8", bg="#040b17", font=("Consolas", 9, "bold"))
        self.weather_lbl.pack(side="left", padx=12)

        self.clock_lbl = tk.Label(tr_frame, text="--:--:--", fg="#00ffcc", bg="#040b17", font=("Consolas", 12, "bold"))
        self.clock_lbl.pack(side="left", padx=8)

        # --- 2. MAIN WORKSPACE CONTAINER (3-COLUMN SCI-FI LAYOUT) ---
        main_work = tk.Frame(self, bg="#01040a")
        main_work.pack(fill="both", expand=True, padx=10, pady=8)

        # === COLUMN 1: LEFT TELEMETRY & CONTROLS DECK ===
        col_left = tk.Frame(main_work, bg="#030814", width=350, bd=1, relief="solid", highlightbackground="#0c2340", highlightthickness=1)
        col_left.pack(side="left", fill="both", padx=(0, 6))

        # Avatar Switcher (CWA vs MJ)
        avatar_frame = tk.Frame(col_left, bg="#061224", padx=8, pady=6)
        avatar_frame.pack(fill="x", padx=8, pady=6)

        tk.Label(avatar_frame, text="NEURAL AVATAR:", fg="#94a3b8", bg="#061224", font=("Consolas", 8, "bold")).pack(side="left", padx=4)
        
        self.cwa_btn = tk.Button(avatar_frame, text="👨 CWA (Male)", bg="#0284c7", fg="#ffffff", font=("Consolas", 8, "bold"), bd=0, padx=6, pady=3,
                                 command=lambda: self._select_persona("CWA"))
        self.cwa_btn.pack(side="left", padx=3)

        self.mj_btn = tk.Button(avatar_frame, text="👩 MJ (Female)", bg="#1e293b", fg="#f472b6", font=("Consolas", 8, "bold"), bd=0, padx=6, pady=3,
                                command=lambda: self._select_persona("MJ"))
        self.mj_btn.pack(side="left", padx=3)

        # Live Waveform Graph 1: Audio Spectrum
        tk.Label(col_left, text="[ AUDIO NEURAL FREQUENCY SPECTRUM ]", fg="#38bdf8", bg="#030814", font=("Consolas", 8, "bold")).pack(anchor="w", padx=10, pady=(6, 2))
        self.audio_graph = LiveWaveformGraph(col_left, width=330, height=60, color="#00f0ff")
        self.audio_graph.pack(fill="x", padx=10)

        # Live Waveform Graph 2: CPU Core Stream
        tk.Label(col_left, text="[ CPU PROCESSOR ACTIVITY & CORE LOAD ]", fg="#a855f7", bg="#030814", font=("Consolas", 8, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.cpu_graph = LiveWaveformGraph(col_left, width=330, height=60, color="#a855f7")
        self.cpu_graph.pack(fill="x", padx=10)

        # Hardware Metrics Grid
        metrics_box = tk.Frame(col_left, bg="#061224", bd=1, relief="ridge")
        metrics_box.pack(fill="x", padx=10, pady=8)

        self.cpu_stat = tk.Label(metrics_box, text="CPU: 0%", fg="#38bdf8", bg="#061224", font=("Consolas", 8, "bold"))
        self.cpu_stat.pack(side="left", expand=True, pady=5)

        self.ram_stat = tk.Label(metrics_box, text="RAM: 0%", fg="#f472b6", bg="#061224", font=("Consolas", 8, "bold"))
        self.ram_stat.pack(side="left", expand=True, pady=5)

        self.pwr_stat = tk.Label(metrics_box, text="PWR: 100%", fg="#34d399", bg="#061224", font=("Consolas", 8, "bold"))
        self.pwr_stat.pack(side="left", expand=True, pady=5)

        # Controls Buttons Deck
        ctrl_box = tk.Frame(col_left, bg="#030814")
        ctrl_box.pack(fill="x", padx=10, pady=4)

        # Manual Mic button made big and primary
        self.mic_btn = tk.Button(ctrl_box, text="🎙️ CLICK TO SPEAK (Voice Command)", bg="#0284c7", fg="#ffffff", activebackground="#0369a1",
                                 activeforeground="#ffffff", font=("Consolas", 10, "bold"), bd=1, relief="ridge", pady=7,
                                 command=self._handle_mic)
        self.mic_btn.pack(fill="x", pady=3)

        row_btns = tk.Frame(ctrl_box, bg="#030814")
        row_btns.pack(fill="x", pady=2)

        self.always_listen_btn = tk.Button(row_btns, text="⚡ AUTO-LISTEN: ACTIVE", bg="#065f46", fg="#10b981",
                                           activebackground="#065f46", activeforeground="#ffffff",
                                           font=("Consolas", 8, "bold"), bd=1, relief="ridge", pady=5,
                                           command=self._toggle_always_listen)
        self.always_listen_btn.pack(side="left", fill="x", expand=True, padx=(0, 2))


        self.vision_btn = tk.Button(row_btns, text="👁️ CAMERA SIGHT", bg="#2a0845", fg="#e879f9", activebackground="#7e22ce",
                                    activeforeground="#ffffff", font=("Consolas", 8, "bold"), bd=1, relief="groove", pady=5,
                                    command=self._handle_vision)
        self.vision_btn.pack(side="right", fill="x", expand=True, padx=(2, 0))

        voice_chk = tk.Checkbutton(ctrl_box, text="🔊 Vocal Audio Output (TTS)", variable=self.voice_output_enabled,
                                   bg="#030814", fg="#94a3b8", selectcolor="#01040a", activebackground="#030814",
                                   activeforeground="#00f0ff", font=("Consolas", 8))
        voice_chk.pack(anchor="w", pady=2)

        util_row = tk.Frame(ctrl_box, bg="#030814")
        util_row.pack(fill="x", pady=2)

        self.key_btn = tk.Button(util_row, text="⚙️ SET API KEY", bg="#1e293b", fg="#cbd5e1", font=("Consolas", 8), bd=0, pady=3,
                                 command=self._set_api_key_dialog)
        self.key_btn.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self.droid_btn = tk.Button(util_row, text="📷 DROIDCAM SETUP", bg="#312e81", fg="#c7d2fe", font=("Consolas", 8, "bold"), bd=0, pady=3,
                                   command=self._droidcam_setup_dialog)
        self.droid_btn.pack(side="left", fill="x", expand=True, padx=(2, 2))

        self.theme_btn = tk.Button(util_row, text="☀️ LIGHT MODE", bg="#1e293b", fg="#fbbf24", font=("Consolas", 8, "bold"), bd=0, pady=3,
                                   command=self._toggle_theme)
        self.theme_btn.pack(side="left", fill="x", expand=True, padx=(2, 2))

        clear_btn = tk.Button(util_row, text="🧹 CLEAR", bg="#1e293b", fg="#cbd5e1", font=("Consolas", 8), bd=0, pady=3,
                              command=self._clear_logs)
        clear_btn.pack(side="right", fill="x", expand=True, padx=(2, 0))

        # Telegram Phone Remote Control Bridge Button
        self.tele_btn = tk.Button(ctrl_box, text="📱 TELEGRAM REMOTE BRIDGE", bg="#0c4a6e", fg="#38bdf8",
                                  activebackground="#0369a1", activeforeground="#ffffff",
                                  font=("Consolas", 8, "bold"), bd=1, relief="groove", pady=4,
                                  command=self._telegram_bridge_dialog)
        self.tele_btn.pack(fill="x", pady=(3, 1))

        # GPS Route & Destination Navigator Button
        self.nav_btn = tk.Button(ctrl_box, text="🗺️ DESTINATION & ROUTE NAVIGATOR", bg="#065f46", fg="#34d399",
                                 activebackground="#047857", activeforeground="#ffffff",
                                 font=("Consolas", 8, "bold"), bd=1, relief="groove", pady=4,
                                 command=self._show_route_navigator_dialog)
        self.nav_btn.pack(fill="x", pady=(1, 1))

        # Rebuild / Update App Button
        self.update_btn = tk.Button(ctrl_box, text="REBUILD / UPDATE APP (.EXE)", bg="#1e1b4b", fg="#a5b4fc",
                                    activebackground="#312e81", activeforeground="#ffffff",
                                    font=("Consolas", 8, "bold"), bd=1, relief="groove", pady=4,
                                    command=self._trigger_app_rebuild)
        self.update_btn.pack(fill="x", pady=(1, 1))

        # --- Live Media Download Matrix Deck ---
        dl_deck = tk.Frame(col_left, bg="#030814")
        dl_deck.pack(fill="x", padx=10, pady=(6, 2))

        tk.Label(dl_deck, text="[ LIVE MEDIA DOWNLOAD PROGRESS ]", fg="#38bdf8", bg="#030814", font=("Consolas", 8, "bold")).pack(anchor="w", pady=(0, 2))

        self.dl_card = tk.Frame(dl_deck, bg="#061224", bd=1, relief="ridge", padx=8, pady=6)
        self.dl_card.pack(fill="x")

        self.dl_title_lbl = tk.Label(self.dl_card, text="● READY FOR MEDIA DOWNLOADS", fg="#64748b", bg="#061224", font=("Consolas", 8, "bold"), anchor="w")
        self.dl_title_lbl.pack(fill="x")

        # Progress bar canvas (neon glowing bar)
        self.dl_canvas = tk.Canvas(self.dl_card, height=12, bg="#0a192f", highlightthickness=0)
        self.dl_canvas.pack(fill="x", pady=4)

        # Stats row (Percent, Speed, Size, ETA)
        stats_row = tk.Frame(self.dl_card, bg="#061224")
        stats_row.pack(fill="x")

        self.dl_pct_lbl = tk.Label(stats_row, text="0.0%", fg="#00ffcc", bg="#061224", font=("Consolas", 8, "bold"))
        self.dl_pct_lbl.pack(side="left")

        self.dl_info_lbl = tk.Label(stats_row, text="Speed: -- | Size: --", fg="#94a3b8", bg="#061224", font=("Consolas", 7), anchor="e")
        self.dl_info_lbl.pack(side="right")

        # Open Downloads Folder button
        self.dl_open_btn = tk.Button(self.dl_card, text="📂 OPEN DOWNLOADS FOLDER", bg="#0c4a6e", fg="#7dd3fc", font=("Consolas", 7, "bold"), bd=0, pady=3,
                                     command=lambda: os.startfile(str(DOWNLOADS_DIR)) if os.path.exists(str(DOWNLOADS_DIR)) else None)
        self.dl_open_btn.pack(fill="x", pady=(4, 0))

        # --- Live System & App Notification Sentry Deck (Right below Media Download) ---
        notif_deck = tk.Frame(col_left, bg="#030814")
        notif_deck.pack(fill="x", padx=10, pady=(6, 2))

        tk.Label(notif_deck, text="[ 🔔 LIVE NOTIFICATION SENTRY ]", fg="#f59e0b", bg="#030814", font=("Consolas", 8, "bold")).pack(anchor="w", pady=(0, 2))

        self.notif_card = tk.Frame(notif_deck, bg="#061224", bd=1, relief="ridge", padx=8, pady=6, highlightbackground="#0284c7", highlightthickness=1)
        self.notif_card.pack(fill="x")

        # Top line: App Badge & Time
        notif_top_row = tk.Frame(self.notif_card, bg="#061224")
        notif_top_row.pack(fill="x")

        self.notif_app_lbl = tk.Label(notif_top_row, text="● SENTRY ACTIVE // STANDBY", fg="#10b981", bg="#061224", font=("Consolas", 8, "bold"), anchor="w")
        self.notif_app_lbl.pack(side="left")

        self.notif_time_lbl = tk.Label(notif_top_row, text="", fg="#64748b", bg="#061224", font=("Consolas", 7))
        self.notif_time_lbl.pack(side="right")

        # Title / Sender
        self.notif_title_lbl = tk.Label(self.notif_card, text="No active notifications", fg="#64748b", bg="#061224", font=("Consolas", 8, "bold"), anchor="w", wraplength=230, justify="left")
        self.notif_title_lbl.pack(fill="x", pady=(2, 1))

        # Body Message Text
        self.notif_body_lbl = tk.Label(self.notif_card, text="Listening for all incoming system & app alerts...", fg="#475569", bg="#061224", font=("Consolas", 7), anchor="w", wraplength=230, justify="left")
        self.notif_body_lbl.pack(fill="x", pady=(0, 4))

        # Action Buttons Row: [ ⚡ OPEN APP ] and [ ❌ DISMISS ]
        self.notif_btn_row = tk.Frame(self.notif_card, bg="#061224")
        self.notif_btn_row.pack(fill="x", pady=(2, 0))

        self.notif_open_btn = tk.Button(self.notif_btn_row, text="⚡ OPEN APP", bg="#0c2340", fg="#475569", activebackground="#0369a1",
                                        activeforeground="#ffffff", font=("Consolas", 8, "bold"), bd=0, pady=3,
                                        command=self._on_notif_open_click, state="disabled")
        self.notif_open_btn.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self.notif_close_btn = tk.Button(self.notif_btn_row, text="❌ DISMISS", bg="#0c2340", fg="#475569", activebackground="#334155",
                                         activeforeground="#ffffff", font=("Consolas", 8), bd=0, pady=3,
                                         command=self._on_notif_dismiss_click, state="disabled")
        self.notif_close_btn.pack(side="right", fill="x", expand=True, padx=(2, 0))

        # --- Quantum Tic-Tac-Toe Neural Gaming Arena Deck ---
        ttt_deck = tk.Frame(col_left, bg="#030814")
        ttt_deck.pack(fill="x", padx=10, pady=(6, 4))

        # Collapsible Header Bar
        ttt_head_bar = tk.Frame(ttt_deck, bg="#030814")
        ttt_head_bar.pack(fill="x", pady=(0, 2))

        tk.Label(ttt_head_bar, text="[ 🎮 TIC-TAC-TOE // ALI vs CWA ]", fg="#00f0ff", bg="#030814", font=("Consolas", 8, "bold")).pack(side="left")

        self.ttt_is_expanded = False
        self.ttt_toggle_btn = tk.Button(ttt_head_bar, text="▼ OPEN GAME", bg="#1e293b", fg="#94a3b8", activebackground="#0284c7", activeforeground="#ffffff",
                                        font=("Consolas", 7, "bold"), bd=0, padx=6, pady=1,
                                        command=self._toggle_ttt_panel)
        self.ttt_toggle_btn.pack(side="right")

        self.ttt_card = tk.Frame(ttt_deck, bg="#061224", bd=1, relief="ridge", padx=6, pady=4, highlightbackground="#0284c7", highlightthickness=1)
        # Hidden by default — user must click OPEN GAME to expand

        # Top line: Status & Scoreboard
        ttt_top = tk.Frame(self.ttt_card, bg="#061224")
        ttt_top.pack(fill="x", pady=(0, 3))

        self.ttt_status_lbl = tk.Label(ttt_top, text="● YOUR TURN (X)", fg="#10b981", bg="#061224", font=("Consolas", 8, "bold"))
        self.ttt_status_lbl.pack(side="left")

        self.ttt_score_lbl = tk.Label(ttt_top, text="ALI: 0 | CWA: 0 | D: 0", fg="#fbbf24", bg="#061224", font=("Consolas", 7, "bold"))
        self.ttt_score_lbl.pack(side="right")

        # 3x3 Grid of Buttons
        grid_frame = tk.Frame(self.ttt_card, bg="#061224")
        grid_frame.pack(pady=2)

        self.ttt_buttons = []
        for r in range(3):
            row_frame = tk.Frame(grid_frame, bg="#061224")
            row_frame.pack()
            for c in range(3):
                idx = r * 3 + c
                btn = tk.Button(
                    row_frame,
                    text=" ",
                    font=("Consolas", 11, "bold"),
                    width=4,
                    height=1,
                    bg="#0a192f",
                    fg="#00f0ff",
                    activebackground="#0c2340",
                    activeforeground="#38bdf8",
                    bd=1,
                    relief="ridge",
                    command=lambda i=idx: self._on_ttt_cell_click(i)
                )
                btn.pack(side="left", padx=2, pady=2)
                self.ttt_buttons.append(btn)

        # Control Buttons: [ 🔄 NEW GAME ] [ 🤖 CWA FIRST ] [ 🧹 RESET ]
        ttt_ctrl = tk.Frame(self.ttt_card, bg="#061224")
        ttt_ctrl.pack(fill="x", pady=(3, 0))

        self.ttt_new_btn = tk.Button(ttt_ctrl, text="🔄 NEW", bg="#0c4a6e", fg="#38bdf8", font=("Consolas", 7, "bold"), bd=0, pady=2,
                                     command=self._on_ttt_new_game)
        self.ttt_new_btn.pack(side="left", fill="x", expand=True, padx=(0, 1))

        self.ttt_ai_start_btn = tk.Button(ttt_ctrl, text="🤖 CWA 1ST", bg="#1e1b4b", fg="#a5b4fc", font=("Consolas", 7, "bold"), bd=0, pady=2,
                                          command=self._on_ttt_ai_first)
        self.ttt_ai_start_btn.pack(side="left", fill="x", expand=True, padx=(1, 1))

        self.ttt_reset_btn = tk.Button(ttt_ctrl, text="🧹 RESET", bg="#1e293b", fg="#94a3b8", font=("Consolas", 7), bd=0, pady=2,
                                       command=self._on_ttt_reset_scores)
        self.ttt_reset_btn.pack(side="right", fill="x", expand=True, padx=(1, 0))

        # --- Smart Clipboard History Manager Deck (collapsed by default) ---
        clip_deck = tk.Frame(col_left, bg="#030814")
        clip_deck.pack(fill="x", padx=10, pady=(6, 2))

        clip_head_bar = tk.Frame(clip_deck, bg="#030814")
        clip_head_bar.pack(fill="x", pady=(0, 2))

        tk.Label(clip_head_bar, text="[ 📋 SMART CLIPBOARD MANAGER ]", fg="#a78bfa", bg="#030814", font=("Consolas", 8, "bold")).pack(side="left")

        self.clip_is_expanded = False
        self.clip_toggle_btn = tk.Button(clip_head_bar, text="▼ OPEN", bg="#0c4a6e", fg="#38bdf8",
                                         activebackground="#0284c7", activeforeground="#ffffff",
                                         font=("Consolas", 7, "bold"), bd=0, padx=6, pady=1,
                                         command=self._toggle_clipboard_panel)
        self.clip_toggle_btn.pack(side="right")

        self.clip_card = tk.Frame(clip_deck, bg="#0d0a1f", bd=1, relief="ridge", padx=6, pady=4,
                                   highlightbackground="#7c3aed", highlightthickness=1)
        # Hidden by default

        clip_top = tk.Frame(self.clip_card, bg="#0d0a1f")
        clip_top.pack(fill="x", pady=(0, 3))

        self.clip_status_lbl = tk.Label(clip_top, text="● MONITORING CLIPBOARD", fg="#a78bfa", bg="#0d0a1f", font=("Consolas", 8, "bold"))
        self.clip_status_lbl.pack(side="left")
        self.clip_count_lbl = tk.Label(clip_top, text="0 items", fg="#64748b", bg="#0d0a1f", font=("Consolas", 7))
        self.clip_count_lbl.pack(side="right")

        # Listbox for history (scrollable)
        clip_list_frame = tk.Frame(self.clip_card, bg="#0d0a1f")
        clip_list_frame.pack(fill="x")

        self.clip_listbox = tk.Listbox(clip_list_frame, bg="#070516", fg="#e2e8f0", selectbackground="#6d28d9",
                                        font=("Consolas", 8), bd=0, highlightthickness=0, height=5,
                                        exportselection=False)
        self.clip_listbox.pack(side="left", fill="x", expand=True)

        clip_scroll = tk.Scrollbar(clip_list_frame, orient="vertical", command=self.clip_listbox.yview)
        clip_scroll.pack(side="right", fill="y")
        self.clip_listbox.config(yscrollcommand=clip_scroll.set)

        # Clipboard action buttons
        clip_btn_row = tk.Frame(self.clip_card, bg="#0d0a1f")
        clip_btn_row.pack(fill="x", pady=(4, 0))

        self.clip_paste_btn = tk.Button(clip_btn_row, text="📋 COPY SELECTED", bg="#4c1d95", fg="#e9d5ff",
                                         activebackground="#6d28d9", activeforeground="#ffffff",
                                         font=("Consolas", 7, "bold"), bd=0, pady=3,
                                         command=self._on_clipboard_copy_selected)
        self.clip_paste_btn.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self.clip_clear_btn = tk.Button(clip_btn_row, text="🗑️ CLEAR ALL", bg="#1e293b", fg="#94a3b8",
                                         activebackground="#334155", activeforeground="#ffffff",
                                         font=("Consolas", 7), bd=0, pady=3,
                                         command=self._on_clipboard_clear)
        self.clip_clear_btn.pack(side="right", fill="x", expand=True, padx=(2, 0))

        # --- Network & WiFi Monitor Deck (collapsed by default) ---
        net_deck = tk.Frame(col_left, bg="#030814")
        net_deck.pack(fill="x", padx=10, pady=(4, 2))

        net_head_bar = tk.Frame(net_deck, bg="#030814")
        net_head_bar.pack(fill="x", pady=(0, 2))

        tk.Label(net_head_bar, text="[ 📡 NETWORK & WIFI MONITOR ]", fg="#34d399", bg="#030814", font=("Consolas", 8, "bold")).pack(side="left")

        self.net_is_expanded = False
        self.net_toggle_btn = tk.Button(net_head_bar, text="▼ OPEN", bg="#064e3b", fg="#34d399",
                                         activebackground="#065f46", activeforeground="#ffffff",
                                         font=("Consolas", 7, "bold"), bd=0, padx=6, pady=1,
                                         command=self._toggle_network_panel)
        self.net_toggle_btn.pack(side="right")

        self.net_card = tk.Frame(net_deck, bg="#071a10", bd=1, relief="ridge", padx=6, pady=4,
                                  highlightbackground="#059669", highlightthickness=1)
        # Hidden by default

        # Status row
        net_status_row = tk.Frame(self.net_card, bg="#071a10")
        net_status_row.pack(fill="x")

        self.net_dot_lbl = tk.Label(net_status_row, text="●", fg="#10b981", bg="#071a10", font=("Consolas", 10, "bold"))
        self.net_dot_lbl.pack(side="left")

        self.net_status_lbl = tk.Label(net_status_row, text="ONLINE", fg="#10b981", bg="#071a10", font=("Consolas", 8, "bold"))
        self.net_status_lbl.pack(side="left", padx=(3, 0))

        self.net_ping_lbl = tk.Label(net_status_row, text="Ping: -- ms", fg="#fbbf24", bg="#071a10", font=("Consolas", 8, "bold"))
        self.net_ping_lbl.pack(side="right")

        # WiFi SSID row
        net_wifi_row = tk.Frame(self.net_card, bg="#071a10")
        net_wifi_row.pack(fill="x", pady=(2, 0))

        tk.Label(net_wifi_row, text="WiFi:", fg="#64748b", bg="#071a10", font=("Consolas", 7)).pack(side="left")
        self.net_ssid_lbl = tk.Label(net_wifi_row, text="Detecting...", fg="#34d399", bg="#071a10", font=("Consolas", 8, "bold"))
        self.net_ssid_lbl.pack(side="left", padx=(4, 0))

        # IP + Adapter row
        net_ip_row = tk.Frame(self.net_card, bg="#071a10")
        net_ip_row.pack(fill="x", pady=(2, 2))

        tk.Label(net_ip_row, text="IP:", fg="#64748b", bg="#071a10", font=("Consolas", 7)).pack(side="left")
        self.net_ip_lbl = tk.Label(net_ip_row, text="---.---.---.---", fg="#94a3b8", bg="#071a10", font=("Consolas", 8))
        self.net_ip_lbl.pack(side="left", padx=(4, 12))

        tk.Label(net_ip_row, text="Adapter:", fg="#64748b", bg="#071a10", font=("Consolas", 7)).pack(side="left")
        self.net_adapter_lbl = tk.Label(net_ip_row, text="---", fg="#94a3b8", bg="#071a10", font=("Consolas", 8))
        self.net_adapter_lbl.pack(side="left", padx=(4, 0))

        # Ping quality bar canvas
        self.net_ping_canvas = tk.Canvas(self.net_card, height=8, bg="#020f08", highlightthickness=0)
        self.net_ping_canvas.pack(fill="x", pady=(2, 3))

        # Last updated label
        self.net_last_lbl = tk.Label(self.net_card, text="Monitoring...", fg="#334155", bg="#071a10", font=("Consolas", 7))
        self.net_last_lbl.pack(anchor="e")

        # Refresh button
        self.net_refresh_btn = tk.Button(self.net_card, text="🔄 REFRESH NOW", bg="#064e3b", fg="#34d399",
                                          activebackground="#065f46", activeforeground="#ffffff",
                                          font=("Consolas", 7, "bold"), bd=0, pady=3,
                                          command=self._on_network_refresh)
        self.net_refresh_btn.pack(fill="x")

        # --- 🚫 Ignore Words Manager Deck (collapsed by default) ---
        iw_deck = tk.Frame(col_left, bg="#030814")
        iw_deck.pack(fill="x", padx=10, pady=(4, 2))

        iw_head_bar = tk.Frame(iw_deck, bg="#030814")
        iw_head_bar.pack(fill="x", pady=(0, 2))

        tk.Label(iw_head_bar, text="[ 🚫 IGNORE WORDS ]", fg="#f97316", bg="#030814", font=("Consolas", 8, "bold")).pack(side="left")

        self.iw_popup_btn = tk.Button(iw_head_bar, text="⚙️ MANAGE", bg="#0f172a", fg="#38bdf8",
                                       activebackground="#0284c7", activeforeground="#ffffff",
                                       font=("Consolas", 7, "bold"), bd=0, padx=4, pady=1,
                                       command=self._open_iw_manager_dialog)
        self.iw_popup_btn.pack(side="right", padx=(2, 0))

        self.iw_is_expanded = False
        self.iw_toggle_btn = tk.Button(iw_head_bar, text="▼ OPEN", bg="#7c2d12", fg="#fb923c",
                                        activebackground="#9a3412", activeforeground="#ffffff",
                                        font=("Consolas", 7, "bold"), bd=0, padx=4, pady=1,
                                        command=self._toggle_iw_panel)
        self.iw_toggle_btn.pack(side="right")

        self.iw_card = tk.Frame(iw_deck, bg="#0f0a04", bd=1, relief="ridge", padx=6, pady=6,
                                 highlightbackground="#c2410c", highlightthickness=1)
        # Hidden by default

        # --- Persona Selector Row ---
        iw_persona_row = tk.Frame(self.iw_card, bg="#0f0a04")
        iw_persona_row.pack(fill="x", pady=(0, 4))

        tk.Label(iw_persona_row, text="PERSONA:", fg="#94a3b8", bg="#0f0a04", font=("Consolas", 7, "bold")).pack(side="left")

        self.iw_persona_var = tk.StringVar(value="auto")
        for p_val, p_text, p_color in [("male", "👨 MALE", "#38bdf8"), ("female", "👩 FEMALE", "#f472b6"), ("both", "🌐 BOTH", "#34d399")]:
            tk.Radiobutton(iw_persona_row, text=p_text, variable=self.iw_persona_var, value=p_val,
                           bg="#0f0a04", fg=p_color, selectcolor="#1a0a00", activebackground="#0f0a04",
                           activeforeground=p_color, font=("Consolas", 7, "bold"), bd=0
                           ).pack(side="left", padx=3)

        # --- Word Input Row ---
        iw_input_row = tk.Frame(self.iw_card, bg="#0f0a04")
        iw_input_row.pack(fill="x", pady=(2, 2))

        tk.Label(iw_input_row, text="WORD:", fg="#94a3b8", bg="#0f0a04", font=("Consolas", 7, "bold")).pack(side="left")
        self.iw_word_entry = tk.Entry(iw_input_row, bg="#1a0a00", fg="#fb923c", insertbackground="#fb923c",
                                       font=("Consolas", 9, "bold"), bd=1, relief="ridge", width=16)
        self.iw_word_entry.pack(side="left", padx=(4, 2), ipady=3)
        self.iw_word_entry.bind("<Return>", lambda e: self._iw_add_forbidden())

        # --- Replace With Row ---
        iw_replace_row = tk.Frame(self.iw_card, bg="#0f0a04")
        iw_replace_row.pack(fill="x", pady=(0, 4))

        tk.Label(iw_replace_row, text="REPLACE:", fg="#94a3b8", bg="#0f0a04", font=("Consolas", 7, "bold")).pack(side="left")
        self.iw_replace_entry = tk.Entry(iw_replace_row, bg="#0a1a00", fg="#34d399", insertbackground="#34d399",
                                          font=("Consolas", 9, "bold"), bd=1, relief="ridge", width=16)
        self.iw_replace_entry.pack(side="left", padx=(4, 2), ipady=3)
        tk.Label(iw_replace_row, text="(optional)", fg="#475569", bg="#0f0a04", font=("Consolas", 6)).pack(side="left")

        # --- Action Buttons Row ---
        iw_btn_row = tk.Frame(self.iw_card, bg="#0f0a04")
        iw_btn_row.pack(fill="x", pady=(2, 4))

        self.iw_forbid_btn = tk.Button(iw_btn_row, text="🚫 FORBID WORD", bg="#7c2d12", fg="#fca5a5",
                                        activebackground="#991b1b", activeforeground="#ffffff",
                                        font=("Consolas", 7, "bold"), bd=0, pady=4,
                                        command=self._iw_add_forbidden)
        self.iw_forbid_btn.pack(side="left", fill="x", expand=True, padx=(0, 1))

        self.iw_replace_btn = tk.Button(iw_btn_row, text="🔄 ADD REPLACE", bg="#14532d", fg="#86efac",
                                         activebackground="#166534", activeforeground="#ffffff",
                                         font=("Consolas", 7, "bold"), bd=0, pady=4,
                                         command=self._iw_add_replacement)
        self.iw_replace_btn.pack(side="right", fill="x", expand=True, padx=(1, 0))

        # --- Status Label ---
        self.iw_status_lbl = tk.Label(self.iw_card, text="● Type a word above and click FORBID or ADD REPLACE",
                                       fg="#475569", bg="#0f0a04", font=("Consolas", 7), anchor="w", wraplength=300, justify="left")
        self.iw_status_lbl.pack(fill="x", pady=(0, 4))

        # --- Live List: Forbidden Words ---
        tk.Label(self.iw_card, text="🚫 FORBIDDEN WORDS:", fg="#f97316", bg="#0f0a04", font=("Consolas", 7, "bold")).pack(anchor="w")

        iw_forb_list_frame = tk.Frame(self.iw_card, bg="#0f0a04")
        iw_forb_list_frame.pack(fill="x", pady=(1, 3))

        self.iw_forb_listbox = tk.Listbox(iw_forb_list_frame, bg="#160800", fg="#fca5a5", selectbackground="#7c2d12",
                                            font=("Consolas", 8), bd=0, highlightthickness=0, height=4,
                                            exportselection=False)
        self.iw_forb_listbox.pack(side="left", fill="x", expand=True)

        iw_forb_scroll = tk.Scrollbar(iw_forb_list_frame, orient="vertical", command=self.iw_forb_listbox.yview)
        iw_forb_scroll.pack(side="right", fill="y")
        self.iw_forb_listbox.config(yscrollcommand=iw_forb_scroll.set)

        # --- Live List: Replacements ---
        tk.Label(self.iw_card, text="🔄 WORD REPLACEMENTS:", fg="#34d399", bg="#0f0a04", font=("Consolas", 7, "bold")).pack(anchor="w")

        iw_repl_list_frame = tk.Frame(self.iw_card, bg="#0f0a04")
        iw_repl_list_frame.pack(fill="x", pady=(1, 3))

        self.iw_repl_listbox = tk.Listbox(iw_repl_list_frame, bg="#001608", fg="#86efac", selectbackground="#14532d",
                                            font=("Consolas", 8), bd=0, highlightthickness=0, height=3,
                                            exportselection=False)
        self.iw_repl_listbox.pack(side="left", fill="x", expand=True)

        iw_repl_scroll = tk.Scrollbar(iw_repl_list_frame, orient="vertical", command=self.iw_repl_listbox.yview)
        iw_repl_scroll.pack(side="right", fill="y")
        self.iw_repl_listbox.config(yscrollcommand=iw_repl_scroll.set)

        # --- Delete Selected Button ---
        self.iw_delete_btn = tk.Button(self.iw_card, text="🗑️ DELETE SELECTED RULE", bg="#1e293b", fg="#94a3b8",
                                        activebackground="#334155", activeforeground="#ffffff",
                                        font=("Consolas", 7, "bold"), bd=0, pady=3,
                                        command=self._iw_delete_selected)
        self.iw_delete_btn.pack(fill="x", pady=(2, 0))

        # === COLUMN 2: CENTER HOLOGRAPHIC 3D IRON MAN AVATAR DECK ===

        col_center = tk.Frame(main_work, bg="#01040a", width=400, bd=1, relief="solid", highlightbackground="#0c2340", highlightthickness=1)
        col_center.pack(side="left", fill="both", padx=4)

        reactor_head = tk.Label(col_center, text="[ NEURAL QUANTUM MATRIX // MARK-VII AVATAR ]", fg="#00f0ff", bg="#01040a", font=("Consolas", 8, "bold"))
        reactor_head.pack(pady=(6, 0))

        self.reactor = JarvisIronManHologram(col_center, width=395, height=460, on_mic_click=self._handle_mic)
        self.reactor.pack(fill="both", expand=True, pady=(2, 4))


        # === COLUMN 3: RIGHT HOLOGRAPHIC INTERACTIVE TERMINAL ===
        col_right = tk.Frame(main_work, bg="#030814", bd=1, relief="solid", highlightbackground="#0c2340", highlightthickness=1)
        col_right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        # 1. Top Terminal Header
        term_head = tk.Frame(col_right, bg="#051020", pady=6, padx=10)
        term_head.pack(fill="x", side="top")

        tk.Label(term_head, text="[ JARVIS ACTIVITY LOG & COMMAND CONSOLE ]", fg="#00f0ff", bg="#051020", font=("Consolas", 9, "bold")).pack(side="left")
        self.sys_status_tag = tk.Label(term_head, text="● READY", fg="#10b981", bg="#051020", font=("Consolas", 8, "bold"))
        self.sys_status_tag.pack(side="right")

        # 2. PINNED AT THE VERY BOTTOM: Interaction Container & Mode Switcher Deck
        bottom_container = tk.Frame(col_right, bg="#030814")
        bottom_container.pack(side="bottom", fill="x", padx=8, pady=(2, 6))

        # Mode Switcher Tabs Bar
        mode_bar = tk.Frame(bottom_container, bg="#051020", bd=1, relief="solid", highlightbackground="#0c2340", highlightthickness=1)
        mode_bar.pack(fill="x", pady=(0, 4))

        tk.Label(mode_bar, text="MODE:", fg="#94a3b8", bg="#051020", font=("Consolas", 8, "bold")).pack(side="left", padx=6)

        self.tab_text_btn = tk.Button(mode_bar, text="💬 TYPE / TEXT MODE", bg="#0284c7", fg="#ffffff",
                                      font=("Consolas", 8, "bold"), bd=0, padx=8, pady=3,
                                      command=lambda: self._set_interaction_mode("text"))
        self.tab_text_btn.pack(side="left", padx=2)

        self.tab_voice_btn = tk.Button(mode_bar, text="🎙️ VOICE / MIC MODE", bg="#1e293b", fg="#94a3b8",
                                       font=("Consolas", 8, "bold"), bd=0, padx=8, pady=3,
                                       command=lambda: self._set_interaction_mode("voice"))
        self.tab_voice_btn.pack(side="left", padx=2)

        self.tab_tools_btn = tk.Button(mode_bar, text="🛠️ TOOLS (Vision & Code)", bg="#1e293b", fg="#94a3b8",
                                       font=("Consolas", 8, "bold"), bd=0, padx=8, pady=3,
                                       command=lambda: self._set_interaction_mode("tools"))
        self.tab_tools_btn.pack(side="left", padx=2)

        # Quick Action Chips (Always available across modes)
        chips_frame = tk.Frame(bottom_container, bg="#030814", pady=2)
        chips_frame.pack(fill="x")

        chips = [
            ("🗺️ Route", "__SHOW_ROUTE_MODAL__"),
            ("✂️ Remove BG", "__SHOW_BG_REMOVER__"),
            ("📸 Paste Snip", "__PASTE_SCREENSHOT__"),
            ("✂️ Snip Screen", "__SNIP_SCREEN__"),
            ("📱 QR Code", "__SHOW_QR_STUDIO__"),
            ("🎨 Gen Image", "__SHOW_IMAGE_STUDIO__"),
            ("🎵 Play Music", "YouTube par trending music play karo"),
            ("📝 Notepad", "Notepad kholo aur usme code likho"),
            ("📊 Diagnostics", "System CPU, RAM aur battery check karo")
        ]

        for label, query in chips:
            if query == "__SHOW_ROUTE_MODAL__":
                btn = tk.Button(chips_frame, text=label, bg="#064e3b", fg="#6ee7b7", activebackground="#065f46",
                                activeforeground="#ffffff", font=("Consolas", 8, "bold"), bd=0, padx=5, pady=2,
                                command=lambda: self.show_route_modal())
            elif query == "__SHOW_IMAGE_STUDIO__":
                btn = tk.Button(chips_frame, text=label, bg="#061224", fg="#38bdf8", activebackground="#0c2340",
                                activeforeground="#00f0ff", font=("Consolas", 8, "bold"), bd=0, padx=5, pady=2,
                                command=self._show_image_generator_dialog)
            elif query == "__SHOW_QR_STUDIO__":
                btn = tk.Button(chips_frame, text=label, bg="#061224", fg="#38bdf8", activebackground="#0c2340",
                                activeforeground="#00f0ff", font=("Consolas", 8, "bold"), bd=0, padx=5, pady=2,
                                command=self._show_qr_generator_dialog)
            elif query == "__SHOW_BG_REMOVER__":
                btn = tk.Button(chips_frame, text=label, bg="#78350f", fg="#fde68a", activebackground="#92400e",
                                activeforeground="#ffffff", font=("Consolas", 8, "bold"), bd=0, padx=5, pady=2,
                                command=self._show_bg_remover_dialog)
            elif query == "__PASTE_SCREENSHOT__":
                btn = tk.Button(chips_frame, text=label, bg="#1e1b4b", fg="#a5b4fc", activebackground="#312e81",
                                activeforeground="#ffffff", font=("Consolas", 8, "bold"), bd=0, padx=5, pady=2,
                                command=self._on_paste_btn_click)
            elif query == "__SNIP_SCREEN__":
                btn = tk.Button(chips_frame, text=label, bg="#064e3b", fg="#34d399", activebackground="#065f46",
                                activeforeground="#ffffff", font=("Consolas", 8, "bold"), bd=0, padx=5, pady=2,
                                command=self._snip_screen_now)
            else:
                btn = tk.Button(chips_frame, text=label, bg="#061224", fg="#94a3b8", activebackground="#0c2340",
                                activeforeground="#38bdf8", font=("Consolas", 8), bd=0, padx=5, pady=2,
                                command=lambda q=query: self._send_quick_chip(q))
            btn.pack(side="left", padx=2)

        # Attachment Preview Bar (Pasted / Captured Screenshot)
        self._pending_attached_image = None
        self._attached_photo_ref = None
        self.attach_preview_frame = tk.Frame(bottom_container, bg="#0d1b2a", padx=8, pady=4, bd=1, relief="ridge", highlightbackground="#38bdf8", highlightthickness=1)
        # Hidden by default, shown when screenshot is pasted or attached

        self.attach_thumb_lbl = tk.Label(self.attach_preview_frame, bg="#040c18")
        self.attach_thumb_lbl.pack(side="left", padx=(0, 6))

        attach_text_frame = tk.Frame(self.attach_preview_frame, bg="#0d1b2a")
        attach_text_frame.pack(side="left", fill="both", expand=True)

        self.attach_title_lbl = tk.Label(attach_text_frame, text="📸 SCREENSHOT ATTACHED // VISION CORTEX READY", fg="#00f0ff", bg="#0d1b2a", font=("Consolas", 8, "bold"), anchor="w")
        self.attach_title_lbl.pack(fill="x")

        self.attach_desc_lbl = tk.Label(attach_text_frame, text="Type a question / prompt below or press EXECUTE to analyze & solve.", fg="#94a3b8", bg="#0d1b2a", font=("Consolas", 7), anchor="w")
        self.attach_desc_lbl.pack(fill="x")

        self.attach_close_btn = tk.Button(self.attach_preview_frame, text="✖ REMOVE", bg="#1e293b", fg="#fca5a5", activebackground="#7f1d1d",
                                          activeforeground="#ffffff", font=("Consolas", 7, "bold"), bd=0, padx=6, pady=2,
                                          command=self._clear_attached_screenshot)
        self.attach_close_btn.pack(side="right", padx=(4, 0))

        # === DECK 1: TEXT CHAT INPUT DECK ===
        self.text_deck = tk.Frame(bottom_container, bg="#061224", padx=8, pady=6, bd=1, relief="ridge", highlightbackground="#0284c7", highlightthickness=1)
        self.text_deck.pack(fill="x", pady=2)

        prompt_ico = tk.Label(self.text_deck, text="▶ YOU:", fg="#00f0ff", bg="#061224", font=("Consolas", 10, "bold"))
        prompt_ico.pack(side="left", padx=(2, 6))

        self.entry = tk.Entry(self.text_deck, bg="#01040a", fg="#ffffff", insertbackground="#00f0ff",
                              font=("Consolas", 11), bd=1, relief="solid", highlightbackground="#0369a1", highlightcolor="#00f0ff", highlightthickness=1)
        self.entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 4))
        self.entry.bind("<Return>", lambda e: self._send_text())
        self.entry.bind("<Control-v>", self._on_entry_paste)
        self.entry.bind("<Control-V>", self._on_entry_paste)
        self.bind("<Control-v>", self._on_global_paste)
        self.bind("<Control-V>", self._on_global_paste)
        self.entry.focus_set()

        self.paste_clip_btn = tk.Button(self.text_deck, text="📸 PASTE", bg="#1e293b", fg="#38bdf8", activebackground="#0284c7",
                                        activeforeground="#ffffff", font=("Consolas", 9, "bold"), bd=0, padx=8, pady=5,
                                        command=self._on_paste_btn_click)
        self.paste_clip_btn.pack(side="right", padx=(0, 4))

        send_btn = tk.Button(self.text_deck, text="EXECUTE ⏎", bg="#0284c7", fg="#ffffff", activebackground="#0369a1",
                             font=("Consolas", 10, "bold"), bd=0, padx=12, pady=5, command=self._send_text)
        send_btn.pack(side="right", padx=(0, 4))

        # === DECK 2: VOICE & MIC CONTROL DECK ===
        self.voice_deck = tk.Frame(bottom_container, bg="#041812", padx=8, pady=6, bd=1, relief="ridge", highlightbackground="#059669", highlightthickness=1)
        # Hidden initially, shown when Voice Mode tab is clicked

        self.big_mic_btn = tk.Button(self.voice_deck, text="🎙️ CLICK TO SPEAK (Speak your command)", bg="#059669", fg="#ffffff",
                                     activebackground="#047857", activeforeground="#ffffff",
                                     font=("Consolas", 10, "bold"), bd=0, pady=8, command=self._handle_mic)
        self.big_mic_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.voice_always_listen_btn = tk.Button(self.voice_deck, text="⚡ AUTO-LISTEN: OFF", bg="#1e293b", fg="#94a3b8",
                                                activebackground="#065f46", activeforeground="#ffffff",
                                                font=("Consolas", 8, "bold"), bd=0, padx=8, pady=8,
                                                command=self._toggle_always_listen)
        self.voice_always_listen_btn.pack(side="right")

        # === DECK 3: VISION, CODE & QR TOOLS DECK ===
        self.tools_deck = tk.Frame(bottom_container, bg="#040c1e", padx=6, pady=4, bd=1, relief="ridge", highlightbackground="#d97706", highlightthickness=1)
        # Hidden initially, shown when Tools tab is clicked

        tools_tab_row = tk.Frame(self.tools_deck, bg="#040c1e")
        tools_tab_row.pack(fill="x", pady=(0, 4))

        self.tool_vis_btn = tk.Button(tools_tab_row, text="📎 Screenshot Vision", bg="#78350f", fg="#fde68a",
                                      font=("Consolas", 8, "bold"), bd=0, padx=6, pady=2, command=self._show_subtool_vision)
        self.tool_vis_btn.pack(side="left", padx=(0, 4))

        self.tool_code_btn = tk.Button(tools_tab_row, text="🖥️ AI Code Editor", bg="#1e293b", fg="#94a3b8",
                                       font=("Consolas", 8, "bold"), bd=0, padx=6, pady=2, command=self._show_subtool_code)
        self.tool_code_btn.pack(side="left", padx=(0, 4))

        self.tool_qr_btn = tk.Button(tools_tab_row, text="📱 QR Generator", bg="#1e293b", fg="#94a3b8",
                                     font=("Consolas", 8, "bold"), bd=0, padx=6, pady=2, command=self._show_subtool_qr)
        self.tool_qr_btn.pack(side="left", padx=(0, 4))

        self.tool_trans_btn = tk.Button(tools_tab_row, text="🌐 Translator", bg="#1e293b", fg="#94a3b8",
                                        font=("Consolas", 8, "bold"), bd=0, padx=6, pady=2, command=self._show_subtool_trans)
        self.tool_trans_btn.pack(side="left")

        # Vision subpanel
        self.img_panel = tk.Frame(self.tools_deck, bg="#040c1e")
        self.img_panel.pack(fill="x")

        img_body = tk.Frame(self.img_panel, bg="#040c1e")
        img_body.pack(fill="x")

        self._uploaded_img_path = None
        self.img_preview_lbl = tk.Label(img_body, text="[ No Image ]\nClick to upload", fg="#475569", bg="#0a1628",
                                        width=12, height=3, font=("Consolas", 7), cursor="hand2", relief="solid", bd=1)
        self.img_preview_lbl.pack(side="left", padx=(0, 6))
        self.img_preview_lbl.bind("<Button-1>", lambda e: self._upload_screenshot())

        img_right = tk.Frame(img_body, bg="#040c1e")
        img_right.pack(side="left", fill="both", expand=True)

        self.img_question_entry = tk.Entry(img_right, bg="#01040a", fg="#e2e8f0", insertbackground="#f59e0b",
                                           font=("Consolas", 8), bd=1, relief="solid")
        self.img_question_entry.insert(0, "Is screenshot mein kya problem hai? Solve karo.")
        self.img_question_entry.pack(fill="x", ipady=2, pady=(0, 2))

        img_btn_row = tk.Frame(img_right, bg="#040c1e")
        img_btn_row.pack(fill="x")

        tk.Button(img_btn_row, text="📂 Browse", bg="#1e293b", fg="#94a3b8", font=("Consolas", 8), bd=0, command=self._upload_screenshot).pack(side="left", padx=(0, 4))
        tk.Button(img_btn_row, text="🔍 ANALYZE IMAGE", bg="#92400e", fg="#fde68a", font=("Consolas", 8, "bold"), bd=0, command=self._analyze_uploaded_image).pack(side="left")
        self.img_status_lbl = tk.Label(img_btn_row, text="", fg="#10b981", bg="#040c1e", font=("Consolas", 7))
        self.img_status_lbl.pack(side="left", padx=4)

        # Code subpanel
        self.code_panel = tk.Frame(self.tools_deck, bg="#0c1a0c")
        # hidden by default

        code_body = tk.Frame(self.code_panel, bg="#0c1a0c", padx=4, pady=2)
        code_body.pack(fill="x")

        self._code_file_path = None
        self.code_file_lbl = tk.Label(code_body, text="[ No file selected ]", fg="#4ade80", bg="#0a140a", font=("Consolas", 7), anchor="w")
        self.code_file_lbl.pack(fill="x", pady=(0, 2))

        self.code_instruction_entry = tk.Entry(code_body, bg="#01040a", fg="#e2e8f0", insertbackground="#4ade80", font=("Consolas", 8), bd=1, relief="solid")
        self.code_instruction_entry.insert(0, "Fix all bugs and add error handling")
        self.code_instruction_entry.pack(fill="x", ipady=2, pady=(0, 2))

        code_btn_row = tk.Frame(code_body, bg="#0c1a0c")
        code_btn_row.pack(fill="x")

        tk.Button(code_btn_row, text="📁 Browse", bg="#1e293b", fg="#94a3b8", font=("Consolas", 8), bd=0, command=self._browse_code_file).pack(side="left", padx=(0, 4))
        tk.Button(code_btn_row, text="⚡ APPLY AI EDITS", bg="#14532d", fg="#86efac", font=("Consolas", 8, "bold"), bd=0, command=self._apply_ai_code_edits).pack(side="left")
        self.code_status_lbl = tk.Label(code_btn_row, text="", fg="#4ade80", bg="#0c1a0c", font=("Consolas", 7))
        self.code_status_lbl.pack(side="left", padx=4)

        # QR Code subpanel
        self.qr_panel = tk.Frame(self.tools_deck, bg="#08182b")
        # hidden by default

        qr_body = tk.Frame(self.qr_panel, bg="#08182b", padx=4, pady=2)
        qr_body.pack(fill="x")

        self.qr_data_entry = tk.Entry(qr_body, bg="#01040a", fg="#e0f2fe", insertbackground="#00f0ff", font=("Consolas", 8), bd=1, relief="solid")
        self.qr_data_entry.insert(0, "https://github.com/my-portfolio")
        self.qr_data_entry.pack(fill="x", ipady=2, pady=(0, 2))

        qr_btn_row = tk.Frame(qr_body, bg="#08182b")
        qr_btn_row.pack(fill="x")

        tk.Button(qr_btn_row, text="⚡ GENERATE & DISPLAY QR CODE", bg="#0284c7", fg="#ffffff", font=("Consolas", 8, "bold"), bd=0, padx=8, pady=2, command=self._generate_manual_qr).pack(side="left")
        self.qr_status_lbl = tk.Label(qr_btn_row, text="Enter text/URL and click generate", fg="#38bdf8", bg="#08182b", font=("Consolas", 7))
        self.qr_status_lbl.pack(side="left", padx=6)

        # Translator subpanel
        self.trans_panel = tk.Frame(self.tools_deck, bg="#1a102f")
        # hidden by default

        trans_body = tk.Frame(self.trans_panel, bg="#1a102f", padx=4, pady=2)
        trans_body.pack(fill="x")

        trans_input_row = tk.Frame(trans_body, bg="#1a102f")
        trans_input_row.pack(fill="x", pady=(0, 2))

        self.trans_input_entry = tk.Entry(trans_input_row, bg="#01040a", fg="#f3e8ff", insertbackground="#c084fc", font=("Consolas", 8), bd=1, relief="solid")
        self.trans_input_entry.insert(0, "We are building an autonomous AI agency")
        self.trans_input_entry.pack(side="left", fill="x", expand=True, ipady=2, padx=(0, 4))

        self.trans_lang_entry = tk.Entry(trans_input_row, bg="#01040a", fg="#e879f9", insertbackground="#c084fc", font=("Consolas", 8, "bold"), width=9, bd=1, relief="solid")
        self.trans_lang_entry.insert(0, "Hindi")
        self.trans_lang_entry.pack(side="right", ipady=2)

        trans_btn_row = tk.Frame(trans_body, bg="#1a102f")
        trans_btn_row.pack(fill="x")

        tk.Button(trans_btn_row, text="⚡ TRANSLATE & DISPLAY", bg="#7e22ce", fg="#f3e8ff", font=("Consolas", 8, "bold"), bd=0, padx=8, pady=2, command=self._generate_manual_translation).pack(side="left")
        self.trans_status_lbl = tk.Label(trans_btn_row, text="Enter text + target language and click translate", fg="#d8b4fe", bg="#1a102f", font=("Consolas", 7))
        self.trans_status_lbl.pack(side="left", padx=6)

        # Translated Result Output Row
        trans_out_row = tk.Frame(trans_body, bg="#1a102f")
        trans_out_row.pack(fill="x", pady=(2, 0))

        tk.Label(trans_out_row, text="RESULT:", fg="#c084fc", bg="#1a102f", font=("Consolas", 8, "bold")).pack(side="left", padx=(0, 4))
        self.trans_output_entry = tk.Entry(trans_out_row, bg="#0d071a", fg="#f5d0fe", insertbackground="#c084fc", font=("Consolas", 9, "bold"), bd=1, relief="solid")
        self.trans_output_entry.pack(side="left", fill="x", expand=True, ipady=2, padx=(0, 4))

        def _copy_trans_res():
            c = self.trans_output_entry.get().strip()
            if c:
                try:
                    self.clipboard_clear()
                    self.clipboard_append(c)
                    self.trans_status_lbl.config(text="✔ Copied to Clipboard!", fg="#10b981")
                except Exception:
                    pass

        tk.Button(trans_out_row, text="📋 Copy", bg="#581c87", fg="#f3e8ff", font=("Consolas", 8), bd=0, padx=6, command=_copy_trans_res).pack(side="right")

        # 4. Chat Log Area (Takes all remaining center space)
        chat_box = tk.Frame(col_right, bg="#01040a")
        chat_box.pack(fill="both", expand=True, padx=8, pady=4)

        self.log_text = tk.Text(
            chat_box,
            bg="#01040a", fg="#e2e8f0",
            insertbackground="#00f0ff",
            font=("Segoe UI Emoji", 10),
            wrap="word", bd=0, padx=10, pady=8,
            state="disabled",          # ← Read-only: cursor nahi jayega, typing nahi hogi
            cursor="arrow",            # ← Mouse cursor arrow rahega, text cursor nahi
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        # Prevent any keyboard focus on log area
        self.log_text.bind("<Key>", lambda e: "break")
        self.log_text.bind("<Button-1>", lambda e: self.log_text.focus_set() or None)

        # Custom Scrollbar
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Jarvis.Vertical.TScrollbar", background="#0c2340", troughcolor="#01040a", bordercolor="#01040a", arrowcolor="#00f0ff")
        scrollbar = ttk.Scrollbar(chat_box, orient="vertical", command=self.log_text.yview, style="Jarvis.Vertical.TScrollbar")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # Color tags for chat and dynamic emotions (Segoe UI Emoji for proper emoji rendering)
        self.log_text.tag_config("user_tag",     foreground="#10b981", font=("Segoe UI Emoji", 10, "bold"))
        self.log_text.tag_config("user_msg",     foreground="#ecfdf5", font=("Segoe UI Emoji", 10))
        self.log_text.tag_config("cwa_tag",      foreground="#00f0ff", font=("Segoe UI Emoji", 10, "bold"))
        self.log_text.tag_config("cwa_msg",      foreground="#e0f2fe", font=("Segoe UI Emoji", 10))
        self.log_text.tag_config("mj_tag",       foreground="#f472b6", font=("Segoe UI Emoji", 10, "bold"))
        self.log_text.tag_config("mj_msg",       foreground="#fdf2f8", font=("Segoe UI Emoji", 10))
        self.log_text.tag_config("system",       foreground="#fbbf24", font=("Segoe UI Emoji", 9))

        # Dynamic emotion badge tags
        self.log_text.tag_config("emo_happy",    foreground="#10b981", font=("Segoe UI Emoji", 9, "bold"))
        self.log_text.tag_config("emo_excited",  foreground="#f59e0b", font=("Segoe UI Emoji", 9, "bold"))
        self.log_text.tag_config("emo_sad",      foreground="#818cf8", font=("Segoe UI Emoji", 9, "bold"))
        self.log_text.tag_config("emo_angry",    foreground="#ef4444", font=("Segoe UI Emoji", 9, "bold"))
        self.log_text.tag_config("emo_witty",    foreground="#c084fc", font=("Segoe UI Emoji", 9, "bold"))
        self.log_text.tag_config("emo_caring",   foreground="#f43f5e", font=("Segoe UI Emoji", 9, "bold"))
        self.log_text.tag_config("emo_surprised",foreground="#ec4899", font=("Segoe UI Emoji", 9, "bold"))
        self.log_text.tag_config("emo_calm",     foreground="#38bdf8", font=("Segoe UI Emoji", 9, "bold"))

        self.log("system", "STARK INDUSTRIES MARK-VII SYSTEM ACTIVE. Hands-Free Voice is Live!\n")
        self.log("system", "💡 Dynamic Neural Emotional Matrix & Sentiment Consciousness Active!\n")

    def _set_interaction_mode(self, mode: str):
        """Switches between Text Input, Voice Mic, and Tools Decks seamlessly."""
        # Reset tab button styles
        self.tab_text_btn.config(bg="#1e293b", fg="#94a3b8")
        self.tab_voice_btn.config(bg="#1e293b", fg="#94a3b8")
        self.tab_tools_btn.config(bg="#1e293b", fg="#94a3b8")

        # Hide all decks
        self.text_deck.pack_forget()
        self.voice_deck.pack_forget()
        self.tools_deck.pack_forget()

        if mode == "voice":
            self.tab_voice_btn.config(bg="#059669", fg="#ffffff")
            self.voice_deck.pack(fill="x", pady=2)
            self.log("system", "[Mode: Voice & Microphone Input Active]\n")
        elif mode == "tools":
            self.tab_tools_btn.config(bg="#d97706", fg="#ffffff")
            self.tools_deck.pack(fill="x", pady=2)
            self.log("system", "[Mode: Vision & AI Code Tools Active]\n")
        else:  # text mode
            self.tab_text_btn.config(bg="#0284c7", fg="#ffffff")
            self.text_deck.pack(fill="x", pady=2)
            self.entry.focus_set()
            self.log("system", "[Mode: Text Chat & Command Entry Active]\n")

    def _show_subtool_vision(self):
        self.tool_vis_btn.config(bg="#78350f", fg="#fde68a")
        self.tool_code_btn.config(bg="#1e293b", fg="#94a3b8")
        self.tool_qr_btn.config(bg="#1e293b", fg="#94a3b8")
        self.tool_trans_btn.config(bg="#1e293b", fg="#94a3b8")
        self.code_panel.pack_forget()
        self.qr_panel.pack_forget()
        self.trans_panel.pack_forget()
        self.img_panel.pack(fill="x", pady=2)

    def _show_subtool_code(self):
        self.tool_code_btn.config(bg="#14532d", fg="#86efac")
        self.tool_vis_btn.config(bg="#1e293b", fg="#94a3b8")
        self.tool_qr_btn.config(bg="#1e293b", fg="#94a3b8")
        self.tool_trans_btn.config(bg="#1e293b", fg="#94a3b8")
        self.img_panel.pack_forget()
        self.qr_panel.pack_forget()
        self.trans_panel.pack_forget()
        self.code_panel.pack(fill="x", pady=2)

    def _show_subtool_qr(self):
        self.tool_qr_btn.config(bg="#0369a1", fg="#e0f2fe")
        self.tool_vis_btn.config(bg="#1e293b", fg="#94a3b8")
        self.tool_code_btn.config(bg="#1e293b", fg="#94a3b8")
        self.tool_trans_btn.config(bg="#1e293b", fg="#94a3b8")
        self.img_panel.pack_forget()
        self.code_panel.pack_forget()
        self.trans_panel.pack_forget()
        self.qr_panel.pack(fill="x", pady=2)

    def _show_subtool_trans(self):
        self.tool_trans_btn.config(bg="#6b21a8", fg="#f3e8ff")
        self.tool_vis_btn.config(bg="#1e293b", fg="#94a3b8")
        self.tool_code_btn.config(bg="#1e293b", fg="#94a3b8")
        self.tool_qr_btn.config(bg="#1e293b", fg="#94a3b8")
        self.img_panel.pack_forget()
        self.code_panel.pack_forget()
        self.qr_panel.pack_forget()
        self.trans_panel.pack(fill="x", pady=2)

    def _generate_manual_qr(self):
        data = self.qr_data_entry.get().strip()
        if not data:
            messagebox.showwarning("Empty Data", "Please enter a URL, text, or data to encode into QR code!")
            return

        self.qr_status_lbl.config(text="⚡ Generating QR...", fg="#f59e0b")
        self.log("user", f"[QR Request] Generate QR code for: {data[:40]}...\n")
        self.set_reactor_state("THINKING")

        def _worker():
            from cwa_agent.core.tools import generate_qr_code
            res = generate_qr_code(data)
            self.after(0, lambda: self._on_manual_qr_done(res))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_manual_qr_done(self, res_text: str):
        self.qr_status_lbl.config(text="✔ QR Generated!", fg="#10b981")
        self.set_reactor_state("IDLE")
        self.log("cwa", f"CWA: {res_text}\n\n")

    def _generate_manual_translation(self):
        text = self.trans_input_entry.get().strip()
        target_lang = self.trans_lang_entry.get().strip()
        if not text:
            messagebox.showwarning("Empty Text", "Please enter text to translate!")
            return

        self.trans_status_lbl.config(text=f"⚡ Translating to {target_lang}...", fg="#d8b4fe")
        self.log("user", f"[Translate Request] ({target_lang}): {text[:40]}...\n")
        self.set_reactor_state("THINKING")

        def _worker():
            from cwa_agent.core.tools import translate_text
            res = translate_text(text, target_language=target_lang)
            self.after(0, lambda: self._on_manual_trans_done(res))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_manual_trans_done(self, res_text: str):
        # Extract clean translation text
        clean_res = res_text
        if "Translation (" in clean_res and "):\n" in clean_res:
            clean_res = clean_res.split("):\n", 1)[-1].strip()

        try:
            self.trans_output_entry.delete(0, tk.END)
            self.trans_output_entry.insert(0, clean_res)
        except Exception:
            pass

        # Auto-copy translated text to clipboard
        try:
            self.clipboard_clear()
            self.clipboard_append(clean_res)
        except Exception:
            pass

        self.trans_status_lbl.config(text="✔ Translated & Copied to Clipboard!", fg="#a855f7")
        self.set_reactor_state("IDLE")
        self.log("cwa", f"CWA: {res_text}\n\n")

    def _show_image_generator_dialog(self):
        """Opens an interactive studio modal to generate custom AI images and wallpapers of user's choice."""
        dialog = tk.Toplevel(self)
        dialog.title("🎨 AI IMAGE & WALLPAPER STUDIO")
        dialog.geometry("560x480")
        dialog.configure(bg="#030814")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Center the dialog on main window
        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 280
            y = self.winfo_y() + (self.winfo_height() // 2) - 240
            dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        header = tk.Frame(dialog, bg="#061224", padx=12, pady=8, bd=1, relief="ridge")
        header.pack(fill="x")
        tk.Label(header, text="🎨 STARK NEURAL AI IMAGE GENERATOR", fg="#00f0ff", bg="#061224", font=("Consolas", 11, "bold")).pack(side="left")
        tk.Label(header, text="● 100% Custom / Zero Limits", fg="#10b981", bg="#061224", font=("Consolas", 8)).pack(side="right")

        body = tk.Frame(dialog, bg="#030814", padx=14, pady=10)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="ENTER IMAGE DESCRIPTION / PROMPT:", fg="#94a3b8", bg="#030814", font=("Consolas", 9, "bold")).pack(anchor="w", pady=(0, 4))

        prompt_entry = tk.Text(body, bg="#01040a", fg="#ffffff", insertbackground="#00f0ff", font=("Segoe UI", 10), height=3, wrap="word", bd=1, relief="solid")
        prompt_entry.insert("1.0", "Futuristic cyberpunk sports car in neon rain 8k wallpaper")
        prompt_entry.pack(fill="x", pady=(0, 8))

        # Inspiration Presets Row
        tk.Label(body, text="💡 INSPIRATION CHIPS (Click to use):", fg="#64748b", bg="#030814", font=("Consolas", 8, "bold")).pack(anchor="w", pady=(0, 2))
        preset_frame = tk.Frame(body, bg="#030814")
        preset_frame.pack(fill="x", pady=(0, 10))

        presets = [
            ("🤖 Iron Man", "Glowing Iron Man arc reactor Stark Industries dark sci-fi 4k wallpaper"),
            ("🏎️ Cyberpunk", "Futuristic cyberpunk sports car neon reflections 8k ultra realistic"),
            ("🌌 Galaxy", "Deep space cosmic galaxy nebula colorful stars 4k wallpaper"),
            ("🏔️ Himalayas", "Scenic snowy Himalayan mountains sunrise golden hour 8k nature photo"),
            ("🧘 Spiritual", "Lord Shiva meditating in cosmic Himalayas glowing aura divine art 8k"),
            ("🎌 Anime", "Cyberpunk anime warrior city lights vibrant aesthetic 4k")
        ]

        def _set_preset(p_text):
            prompt_entry.delete("1.0", tk.END)
            prompt_entry.insert("1.0", p_text)

        for p_label, p_val in presets:
            btn = tk.Button(preset_frame, text=p_label, bg="#0b1e36", fg="#38bdf8", activebackground="#0284c7", activeforeground="#ffffff",
                            font=("Consolas", 8), bd=0, padx=5, pady=2, command=lambda v=p_val: _set_preset(v))
            btn.pack(side="left", padx=2, pady=2)

        # Aspect Ratio / Dimensions
        tk.Label(body, text="📐 ASPECT RATIO / FORMAT:", fg="#94a3b8", bg="#030814", font=("Consolas", 9, "bold")).pack(anchor="w", pady=(0, 4))
        aspect_var = tk.StringVar(value="desktop")
        ratio_frame = tk.Frame(body, bg="#030814")
        ratio_frame.pack(fill="x", pady=(0, 12))

        r1 = tk.Radiobutton(ratio_frame, text="🖥️ Desktop (1920x1080 / 16:9)", variable=aspect_var, value="desktop", bg="#030814", fg="#e2e8f0", selectcolor="#061224", font=("Consolas", 8))
        r1.pack(side="left", padx=(0, 8))
        r2 = tk.Radiobutton(ratio_frame, text="📱 Phone (1080x1920 / 9:16)", variable=aspect_var, value="phone", bg="#030814", fg="#e2e8f0", selectcolor="#061224", font=("Consolas", 8))
        r2.pack(side="left", padx=(0, 8))
        r3 = tk.Radiobutton(ratio_frame, text="🖼️ Square (1024x1024 / 1:1)", variable=aspect_var, value="square", bg="#030814", fg="#e2e8f0", selectcolor="#061224", font=("Consolas", 8))
        r3.pack(side="left")

        status_lbl = tk.Label(body, text="Ready to generate your custom artwork.", fg="#10b981", bg="#030814", font=("Consolas", 8))
        status_lbl.pack(anchor="w", pady=(0, 10))

        # Generator Action Worker
        def _do_generate(set_as_wallpaper=False):
            p = prompt_entry.get("1.0", tk.END).strip()
            if not p:
                messagebox.showwarning("Empty Prompt", "Please enter an image description first!")
                return

            status_lbl.config(text="⚡ Neural engine rendering image... Please wait 3-5 seconds.", fg="#f59e0b")
            self.set_reactor_state("THINKING")

            def _worker():
                import urllib.parse
                import requests
                import time
                import os
                import ctypes
                from cwa_agent.config import DOWNLOADS_DIR

                ratio = aspect_var.get()
                w, h = (1920, 1080) if ratio == "desktop" else ((1080, 1920) if ratio == "phone" else (1024, 1024))
                encoded = urllib.parse.quote(f"{p} high resolution, stunning masterpiece quality")
                img_url = f"https://image.pollinations.ai/prompt/{encoded}?width={w}&height={h}&nologo=true&enhance=true"

                try:
                    resp = requests.get(img_url, timeout=35)
                    if resp.status_code == 200:
                        img_dir = DOWNLOADS_DIR / "Images"
                        img_dir.mkdir(parents=True, exist_ok=True)
                        clean_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in p)[:40].strip() or "ai_image"
                        filepath = img_dir / f"{clean_name}_{int(time.time())}.jpg"
                        with open(filepath, "wb") as f:
                            f.write(resp.content)

                        abs_path = str(filepath.resolve())
                        if set_as_wallpaper and os.name == "nt":
                            try:
                                ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 3)
                            except Exception:
                                pass

                        # Open image in default photo viewer
                        if os.name == "nt":
                            try:
                                os.startfile(abs_path)
                            except Exception:
                                pass

                        def _on_success():
                            msg = f"✔ Image saved to media/Images/ and opened!"
                            if set_as_wallpaper:
                                msg = f"✔ Set as Windows Desktop Wallpaper & saved!"
                            status_lbl.config(text=msg, fg="#10b981")
                            self.set_reactor_state("IDLE")
                            self.log("system", f"[AI Image Studio 🎨] Generated: '{p}' (Saved: {filepath.name})\n")
                            if set_as_wallpaper:
                                self.log("system", f"[Wallpaper Applied 🖼️] Set '{filepath.name}' as Windows background!\n")

                        self.after(0, _on_success)
                    else:
                        self.after(0, lambda: status_lbl.config(text=f"Error: HTTP status {resp.status_code}", fg="#ef4444"))
                        self.set_reactor_state("IDLE")
                except Exception as ex:
                    self.after(0, lambda: status_lbl.config(text=f"Error: {ex}", fg="#ef4444"))
                    self.set_reactor_state("IDLE")

            threading.Thread(target=_worker, daemon=True).start()

        # Action Buttons Row
        btn_frame = tk.Frame(body, bg="#030814")
        btn_frame.pack(fill="x", pady=4)

        gen_btn = tk.Button(btn_frame, text="⚡ GENERATE & VIEW IMAGE", bg="#0284c7", fg="#ffffff", activebackground="#0369a1",
                            font=("Consolas", 9, "bold"), bd=0, padx=12, pady=6, command=lambda: _do_generate(set_as_wallpaper=False))
        gen_btn.pack(side="left", padx=(0, 6), fill="x", expand=True)

        wall_btn = tk.Button(btn_frame, text="🖼️ SET AS DESKTOP WALLPAPER", bg="#059669", fg="#ffffff", activebackground="#047857",
                             font=("Consolas", 9, "bold"), bd=0, padx=12, pady=6, command=lambda: _do_generate(set_as_wallpaper=True))
        wall_btn.pack(side="right", fill="x", expand=True)

    def _show_qr_generator_dialog(self):
        """Opens an interactive modal to generate and view custom QR codes reliably on screen."""
        dialog = tk.Toplevel(self)
        dialog.title("📱 QUANTUM QR CODE STUDIO")
        dialog.geometry("540x520")
        dialog.configure(bg="#030814")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Center dialog
        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 270
            y = self.winfo_y() + (self.winfo_height() // 2) - 260
            dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        header = tk.Frame(dialog, bg="#061224", padx=12, pady=8, bd=1, relief="ridge")
        header.pack(fill="x")
        tk.Label(header, text="📱 QUANTUM QR CODE STUDIO", fg="#00f0ff", bg="#061224", font=("Consolas", 11, "bold")).pack(side="left")
        tk.Label(header, text="● Instant HD Generation", fg="#10b981", bg="#061224", font=("Consolas", 8)).pack(side="right")

        body = tk.Frame(dialog, bg="#030814", padx=14, pady=8)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="ENTER TEXT, URL, UPI ID, OR DATA:", fg="#94a3b8", bg="#030814", font=("Consolas", 9, "bold")).pack(anchor="w", pady=(0, 4))

        data_entry = tk.Entry(body, bg="#01040a", fg="#ffffff", insertbackground="#00f0ff", font=("Consolas", 10), bd=1, relief="solid")
        data_entry.insert(0, "https://github.com/codewithali")
        data_entry.pack(fill="x", ipady=4, pady=(0, 6))

        # Inspiration Presets Row
        tk.Label(body, text="💡 QUICK TEMPLATES (Click to insert):", fg="#64748b", bg="#030814", font=("Consolas", 8, "bold")).pack(anchor="w", pady=(0, 2))
        preset_frame = tk.Frame(body, bg="#030814")
        preset_frame.pack(fill="x", pady=(0, 6))

        presets = [
            ("🌐 Website", "https://"),
            ("💳 UPI", "upi://pay?pa=user@upi&pn=CodeWithAli&cu=INR"),
            ("📶 Wi-Fi", "WIFI:T:WPA;S:MyWiFi;P:Password123;;"),
            ("📱 WhatsApp", "https://wa.me/919999999999"),
            ("📧 Email", "mailto:contact@example.com")
        ]

        def _set_qr_preset(val):
            data_entry.delete(0, tk.END)
            data_entry.insert(0, val)
            data_entry.focus_set()

        for p_label, p_val in presets:
            btn = tk.Button(preset_frame, text=p_label, bg="#0b1e36", fg="#38bdf8", activebackground="#0284c7", activeforeground="#ffffff",
                            font=("Consolas", 8), bd=0, padx=5, pady=2, command=lambda v=p_val: _set_qr_preset(v))
            btn.pack(side="left", padx=2, pady=1)

        # QR Preview Container (Canvas / Label)
        preview_frame = tk.Frame(body, bg="#061224", bd=1, relief="solid", height=180)
        preview_frame.pack(fill="x", pady=6)
        preview_frame.pack_propagate(False)

        qr_preview_lbl = tk.Label(preview_frame, text="[ QR Code Preview will appear here ]\nClick Generate to render", fg="#475569", bg="#061224", font=("Consolas", 9))
        qr_preview_lbl.pack(expand=True)

        status_lbl = tk.Label(body, text="Ready to generate QR code.", fg="#10b981", bg="#030814", font=("Consolas", 8))
        status_lbl.pack(anchor="w", pady=(0, 4))

        # Store image reference to prevent garbage collection
        dialog._qr_photo_ref = None

        def _do_generate_qr():
            d = data_entry.get().strip()
            if not d:
                messagebox.showwarning("Empty Input", "Please enter some text or URL to generate QR code!")
                return

            status_lbl.config(text="⚡ Generating high-resolution QR code...", fg="#f59e0b")

            try:
                import qrcode
                from PIL import Image, ImageTk
                from cwa_agent.config import QRCODES_DIR

                QRCODES_DIR.mkdir(parents=True, exist_ok=True)
                timestamp = int(time.time())
                safe_name = "".join(c if c.isalnum() else '_' for c in d[:15]).strip('_') or "code"
                filename = f"qr_{safe_name}_{timestamp}.png"
                file_path = QRCODES_DIR / filename

                qr = qrcode.QRCode(
                    version=None,
                    error_correction=qrcode.constants.ERROR_CORRECT_H,
                    box_size=10,
                    border=3,
                )
                qr.add_data(d)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                qr_img.save(str(file_path))

                # Render preview in dialog
                preview_pil = qr_img.resize((160, 160), Image.Resampling.LANCZOS)
                dialog._qr_photo_ref = ImageTk.PhotoImage(preview_pil)
                qr_preview_lbl.config(image=dialog._qr_photo_ref, text="")

                # Open externally in Windows Photo Viewer as well
                if os.name == 'nt':
                    try:
                        os.startfile(str(file_path))
                    except Exception:
                        pass

                status_lbl.config(text=f"✔ Saved: {filename} & displayed on screen!", fg="#10b981")
                self.log("system", f"[QR Studio 📱] Generated QR for: '{d[:40]}' (Saved: {filename})\n")
            except Exception as ex:
                status_lbl.config(text=f"Error: {ex}", fg="#ef4444")

        # Action Buttons
        btn_frame = tk.Frame(body, bg="#030814")
        btn_frame.pack(fill="x", pady=4)

        gen_btn = tk.Button(btn_frame, text="⚡ GENERATE & OPEN QR CODE", bg="#0284c7", fg="#ffffff", activebackground="#0369a1",
                            font=("Consolas", 9, "bold"), bd=0, padx=12, pady=6, command=_do_generate_qr)
        gen_btn.pack(side="left", padx=(0, 6), fill="x", expand=True)

        dir_btn = tk.Button(btn_frame, text="📁 OPEN QR FOLDER", bg="#1e293b", fg="#94a3b8", activebackground="#334155",
                            font=("Consolas", 9), bd=0, padx=10, pady=6, command=_open_folder)
        dir_btn.pack(side="right")

    def _show_bg_remover_dialog(self):
        """Opens an interactive studio modal for AI Background Removal with Remove.bg."""
        dialog = tk.Toplevel(self)
        dialog.title("✂️ REMOVE.BG AI STUDIO // BACKGROUND REMOVAL & PORTRAITS")
        dialog.geometry("620x620")
        dialog.configure(bg="#030814")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 310
            y = self.winfo_y() + (self.winfo_height() // 2) - 310
            dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        header = tk.Frame(dialog, bg="#061224", padx=12, pady=8, bd=1, relief="ridge")
        header.pack(fill="x")
        tk.Label(header, text="✂️ REMOVE.BG AI BACKGROUND REMOVAL STUDIO", fg="#f59e0b", bg="#061224", font=("Consolas", 11, "bold")).pack(side="left")
        tk.Label(header, text="● HD AI Cutouts & Studio Portraits", fg="#10b981", bg="#061224", font=("Consolas", 8)).pack(side="right")

        body = tk.Frame(dialog, bg="#030814", padx=14, pady=8)
        body.pack(fill="both", expand=True)

        # 1. Source Image Selection Row
        tk.Label(body, text="1. SELECT SOURCE IMAGE:", fg="#94a3b8", bg="#030814", font=("Consolas", 9, "bold")).pack(anchor="w", pady=(0, 2))

        src_row = tk.Frame(body, bg="#030814")
        src_row.pack(fill="x", pady=(0, 6))

        src_entry = tk.Entry(src_row, bg="#01040a", fg="#ffffff", insertbackground="#00f0ff", font=("Consolas", 9), bd=1, relief="solid")
        src_entry.insert(0, "clipboard")
        src_entry.pack(side="left", fill="x", expand=True, ipady=3, padx=(0, 4))

        def _browse_img():
            from tkinter import filedialog
            f = filedialog.askopenfilename(
                title="Select Image for Background Removal",
                filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All Files", "*.*")]
            )
            if f:
                src_entry.delete(0, tk.END)
                src_entry.insert(0, f)
                _update_source_preview(f)

        def _paste_cb():
            src_entry.delete(0, tk.END)
            src_entry.insert(0, "clipboard")
            status_lbl.config(text="✔ Selected active clipboard image", fg="#10b981")
            try:
                from PIL import ImageGrab
                cb = ImageGrab.grabclipboard()
                if cb:
                    temp_f = str(SCREENSHOTS_DIR / f"temp_preview_{int(time.time())}.png")
                    cb.save(temp_f)
                    _update_source_preview(temp_f)
            except Exception:
                pass

        def _snip_desk():
            src_entry.delete(0, tk.END)
            src_entry.insert(0, "screen")
            status_lbl.config(text="✔ Selected active desktop screenshot", fg="#10b981")
            try:
                from cwa_agent.core.vision import vision
                ok, path = vision.capture_screen(auto_open=False)
                if ok and path:
                    _update_source_preview(path)
            except Exception:
                pass

        def _clear_img():
            src_entry.delete(0, tk.END)
            dialog._out_img_path = None
            dialog._before_photo = None
            dialog._after_photo = None
            before_lbl.config(image="", text="[ Source Preview ]")
            after_lbl.config(image="", text="[ Cutout Preview ]")
            status_lbl.config(text="Image removed/cleared. Please select a new source image.", fg="#fbbf24")

        tk.Button(src_row, text="📁 Browse", bg="#1e293b", fg="#cbd5e1", font=("Consolas", 8), bd=0, padx=6, pady=3, command=_browse_img).pack(side="left", padx=2)
        tk.Button(src_row, text="📸 Paste", bg="#1e1b4b", fg="#a5b4fc", font=("Consolas", 8), bd=0, padx=6, pady=3, command=_paste_cb).pack(side="left", padx=2)
        tk.Button(src_row, text="✂️ Snip", bg="#064e3b", fg="#34d399", font=("Consolas", 8), bd=0, padx=6, pady=3, command=_snip_desk).pack(side="left", padx=2)
        tk.Button(src_row, text="✖ Clear Image", bg="#7f1d1d", fg="#fca5a5", activebackground="#991b1b", activeforeground="#ffffff", font=("Consolas", 8, "bold"), bd=0, padx=6, pady=3, command=_clear_img).pack(side="left", padx=2)

        # 2. Background Color / Preset Choice
        tk.Label(body, text="2. BACKGROUND STYLE & COLOR:", fg="#94a3b8", bg="#030814", font=("Consolas", 9, "bold")).pack(anchor="w", pady=(2, 2))

        bg_color_var = tk.StringVar(value="transparent")
        color_frame = tk.Frame(body, bg="#030814")
        color_frame.pack(fill="x", pady=(0, 6))

        colors_row1 = tk.Frame(color_frame, bg="#030814")
        colors_row1.pack(fill="x")

        for c_label, c_val in [
            ("✨ Transparent PNG", "transparent"),
            ("⚪ Pure White (Resume/ID)", "white"),
            ("🔵 Passport Blue", "passport blue")
        ]:
            tk.Radiobutton(colors_row1, text=c_label, variable=bg_color_var, value=c_val,
                           bg="#030814", fg="#e2e8f0", selectcolor="#061224", activebackground="#030814",
                           font=("Consolas", 8)).pack(side="left", padx=(0, 10))

        colors_row2 = tk.Frame(color_frame, bg="#030814")
        colors_row2.pack(fill="x", pady=(2, 0))

        for c_label, c_val in [
            ("🌑 Navy Blue", "navy blue"),
            ("🏢 Studio Grey", "studio grey"),
            ("🔴 Red", "red"),
            ("🟢 Green", "green")
        ]:
            tk.Radiobutton(colors_row2, text=c_label, variable=bg_color_var, value=c_val,
                           bg="#030814", fg="#e2e8f0", selectcolor="#061224", activebackground="#030814",
                           font=("Consolas", 8)).pack(side="left", padx=(0, 10))

        # 3. Before & After Preview Box
        preview_box = tk.Frame(body, bg="#061224", bd=1, relief="ridge", padx=8, pady=6)
        preview_box.pack(fill="both", expand=True, pady=(2, 6))

        dialog._out_img_path = None
        dialog._before_photo = None
        dialog._after_photo = None

        # Preview Labels Grid
        p_grid = tk.Frame(preview_box, bg="#061224")
        p_grid.pack(fill="both", expand=True)

        left_p = tk.Frame(p_grid, bg="#061224")
        left_p.pack(side="left", fill="both", expand=True, padx=4)
        tk.Label(left_p, text="ORIGINAL IMAGE", fg="#64748b", bg="#061224", font=("Consolas", 7, "bold")).pack()
        before_lbl = tk.Label(left_p, text="[ Source Preview ]", bg="#020813", fg="#475569", width=24, height=8)
        before_lbl.pack(fill="both", expand=True, pady=2)

        right_p = tk.Frame(p_grid, bg="#061224")
        right_p.pack(side="right", fill="both", expand=True, padx=4)
        tk.Label(right_p, text="CUTOUT RESULT", fg="#10b981", bg="#061224", font=("Consolas", 7, "bold")).pack()
        after_lbl = tk.Label(right_p, text="[ Cutout Preview ]", bg="#020813", fg="#475569", width=24, height=8)
        after_lbl.pack(fill="both", expand=True, pady=2)

        def _update_source_preview(fpath):
            try:
                from PIL import Image, ImageTk
                img = Image.open(fpath)
                img.thumbnail((160, 130), Image.Resampling.LANCZOS)
                dialog._before_photo = ImageTk.PhotoImage(img)
                before_lbl.config(image=dialog._before_photo, text="")
            except Exception:
                pass

        status_lbl = tk.Label(body, text="Ready. Select source and click REMOVE BACKGROUND.", fg="#10b981", bg="#030814", font=("Consolas", 8))
        status_lbl.pack(anchor="w", pady=(0, 6))

        # Action Worker
        def _do_remove_bg():
            src = src_entry.get().strip()
            chosen_color = bg_color_var.get()

            status_lbl.config(text="⚡ Remove.bg AI processing cutout... Please wait 2-4 seconds.", fg="#f59e0b")
            self.set_reactor_state("THINKING")

            def _worker():
                from cwa_agent.core.bg_remover import bg_remover
                from PIL import Image, ImageTk

                success, out_path, msg = bg_remover.remove_background(
                    image_input=src,
                    bg_color=chosen_color,
                    auto_open=False
                )

                def _ui_update():
                    if success and out_path:
                        dialog._out_img_path = out_path
                        status_lbl.config(text=f"✔ Success! Cutout saved.", fg="#10b981")
                        self.log("system", f"[Remove.bg ✂️] {msg}\n")
                        try:
                            res_img = Image.open(out_path)
                            res_img.thumbnail((160, 130), Image.Resampling.LANCZOS)
                            dialog._after_photo = ImageTk.PhotoImage(res_img)
                            after_lbl.config(image=dialog._after_photo, text="")
                        except Exception:
                            pass
                        # Open in external viewer
                        if os.name == 'nt':
                            try:
                                os.startfile(out_path)
                            except Exception:
                                pass
                    else:
                        status_lbl.config(text=f"❌ {msg}", fg="#ef4444")
                        self.log("system", f"[Remove.bg Error] {msg}\n")
                    self.set_reactor_state("IDLE")

                self.after(0, _ui_update)

            import threading
            threading.Thread(target=_worker, daemon=True).start()

        # Action Buttons Row
        btn_frame = tk.Frame(body, bg="#030814")
        btn_frame.pack(fill="x", pady=4)

        action_btn = tk.Button(btn_frame, text="⚡ REMOVE BACKGROUND NOW", bg="#d97706", fg="#ffffff", activebackground="#b45309",
                               font=("Consolas", 9, "bold"), bd=0, padx=12, pady=6, command=_do_remove_bg)
        action_btn.pack(side="left", padx=(0, 4), fill="x", expand=True)

        def _open_bg_folder():
            from cwa_agent.config import BG_REMOVED_DIR
            if os.name == 'nt' and BG_REMOVED_DIR.exists():
                os.startfile(str(BG_REMOVED_DIR))

        def _send_tg():
            if dialog._out_img_path and os.path.exists(dialog._out_img_path):
                from cwa_agent.core.tools import send_to_telegram
                res = send_to_telegram(content_type="photo", file_path_or_query=dialog._out_img_path, text_message="Here is your cutout image!")
                status_lbl.config(text=f"✔ Sent to Telegram!", fg="#38bdf8")
            else:
                status_lbl.config(text="⚠️ Please generate a cutout first!", fg="#fbbf24")

        open_btn = tk.Button(btn_frame, text="📂 OPEN FOLDER", bg="#1e293b", fg="#cbd5e1", font=("Consolas", 8), bd=0, padx=8, pady=6, command=_open_bg_folder)
        open_btn.pack(side="left", padx=2)

        tg_btn = tk.Button(btn_frame, text="📱 TO TELEGRAM", bg="#0c4a6e", fg="#38bdf8", font=("Consolas", 8, "bold"), bd=0, padx=8, pady=6, command=_send_tg)
        tg_btn.pack(side="right", padx=(2, 0))

    def show_route_modal(self, r_data: dict = None):
        """Opens the Quantum GPS Route Navigator & Google Maps Dialog."""
        import webbrowser
        import urllib.parse

        dialog = tk.Toplevel(self)
        dialog.title("🗺️ QUANTUM GPS ROUTE NAVIGATOR // GOOGLE MAPS")
        dialog.geometry("640x560")
        dialog.configure(bg="#030814")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 320
            y = self.winfo_y() + (self.winfo_height() // 2) - 280
            dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        header = tk.Frame(dialog, bg="#061224", padx=12, pady=8, bd=1, relief="ridge")
        header.pack(fill="x")
        tk.Label(header, text="🗺️ QUANTUM GPS ROUTE & LIVE MAP NAVIGATOR", fg="#00f0ff", bg="#061224", font=("Consolas", 11, "bold")).pack(side="left")
        tk.Label(header, text="● Google Maps Platform & Traffic", fg="#10b981", bg="#061224", font=("Consolas", 8)).pack(side="right")

        body = tk.Frame(dialog, bg="#030814", padx=14, pady=10)
        body.pack(fill="both", expand=True)

        # Inputs Row
        in_frame = tk.Frame(body, bg="#061224", padx=10, pady=8, bd=1, relief="solid")
        in_frame.pack(fill="x", pady=(0, 10))

        # Origin
        r1 = tk.Frame(in_frame, bg="#061224")
        r1.pack(fill="x", pady=2)
        tk.Label(r1, text="🚩 ORIGIN (START):", fg="#10b981", bg="#061224", font=("Consolas", 8, "bold"), width=16, anchor="w").pack(side="left")
        orig_entry = tk.Entry(r1, bg="#01040a", fg="#ffffff", insertbackground="#00f0ff", font=("Consolas", 9), bd=1, relief="solid")
        orig_entry.pack(side="left", fill="x", expand=True)

        # Destination
        r2 = tk.Frame(in_frame, bg="#061224")
        r2.pack(fill="x", pady=2)
        tk.Label(r2, text="🏁 DESTINATION:", fg="#ef4444", bg="#061224", font=("Consolas", 8, "bold"), width=16, anchor="w").pack(side="left")
        dest_entry = tk.Entry(r2, bg="#01040a", fg="#ffffff", insertbackground="#00f0ff", font=("Consolas", 9), bd=1, relief="solid")
        dest_entry.pack(side="left", fill="x", expand=True)

        # Travel Mode
        r3 = tk.Frame(in_frame, bg="#061224")
        r3.pack(fill="x", pady=2)
        tk.Label(r3, text="🚗 TRAVEL MODE:", fg="#94a3b8", bg="#061224", font=("Consolas", 8, "bold"), width=16, anchor="w").pack(side="left")
        mode_var = tk.StringVar(value="driving")
        for m_lbl, m_val in [("🚗 Driving", "driving"), ("🏍️ Bike", "motorcycle"), ("🚆 Transit", "transit"), ("🚶 Walking", "walking")]:
            tk.Radiobutton(r3, text=m_lbl, variable=mode_var, value=m_val, bg="#061224", fg="#e2e8f0", selectcolor="#030814", font=("Consolas", 8)).pack(side="left", padx=4)

        # Populate if initial data provided
        if r_data:
            orig_entry.insert(0, r_data.get("origin", ""))
            dest_entry.insert(0, r_data.get("destination", ""))
            if r_data.get("travel_mode"):
                mode_var.set(r_data.get("travel_mode", "driving").lower())

        # Card Result Box
        res_card = tk.Frame(body, bg="#061224", padx=12, pady=10, bd=1, relief="ridge")
        res_card.pack(fill="both", expand=True, pady=(0, 10))

        # Big Stat Indicators (Distance & ETA)
        stats_frame = tk.Frame(res_card, bg="#061224")
        stats_frame.pack(fill="x", pady=(0, 6))

        dist_box = tk.Frame(stats_frame, bg="#01040a", padx=10, pady=8, bd=1, relief="solid")
        dist_box.pack(side="left", fill="both", expand=True, padx=(0, 4))
        tk.Label(dist_box, text="⚡ ROAD DISTANCE", fg="#64748b", bg="#01040a", font=("Consolas", 7, "bold")).pack()
        dist_val_lbl = tk.Label(dist_box, text="-- km", fg="#00f0ff", bg="#01040a", font=("Consolas", 15, "bold"))
        dist_val_lbl.pack(pady=2)

        dur_box = tk.Frame(stats_frame, bg="#01040a", padx=10, pady=8, bd=1, relief="solid")
        dur_box.pack(side="right", fill="both", expand=True, padx=(4, 0))
        tk.Label(dur_box, text="⏱️ ESTIMATED TIME", fg="#64748b", bg="#01040a", font=("Consolas", 7, "bold")).pack()
        dur_val_lbl = tk.Label(dur_box, text="-- mins", fg="#f59e0b", bg="#01040a", font=("Consolas", 15, "bold"))
        dur_val_lbl.pack(pady=2)

        # Route info details
        detail_frame = tk.Frame(res_card, bg="#061224")
        detail_frame.pack(fill="x", pady=4)

        from_to_lbl = tk.Label(detail_frame, text="Ready to calculate route...", fg="#cbd5e1", bg="#061224", font=("Consolas", 8), wraplength=580, justify="left")
        from_to_lbl.pack(anchor="w")

        summary_lbl = tk.Label(detail_frame, text="", fg="#94a3b8", bg="#061224", font=("Consolas", 8), wraplength=580, justify="left")
        summary_lbl.pack(anchor="w", pady=(2, 0))

        provider_lbl = tk.Label(detail_frame, text="", fg="#10b981", bg="#061224", font=("Consolas", 7))
        provider_lbl.pack(anchor="w", pady=(2, 0))

        dialog._current_gurl = None

        def _update_ui_with_result(data):
            if not data or not data.get("success"):
                err = data.get("error", "Failed to calculate route") if data else "Error"
                from_to_lbl.config(text=f"❌ {err}", fg="#ef4444")
                dist_val_lbl.config(text="--")
                dur_val_lbl.config(text="--")
                return

            dist_val_lbl.config(text=data.get("distance_str", "--"))
            dur_val_lbl.config(text=data.get("duration_str", "--"))
            from_to_lbl.config(
                text=f"🚩 Start: {data.get('origin_full', data.get('origin'))}\n🏁 End:   {data.get('destination_full', data.get('destination'))}",
                fg="#38bdf8"
            )
            summary_lbl.config(text=f"🛣️ Via: {data.get('summary', 'Direct Route')}")
            provider_lbl.config(text=f"📡 Provider: {data.get('provider', 'Google Maps / OSRM')}")
            dialog._current_gurl = data.get("google_maps_url")

        if r_data and r_data.get("success"):
            _update_ui_with_result(r_data)

        # Worker for calculating route
        def _calc_route():
            o = orig_entry.get().strip()
            d = dest_entry.get().strip()
            m = mode_var.get()

            if not o or not d:
                from_to_lbl.config(text="⚠️ Please enter both Origin and Destination!", fg="#fbbf24")
                return

            from_to_lbl.config(text=f"⚡ Calculating fastest route with live traffic...", fg="#f59e0b")

            def _w():
                from cwa_agent.core.route_navigator import route_navigator
                res = route_navigator.calculate_route(o, d, m)
                self.after(0, lambda: _update_ui_with_result(res))

            threading.Thread(target=_w, daemon=True).start()

        def _open_maps():
            url = dialog._current_gurl
            if not url:
                o = orig_entry.get().strip()
                d = dest_entry.get().strip()
                if o and d:
                    url = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(o)}&destination={urllib.parse.quote(d)}"
            if url:
                webbrowser.open(url)

        def _send_tg():
            if dialog._current_gurl:
                from cwa_agent.core.tools import send_to_telegram
                msg_txt = f"🗺️ Route Navigation: {orig_entry.get()} to {dest_entry.get()}\n⚡ Distance: {dist_val_lbl.cget('text')}\n⏱️ Duration: {dur_val_lbl.cget('text')}\n\n📍 Open Live Google Maps:\n{dialog._current_gurl}"
                send_to_telegram(content_type="text", text_message=msg_txt)
                from_to_lbl.config(text="✔ Route details & Google Maps link sent to Telegram!", fg="#38bdf8")

        # Action Buttons
        btn_bar = tk.Frame(body, bg="#030814")
        btn_bar.pack(fill="x")

        calc_btn = tk.Button(btn_bar, text="⚡ CALCULATE ROUTE", bg="#0284c7", fg="#ffffff", font=("Consolas", 9, "bold"), bd=0, padx=10, pady=6, command=_calc_route)
        calc_btn.pack(side="left", padx=(0, 4))

        maps_btn = tk.Button(btn_bar, text="🌐 OPEN GOOGLE MAPS", bg="#065f46", fg="#34d399", font=("Consolas", 9, "bold"), bd=0, padx=10, pady=6, command=_open_maps)
        maps_btn.pack(side="left", padx=4)

        tg_btn = tk.Button(btn_bar, text="📱 TO TELEGRAM", bg="#0c4a6e", fg="#38bdf8", font=("Consolas", 9, "bold"), bd=0, padx=10, pady=6, command=_send_tg)
        tg_btn.pack(side="left", padx=4)

        close_btn = tk.Button(btn_bar, text="✖ CLOSE", bg="#1e293b", fg="#94a3b8", font=("Consolas", 9), bd=0, padx=8, pady=6, command=dialog.destroy)
        close_btn.pack(side="right")

    def _select_persona(self, persona_name: str):
        self.current_persona.set(persona_name)
        speaker.set_persona(persona_name)
        is_mj = (persona_name == "MJ")

        # Switch center hologram avatar
        self.reactor.set_persona_mode(is_mj)

        if is_mj:
            self.mj_btn.config(bg="#be185d", fg="#ffffff")
            self.cwa_btn.config(bg="#1e293b", fg="#38bdf8")
            self.log("system", "[Persona Transferred: MJ - Female Neural Voice Activated]\n")
        else:
            self.cwa_btn.config(bg="#0284c7", fg="#ffffff")
            self.mj_btn.config(bg="#1e293b", fg="#f472b6")
            self.log("system", "[Persona Transferred: CWA - Male JARVIS Voice Activated]\n")

        if self.on_persona_switch:
            self.on_persona_switch(persona_name)

    def _toggle_theme(self):
        """Switches the HUD between Cyberpunk Stark Dark Mode and Modern Minimal Light Mode."""
        self.is_dark_theme = not self.is_dark_theme
        if self.is_dark_theme:
            self.theme_btn.config(text="☀️ LIGHT MODE", bg="#1e293b", fg="#fbbf24")
            self.configure(bg="#01040a")
            self.log_text.configure(state="normal")
            self.log_text.config(bg="#01040a", fg="#ffffff")
            self.log_text.configure(state="disabled")
            self.log("system", "[Theme Activated: Cyberpunk Dark Neon Matrix]\n")
        else:
            self.theme_btn.config(text="🌙 DARK MODE", bg="#e2e8f0", fg="#0f172a")
            self.configure(bg="#f1f5f9")
            self.log_text.configure(state="normal")
            self.log_text.config(bg="#ffffff", fg="#0f172a")
            self.log_text.configure(state="disabled")
            self.log("system", "[Theme Activated: Clean Daylight Matrix]\n")

    def _start_clock_and_telemetry(self):
        def _worker():
            while True:
                try:
                    now = datetime.datetime.now().strftime("%I:%M:%S %p")
                    cpu = psutil.cpu_percent(interval=None)
                    ram = psutil.virtual_memory().percent
                    bat = psutil.sensors_battery()
                    bat_pct = bat.percent if bat else 100

                    def _update_ui(t=now, c=cpu, r=ram, p=bat_pct):
                        try:
                            self.clock_lbl.config(text=t)
                            self.cpu_stat.config(text=f"CPU: {c}%")
                            self.ram_stat.config(text=f"RAM: {r}%")
                            self.pwr_stat.config(text=f"PWR: {p}%")
                        except Exception:
                            pass

                    self.after(0, _update_ui)
                except Exception:
                    pass
                time.sleep(1.5)

        threading.Thread(target=_worker, daemon=True).start()

    def update_download_progress(self, title: str, percent: float, speed: str = "", size_str: str = "", eta: str = "", status: str = "DOWNLOADING"):
        """Updates the live media download card and neon progress bar in real-time."""
        try:
            pct = max(0.0, min(100.0, float(percent)))
            clean_title = title if len(title) <= 32 else title[:29] + "..."

            if status == "DOWNLOADING":
                self.dl_title_lbl.config(text=f"⬇ {clean_title}", fg="#38bdf8")
                self.dl_pct_lbl.config(text=f"{pct:.1f}%", fg="#00ffcc")
                self.dl_info_lbl.config(text=f"{speed} | {size_str} (ETA: {eta})", fg="#94a3b8")

                # Draw neon gradient progress fill on canvas
                self.dl_canvas.delete("all")
                cw = self.dl_canvas.winfo_width() or 240
                ch = self.dl_canvas.winfo_height() or 12
                fill_w = int((pct / 100.0) * cw)
                if fill_w > 0:
                    self.dl_canvas.create_rectangle(0, 0, fill_w, ch, fill="#0284c7", outline="")
                    self.dl_canvas.create_rectangle(0, 0, fill_w, 2, fill="#38bdf8", outline="")

            elif status == "FINISHED":
                self.dl_title_lbl.config(text=f"✔ COMPLETED: {clean_title}", fg="#10b981")
                self.dl_pct_lbl.config(text="100%", fg="#10b981")
                self.dl_info_lbl.config(text=f"{size_str} | Saved to Downloads", fg="#6ee7b7")
                self.dl_canvas.delete("all")
                cw = self.dl_canvas.winfo_width() or 240
                ch = self.dl_canvas.winfo_height() or 12
                self.dl_canvas.create_rectangle(0, 0, cw, ch, fill="#059669", outline="")
                self.log("system", f"[Download Completed 📁] '{title}' saved directly to Downloads/CWA_Media!\n")
                # Auto-refresh / reset back to clean ready state after 5 seconds
                self.after(5000, self._reset_download_card)
        except Exception:
            pass

    def _reset_download_card(self):
        """Auto-resets the download matrix card back to clean ready state."""
        try:
            self.dl_title_lbl.config(text="● READY FOR MEDIA DOWNLOADS", fg="#64748b")
            self.dl_pct_lbl.config(text="0.0%", fg="#00ffcc")
            self.dl_info_lbl.config(text="Speed: -- | Size: --", fg="#94a3b8")
            self.dl_canvas.delete("all")
        except Exception:
            pass

    # --- Notification Sentry GUI Methods ---

    def update_notification_card(self, notif_data: dict):
        """Updates the notification sentry card in the HUD with a new incoming notification. Called from notification_sentry daemon thread via root.after."""
        try:
            app_name = notif_data.get("app", "App")
            title = notif_data.get("title", "Notification")
            body = notif_data.get("body", "")
            time_str = notif_data.get("time", "")

            # Flash the card border with amber glow for attention
            self.notif_card.config(highlightbackground="#f59e0b", highlightthickness=2)

            # Update labels
            self.notif_app_lbl.config(text=f"🔔 {app_name}", fg="#f59e0b")
            self.notif_time_lbl.config(text=time_str, fg="#94a3b8")
            self.notif_title_lbl.config(text=title[:120] if title else "New notification", fg="#e2e8f0")
            self.notif_body_lbl.config(text=body[:200] if body else "", fg="#94a3b8")

            # Enable action buttons
            self.notif_open_btn.config(state="normal", bg="#0369a1", fg="#38bdf8")
            self.notif_close_btn.config(state="normal", bg="#7f1d1d", fg="#fca5a5")

            # Store active notification data for button click handling
            self._active_notif_data = notif_data

            # Log to activity terminal
            self.log("system", f"[🔔 Notification Alert] {app_name}: {title}\n")

        except Exception as e:
            print(f"[Notification Card Update Error]: {e}")

    def _on_notif_open_click(self):
        """Handler when user clicks OPEN APP button on notification card."""
        try:
            notif = getattr(self, '_active_notif_data', None)
            if not notif:
                return

            app_name = notif.get("app", "")
            self.log("system", f"[🔔 Opening {app_name} from notification...]\n")

            # Use app_control tool to open the app dynamically
            from cwa_agent.core.notification_sentry import notification_sentry
            result = notification_sentry.handle_user_decision("open")
            self.log("assistant", f"{result}\n")

            # Reset card to standby
            self._reset_notification_card()

        except Exception as e:
            print(f"[Notification Open Error]: {e}")

    def _on_notif_dismiss_click(self):
        """Handler when user clicks DISMISS button on notification card."""
        try:
            from cwa_agent.core.notification_sentry import notification_sentry
            result = notification_sentry.handle_user_decision("close")
            self.log("system", f"[🔔 {result}]\n")

            # Reset card to standby
            self._reset_notification_card()

        except Exception as e:
            print(f"[Notification Dismiss Error]: {e}")

    def _reset_notification_card(self):
        """Resets the notification card back to standby state."""
        try:
            self.notif_card.config(highlightbackground="#0284c7", highlightthickness=1)
            self.notif_app_lbl.config(text="● SENTRY ACTIVE // STANDBY", fg="#10b981")
            self.notif_time_lbl.config(text="")
            self.notif_title_lbl.config(text="No active notifications", fg="#64748b")
            self.notif_body_lbl.config(text="Listening for all incoming system & app alerts...", fg="#475569")
            self.notif_open_btn.config(state="disabled", bg="#0c2340", fg="#475569")
            self.notif_close_btn.config(state="disabled", bg="#0c2340", fg="#475569")
            self._active_notif_data = None
        except Exception:
            pass

    # --- Quantum Neural Tic-Tac-Toe GUI Engine ---

    def _update_ttt_scoreboard(self):
        """Refreshes the live scoreboard display."""
        try:
            from cwa_agent.core.tictactoe_engine import ttt_engine
            u = ttt_engine.scores["user"]
            a = ttt_engine.scores["ai"]
            d = ttt_engine.scores["draws"]
            self.ttt_score_lbl.config(text=f"ALI: {u} | CWA: {a} | D: {d}")
        except Exception:
            pass

    def _on_ttt_cell_click(self, idx: int):
        """Executes user move when clicking a grid cell."""
        try:
            from cwa_agent.core.tictactoe_engine import ttt_engine
            from cwa_agent.core.speaker import speaker

            if ttt_engine.game_over:
                self.log("system", "[Tic-Tac-Toe] Game over. Click 'NEW' to start a new match.\n")
                return

            success, winner, msg = ttt_engine.make_user_move(idx)
            if not success:
                return

            # Update clicked button to X (Neon Cyan)
            self.ttt_buttons[idx].config(text="X", fg="#00f0ff", bg="#0a192f")

            if winner == 'X':
                self._update_ttt_scoreboard()
                self.ttt_status_lbl.config(text="🏆 ALI WON!", fg="#fbbf24")
                self.ttt_card.config(highlightbackground="#fbbf24", highlightthickness=2)
                # Highlight winning line
                for pos in ttt_engine.winning_line:
                    self.ttt_buttons[pos].config(bg="#1e3a8a", fg="#fbbf24")
                self.log("assistant", f"🏆 Shandar Ali! Aap yeh round jeet gaye!\n")
                speaker.speak("Shandar Ali! Aap yeh round jeet gaye! Kya ek aur match khelein?")
                self.after(400, lambda: self._show_ttt_gameover_modal('X'))
                return

            elif winner == 'Draw':
                self._update_ttt_scoreboard()
                self.ttt_status_lbl.config(text="🤝 MATCH DRAW!", fg="#38bdf8")
                self.log("system", f"🤝 Match tie ho gaya! Kadi takkar thi.\n")
                speaker.speak("Match tie ho gaya Ali! Kadi takkar thi.")
                self.after(400, lambda: self._show_ttt_gameover_modal('Draw'))
                return

            # Game continues -> AI Turn
            self.ttt_status_lbl.config(text="🤖 CWA THINKING...", fg="#f59e0b")
            self.after(300, self._do_ttt_ai_move)

        except Exception as e:
            print(f"[TicTacToe Click Error]: {e}")

    def _do_ttt_ai_move(self):
        """Executes AI's turn with Minimax decision and voice commentary."""
        try:
            from cwa_agent.core.tictactoe_engine import ttt_engine
            from cwa_agent.core.speaker import speaker

            if ttt_engine.game_over:
                return

            pos, winner, commentary = ttt_engine.make_ai_move()
            if pos >= 0:
                self.ttt_buttons[pos].config(text="O", fg="#f43f5e", bg="#0a192f")

            if winner == 'O':
                self._update_ttt_scoreboard()
                self.ttt_status_lbl.config(text="🤖 CWA WON!", fg="#f43f5e")
                self.ttt_card.config(highlightbackground="#f43f5e", highlightthickness=2)
                for p in ttt_engine.winning_line:
                    self.ttt_buttons[p].config(bg="#881337", fg="#fbbf24")
                self.log("assistant", f"{commentary}\n")
                speaker.speak(commentary)
                self.after(400, lambda: self._show_ttt_gameover_modal('O'))

            elif winner == 'Draw':
                self._update_ttt_scoreboard()
                self.ttt_status_lbl.config(text="🤝 MATCH DRAW!", fg="#38bdf8")
                self.log("system", f"{commentary}\n")
                speaker.speak(commentary)
                self.after(400, lambda: self._show_ttt_gameover_modal('Draw'))

            else:
                self.ttt_status_lbl.config(text="● YOUR TURN (X)", fg="#10b981")
                if commentary:
                    self.log("system", f"[CWA Game]: {commentary}\n")

        except Exception as e:
            print(f"[TicTacToe AI Move Error]: {e}")

    def _show_ttt_gameover_modal(self, winner: str):
        """Displays an instant, sleek Stark HUD Game-Over Pop-up Modal with score summary and restart button."""
        try:
            from cwa_agent.core.tictactoe_engine import ttt_engine
            from cwa_agent.config import USER_NAME

            modal = tk.Toplevel(self)
            modal.title("Quantum Arena // Match Result")
            modal.geometry("380x290")
            modal.configure(bg="#030814")
            modal.attributes("-topmost", True)
            modal.resizable(False, False)

            # Center modal on screen
            self.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - 190
            y = self.winfo_y() + (self.winfo_height() // 2) - 145
            modal.geometry(f"+{max(0, x)}+{max(0, y)}")

            # Container with glowing border
            border_color = "#fbbf24" if winner == 'X' else "#f43f5e" if winner == 'O' else "#38bdf8"
            container = tk.Frame(modal, bg="#061224", bd=2, relief="ridge", highlightbackground=border_color, highlightthickness=1)
            container.pack(fill="both", expand=True, padx=8, pady=8)

            # Header Tag
            tk.Label(container, text="[ 🎮 QUANTUM ARENA // MATCH RESULT ]", fg=border_color, bg="#061224", font=("Consolas", 8, "bold")).pack(pady=(10, 4))

            # Winner Banner Icon & Title
            u_name = USER_NAME or "Sir"
            if winner == 'X':
                main_txt = "🏆 VICTORY!"
                sub_txt = f"Shandar Khel {u_name}! Aap Jeet Gaye!"
                tag_fg = "#fbbf24"
            elif winner == 'O':
                main_txt = "🤖 CWA VICTORY!"
                sub_txt = f"Maine Yeh Round Jeet Liya, {u_name}!"
                tag_fg = "#f43f5e"
            else:
                main_txt = "🤝 MATCH DRAW!"
                sub_txt = f"Solid Game! Kadi Takkar Thi {u_name}!"
                tag_fg = "#38bdf8"

            tk.Label(container, text=main_txt, fg=tag_fg, bg="#061224", font=("Consolas", 18, "bold")).pack(pady=(4, 2))
            tk.Label(container, text=sub_txt, fg="#e2e8f0", bg="#061224", font=("Consolas", 9)).pack(pady=(0, 10))

            # Score Summary Box
            score_box = tk.Frame(container, bg="#0a192f", bd=1, relief="ridge", padx=10, pady=8)
            score_box.pack(fill="x", padx=16, pady=4)

            u = ttt_engine.scores["user"]
            a = ttt_engine.scores["ai"]
            d = ttt_engine.scores["draws"]

            tk.Label(score_box, text=f"ALI (X): {u}   |   CWA (O): {a}   |   DRAWS: {d}", fg="#fbbf24", bg="#0a192f", font=("Consolas", 9, "bold")).pack()

            # Buttons: Play Again / Restart & Close
            btn_row = tk.Frame(container, bg="#061224")
            btn_row.pack(fill="x", padx=16, pady=(14, 8))

            def _on_play_again():
                modal.destroy()
                self._on_ttt_new_game()

            play_btn = tk.Button(btn_row, text="🔄 PLAY AGAIN / RESTART", bg="#0284c7", fg="#ffffff", activebackground="#0369a1",
                                 activeforeground="#ffffff", font=("Consolas", 9, "bold"), bd=0, pady=6,
                                 command=_on_play_again)
            play_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

            close_btn = tk.Button(btn_row, text="❌ CLOSE", bg="#1e293b", fg="#94a3b8", activebackground="#334155",
                                  activeforeground="#ffffff", font=("Consolas", 9), bd=0, pady=6,
                                  command=modal.destroy)
            close_btn.pack(side="right", fill="x", expand=True, padx=(4, 0))

        except Exception as e:
            print(f"[GameOver Modal Error]: {e}")

    def _on_ttt_new_game(self):
        """Resets board for a new game."""
        try:
            from cwa_agent.core.tictactoe_engine import ttt_engine
            ttt_engine.reset_game()
            for btn in self.ttt_buttons:
                btn.config(text=" ", bg="#0a192f", fg="#00f0ff")
            self.ttt_card.config(highlightbackground="#0284c7", highlightthickness=1)
            self.ttt_status_lbl.config(text="● YOUR TURN (X)", fg="#10b981")
            self.log("system", "[Tic-Tac-Toe] Naya game shuru! Pehli move aapki hai (X).\n")
        except Exception:
            pass

    def _on_ttt_ai_first(self):
        """Starts new game with CWA making the first move."""
        try:
            from cwa_agent.core.tictactoe_engine import ttt_engine
            from cwa_agent.core.speaker import speaker
            ttt_engine.reset_game(start_ai=True)
            for btn in self.ttt_buttons:
                btn.config(text=" ", bg="#0a192f", fg="#00f0ff")
            self.ttt_card.config(highlightbackground="#0284c7", highlightthickness=1)
            self.ttt_status_lbl.config(text="🤖 CWA THINKING...", fg="#f59e0b")
            speaker.speak("Game shuru! Pehli move main chal raha hoon.")
            self.after(300, self._do_ttt_ai_move)
        except Exception:
            pass

    def _on_ttt_reset_scores(self):
        """Resets all scores and board."""
        try:
            from cwa_agent.core.tictactoe_engine import ttt_engine
            ttt_engine.reset_all_scores()
            for btn in self.ttt_buttons:
                btn.config(text=" ", bg="#0a192f", fg="#00f0ff")
            self.ttt_score_lbl.config(text="ALI: 0 | CWA: 0 | D: 0")
            self.ttt_card.config(highlightbackground="#0284c7", highlightthickness=1)
            self.ttt_status_lbl.config(text="● YOUR TURN (X)", fg="#10b981")
            self.log("system", "[Tic-Tac-Toe] Scoreboard reset ho gaya!\n")
        except Exception:
            pass

    def _toggle_ttt_panel(self):
        """Toggles expanding/collapsing the Tic-Tac-Toe arena to save space on the left HUD panel."""
        try:
            if self.ttt_is_expanded:
                self.ttt_card.pack_forget()
                self.ttt_toggle_btn.config(text="▼ OPEN GAME", bg="#0c4a6e", fg="#38bdf8")
                self.ttt_is_expanded = False
            else:
                self.ttt_card.pack(fill="x")
                self.ttt_toggle_btn.config(text="▲ CLOSE GAME", bg="#1e293b", fg="#94a3b8")
                self.ttt_is_expanded = True
        except Exception:
            pass

    def expand_ttt_panel(self):
        """Ensures the Tic-Tac-Toe arena is opened/expanded when user requests to play."""
        try:
            if not getattr(self, "ttt_is_expanded", True):
                self.ttt_card.pack(fill="x")
                self.ttt_toggle_btn.config(text="▲ CLOSE GAME", bg="#1e293b", fg="#94a3b8")
                self.ttt_is_expanded = True
        except Exception:
            pass

    # --- Smart Clipboard Manager Toggle & Handlers ---

    def _toggle_clipboard_panel(self):
        """Toggles Smart Clipboard Manager panel open/closed."""
        try:
            if self.clip_is_expanded:
                self.clip_card.pack_forget()
                self.clip_toggle_btn.config(text="▼ OPEN", bg="#0c4a6e", fg="#38bdf8")
                self.clip_is_expanded = False
            else:
                self.clip_card.pack(fill="x")
                self.clip_toggle_btn.config(text="▲ CLOSE", bg="#1e293b", fg="#94a3b8")
                self.clip_is_expanded = True
        except Exception:
            pass

    def update_clipboard_history(self, entry: dict):
        """Called when a new item is copied to clipboard — updates the listbox."""
        def _do():
            try:
                from cwa_agent.core.clipboard_manager import clipboard_manager
                self.clip_listbox.delete(0, "end")
                for item in clipboard_manager.history:
                    preview = item.get("preview", "")[:55]
                    ts = item.get("timestamp", "")
                    self.clip_listbox.insert("end", f"[{ts}] {preview}")
                self.clip_count_lbl.config(text=f"{len(clipboard_manager.history)} items")
            except Exception:
                pass
        self.after(0, _do)

    def _on_clipboard_copy_selected(self):
        """Copies the selected history item back to the system clipboard."""
        try:
            from cwa_agent.core.clipboard_manager import clipboard_manager
            sel = self.clip_listbox.curselection()
            if not sel:
                self.clip_status_lbl.config(text="⚠️ Select an item first", fg="#f59e0b")
                return
            idx = sel[0]
            text = clipboard_manager.copy_item(idx)
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
                self.clip_status_lbl.config(text="✔ Copied to clipboard!", fg="#10b981")
                self.after(2000, lambda: self.clip_status_lbl.config(text="● MONITORING CLIPBOARD", fg="#a78bfa"))
        except Exception:
            pass

    def _on_clipboard_clear(self):
        """Clears all clipboard history."""
        try:
            from cwa_agent.core.clipboard_manager import clipboard_manager
            clipboard_manager.clear_history()
            self.clip_listbox.delete(0, "end")
            self.clip_count_lbl.config(text="0 items")
            self.clip_status_lbl.config(text="✔ History cleared", fg="#10b981")
            self.after(2000, lambda: self.clip_status_lbl.config(text="● MONITORING CLIPBOARD", fg="#a78bfa"))
        except Exception:
            pass

    # --- Network & WiFi Monitor Toggle & Handlers ---

    def _toggle_network_panel(self):
        """Toggles Network & WiFi Monitor panel open/closed."""
        try:
            if self.net_is_expanded:
                self.net_card.pack_forget()
                self.net_toggle_btn.config(text="▼ OPEN", bg="#064e3b", fg="#34d399")
                self.net_is_expanded = False
            else:
                self.net_card.pack(fill="x")
                self.net_toggle_btn.config(text="▲ CLOSE", bg="#1e293b", fg="#94a3b8")
                self.net_is_expanded = True
        except Exception:
            pass

    def update_network_stats(self, stats: dict):
        """Updates the network monitor card with live stats."""
        def _do():
            try:
                connected = stats.get("connected", False)
                ping = stats.get("ping_ms")
                ssid = stats.get("ssid")
                ip = stats.get("ip", "N/A")
                adapter = stats.get("adapter", "---")
                last = stats.get("last_checked", "")

                if connected:
                    self.net_dot_lbl.config(fg="#10b981")
                    self.net_status_lbl.config(text="ONLINE", fg="#10b981")

                    # Ping color: green <50ms, yellow 50-150ms, red >150ms
                    if ping is not None:
                        ping_color = "#10b981" if ping < 50 else "#fbbf24" if ping < 150 else "#ef4444"
                        self.net_ping_lbl.config(text=f"Ping: {ping} ms", fg=ping_color)
                        # Draw ping quality bar
                        self.net_ping_canvas.delete("all")
                        w = self.net_ping_canvas.winfo_width() or 220
                        # Normalize: 0ms = full bar, 300ms = minimal bar
                        fill_ratio = max(0.05, 1.0 - min(ping / 300.0, 1.0))
                        self.net_ping_canvas.create_rectangle(0, 0, w, 8, fill="#0a2015", outline="")
                        self.net_ping_canvas.create_rectangle(0, 0, int(w * fill_ratio), 8, fill=ping_color, outline="")
                else:
                    self.net_dot_lbl.config(fg="#ef4444")
                    self.net_status_lbl.config(text="OFFLINE", fg="#ef4444")
                    self.net_ping_lbl.config(text="Ping: N/A", fg="#ef4444")
                    self.net_ping_canvas.delete("all")
                    w = self.net_ping_canvas.winfo_width() or 220
                    self.net_ping_canvas.create_rectangle(0, 0, w, 8, fill="#2d0a0a", outline="")

                self.net_ssid_lbl.config(text=ssid if ssid else "Ethernet/LAN")
                self.net_ip_lbl.config(text=ip)
                self.net_adapter_lbl.config(text=adapter[:18] if adapter else "---")
                self.net_last_lbl.config(text=f"Last updated: {last}")
            except Exception:
                pass
        self.after(0, _do)

    def _on_network_refresh(self):
        """Manually triggers a network stats refresh."""
        try:
            from cwa_agent.core.network_monitor import network_monitor
            self.net_last_lbl.config(text="Refreshing...")
            import threading
            def _worker():
                stats = {
                    "connected": network_monitor._ping_host() is not None,
                    "ping_ms": network_monitor._ping_host(),
                    "ssid": network_monitor._get_wifi_ssid(),
                    "ip": network_monitor._get_local_ip(),
                    "adapter": network_monitor._get_adapter_name(),
                    "last_checked": __import__("datetime").datetime.now().strftime("%H:%M:%S")
                }
                self.update_network_stats(stats)
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            pass

    # --- Ignore Words Manager Toggle & Handlers ---

    def _toggle_iw_panel(self):
        """Toggles Ignore Words Manager panel open/closed."""
        try:
            if self.iw_is_expanded:
                self.iw_card.pack_forget()
                self.iw_toggle_btn.config(text="▼ OPEN", bg="#7c2d12", fg="#fb923c")
                self.iw_is_expanded = False
            else:
                self.iw_card.pack(fill="x")
                self.iw_toggle_btn.config(text="▲ CLOSE", bg="#1e293b", fg="#94a3b8")
                self.iw_is_expanded = True
                self._refresh_iw_lists()
        except Exception:
            pass

    def _refresh_iw_lists(self):
        """Refreshes forbidden words and word replacements listboxes in HUD."""
        try:
            from cwa_agent.core.ignore_words import ignore_words_manager
            self.iw_forb_listbox.delete(0, "end")
            self.iw_repl_listbox.delete(0, "end")

            # Load Male rules
            for w in ignore_words_manager.male_rules.get("forbidden_words", []):
                self.iw_forb_listbox.insert("end", f"👨 [MALE] {w}")
            for k, v in ignore_words_manager.male_rules.get("word_replacements", {}).items():
                self.iw_repl_listbox.insert("end", f"👨 [MALE] '{k}' ➔ '{v}'")

            # Load Female rules
            for w in ignore_words_manager.female_rules.get("forbidden_words", []):
                self.iw_forb_listbox.insert("end", f"👩 [FEMALE] {w}")
            for k, v in ignore_words_manager.female_rules.get("word_replacements", {}).items():
                self.iw_repl_listbox.insert("end", f"👩 [FEMALE] '{k}' ➔ '{v}'")

            # Load Global rules
            for w in ignore_words_manager.global_rules.get("forbidden_words", []):
                self.iw_forb_listbox.insert("end", f"🌐 [GLOBAL] {w}")
            for k, v in ignore_words_manager.global_rules.get("word_replacements", {}).items():
                self.iw_repl_listbox.insert("end", f"🌐 [GLOBAL] '{k}' ➔ '{v}'")

        except Exception as e:
            print(f"[HUD IW Error] Refresh failed: {e}")

    def _iw_add_forbidden(self):
        """Adds a forbidden word from HUD input to ignore_words_manager."""
        try:
            from cwa_agent.core.ignore_words import ignore_words_manager
            word = self.iw_word_entry.get().strip()
            if not word:
                self.iw_status_lbl.config(text="⚠️ Please enter a word in the WORD box.", fg="#f87171")
                return
            persona = self.iw_persona_var.get()
            msg = ignore_words_manager.add_forbidden_word(word, persona=persona)
            self.iw_word_entry.delete(0, "end")
            self.iw_status_lbl.config(text=f"✔ Added '{word}' to forbidden list ({persona})", fg="#34d399")
            self._refresh_iw_lists()
            self.log("system", f"[Ignore Words] Added forbidden word: '{word}' ({persona})\n")
        except Exception as e:
            self.iw_status_lbl.config(text=f"❌ Error: {e}", fg="#f87171")

    def _iw_add_replacement(self):
        """Adds a word replacement rule from HUD input."""
        try:
            from cwa_agent.core.ignore_words import ignore_words_manager
            word = self.iw_word_entry.get().strip()
            repl = self.iw_replace_entry.get().strip()
            if not word:
                self.iw_status_lbl.config(text="⚠️ Please enter a word in the WORD box.", fg="#f87171")
                return
            persona = self.iw_persona_var.get()
            msg = ignore_words_manager.add_word_replacement(word, replace_with=repl, persona=persona)
            self.iw_word_entry.delete(0, "end")
            self.iw_replace_entry.delete(0, "end")
            self.iw_status_lbl.config(text=f"✔ Rule: '{word}' ➔ '{repl}' ({persona})", fg="#34d399")
            self._refresh_iw_lists()
            self.log("system", f"[Ignore Words] Added replacement: '{word}' ➔ '{repl}' ({persona})\n")
        except Exception as e:
            self.iw_status_lbl.config(text=f"❌ Error: {e}", fg="#f87171")

    def _iw_delete_selected(self):
        """Deletes selected rule from either forbidden or replacement listbox."""
        try:
            from cwa_agent.core.ignore_words import ignore_words_manager
            import re
            
            # Check forbidden selection
            forb_sel = self.iw_forb_listbox.curselection()
            if forb_sel:
                text = self.iw_forb_listbox.get(forb_sel[0])
                # Format: "👨 [MALE] word"
                persona = "male" if "[MALE]" in text else "female" if "[FEMALE]" in text else "global"
                word = re.sub(r"^.*?\]\s*", "", text).strip()
                ignore_words_manager.remove_rule(word, persona=persona)
                self.iw_status_lbl.config(text=f"✔ Deleted forbidden word '{word}' ({persona})", fg="#34d399")
                self._refresh_iw_lists()
                return

            # Check replacement selection
            repl_sel = self.iw_repl_listbox.curselection()
            if repl_sel:
                text = self.iw_repl_listbox.get(repl_sel[0])
                # Format: "👨 [MALE] 'orig' ➔ 'repl'"
                persona = "male" if "[MALE]" in text else "female" if "[FEMALE]" in text else "global"
                m = re.search(r"'([^']+)'\s*➔", text)
                if m:
                    word = m.group(1)
                    ignore_words_manager.remove_rule(word, persona=persona)
                    self.iw_status_lbl.config(text=f"✔ Deleted replacement '{word}' ({persona})", fg="#34d399")
                    self._refresh_iw_lists()
                    return

            self.iw_status_lbl.config(text="⚠️ Select an item from either list first.", fg="#fbbf24")
        except Exception as e:
            self.iw_status_lbl.config(text=f"❌ Error: {e}", fg="#f87171")

    def _open_iw_manager_dialog(self):
        """Opens a dedicated floating dialog for full Ignore Words Manager."""
        try:
            from cwa_agent.core.ignore_words import ignore_words_manager
            import re

            dlg = tk.Toplevel(self)
            dlg.title("JARVIS OS // IGNORE & FORBIDDEN WORDS MANAGER")
            dlg.geometry("520x560")
            dlg.configure(bg="#050b14")
            dlg.resizable(True, True)
            dlg.transient(self)

            # Header
            head = tk.Frame(dlg, bg="#0b172a", pady=10, padx=12)
            head.pack(fill="x")
            tk.Label(head, text="🚫 PERSONA IGNORE & WORD REPLACEMENT MANAGER", fg="#f97316", bg="#0b172a", font=("Consolas", 11, "bold")).pack(anchor="w")
            tk.Label(head, text="Manage forbidden words & word replacements for Male (CWA) & Female (MJ)", fg="#64748b", bg="#0b172a", font=("Consolas", 8)).pack(anchor="w")

            content = tk.Frame(dlg, bg="#050b14", padx=14, pady=10)
            content.pack(fill="both", expand=True)

            # Persona choice
            p_row = tk.Frame(content, bg="#050b14")
            p_row.pack(fill="x", pady=(0, 8))
            tk.Label(p_row, text="TARGET PERSONA:", fg="#94a3b8", bg="#050b14", font=("Consolas", 9, "bold")).pack(side="left", padx=(0, 8))

            dlg_p_var = tk.StringVar(value="female")
            for p_val, p_text, p_color in [("male", "👨 MALE (CWA)", "#38bdf8"), ("female", "👩 FEMALE (MJ)", "#f472b6"), ("both", "🌐 GLOBAL (BOTH)", "#34d399")]:
                tk.Radiobutton(p_row, text=p_text, variable=dlg_p_var, value=p_val,
                               bg="#050b14", fg=p_color, selectcolor="#0f172a", activebackground="#050b14",
                               activeforeground=p_color, font=("Consolas", 8, "bold"), bd=0).pack(side="left", padx=4)

            # Input fields
            in_grid = tk.Frame(content, bg="#0b172a", padx=10, pady=8, bd=1, relief="ridge")
            in_grid.pack(fill="x", pady=(0, 10))

            # Word row
            w_row = tk.Frame(in_grid, bg="#0b172a")
            w_row.pack(fill="x", pady=2)
            tk.Label(w_row, text="Word / Phrase:", fg="#cbd5e1", bg="#0b172a", font=("Consolas", 8, "bold"), width=16, anchor="w").pack(side="left")
            w_entry = tk.Entry(w_row, bg="#030712", fg="#fb923c", insertbackground="#fb923c", font=("Consolas", 9, "bold"), bd=1, relief="ridge")
            w_entry.pack(side="left", fill="x", expand=True, ipady=3)

            # Replace row
            r_row = tk.Frame(in_grid, bg="#0b172a")
            r_row.pack(fill="x", pady=4)
            tk.Label(r_row, text="Replace With:", fg="#cbd5e1", bg="#0b172a", font=("Consolas", 8, "bold"), width=16, anchor="w").pack(side="left")
            r_entry = tk.Entry(r_row, bg="#030712", fg="#34d399", insertbackground="#34d399", font=("Consolas", 9, "bold"), bd=1, relief="ridge")
            r_entry.pack(side="left", fill="x", expand=True, ipady=3)

            # Action buttons
            btn_box = tk.Frame(in_grid, bg="#0b172a")
            btn_box.pack(fill="x", pady=(6, 2))

            status_lbl = tk.Label(content, text="Ready. Enter word and choose action.", fg="#64748b", bg="#050b14", font=("Consolas", 8))
            status_lbl.pack(fill="x", pady=(0, 6))

            # Listboxes
            list_split = tk.Frame(content, bg="#050b14")
            list_split.pack(fill="both", expand=True)

            # Left list: Forbidden
            f_box = tk.Frame(list_split, bg="#050b14")
            f_box.pack(side="left", fill="both", expand=True, padx=(0, 4))
            tk.Label(f_box, text="🚫 FORBIDDEN WORDS:", fg="#f97316", bg="#050b14", font=("Consolas", 8, "bold")).pack(anchor="w")
            
            f_list_f = tk.Frame(f_box, bg="#050b14")
            f_list_f.pack(fill="both", expand=True)
            dlg_forb_lb = tk.Listbox(f_list_f, bg="#030712", fg="#fca5a5", selectbackground="#7c2d12", font=("Consolas", 8), bd=1, relief="ridge")
            dlg_forb_lb.pack(side="left", fill="both", expand=True)
            f_sb = tk.Scrollbar(f_list_f, orient="vertical", command=dlg_forb_lb.yview)
            f_sb.pack(side="right", fill="y")
            dlg_forb_lb.config(yscrollcommand=f_sb.set)

            # Right list: Replacements
            r_box = tk.Frame(list_split, bg="#050b14")
            r_box.pack(side="right", fill="both", expand=True, padx=(4, 0))
            tk.Label(r_box, text="🔄 REPLACEMENTS:", fg="#34d399", bg="#050b14", font=("Consolas", 8, "bold")).pack(anchor="w")
            
            r_list_f = tk.Frame(r_box, bg="#050b14")
            r_list_f.pack(fill="both", expand=True)
            dlg_repl_lb = tk.Listbox(r_list_f, bg="#030712", fg="#86efac", selectbackground="#14532d", font=("Consolas", 8), bd=1, relief="ridge")
            dlg_repl_lb.pack(side="left", fill="both", expand=True)
            r_sb = tk.Scrollbar(r_list_f, orient="vertical", command=dlg_repl_lb.yview)
            r_sb.pack(side="right", fill="y")
            dlg_repl_lb.config(yscrollcommand=r_sb.set)

            def _refresh():
                dlg_forb_lb.delete(0, "end")
                dlg_repl_lb.delete(0, "end")
                for w in ignore_words_manager.male_rules.get("forbidden_words", []):
                    dlg_forb_lb.insert("end", f"👨 [MALE] {w}")
                for k, v in ignore_words_manager.male_rules.get("word_replacements", {}).items():
                    dlg_repl_lb.insert("end", f"👨 [MALE] '{k}' ➔ '{v}'")

                for w in ignore_words_manager.female_rules.get("forbidden_words", []):
                    dlg_forb_lb.insert("end", f"👩 [FEMALE] {w}")
                for k, v in ignore_words_manager.female_rules.get("word_replacements", {}).items():
                    dlg_repl_lb.insert("end", f"👩 [FEMALE] '{k}' ➔ '{v}'")

                for w in ignore_words_manager.global_rules.get("forbidden_words", []):
                    dlg_forb_lb.insert("end", f"🌐 [GLOBAL] {w}")
                for k, v in ignore_words_manager.global_rules.get("word_replacements", {}).items():
                    dlg_repl_lb.insert("end", f"🌐 [GLOBAL] '{k}' ➔ '{v}'")
                self._refresh_iw_lists()

            def _do_forbid():
                word = w_entry.get().strip()
                if not word:
                    status_lbl.config(text="⚠️ Enter a word in 'Word / Phrase' box.", fg="#f87171")
                    return
                p = dlg_p_var.get()
                ignore_words_manager.add_forbidden_word(word, persona=p)
                w_entry.delete(0, "end")
                status_lbl.config(text=f"✔ Banned '{word}' for {p.upper()}", fg="#34d399")
                _refresh()

            def _do_replace():
                word = w_entry.get().strip()
                repl = r_entry.get().strip()
                if not word:
                    status_lbl.config(text="⚠️ Enter word to replace.", fg="#f87171")
                    return
                p = dlg_p_var.get()
                ignore_words_manager.add_word_replacement(word, replace_with=repl, persona=p)
                w_entry.delete(0, "end")
                r_entry.delete(0, "end")
                status_lbl.config(text=f"✔ Added rule: '{word}' ➔ '{repl}' for {p.upper()}", fg="#34d399")
                _refresh()

            def _do_del():
                f_sel = dlg_forb_lb.curselection()
                if f_sel:
                    t = dlg_forb_lb.get(f_sel[0])
                    p = "male" if "[MALE]" in t else "female" if "[FEMALE]" in t else "global"
                    w = re.sub(r"^.*?\]\s*", "", t).strip()
                    ignore_words_manager.remove_rule(w, persona=p)
                    status_lbl.config(text=f"✔ Deleted forbidden word '{w}' ({p})", fg="#34d399")
                    _refresh()
                    return
                r_sel = dlg_repl_lb.curselection()
                if r_sel:
                    t = dlg_repl_lb.get(r_sel[0])
                    p = "male" if "[MALE]" in t else "female" if "[FEMALE]" in t else "global"
                    m = re.search(r"'([^']+)'\s*➔", t)
                    if m:
                        w = m.group(1)
                        ignore_words_manager.remove_rule(w, persona=p)
                        status_lbl.config(text=f"✔ Deleted replacement '{w}' ({p})", fg="#34d399")
                        _refresh()
                        return
                status_lbl.config(text="⚠️ Select an item from either list to delete.", fg="#fbbf24")

            tk.Button(btn_box, text="🚫 FORBID WORD", bg="#7c2d12", fg="#fca5a5", activebackground="#991b1b",
                      activeforeground="#ffffff", font=("Consolas", 8, "bold"), bd=0, pady=5, command=_do_forbid
                      ).pack(side="left", fill="x", expand=True, padx=(0, 2))

            tk.Button(btn_box, text="🔄 ADD REPLACEMENT", bg="#14532d", fg="#86efac", activebackground="#166534",
                      activeforeground="#ffffff", font=("Consolas", 8, "bold"), bd=0, pady=5, command=_do_replace
                      ).pack(side="left", fill="x", expand=True, padx=(2, 2))

            tk.Button(btn_box, text="🗑️ DELETE SELECTED", bg="#1e293b", fg="#94a3b8", activebackground="#334155",
                      activeforeground="#ffffff", font=("Consolas", 8, "bold"), bd=0, pady=5, command=_do_del
                      ).pack(side="left", fill="x", expand=True, padx=(2, 0))

            _refresh()

        except Exception as e:
            print(f"[IW Dialog Error]: {e}")

    def _toggle_always_listen(self):
        new_val = not self.always_listen_enabled.get()
        self.always_listen_enabled.set(new_val)
        if new_val:
            self.always_listen_btn.config(text="⚡ HANDS-FREE: ON (Auto-Listen)", bg="#065f46", fg="#10b981")
            self.sys_status_tag.config(text="● AUTO-LISTENING", fg="#10b981")
            self.log("system", "[Hands-Free Activated: Continuous Auto-Listening Enabled]\n")
        else:
            self.always_listen_btn.config(text="⚡ HANDS-FREE: OFF", bg="#1f2937", fg="#9ca3af")
            self.sys_status_tag.config(text="● MANUAL MODE", fg="#94a3b8")
            self.log("system", "[Hands-Free Deactivated: Manual Mic Mode Enabled]\n")

        if self.on_always_listen_toggle:
            self.on_always_listen_toggle(new_val)

    def _handle_mic(self):
        if self.on_mic_toggle:
            self.on_mic_toggle()

    def _handle_vision(self):
        if self.on_vision_trigger:
            self.on_vision_trigger()

    def _send_quick_chip(self, query: str):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, query)
        self._send_text()

    def _on_entry_paste(self, event=None):
        """Intercepts Ctrl+V in the chat text entry to check if clipboard contains an image/screenshot."""
        handled = self._handle_clipboard_image()
        if handled:
            return "break"  # prevent Tkinter from pasting binary/invalid string
        return None  # allow standard text paste

    def _on_global_paste(self, event=None):
        """Intercepts Ctrl+V globally across the HUD window."""
        handled = self._handle_clipboard_image()
        if handled:
            return "break"
        return None

    def _handle_clipboard_image(self) -> bool:
        """Grabs screenshot/image from Windows clipboard (Win+Shift+S / PrintScreen / Copied file), saves it, and attaches to HUD chat."""
        try:
            from PIL import ImageGrab, Image
            from cwa_agent.config import SCREENSHOTS_DIR

            cb_data = ImageGrab.grabclipboard()
            if cb_data is None:
                return False

            SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())

            # Case 1: Direct PIL Image in clipboard (Win+Shift+S / Snipping Tool / Screenshot)
            if isinstance(cb_data, Image.Image):
                save_path = str(SCREENSHOTS_DIR / f"clipboard_snap_{timestamp}.png")
                cb_data.save(save_path)
                self._attach_screenshot(save_path)
                return True

            # Case 2: List of file paths copied to clipboard
            if isinstance(cb_data, list):
                for fp in cb_data:
                    ext = os.path.splitext(str(fp))[1].lower()
                    if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]:
                        self._attach_screenshot(str(fp))
                        return True

            return False
        except Exception as e:
            print(f"[HUD Clipboard Image Notice]: {e}")
            return False

    def _attach_screenshot(self, filepath: str):
        """Displays screenshot thumbnail preview in attachment bar right above chat entry."""
        try:
            from PIL import Image, ImageTk
            self._pending_attached_image = filepath
            img = Image.open(filepath)
            img.thumbnail((60, 45), Image.Resampling.LANCZOS)
            self._attached_photo_ref = ImageTk.PhotoImage(img)
            self.attach_thumb_lbl.config(image=self._attached_photo_ref, text="")

            fname = os.path.basename(filepath)
            self.attach_title_lbl.config(text=f"📸 SCREENSHOT ATTACHED: {fname[:24]}")
            self.attach_desc_lbl.config(text="Type your question / prompt or press EXECUTE (Enter) to analyze & solve.")
            self.attach_preview_frame.pack(fill="x", pady=(0, 2), before=self.text_deck)
            self.entry.focus_set()
            self.log("system", f"[📸 Screenshot attached: {fname} — Press EXECUTE or type your question]\n")
        except Exception as e:
            print(f"[HUD Attach Error]: {e}")

    def _clear_attached_screenshot(self, keep_file: bool = False):
        """Removes the attached screenshot preview."""
        self._pending_attached_image = None
        self._attached_photo_ref = None
        self.attach_preview_frame.pack_forget()

    def _snip_screen_now(self):
        """Instantly captures the screen and attaches it to the chat input for vision analysis."""
        try:
            from cwa_agent.core.vision import vision
            self.log("system", "[📸 Capturing desktop screenshot...]\n")
            success, path = vision.capture_screen(auto_open=False)
            if success and path:
                self._attach_screenshot(path)
            else:
                self.log("system", "[❌ Screen capture failed]\n")
        except Exception as e:
            self.log("system", f"[❌ Screen capture error: {e}]\n")

    def _on_paste_btn_click(self):
        """Triggered when clicking the PASTE SNIP button."""
        handled = self._handle_clipboard_image()
        if not handled:
            # If no image is on clipboard, capture active screen right away!
            self._snip_screen_now()

    def _send_text(self):
        query = self.entry.get().strip()
        attached_img = getattr(self, '_pending_attached_image', None)

        if not query and not attached_img:
            return

        self.entry.delete(0, tk.END)

        if attached_img:
            self._clear_attached_screenshot(keep_file=True)
            default_prompt = "Is screenshot / image ko deeply analyze karo, isme kya code, error ya problem hai use identify karo, aur mujhe step-by-step complete detailed solution aur code fix do."
            user_prompt = query if query else default_prompt

            self.log("user", f"You (Vision): 📸 [Attached Screenshot] {user_prompt}\n")
            self.set_reactor_state("VISION")
            self.log("system", "[Analyzing Screenshot with Gemini Multimodal Vision AI...]\n")

            def _vision_worker():
                try:
                    from cwa_agent.core.vision import vision
                    analysis = vision.analyze_image_with_gemini(attached_img, prompt=user_prompt)
                    self.after(0, lambda: self._on_vision_result(analysis))
                except Exception as e:
                    self.after(0, lambda: self._on_vision_result(f"Vision analysis failed: {e}"))

            threading.Thread(target=_vision_worker, daemon=True).start()
            return

        self.log("user", f"You: {query}\n")
        if self.on_user_query:
            speak_voice = self.voice_output_enabled.get()
            threading.Thread(target=self.on_user_query, args=(query, speak_voice), daemon=True).start()

    def _toggle_vision_panel(self):
        """Shows or hides the Vision Upload drawer to keep chat clean."""
        if self.img_panel.winfo_ismapped():
            self.img_panel.pack_forget()
            self.vision_open_btn.config(text="📎 Open Vision Upload", bg="#1e293b")
        else:
            if self.code_panel.winfo_ismapped():
                self.code_panel.pack_forget()
                self.code_open_btn.config(text="🖥️ Open AI Code Editor", bg="#1e293b")
            self.img_panel.pack(fill="x", pady=2)
            self.vision_open_btn.config(text="▲ Close Vision Upload", bg="#78350f")

    def _toggle_code_panel(self):
        """Shows or hides the Code Editor drawer to keep chat clean."""
        if self.code_panel.winfo_ismapped():
            self.code_panel.pack_forget()
            self.code_open_btn.config(text="🖥️ Open AI Code Editor", bg="#1e293b")
        else:
            if self.img_panel.winfo_ismapped():
                self.img_panel.pack_forget()
                self.vision_open_btn.config(text="📎 Open Vision Upload", bg="#1e293b")
            self.code_panel.pack(fill="x", pady=2)
            self.code_open_btn.config(text="▲ Close AI Code Editor", bg="#14532d")

    def update_scan_progress(self, percent: int, status_text: str):
        """Safe no-op since progress bar widget is removed from UI."""
        pass

    def clear_logs_ui(self):
        """Clears the visual terminal log text."""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")
        self.log("system", "Activity logs & chat history cleared, Sir.\n")


    def _clear_logs(self):
        self.clear_logs_ui()
        from cwa_agent.core.brain import brain
        threading.Thread(target=brain.clear_chat, daemon=True).start()

    def _set_api_key_dialog(self):
        key = simpledialog.askstring("Gemini API Key", "Enter your Gemini API Key:", parent=self)
        if key:
            from cwa_agent.core.brain import brain
            from cwa_agent.config import ENV_PATH
            clean_key = key.strip()
            if brain.set_api_key(clean_key):
                try:
                    env_lines = []
                    if os.path.exists(ENV_PATH):
                        with open(ENV_PATH, "r", encoding="utf-8") as f:
                            env_lines = f.readlines()

                    found = False
                    new_lines = []
                    for line in env_lines:
                        if line.startswith("GEMINI_API_KEY="):
                            new_lines.append(f"GEMINI_API_KEY={clean_key}\n")
                            found = True
                        else:
                            new_lines.append(line)

                    if not found:
                        new_lines.insert(0, f"GEMINI_API_KEY={clean_key}\n")

                    with open(ENV_PATH, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)

                    self.log("system", "Gemini API Key successfully updated and saved to .env!\n")
                    messagebox.showinfo("Success", "Gemini API Key successfully configured!")
                except Exception as e:
                    self.log("system", f"Saved in memory. Warning: could not write .env: {e}\n")
            else:
                messagebox.showerror("Error", "Could not initialize with this key.")

    def _trigger_app_rebuild(self):
        """Triggers PyInstaller rebuild process to update the standalone application with latest changes."""
        confirm = messagebox.askyesno(
            "Rebuild / Update CWA Application",
            "Do you want to re-compile CWA-JARVIS with all your latest code changes, new tools, and functions?\n\nThis will refresh the 'dist/CWA-JARVIS.exe' application in background."
        )
        if not confirm:
            return

        self.update_btn.config(text="⏳ REBUILDING APP...", state="disabled", bg="#312e81", fg="#fde68a")
        self.log("system", "[App Updater] Starting PyInstaller background rebuild process...\n")
        self.set_reactor_state("THINKING")

        def _worker():
            import sys
            import subprocess
            try:
                build_script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "build_app.py")
                res = subprocess.run([sys.executable, build_script], capture_output=True, text=True)
                if res.returncode == 0:
                    self.after(0, lambda: self._on_rebuild_success())
                else:
                    self.after(0, lambda: self._on_rebuild_failure(res.stderr[:200]))
            except Exception as e:
                self.after(0, lambda: self._on_rebuild_failure(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_rebuild_success(self):
        self.update_btn.config(text="🔄 REBUILD / UPDATE APP (.EXE)", state="normal", bg="#1e1b4b", fg="#a5b4fc")
        self.set_reactor_state("IDLE")
        self.log("system", "[App Updater] ✔ CWA-JARVIS Application (.exe) successfully updated with all latest features!\n")
        messagebox.showinfo("Update Complete", "CWA-JARVIS Application (.exe) has been successfully re-compiled and updated!")

    def _on_rebuild_failure(self, err: str):
        self.update_btn.config(text="🔄 REBUILD / UPDATE APP (.EXE)", state="normal", bg="#1e1b4b", fg="#a5b4fc")
        self.set_reactor_state("IDLE")
        self.log("system", f"[App Updater] ❌ Rebuild encountered an issue: {err}\n")
        messagebox.showerror("Update Issue", f"Could not complete build: {err}")

    def _upload_screenshot(self):
        """Opens file dialog for user to select a screenshot or image."""
        filetypes = [
            ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff"),
            ("PNG files", "*.png"),
            ("JPEG files", "*.jpg *.jpeg"),
            ("All files", "*.*")
        ]
        filepath = filedialog.askopenfilename(
            title="Select Screenshot or Image for CWA Vision Analysis",
            filetypes=filetypes
        )
        if filepath:
            self._uploaded_img_path = filepath
            # Show thumbnail preview
            try:
                img = Image.open(filepath)
                img.thumbnail((90, 70), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.img_preview_lbl.config(image=photo, text="", bg="#0a1628", width=90, height=70)
                self.img_preview_lbl.image = photo  # Keep reference
                filename = filepath.split("\\")[-1].split("/")[-1]
                self.img_status_lbl.config(text=f"✔ {filename[:22]}", fg="#10b981")
                self.log("system", f"[Vision Upload] Image loaded: {filename}\n")
            except Exception as e:
                self.img_status_lbl.config(text="✔ Image ready", fg="#10b981")
                self.log("system", f"[Vision Upload] Image loaded (preview error: {e})\n")

    def _analyze_uploaded_image(self):
        """Sends uploaded image + question to CWA brain for Gemini Vision analysis."""
        if not self._uploaded_img_path:
            self.log("system", "[Vision] No image uploaded yet. Please browse an image first.\n")
            messagebox.showwarning("No Image", "Please upload a screenshot or image first!")
            return

        question = self.img_question_entry.get().strip()
        if not question or question == "Is mein kya problem hai? Solve karo.":
            question = "Analyze this image in detail. Identify any errors, problems, or important information and explain how to solve or understand it."

        self.img_status_lbl.config(text="⚡ Analyzing...", fg="#f59e0b")
        self.log("user", f"[Vision Query] Image uploaded + Question: {question}\n")
        self.set_reactor_state("VISION")

        def _do_analysis():
            try:
                from cwa_agent.core.vision import vision
                result = vision.analyze_image_with_gemini(
                    self._uploaded_img_path,
                    prompt=question
                )
                self.after(0, lambda: self._on_vision_result(result))
            except Exception as e:
                self.after(0, lambda: self._on_vision_result(f"Vision analysis failed: {e}"))

        threading.Thread(target=_do_analysis, daemon=True).start()

    def _on_vision_result(self, result: str):
        """Handles vision analysis result — display in terminal and speak it."""
        self.img_status_lbl.config(text="✔ Done", fg="#10b981")
        self.set_reactor_state("SPEAKING")
        self.log("cwa", f"{result}\n")
        # Speak the result if voice is enabled
        if self.voice_output_enabled.get():
            from cwa_agent.core.speaker import speaker
            threading.Thread(target=speaker.speak, args=(result,), daemon=True).start()
        self.set_reactor_state("IDLE")

    def log(self, tag: str, message: str, emotion: str = "", intensity: int = 0, emoji_char: str = ""):
        self.log_text.configure(state="normal")   # ← temporarily enable to insert
        if tag == "user":
            self._insert_rich_text("● YOU > ", "user_tag")
            self._insert_rich_text(message.replace("You: ", ""), "user_msg")
        elif tag == "cwa":
            is_mj = (getattr(speaker, 'persona', 'CWA') == 'MJ')
            prefix = "● MJ 👩 > " if is_mj else "● CWA 👨 > "
            style_tag = "mj_tag" if is_mj else "cwa_tag"
            msg_tag = "mj_msg" if is_mj else "cwa_msg"

            self._insert_rich_text(prefix, style_tag)
            clean_msg = message.replace("CWA: ", "").replace("MJ: ", "")
            self._insert_rich_text(clean_msg, msg_tag)
        else:
            self._insert_rich_text(message, tag)

        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")  # ← lock back: read-only


    def _browse_code_file(self):
        """Opens file dialog for user to select a code file for AI editing."""
        filetypes = [
            ("Code files", "*.py *.js *.ts *.html *.css *.java *.cpp *.c *.cs *.go *.rs *.php *.rb"),
            ("Python", "*.py"),
            ("JavaScript/TypeScript", "*.js *.ts"),
            ("Web files", "*.html *.css"),
            ("All files", "*.*")
        ]
        filepath = filedialog.askopenfilename(
            title="Select Code File for CWA AI Code Editor",
            filetypes=filetypes
        )
        if filepath:
            self._code_file_path = filepath
            filename = filepath.replace("\\", "/").split("/")[-1]
            self.code_file_lbl.config(
                text=f"📄 {filename}  [{filepath[:45]}...]" if len(filepath) > 45 else f"📄 {filename}  [{filepath}]",
                fg="#4ade80"
            )
            self.code_status_lbl.config(text="", fg="#4ade80")
            self.log("system", f"[AI Code Editor] File loaded: {filename}\n")

    def _apply_ai_code_edits(self):
        """Sends the code file + instruction to Gemini AI for modification and saves it back."""
        if not self._code_file_path:
            messagebox.showwarning("No File", "Please select a code file first using Browse Code File!")
            return

        instruction = self.code_instruction_entry.get().strip()
        if not instruction:
            messagebox.showwarning("No Instruction", "Please tell CWA what changes to make!")
            return

        filename = self._code_file_path.replace("\\", "/").split("/")[-1]
        self.code_status_lbl.config(text="⚡ AI editing...", fg="#f59e0b")
        self.log("user", f"[Code Edit] File: {filename} | Instruction: {instruction}\n")
        self.set_reactor_state("THINKING")

        def _do_edit():
            try:
                from cwa_agent.core.tools import edit_code_file
                result = edit_code_file(self._code_file_path, instruction)
                self.after(0, lambda: self._on_code_edit_result(result))
            except Exception as e:
                self.after(0, lambda: self._on_code_edit_result(f"Code edit error: {e}"))

        threading.Thread(target=_do_edit, daemon=True).start()

    def _on_code_edit_result(self, result: str):
        """Handles AI code edit result — shows in terminal and speaks summary."""
        self.code_status_lbl.config(text="✔ Done! File saved.", fg="#4ade80")
        self.set_reactor_state("SPEAKING")
        self.log("cwa", f"{result}\n")
        if self.voice_output_enabled.get():
            # Speak a short summary, not the full long result
            short_summary = result.split("\n")[0] if "\n" in result else result[:150]
            threading.Thread(target=speaker.speak, args=(short_summary,), daemon=True).start()
        self.set_reactor_state("IDLE")

    def set_reactor_state(self, state: str):
        self.reactor.set_state(state)

    def set_emotion(self, emotion: str, intensity: int = 50, reason: str = "", emoji_char: str = ""):
        """
        Dynamically updates agent emotion matrix across all HUD components:
        - Hologram avatar state & top mood matrix pill
        - Top status bar telemetry badge
        - Live waveform spectrum glow colors
        """
        emo = emotion.upper().strip() if emotion else "CALM"
        palette = JarvisIronManHologram.EMOTION_PALETTES.get(emo, JarvisIronManHologram.EMOTION_PALETTES["CALM"])
        active_icon = emoji_char if emoji_char else palette["icon"]
        
        # Update hologram
        self.reactor.set_emotion(emo, intensity, reason, emoji_char=emoji_char)

        # Update top status bar badge
        if hasattr(self, "emotion_lbl"):
            self.emotion_lbl.config(text=f"MOOD: {active_icon} {emo} ({intensity}%)", fg=palette["neon"])

        # Dynamically modulate waveform graph color to match active emotion aura
        if hasattr(self, "audio_graph"):
            self.audio_graph.set_color(palette["neon"])

    def _telegram_bridge_dialog(self):
        """Opens configuration dialog for Telegram Phone Remote Control Bridge."""
        from cwa_agent.core.remote_bridge import remote_bridge
        
        dialog = tk.Toplevel(self)
        dialog.title("TELEGRAM PHONE REMOTE BRIDGE // CONFIG")
        dialog.geometry("520x420")
        dialog.configure(bg="#040c1a")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        head = tk.Label(dialog, text="📱 TELEGRAM PHONE REMOTE CONTROL BRIDGE", fg="#38bdf8", bg="#040c1a", font=("Consolas", 11, "bold"))
        head.pack(pady=(15, 6))

        desc = tk.Label(
            dialog,
            text="Control your workstation, get desktop screenshots, camera snaps, and lock PC\nremotely from your phone via your personal Telegram Bot.",
            fg="#94a3b8", bg="#040c1a", font=("Consolas", 8), justify="center"
        )
        desc.pack(pady=(0, 12))

        # Status badge
        is_conn = remote_bridge.is_configured()
        stat_text = "STATUS: ● CONNECTED & ACTIVE" if is_conn else "STATUS: ○ NOT CONFIGURED"
        stat_color = "#10b981" if is_conn else "#f59e0b"
        stat_lbl = tk.Label(dialog, text=stat_text, fg=stat_color, bg="#0e1f38", font=("Consolas", 9, "bold"), padx=10, pady=3)
        stat_lbl.pack(pady=(0, 10))

        # Form Box
        form = tk.Frame(dialog, bg="#030814", padx=15, pady=12, bd=1, relief="ridge")
        form.pack(fill="x", padx=20, pady=5)

        tk.Label(form, text="1. TELEGRAM BOT TOKEN (from @BotFather):", fg="#00f0ff", bg="#030814", font=("Consolas", 8, "bold")).pack(anchor="w")
        token_entry = tk.Entry(form, bg="#0a192f", fg="#ffffff", insertbackground="#00f0ff", font=("Consolas", 9), bd=1, relief="solid")
        token_entry.pack(fill="x", pady=(3, 8))
        if remote_bridge.token:
            token_entry.insert(0, remote_bridge.token)

        tk.Label(form, text="2. AUTHORIZED CHAT ID (Optional - auto-detects on 1st message):", fg="#94a3b8", bg="#030814", font=("Consolas", 8)).pack(anchor="w")
        chat_id_entry = tk.Entry(form, bg="#0a192f", fg="#ffffff", insertbackground="#00f0ff", font=("Consolas", 9), bd=1, relief="solid")
        chat_id_entry.pack(fill="x", pady=(3, 4))
        if remote_bridge.authorized_chat_id:
            chat_id_entry.insert(0, remote_bridge.authorized_chat_id)

        # Instructions / Help
        help_text = (
            "Quick Setup (takes 30 seconds):\n"
            "1. Open Telegram on phone → search '@BotFather' → send '/newbot'\n"
            "2. Copy the HTTP API Token and paste it above.\n"
            "3. Click 'SAVE & CONNECT' → Send any message to your bot on phone!"
        )
        tk.Label(dialog, text=help_text, fg="#64748b", bg="#040c1a", font=("Consolas", 8), justify="left").pack(anchor="w", padx=25, pady=8)

        def _save_and_start():
            tok = token_entry.get().strip()
            cid = chat_id_entry.get().strip()
            if not tok:
                messagebox.showwarning("Missing Token", "Please enter a valid Telegram Bot Token from @BotFather.")
                return

            success = remote_bridge.set_credentials(tok, cid)
            if success:
                messagebox.showinfo("Connected", "✔ Telegram Phone Remote Bridge is now ACTIVE!\nSend a message like 'screenshot bhej' from your phone to test!")
                self.log("system", "[Telegram Bridge 📱] Remote phone connection activated successfully!\n")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Could not start Telegram polling daemon. Please check your token.")

        save_btn = tk.Button(
            dialog, text="💾 SAVE & CONNECT PHONE BRIDGE",
            bg="#0284c7", fg="#ffffff", activebackground="#0369a1",
            font=("Consolas", 9, "bold"), bd=0, pady=7, padx=15,
            command=_save_and_start
        )
        save_btn.pack(pady=10)

    def _droidcam_setup_dialog(self):
        """Opens interactive configuration dialog for DroidCam & Wireless Phone Webcams."""
        from cwa_agent.config import CAMERA_URL, CAMERA_INDEX, ENV_PATH
        import cwa_agent.config as cwa_cfg
        from cwa_agent.core.vision import vision

        dialog = tk.Toplevel(self)
        dialog.title("DROIDCAM & CAMERA CONFIGURATION")
        dialog.geometry("540x480")
        dialog.configure(bg="#040c1a")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        head = tk.Label(dialog, text="📷 DROIDCAM & WEBCAM CONFIGURATION", fg="#a855f7", bg="#040c1a", font=("Consolas", 11, "bold"))
        head.pack(pady=(15, 4))

        desc = tk.Label(
            dialog,
            text="Connect your Phone's front or back camera directly using DroidCam over WiFi,\nor select a USB webcam / DroidCam PC Client index.",
            fg="#94a3b8", bg="#040c1a", font=("Consolas", 8), justify="center"
        )
        desc.pack(pady=(0, 10))

        # Status badge
        cur_src = cwa_cfg.CAMERA_URL or f"Camera Index {cwa_cfg.CAMERA_INDEX}"
        stat_lbl = tk.Label(dialog, text=f"CURRENT ACTIVE SOURCE: {cur_src}", fg="#38bdf8", bg="#0e1f38", font=("Consolas", 8, "bold"), padx=10, pady=4)
        stat_lbl.pack(pady=(0, 8))

        # Form Box
        form = tk.Frame(dialog, bg="#030814", padx=15, pady=12, bd=1, relief="ridge")
        form.pack(fill="x", padx=20, pady=5)

        tk.Label(form, text="OPTION 1: DROIDCAM PHONE WI-FI IP (Recommended):", fg="#00f0ff", bg="#030814", font=("Consolas", 8, "bold")).pack(anchor="w")
        tk.Label(form, text="Open DroidCam app on phone -> Note 'WiFi IP' & 'Port':", fg="#64748b", bg="#030814", font=("Consolas", 8)).pack(anchor="w")

        ip_row = tk.Frame(form, bg="#030814")
        ip_row.pack(fill="x", pady=(3, 8))

        # Extract current IP & Port if present
        def_ip = ""
        def_port = "4747"
        if cwa_cfg.CAMERA_URL and "://" in cwa_cfg.CAMERA_URL:
            try:
                part = cwa_cfg.CAMERA_URL.split("://")[1].split("/")[0]
                if ":" in part:
                    def_ip, def_port = part.split(":")
                else:
                    def_ip = part
            except Exception:
                pass

        tk.Label(ip_row, text="Phone IP:", fg="#e2e8f0", bg="#030814", font=("Consolas", 8)).pack(side="left")
        ip_entry = tk.Entry(ip_row, bg="#0a192f", fg="#ffffff", insertbackground="#00f0ff", font=("Consolas", 9), bd=1, relief="solid", width=18)
        ip_entry.pack(side="left", padx=(4, 10))
        if def_ip:
            ip_entry.insert(0, def_ip)
        else:
            ip_entry.insert(0, "192.168.1.XX")

        tk.Label(ip_row, text="Port:", fg="#e2e8f0", bg="#030814", font=("Consolas", 8)).pack(side="left")
        port_entry = tk.Entry(ip_row, bg="#0a192f", fg="#ffffff", insertbackground="#00f0ff", font=("Consolas", 9), bd=1, relief="solid", width=8)
        port_entry.pack(side="left", padx=(4, 0))
        port_entry.insert(0, def_port)

        tk.Label(form, text="OPTION 2: PC WEBCAM / DROIDCAM CLIENT INDEX (0, 1, 2):", fg="#a855f7", bg="#030814", font=("Consolas", 8, "bold")).pack(anchor="w", pady=(4, 0))
        idx_entry = tk.Entry(form, bg="#0a192f", fg="#ffffff", insertbackground="#00f0ff", font=("Consolas", 9), bd=1, relief="solid", width=8)
        idx_entry.pack(anchor="w", pady=(3, 2))
        idx_entry.insert(0, str(cwa_cfg.CAMERA_INDEX))

        feedback_lbl = tk.Label(dialog, text="", fg="#10b981", bg="#040c1a", font=("Consolas", 8, "bold"))
        feedback_lbl.pack(pady=4)

        def _test_and_save():
            raw_ip = ip_entry.get().strip()
            raw_port = port_entry.get().strip() or "4747"
            raw_idx = idx_entry.get().strip()

            target_url = ""
            if raw_ip and "XX" not in raw_ip and not raw_ip.startswith("0.0.0.0"):
                if raw_ip.startswith("http://") or raw_ip.startswith("https://"):
                    target_url = raw_ip
                else:
                    target_url = f"http://{raw_ip}:{raw_port}/video"

            feedback_lbl.config(text="⏳ Testing camera connection...", fg="#f59e0b")
            dialog.update_idletasks()

            def _test_worker():
                import cv2
                tested_ok = False
                source_used = ""

                # Test URL if provided
                if target_url:
                    for test_u in [target_url, target_url.replace("/video", "/mjpegfeed")]:
                        try:
                            c = cv2.VideoCapture(test_u)
                            if c.isOpened():
                                ret, f = c.read()
                                c.release()
                                if ret and f is not None:
                                    tested_ok = True
                                    source_used = test_u
                                    break
                        except Exception:
                            pass

                # Test index if URL didn't work
                if not tested_ok and raw_idx.isdigit():
                    idx_val = int(raw_idx)
                    for b in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
                        try:
                            c = cv2.VideoCapture(idx_val, b)
                            if c.isOpened():
                                ret, f = c.read()
                                c.release()
                                if ret and f is not None:
                                    tested_ok = True
                                    source_used = f"Index {idx_val}"
                                    break
                        except Exception:
                            pass

                def _ui_done():
                    if tested_ok:
                        cwa_cfg.CAMERA_URL = source_used if target_url and "Index" not in source_used else ""
                        if raw_idx.isdigit():
                            cwa_cfg.CAMERA_INDEX = int(raw_idx)
                            vision.camera_index = int(raw_idx)

                        # Write to .env
                        try:
                            env_lines = []
                            if os.path.exists(ENV_PATH):
                                with open(ENV_PATH, "r", encoding="utf-8") as f:
                                    env_lines = f.readlines()
                            new_lines = []
                            found_u, found_i = False, False
                            for l in env_lines:
                                if l.startswith("CAMERA_URL=") or l.startswith("DROIDCAM_URL="):
                                    new_lines.append(f"CAMERA_URL={cwa_cfg.CAMERA_URL}\n")
                                    found_u = True
                                elif l.startswith("CAMERA_INDEX="):
                                    new_lines.append(f"CAMERA_INDEX={cwa_cfg.CAMERA_INDEX}\n")
                                    found_i = True
                                else:
                                    new_lines.append(l)
                            if not found_u and cwa_cfg.CAMERA_URL:
                                new_lines.append(f"CAMERA_URL={cwa_cfg.CAMERA_URL}\n")
                            if not found_i:
                                new_lines.append(f"CAMERA_INDEX={cwa_cfg.CAMERA_INDEX}\n")
                            with open(ENV_PATH, "w", encoding="utf-8") as f:
                                f.writelines(new_lines)
                        except Exception:
                            pass

                        stat_lbl.config(text=f"CURRENT ACTIVE SOURCE: {source_used}")
                        feedback_lbl.config(text=f"✔ Connected & Verified ({source_used})! Ready to use.", fg="#10b981")
                        self.log("system", f"[Vision 📸] Connected camera feed: {source_used}\n")
                        messagebox.showinfo("Camera Connected", f"✔ DroidCam / Camera successfully verified and connected:\n{source_used}\n\nYou can now click '👁️ CAMERA SIGHT' anytime!")
                        dialog.destroy()
                    else:
                        feedback_lbl.config(text="❌ Could not connect. Check phone WiFi IP or DroidCam app.", fg="#ef4444")
                        messagebox.showerror(
                            "Connection Failed",
                            "Could not receive video stream from DroidCam.\n\n"
                            "Checklist:\n"
                            "1. Is DroidCam app open on your phone?\n"
                            "2. Is your PC connected to the same Wi-Fi / Hotspot as your phone?\n"
                            "3. Double check the IP address numbers (e.g. 192.168.1.15)."
                        )

                self.after(0, _ui_done)

            threading.Thread(target=_test_worker, daemon=True).start()

        btn_row = tk.Frame(dialog, bg="#040c1a")
        btn_row.pack(pady=(6, 12))

        test_btn = tk.Button(
            btn_row, text="🔌 TEST & CONNECT CAMERA",
            bg="#7e22ce", fg="#ffffff", activebackground="#6b21a8",
            font=("Consolas", 9, "bold"), bd=0, pady=7, padx=16,
            command=_test_and_save
        )
        test_btn.pack(side="left", padx=5)

        close_btn = tk.Button(
            btn_row, text="✖ Close", bg="#0f172a", fg="#94a3b8",
            font=("Consolas", 8), bd=0, pady=7, padx=12,
            command=dialog.destroy
        )
        close_btn.pack(side="left", padx=5)

    def show_qr_modal(self, image_path: str, content_text: str = "", title: str = ""):
        """
        Displays an interactive Stark HUD popup on screen showing the generated QR code
        with live preview, content display, and multiple download / save options.
        """
        def _render():
            if not os.path.exists(image_path):
                return

            dialog = tk.Toplevel(self)
            dialog.title("JARVIS OS // QUANTUM QR CODE GENERATOR")
            dialog.geometry("460x570")
            dialog.configure(bg="#040c1a")
            dialog.resizable(False, False)
            dialog.transient(self)

            # Center relative to main HUD
            try:
                dialog.update_idletasks()
                w, h = 460, 570
                x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
                y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
                dialog.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
            except Exception:
                pass

            # Header Frame
            head_frame = tk.Frame(dialog, bg="#05152b", pady=8, padx=12)
            head_frame.pack(fill="x")

            tk.Label(head_frame, text="📱 QUANTUM QR MATRIX GENERATOR", fg="#00f0ff", bg="#05152b", font=("Consolas", 11, "bold")).pack(side="left")
            disp_title = title if title else "Generated QR Code"
            tk.Label(head_frame, text=f"[{disp_title[:20]}]", fg="#94a3b8", bg="#05152b", font=("Consolas", 8, "bold")).pack(side="right")

            # Body Container
            body = tk.Frame(dialog, bg="#040c1a", padx=16, pady=10)
            body.pack(fill="both", expand=True)

            # QR Code Image Frame (White high-contrast backing border)
            img_container = tk.Frame(body, bg="#0c2340", padx=6, pady=6, bd=1, relief="ridge")
            img_container.pack(pady=(2, 6))

            try:
                pil_img = Image.open(image_path)
                pil_img = pil_img.resize((240, 240), Image.NEAREST)
                qr_photo = ImageTk.PhotoImage(pil_img)

                img_lbl = tk.Label(img_container, image=qr_photo, bg="#ffffff", bd=4, relief="solid")
                img_lbl.image = qr_photo  # Keep reference
                img_lbl.pack()
            except Exception as e:
                tk.Label(img_container, text=f"Error loading QR: {e}", fg="#ef4444", bg="#040c1a").pack()

            # Content Text Box
            tk.Label(body, text="ENCODED CONTENT / PAYLOAD:", fg="#38bdf8", bg="#040c1a", font=("Consolas", 8, "bold")).pack(anchor="w", pady=(2, 2))

            text_frame = tk.Frame(body, bg="#06162a", bd=1, relief="solid")
            text_frame.pack(fill="x", pady=(0, 8))

            preview_text = content_text if content_text else "No text preview"
            content_lbl = tk.Label(
                text_frame, text=preview_text[:140] + ("..." if len(preview_text) > 140 else ""),
                fg="#e2e8f0", bg="#06162a", font=("Consolas", 8), wraplength=410, justify="left", padx=6, pady=4
            )
            content_lbl.pack(fill="x")

            # Status Label
            status_lbl = tk.Label(body, text="✔ QR Code Ready for Instant Phone Scan or Download", fg="#10b981", bg="#040c1a", font=("Consolas", 8))
            status_lbl.pack(pady=(0, 8))

            # Action Buttons Frame
            btn_box = tk.Frame(body, bg="#040c1a")
            btn_box.pack(fill="x")

            def _save_as():
                import shutil
                default_name = os.path.basename(image_path)
                save_dest = filedialog.asksaveasfilename(
                    title="Save QR Code Image As",
                    initialfile=default_name,
                    defaultextension=".png",
                    filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg"), ("All Files", "*.*")],
                    parent=dialog
                )
                if save_dest:
                    try:
                        shutil.copyfile(image_path, save_dest)
                        status_lbl.config(text=f"✔ Saved to: {os.path.basename(save_dest)}", fg="#10b981")
                        self.log("system", f"[QR Download] Saved QR code to: {save_dest}\n")
                        messagebox.showinfo("QR Saved", f"QR Code successfully saved to:\n{save_dest}", parent=dialog)
                    except Exception as err:
                        status_lbl.config(text=f"❌ Error saving: {err}", fg="#ef4444")

            def _quick_save_desktop():
                import shutil
                from pathlib import Path
                try:
                    desktop_dir = Path(os.path.expanduser("~")) / "Desktop"
                    if not desktop_dir.exists():
                        desktop_dir = Path(os.path.expanduser("~")) / "Downloads"
                    dest_file = desktop_dir / os.path.basename(image_path)
                    shutil.copyfile(image_path, str(dest_file))
                    status_lbl.config(text=f"✔ Saved to Desktop: {dest_file.name}", fg="#10b981")
                    self.log("system", f"[QR Download] Quick saved QR code to Desktop: {dest_file}\n")
                    messagebox.showinfo("Saved to Desktop", f"✔ QR Code saved directly to your Desktop:\n{dest_file.name}", parent=dialog)
                except Exception as err:
                    status_lbl.config(text=f"❌ Save error: {err}", fg="#ef4444")

            def _copy_content():
                try:
                    self.clipboard_clear()
                    self.clipboard_append(content_text)
                    status_lbl.config(text="✔ Content Copied to Clipboard!", fg="#38bdf8")
                except Exception:
                    pass

            # Button Row 1: Primary Download
            download_btn = tk.Button(
                btn_box, text="📥 DOWNLOAD / SAVE AS...", bg="#0284c7", fg="#ffffff",
                activebackground="#0369a1", activeforeground="#ffffff",
                font=("Consolas", 9, "bold"), bd=0, pady=6, command=_save_as
            )
            download_btn.pack(fill="x", pady=2)

            # Button Row 2: Quick Save & Copy Content
            row2 = tk.Frame(btn_box, bg="#040c1a")
            row2.pack(fill="x", pady=2)

            quick_btn = tk.Button(
                row2, text="💾 Save to Desktop", bg="#065f46", fg="#6ee7b7",
                activebackground="#047857", activeforeground="#ffffff",
                font=("Consolas", 8, "bold"), bd=0, pady=5, command=_quick_save_desktop
            )
            quick_btn.pack(side="left", fill="x", expand=True, padx=(0, 2))

            copy_btn = tk.Button(
                row2, text="📋 Copy Text", bg="#1e293b", fg="#cbd5e1",
                font=("Consolas", 8), bd=0, pady=5, command=_copy_content
            )
            copy_btn.pack(side="right", fill="x", expand=True, padx=(2, 0))

            # Close Button
            close_btn = tk.Button(
                btn_box, text="✖ Close", bg="#0f172a", fg="#94a3b8",
                font=("Consolas", 8), bd=0, pady=4, command=dialog.destroy
            )
            close_btn.pack(fill="x", pady=(4, 0))

        self.after(0, _render)

    def show_translation_modal(self, original_text: str, translated_text: str, src_lang: str = "en", tgt_lang: str = "hindi"):
        """
        Displays an interactive Stark HUD popup showing live translation results
        with original comparison, formatted native script, audio speech, and 1-click clipboard copy.
        """
        def _render():
            dialog = tk.Toplevel(self)
            dialog.title("JARVIS OS // NEURAL QUANTUM TRANSLATOR")
            dialog.geometry("520x480")
            dialog.configure(bg="#040c1a")
            dialog.resizable(False, False)
            dialog.transient(self)

            # Center relative to main HUD
            try:
                dialog.update_idletasks()
                w, h = 520, 480
                x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
                y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
                dialog.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
            except Exception:
                pass

            # Header Frame
            head_frame = tk.Frame(dialog, bg="#1a0b2e", pady=8, padx=14)
            head_frame.pack(fill="x")

            tk.Label(head_frame, text="🌐 NEURAL TRANSLATOR MATRIX", fg="#d8b4fe", bg="#1a0b2e", font=("Consolas", 11, "bold")).pack(side="left")
            tk.Label(head_frame, text=f"[{src_lang.upper()} ➔ {tgt_lang.upper()}]", fg="#38bdf8", bg="#1a0b2e", font=("Consolas", 9, "bold")).pack(side="right")

            # Body
            body = tk.Frame(dialog, bg="#040c1a", padx=16, pady=10)
            body.pack(fill="both", expand=True)

            # 1. Original Text Box
            tk.Label(body, text=f"SOURCE TEXT ({src_lang.upper()}):", fg="#94a3b8", bg="#040c1a", font=("Consolas", 8, "bold")).pack(anchor="w", pady=(2, 2))
            orig_frame = tk.Frame(body, bg="#071322", bd=1, relief="solid")
            orig_frame.pack(fill="x", pady=(0, 8))

            orig_lbl = tk.Label(
                orig_frame, text=original_text[:280] + ("..." if len(original_text) > 280 else ""),
                fg="#cbd5e1", bg="#071322", font=("Consolas", 9), wraplength=470, justify="left", padx=8, pady=6
            )
            orig_lbl.pack(fill="x")

            # Arrow indicator
            tk.Label(body, text="▼ TRANSLATED OUTPUT ▼", fg="#c084fc", bg="#040c1a", font=("Consolas", 8, "bold")).pack(pady=(2, 2))

            # 2. Translated Result Box (Big, glowing, clear Devanagari/native font)
            trans_frame = tk.Frame(body, bg="#180c2e", bd=1, relief="ridge", highlightbackground="#a855f7", highlightthickness=1)
            trans_frame.pack(fill="both", expand=True, pady=(0, 8))

            trans_lbl = tk.Label(
                trans_frame, text=translated_text,
                fg="#f3e8ff", bg="#180c2e", font=("Nirmala UI", 12, "bold") if "hin" in tgt_lang or "ur" in tgt_lang else ("Consolas", 11, "bold"),
                wraplength=470, justify="left", padx=10, pady=8
            )
            trans_lbl.pack(fill="both", expand=True)

            # Status Label
            status_lbl = tk.Label(body, text="✔ Translation Complete and Ready to Use", fg="#a855f7", bg="#040c1a", font=("Consolas", 8))
            status_lbl.pack(pady=(0, 6))

            # Actions Box
            btn_box = tk.Frame(body, bg="#040c1a")
            btn_box.pack(fill="x")

            def _copy_translation():
                try:
                    self.clipboard_clear()
                    self.clipboard_append(translated_text)
                    status_lbl.config(text="✔ Translated Text Copied to Clipboard!", fg="#10b981")
                    self.log("system", f"[Translation] Copied translation to clipboard.\n")
                except Exception as ex:
                    status_lbl.config(text=f"❌ Copy error: {ex}", fg="#ef4444")

            def _speak_translation():
                status_lbl.config(text="🔊 Speaking translation...", fg="#38bdf8")
                from cwa_agent.core.speaker import speaker
                threading.Thread(target=speaker.speak, args=(translated_text,), daemon=True).start()

            row1 = tk.Frame(btn_box, bg="#040c1a")
            row1.pack(fill="x", pady=2)

            copy_btn = tk.Button(
                row1, text="📋 COPY TRANSLATED TEXT", bg="#7e22ce", fg="#ffffff",
                activebackground="#6b21a8", activeforeground="#ffffff",
                font=("Consolas", 9, "bold"), bd=0, pady=6, command=_copy_translation
            )
            copy_btn.pack(side="left", fill="x", expand=True, padx=(0, 3))

            speak_btn = tk.Button(
                row1, text="🔊 LISTEN / SPEAK", bg="#0284c7", fg="#ffffff",
                activebackground="#0369a1", activeforeground="#ffffff",
                font=("Consolas", 9, "bold"), bd=0, pady=6, command=_speak_translation
            )
            speak_btn.pack(side="right", fill="x", expand=True, padx=(3, 0))

            close_btn = tk.Button(
                btn_box, text="✖ Close", bg="#0f172a", fg="#94a3b8",
                font=("Consolas", 8), bd=0, pady=4, command=dialog.destroy
            )
            close_btn.pack(fill="x", pady=(4, 0))

        self.after(0, _render)

    # --- Quantum GPS Route & Destination Navigator Dialog ---

    def show_route_modal(self, route_data: dict):
        """Called by tools or voice to display route calculation in modal."""
        self.after(0, lambda: self._show_route_navigator_dialog(
            initial_origin=route_data.get("origin", ""),
            initial_dest=route_data.get("destination", ""),
            initial_mode=route_data.get("travel_mode", "driving").lower(),
            precomputed_data=route_data
        ))

    def _show_route_navigator_dialog(self, initial_origin: str = "", initial_dest: str = "", initial_mode: str = "driving", precomputed_data: dict = None):
        """
        Interactive Quantum GPS Route & Destination Navigator Dialog.
        Calculates live distances, ETA travel duration, route map vector canvas, and provides 1-click Google Maps live navigation.
        """
        import webbrowser
        from cwa_agent.core.route_navigator import route_navigator

        dialog = tk.Toplevel(self)
        dialog.title("JARVIS OS // QUANTUM GPS ROUTE & DESTINATION NAVIGATOR")
        dialog.geometry("520x640")
        dialog.configure(bg="#030814")
        dialog.resizable(False, False)
        dialog.transient(self)

        # Center on screen
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 260
        y = self.winfo_y() + (self.winfo_height() // 2) - 320
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

        # Container
        body = tk.Frame(dialog, bg="#061224", bd=2, relief="ridge", highlightbackground="#0284c7", highlightthickness=1)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        # Header Title
        tk.Label(body, text="[ 🧭 QUANTUM GPS ROUTE & DESTINATION NAVIGATOR ]", fg="#00f0ff", bg="#061224", font=("Consolas", 10, "bold")).pack(pady=(10, 6))

        # Inputs Frame
        inp_frame = tk.Frame(body, bg="#0a192f", bd=1, relief="ridge", padx=10, pady=8)
        inp_frame.pack(fill="x", padx=12, pady=(0, 6))

        # 1. Origin (Starting Location)
        tk.Label(inp_frame, text="📍 STARTING POINT (ORIGIN):", fg="#34d399", bg="#0a192f", font=("Consolas", 8, "bold")).pack(anchor="w")
        orig_entry = tk.Entry(inp_frame, bg="#030814", fg="#ffffff", insertbackground="#00f0ff", font=("Consolas", 9), bd=1, relief="solid")
        orig_entry.pack(fill="x", pady=(2, 6))
        if initial_origin:
            orig_entry.insert(0, initial_origin)
        else:
            orig_entry.insert(0, "Delhi")

        # 2. Destination (Target Location)
        tk.Label(inp_frame, text="🏁 DESTINATION (TARGET):", fg="#f87171", bg="#0a192f", font=("Consolas", 8, "bold")).pack(anchor="w")
        dest_entry = tk.Entry(inp_frame, bg="#030814", fg="#ffffff", insertbackground="#00f0ff", font=("Consolas", 9), bd=1, relief="solid")
        dest_entry.pack(fill="x", pady=(2, 6))
        if initial_dest:
            dest_entry.insert(0, initial_dest)
        else:
            dest_entry.insert(0, "Agra")

        # 3. Travel Mode Selector
        mode_frame = tk.Frame(inp_frame, bg="#0a192f")
        mode_frame.pack(fill="x", pady=(2, 0))

        selected_mode = tk.StringVar(value=initial_mode if initial_mode in ["driving", "motorcycle", "transit", "walking"] else "driving")

        modes = [("🚗 Driving", "driving"), ("🏍️ Bike", "motorcycle"), ("🚆 Train", "transit"), ("🚶 Walk", "walking")]
        for lbl, m_val in modes:
            rb = tk.Radiobutton(
                mode_frame, text=lbl, value=m_val, variable=selected_mode,
                bg="#0a192f", fg="#cbd5e1", activebackground="#0a192f", activeforeground="#00f0ff",
                selectcolor="#0284c7", font=("Consolas", 8, "bold")
            )
            rb.pack(side="left", padx=(0, 8))

        # Status & Results Container
        status_lbl = tk.Label(body, text="Ready to calculate route and ETA", fg="#64748b", bg="#061224", font=("Consolas", 8))
        status_lbl.pack(pady=2)

        res_card = tk.Frame(body, bg="#030814", bd=1, relief="ridge", padx=10, pady=8, highlightbackground="#0284c7", highlightthickness=1)
        res_card.pack(fill="x", padx=12, pady=4)

        stats_row = tk.Frame(res_card, bg="#030814")
        stats_row.pack(fill="x")

        dist_lbl = tk.Label(stats_row, text="Distance: -- km", fg="#00f0ff", bg="#030814", font=("Consolas", 11, "bold"))
        dist_lbl.pack(side="left")

        time_lbl = tk.Label(stats_row, text="ETA: --", fg="#fbbf24", bg="#030814", font=("Consolas", 11, "bold"))
        time_lbl.pack(side="right")

        route_desc_lbl = tk.Label(res_card, text="Enter origin and destination above, then click Calculate Route.", fg="#94a3b8", bg="#030814", font=("Consolas", 8), wraplength=460, justify="left")
        route_desc_lbl.pack(fill="x", pady=(4, 0))

        # Visual Route Map Vector Canvas (Holographic Cyber Route)
        map_canvas = tk.Canvas(body, height=130, bg="#020617", highlightthickness=1, highlightbackground="#0f172a")
        map_canvas.pack(fill="x", padx=12, pady=4)

        def _draw_map_vector(orig_name: str, dest_name: str, dist_str: str, time_str: str):
            map_canvas.delete("all")
            # Grid background
            w = map_canvas.winfo_width() or 480
            h = map_canvas.winfo_height() or 130
            for gx in range(0, w, 30):
                map_canvas.create_line(gx, 0, gx, h, fill="#0f172a", width=1)
            for gy in range(0, h, 20):
                map_canvas.create_line(0, gy, w, gy, fill="#0f172a", width=1)

            # Curved route trajectory
            x1, y1 = 50, h // 2
            x2, y2 = w - 50, h // 2
            cx1, cy1 = x1 + (x2 - x1) * 0.35, y1 - 25
            cx2, cy2 = x1 + (x2 - x1) * 0.65, y1 + 25

            # Glow trajectory
            map_canvas.create_line(x1, y1, cx1, cy1, cx2, cy2, x2, y2, smooth=True, fill="#0284c7", width=5)
            map_canvas.create_line(x1, y1, cx1, cy1, cx2, cy2, x2, y2, smooth=True, fill="#00f0ff", width=2)

            # Origin Pin (Green)
            map_canvas.create_oval(x1-8, y1-8, x1+8, y1+8, fill="#10b981", outline="#34d399", width=2)
            map_canvas.create_text(x1, y1-16, text=f"📍 {orig_name[:15]}", fill="#34d399", font=("Consolas", 8, "bold"))

            # Destination Pin (Red)
            map_canvas.create_oval(x2-8, y2-8, x2+8, y2+8, fill="#ef4444", outline="#f87171", width=2)
            map_canvas.create_text(x2, y2-16, text=f"🏁 {dest_name[:15]}", fill="#f87171", font=("Consolas", 8, "bold"))

            # Midpoint Distance & Time Badge
            mid_x = (x1 + x2) // 2
            mid_y = h // 2 - 10
            map_canvas.create_rectangle(mid_x - 60, mid_y - 12, mid_x + 60, mid_y + 12, fill="#0a192f", outline="#00f0ff", width=1)
            map_canvas.create_text(mid_x, mid_y, text=f"⚡ {dist_str} | {time_str}", fill="#fbbf24", font=("Consolas", 8, "bold"))

        # Store active google maps url
        current_gmaps_url = ["https://maps.google.com"]

        def _apply_route_data(data: dict):
            if not data.get("success"):
                status_lbl.config(text=f"❌ {data.get('error', 'Could not calculate route')}", fg="#ef4444")
                return

            d_str = data.get("distance_str", "--")
            t_str = data.get("duration_str", "--")
            m_str = data.get("travel_mode", "Driving")
            g_url = data.get("google_maps_url", "")
            current_gmaps_url[0] = g_url

            dist_lbl.config(text=f"📍 Distance: {d_str}")
            time_lbl.config(text=f"⏱️ ETA: {t_str}")
            route_desc_lbl.config(text=f"✔ Route: {data.get('origin', '')} ➔ {data.get('destination', '')} ({m_str})\nSummary: {data.get('summary', '')}")
            status_lbl.config(text="✔ Route & ETA Calculated Successfully!", fg="#10b981")

            map_canvas.after(50, lambda: _draw_map_vector(data.get("origin", "Start"), data.get("destination", "End"), d_str, t_str))

        def _do_calculate():
            o = orig_entry.get().strip()
            d = dest_entry.get().strip()
            m = selected_mode.get()

            if not o or not d:
                status_lbl.config(text="⚠️ Please enter both Starting Point and Destination.", fg="#f59e0b")
                return

            status_lbl.config(text="⏳ Calculating route & live GPS distance...", fg="#38bdf8")
            calc_btn.config(state="disabled")

            def _worker():
                res = route_navigator.calculate_route(o, d, m)
                def _done():
                    calc_btn.config(state="normal")
                    _apply_route_data(res)
                dialog.after(0, _done)

            threading.Thread(target=_worker, daemon=True).start()

        # Action Buttons
        act_box = tk.Frame(body, bg="#061224")
        act_box.pack(fill="x", padx=12, pady=(6, 0))

        calc_btn = tk.Button(act_box, text="🚀 CALCULATE ROUTE & TIME", bg="#0284c7", fg="#ffffff",
                             activebackground="#0369a1", activeforeground="#ffffff", font=("Consolas", 9, "bold"), bd=0, pady=6,
                             command=_do_calculate)
        calc_btn.pack(fill="x", pady=(0, 4))

        def _open_google_maps():
            webbrowser.open(current_gmaps_url[0])
            status_lbl.config(text="✔ Opened Live Navigation on Google Maps!", fg="#34d399")

        gmaps_btn = tk.Button(act_box, text="🌐 VIEW LIVE ROUTE ON GOOGLE MAPS", bg="#065f46", fg="#34d399",
                              activebackground="#047857", activeforeground="#ffffff", font=("Consolas", 9, "bold"), bd=0, pady=6,
                              command=_open_google_maps)
        gmaps_btn.pack(fill="x", pady=(0, 4))

        sub_btns = tk.Frame(act_box, bg="#061224")
        sub_btns.pack(fill="x", pady=(0, 4))

        def _copy_info():
            txt = f"Route: {orig_entry.get()} -> {dest_entry.get()}\n{dist_lbl.cget('text')} | {time_lbl.cget('text')}\nGoogle Maps: {current_gmaps_url[0]}"
            self.clipboard_clear()
            self.clipboard_append(txt)
            status_lbl.config(text="✔ Route details copied to clipboard!", fg="#10b981")

        def _speak_info():
            from cwa_agent.core.speaker import speaker
            o = orig_entry.get()
            d = dest_entry.get()
            dist = dist_lbl.cget("text")
            eta = time_lbl.cget("text")
            speaker.speak(f"Sir, {o} se {d} tak ka {dist}, aur lagbhag {eta} lagenge.")

        copy_btn = tk.Button(sub_btns, text="📋 COPY INFO", bg="#1e293b", fg="#cbd5e1", font=("Consolas", 8), bd=0, pady=4, command=_copy_info)
        copy_btn.pack(side="left", fill="x", expand=True, padx=(0, 2))

        speak_btn = tk.Button(sub_btns, text="🔊 SPEAK ROUTE", bg="#1e1b4b", fg="#a5b4fc", font=("Consolas", 8, "bold"), bd=0, pady=4, command=_speak_info)
        speak_btn.pack(side="left", fill="x", expand=True, padx=(2, 2))

        close_btn = tk.Button(sub_btns, text="✖ CLOSE", bg="#1e293b", fg="#94a3b8", font=("Consolas", 8), bd=0, pady=4, command=dialog.destroy)
        close_btn.pack(side="right", fill="x", expand=True, padx=(2, 0))

        # If precomputed data provided, render immediately
        if precomputed_data:
            _apply_route_data(precomputed_data)
        elif initial_origin and initial_dest:
            _do_calculate()
        else:
            map_canvas.after(100, lambda: _draw_map_vector("Delhi", "Agra", "202.4 km", "2 hr 29 min"))




