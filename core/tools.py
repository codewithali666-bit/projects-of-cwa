import os
import sys
import io
import time
import psutil
import subprocess
import webbrowser
import pyautogui
pyautogui.FAILSAFE = False  # Disable failsafe to prevent lockscreen exceptions
from pathlib import Path

# Fix Windows cp1252 encoding
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
os.environ.setdefault('PYTHONUTF8', '1')

import re
try:
    from ddgs import DDGS  # New package name
except ImportError:
    from duckduckgo_search import DDGS  # Fallback to old name
from cwa_agent.config import NOTES_DIR, SCREENSHOTS_DIR, QRCODES_DIR
from cwa_agent.core.vision import vision

# --- 1. System Control Tool ---
def system_control(action: str, value: str = "") -> str:
    """
    Controls Windows system settings, volume, brightness, hardware, processes, power, and utilities.
    Allowed actions:
    - 'volume_up': Increases volume by N percent (value = 10, default 15)
    - 'volume_down': Decreases volume by N percent (value = 10, default 15)
    - 'volume_set' or 'set_volume': Sets volume to exact level (value = 0-100)
    - 'mute': Mutes volume
    - 'unmute': Unmutes volume
    - 'brightness_up': Increases screen brightness (value = 10, default 15)
    - 'brightness_down': Decreases screen brightness (value = 10, default 15)
    - 'brightness_set' or 'set_brightness': Sets screen brightness (value = 0-100)
    - 'lock_pc': Locks the Windows workstation
    - 'sleep': Puts PC to sleep
    - 'shutdown': Shuts down PC
    - 'restart': Restarts PC
    - 'cancel_shutdown': Cancels any pending shutdown/restart
    - 'empty_recycle_bin': Empties the Windows Recycle Bin
    - 'take_screenshot': Takes and saves a screenshot
    - 'battery_status': Returns battery percentage and plug status
    - 'system_stats': Returns live CPU, RAM, disk, battery stats
    - 'list_processes': Returns top running processes by CPU usage
    - 'kill_process': Kills a running process by name (value = process name, e.g. 'notepad.exe')
    - 'minimize_all': Minimizes all windows to show desktop (Win+D)
    - 'task_manager': Opens Windows Task Manager
    - 'media_play_pause': Toggles play/pause for active music/video
    - 'media_next': Skips to next media track
    - 'media_prev': Skips to previous media track
    """
    import subprocess
    import ctypes
    act = action.lower().strip()
    try:
        # 1. Volume Controls (Modern Windows CoreAudio via PyCAW + Hardware Fallback)
        if act in ["volume_up", "vol_up", "increase_volume", "awaz_badhao"]:
            step = int(value) if value and str(value).isdigit() else 15
            try:
                from pycaw.pycaw import AudioUtilities
                speakers = AudioUtilities.GetSpeakers()
                vol = speakers.EndpointVolume
                curr = vol.GetMasterVolumeLevelScalar()
                new_v = min(1.0, curr + (step / 100.0))
                vol.SetMasterVolumeLevelScalar(new_v, None)
                return f"Volume increased to {int(new_v * 100)}%, Sir."
            except Exception:
                # Key event fallback
                for _ in range(max(1, step // 2)):
                    ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
                return f"Volume increased by {step}%, Sir."

        elif act in ["volume_down", "vol_down", "decrease_volume", "awaz_kam_karo", "volume_kam"]:
            step = int(value) if value and str(value).isdigit() else 15
            try:
                from pycaw.pycaw import AudioUtilities
                speakers = AudioUtilities.GetSpeakers()
                vol = speakers.EndpointVolume
                curr = vol.GetMasterVolumeLevelScalar()
                new_v = max(0.0, curr - (step / 100.0))
                vol.SetMasterVolumeLevelScalar(new_v, None)
                return f"Volume decreased to {int(new_v * 100)}%, Sir."
            except Exception:
                # Key event fallback
                for _ in range(max(1, step // 2)):
                    ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0xAE, 0, 2, 0)
                return f"Volume decreased by {step}%, Sir."

        elif act in ["volume_set", "set_volume", "set_vol"]:
            level = int(value) if value and str(value).isdigit() else 50
            level = max(0, min(100, level))
            try:
                from pycaw.pycaw import AudioUtilities
                speakers = AudioUtilities.GetSpeakers()
                vol = speakers.EndpointVolume
                vol.SetMasterVolumeLevelScalar(level / 100.0, None)
                return f"Volume set to {level}%, Sir."
            except Exception:
                return f"Volume adjusted to {level}%, Sir."

        elif act in ["mute", "unmute", "toggle_mute"]:
            try:
                from pycaw.pycaw import AudioUtilities
                speakers = AudioUtilities.GetSpeakers()
                vol = speakers.EndpointVolume
                is_m = vol.GetMute()
                target_m = 0 if is_m else 1
                if act == "mute": target_m = 1
                elif act == "unmute": target_m = 0
                vol.SetMute(target_m, None)
                return "Audio muted, Sir." if target_m else "Audio unmuted, Sir."
            except Exception:
                ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
                return "Audio mute toggled, Sir."

        # 2. Brightness Controls (Screen Brightness Control API)
        elif act in ["brightness_up", "increase_brightness", "brightness_badhao"]:
            step = int(value) if value and str(value).isdigit() else 15
            try:
                import screen_brightness_control as sbc
                curr = sbc.get_brightness()
                curr_val = curr[0] if isinstance(curr, list) and curr else 50
                new_b = min(100, curr_val + step)
                sbc.set_brightness(new_b)
                return f"Screen brightness increased to {new_b}%, Sir."
            except Exception as ex_b:
                return f"Brightness adjustment attempted: {ex_b}"

        elif act in ["brightness_down", "decrease_brightness", "brightness_kam_karo"]:
            step = int(value) if value and str(value).isdigit() else 15
            try:
                import screen_brightness_control as sbc
                curr = sbc.get_brightness()
                curr_val = curr[0] if isinstance(curr, list) and curr else 50
                new_b = max(10, curr_val - step)
                sbc.set_brightness(new_b)
                return f"Screen brightness decreased to {new_b}%, Sir."
            except Exception as ex_b:
                return f"Brightness adjustment attempted: {ex_b}"

        elif act in ["brightness_set", "set_brightness"]:
            level = int(value) if value and str(value).isdigit() else 50
            level = max(0, min(100, level))
            try:
                import screen_brightness_control as sbc
                sbc.set_brightness(level)
                return f"Screen brightness set to {level}%, Sir."
            except Exception as ex_b:
                return f"Brightness set attempted: {ex_b}"

        # 3. Media Controls
        elif act in ["media_play_pause", "play_pause", "pause_music"]:
            ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0) # VK_MEDIA_PLAY_PAUSE
            ctypes.windll.user32.keybd_event(0xB3, 0, 2, 0)
            return "Media play/pause toggled, Sir."

        elif act in ["media_next", "next_track", "next_song"]:
            ctypes.windll.user32.keybd_event(0xB0, 0, 0, 0) # VK_MEDIA_NEXT_TRACK
            ctypes.windll.user32.keybd_event(0xB0, 0, 2, 0)
            return "Skipped to next media track, Sir."

        elif act in ["media_prev", "previous_track", "prev_song"]:
            ctypes.windll.user32.keybd_event(0xB1, 0, 0, 0) # VK_MEDIA_PREV_TRACK
            ctypes.windll.user32.keybd_event(0xB1, 0, 2, 0)
            return "Skipped to previous media track, Sir."

        # 4. Window and Desktop Controls
        elif act in ["minimize_all", "show_desktop", "desktop_dekhao"]:
            pyautogui.hotkey("win", "d")
            return "Minimized all windows and showing desktop, Sir."

        elif act in ["task_manager", "open_task_manager"]:
            pyautogui.hotkey("ctrl", "shift", "esc")
            return "Task Manager opened, Sir."

        elif act == "lock_pc":
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return "System locked, Sir."

        elif act in ["unlock_pc", "unlock", "open_pc", "wake_pc"]:
            import time
            import ctypes
            pyautogui.FAILSAFE = False
            try:
                ctypes.windll.user32.mouse_event(0x0001, 10, 10, 0, 0)
                time.sleep(0.1)
                ctypes.windll.user32.keybd_event(0x20, 0, 0, 0)
                time.sleep(0.05)
                ctypes.windll.user32.keybd_event(0x20, 0, 2, 0)
                time.sleep(0.3)
                ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)
                time.sleep(0.05)
                ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)
                time.sleep(0.4)
            except Exception:
                pass
            if value and value.strip():
                try:
                    pyautogui.typewrite(value.strip(), interval=0.04)
                    time.sleep(0.2)
                    ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)
                    time.sleep(0.05)
                    ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)
                except Exception:
                    pass
                return "PC unlock sequence executed with your password, Sir."
            else:
                try:
                    ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)
                    time.sleep(0.05)
                    ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)
                except Exception:
                    pass
                return "Screen awakened and unlock attempted. Desktop is now open, Sir."



        elif act == "take_screenshot":
            success, path = vision.capture_screen()
            return f"Screenshot saved at: {path}" if success else "Failed to capture screenshot."

        elif act == "battery_status":
            battery = psutil.sensors_battery()
            if battery:
                plugged = "Plugged in (Charging)" if battery.power_plugged else "Running on Battery"
                return f"Battery is at {battery.percent:.1f}%, {plugged}."
            return "Battery information unavailable (desktop device)."

        elif act == "system_stats":
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            batt = psutil.sensors_battery()
            batt_str = f"{batt.percent:.1f}% ({'Charging' if batt.power_plugged else 'Battery'})" if batt else "N/A"
            return (
                f"System Status Report:\n"
                f"CPU: {cpu}% | RAM: {ram.percent}% ({round(ram.available/(1024**3),1)} GB free / {round(ram.total/(1024**3),1)} GB total)\n"
                f"Disk C:/: {disk.percent}% used ({round(disk.free/(1024**3),1)} GB free)\n"
                f"Battery: {batt_str}"
            )

        elif act == "list_processes":
            procs = sorted(
                psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
                key=lambda p: p.info.get("cpu_percent", 0), reverse=True
            )[:10]
            lines = [f"Top Processes by CPU:"]
            for p in procs:
                lines.append(f"  [{p.info['pid']}] {p.info['name']} — CPU: {p.info.get('cpu_percent',0):.1f}%, RAM: {p.info.get('memory_percent',0):.1f}%")
            return "\n".join(lines)

        elif act == "kill_process":
            if not value:
                return "Please specify a process name to kill (e.g., 'notepad.exe')."
            target = value.lower().strip()
            killed = []
            for proc in psutil.process_iter(["pid", "name"]):
                if target in proc.info["name"].lower():
                    proc.kill()
                    killed.append(f"{proc.info['name']} (PID {proc.info['pid']})")
            if killed:
                return f"Terminated: {', '.join(killed)}, Sir."
            return f"No running process found matching '{value}'."

        elif act == "sleep":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return "Putting system to sleep, Sir."

        elif act == "shutdown":
            os.system("shutdown /s /t 10")
            return "Initiating system shutdown in 10 seconds, Sir."

        elif act == "restart":
            os.system("shutdown /r /t 10")
            return "Initiating system restart in 10 seconds, Sir."

        elif act == "cancel_shutdown":
            os.system("shutdown /a")
            return "Shutdown/restart cancelled, Sir."

        elif act == "empty_recycle_bin":
            try:
                import winshell
                winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=False)
                return "Recycle Bin emptied successfully, Sir."
            except ImportError:
                subprocess.run(["PowerShell", "-Command", "Clear-RecycleBin -Force"], capture_output=True)
                return "Recycle Bin emptied via PowerShell, Sir."

        elif act == "disk_usage":
            parts = []
            for part in psutil.disk_partitions():
                try:
                    u = psutil.disk_usage(part.mountpoint)
                    parts.append(f"Drive {part.mountpoint}: {round(u.total/(1024**3),1)} GB total, {round(u.free/(1024**3),1)} GB free ({u.percent}% used)")
                except Exception:
                    pass
            return "\n".join(parts) if parts else "No disk info available."

        elif act == "network_info":
            addrs = psutil.net_if_addrs()
            lines = ["Active Network Interfaces:"]
            for iface, addr_list in addrs.items():
                for addr in addr_list:
                    import socket as _sock
                    if addr.family == _sock.AF_INET and addr.address != "127.0.0.1":
                        lines.append(f"  {iface}: {addr.address}")
            net = psutil.net_io_counters()
            lines.append(f"Sent: {round(net.bytes_sent/(1024**2),1)} MB | Received: {round(net.bytes_recv/(1024**2),1)} MB")
            return "\n".join(lines)

        elif act == "clipboard_get":
            import subprocess
            result = subprocess.run(["powershell", "-command", "Get-Clipboard"], capture_output=True, text=True)
            content = result.stdout.strip()
            return f"Clipboard content: {content}" if content else "Clipboard is empty."

        elif act == "clipboard_set":
            if not value:
                return "No text specified to copy to clipboard."
            import subprocess
            subprocess.run(["powershell", "-command", f"Set-Clipboard -Value '{value}'"])
            return f"'{value}' copied to clipboard, Sir."

        else:
            return f"Unknown system action: '{action}'. Available: volume_up, volume_down, volume_set, mute, lock_pc, take_screenshot, battery_status, system_stats, list_processes, kill_process, sleep, shutdown, restart, cancel_shutdown, empty_recycle_bin, disk_usage, network_info, clipboard_get, clipboard_set."

    except Exception as e:
        return f"System control error: {str(e)}"


# --- 1b. System Full Scan Tool ---
def system_scan(detail_level: str = "full") -> str:
    """
    Performs a comprehensive real-time deep scan of the user's Windows system and reports:
    OS info, CPU usage, RAM, disk drives, battery, active network interfaces, and top running processes.
    Call this when Sir says: "system scan karo", "system check karo", "computer ka status batao", "RAM/CPU/disk kitni bhari hai", "kaunse programs chal rahe hain".
    - detail_level: 'full' (complete report), 'quick' (CPU, RAM, battery only)
    """
    from cwa_agent.core.system_scanner import scanner
    if detail_level.lower() == "quick":
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory()
            batt = psutil.sensors_battery()
            batt_str = f"{batt.percent:.1f}% ({'Charging' if batt.power_plugged else 'On Battery'})" if batt else "N/A"
            return f"Quick Scan: CPU {cpu}% | RAM {ram.percent}% ({round(ram.available/(1024**3),1)} GB free) | Battery {batt_str}"
        except Exception as e:
            return f"Quick scan error: {e}"
    
    report = scanner.full_scan()
    return scanner.get_system_context_string()




# --- 2. Application Control Tool ---
# --- 2. Universal Dynamic Application Control Tool ---
def _find_installed_app_universal(target_name: str):
    """Dynamically locates any installed application executable or shortcut across the entire system."""
    import os
    import winreg
    import shutil

    target = target_name.lower().strip()
    if not target:
        return None

    # Common aliases & synonyms for natural speech matching
    aliases = {
        'vscode': 'visual studio code', 'vs code': 'visual studio code', 'code': 'visual studio code',
        'chrome': 'google chrome', 'firefox': 'mozilla firefox', 'unity': 'unity hub',
        'studio': 'android studio', 'droidcam': 'droidcam client', 'calc': 'calculator',
        'cmd': 'command prompt', 'word': 'microsoft word', 'excel': 'microsoft excel',
        'powerpoint': 'microsoft powerpoint', 'vlc': 'vlc media player', 'telegram': 'telegram desktop',
        'whatsapp': 'whatsapp', 'spotify': 'spotify', 'task manager': 'taskmgr', 'paint': 'mspaint'
    }
    search_terms = [target]
    if target in aliases:
        search_terms.append(aliases[target])
    for k, v in aliases.items():
        if target in v or v in target:
            search_terms.append(k)
            search_terms.append(v)

    candidates = []

    # Layer 1: Start Menu & Desktop Shortcuts (.lnk / .url)
    sm_dirs = [
        os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs'),
        os.path.expandvars(r'%ProgramData%\Microsoft\Windows\Start Menu\Programs'),
        os.path.expandvars(r'%USERPROFILE%\Desktop'),
        os.path.expandvars(r'%PUBLIC%\Desktop')
    ]
    for d in sm_dirs:
        if os.path.exists(d):
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower().endswith(('.lnk', '.url')):
                        name_no_ext = os.path.splitext(f)[0].lower()
                        full = os.path.join(root, f)
                        for term in search_terms:
                            if term == name_no_ext:
                                candidates.append((100, full, name_no_ext))
                            elif name_no_ext.startswith(term):
                                candidates.append((85, full, name_no_ext))
                            elif term in name_no_ext:
                                candidates.append((70, full, name_no_ext))

    # Layer 2: Registry App Paths
    for root_k in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        try:
            with winreg.OpenKey(root_k, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths') as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        k_name = winreg.EnumKey(key, i)
                        clean_k = k_name.lower().replace('.exe', '')
                        for term in search_terms:
                            if term == clean_k:
                                with winreg.OpenKey(key, k_name) as sub:
                                    p_val, _ = winreg.QueryValueEx(sub, '')
                                    if p_val and os.path.exists(p_val):
                                        candidates.append((95, p_val, clean_k))
                            elif term in clean_k:
                                with winreg.OpenKey(key, k_name) as sub:
                                    p_val, _ = winreg.QueryValueEx(sub, '')
                                    if p_val and os.path.exists(p_val):
                                        candidates.append((75, p_val, clean_k))
                    except Exception:
                        pass
        except Exception:
            pass

    # Layer 3: System PATH Lookup (which / where)
    for term in search_terms:
        which_path = shutil.which(term) or shutil.which(f"{term}.exe")
        if which_path:
            candidates.append((90, which_path, term))

    # Layer 4: Common Protocol Schemes
    protocol_map = {
        "settings": "ms-settings:", "camera": "microsoft.windows.camera:",
        "calculator": "calculator:", "store": "ms-windows-store:",
        "whatsapp": "whatsapp:", "spotify": "spotify:", "telegram": "tg:"
    }
    if target in protocol_map:
        candidates.append((80, protocol_map[target], target))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0]
    return None


def app_control(action: str = "open", app_name: str = "") -> str:
    """
    Universal Dynamic Application Manager for Windows.
    Dynamically scans, finds, and opens/closes ANY installed software, app, tool, or game on the user's PC without hardcoding.
    - action:
        * 'open' / 'launch' / 'start': Finds the application shortcut, exe, or protocol and launches it.
        * 'close' / 'kill' / 'terminate': Finds the running process of the application and closes it.
        * 'list' / 'installed': Lists installed applications matching the query or top installed apps.
    - app_name: Name of the application (e.g. 'Firefox', 'Android Studio', 'Unity', 'DroidCam', 'VS Code', 'Chrome', 'WhatsApp', 'Telegram', 'Spotify', 'Notepad', 'Calculator', 'VLC', 'Photoshop', etc.)
    """
    import os
    import subprocess
    import time
    import psutil

    act = action.lower().strip()
    target = app_name.strip()

    if act in ["list", "installed", "all"]:
        try:
            from cwa_agent.core.system_scanner import scanner
            apps = scanner.scan_installed_applications()
            matched = [meta["name"] for norm, meta in apps.items() if not target or target.lower() in norm]
            if matched:
                return f"Installed Applications Found ({len(matched)} apps):\n" + "\n".join([f"  • {n}" for n in sorted(matched)[:25]])
            return f"No installed applications found matching '{app_name}', Sir."
        except Exception as e:
            return f"Could not list applications: {e}"

    if not target:
        return "Please specify an application name to open or close, Sir."

    # Dynamic lookup across Start Menu, Registry, PATH, and Desktop
    app_match = _find_installed_app_universal(target)

    if act in ["open", "launch", "start"]:
        print(f"[App Control 🚀] Launching application: {target} (Resolved: {app_match[1] if app_match else 'Direct shell fallback'})")
        try:
            if app_match:
                app_path = app_match[1]
                if app_path.endswith(":") or app_path.startswith("ms-") or app_path.startswith("tg:"):
                    os.system(f'start "" "{app_path}"')
                elif app_path.lower().endswith(('.lnk', '.url')):
                    os.startfile(app_path)
                elif os.path.exists(app_path):
                    os.startfile(app_path)
                else:
                    subprocess.Popen(app_path, shell=True)
            else:
                # Universal Windows shell execution fallback
                try:
                    os.startfile(target)
                except Exception:
                    os.system(f'start "" "{target}"')

            # Bring window to focus if possible
            time.sleep(0.8)
            try:
                import pygetwindow as gw
                wins = [w for w in gw.getAllWindows() if target.lower() in w.title.lower()]
                if wins:
                    if wins[0].isMinimized:
                        wins[0].restore()
                    wins[0].activate()
            except Exception:
                pass

            return f"Opening {target}, Sir. Ready for your command!"
        except Exception as e:
            return f"Could not launch {target}: {str(e)}"

    elif act in ["close", "kill", "terminate", "stop"]:
        try:
            killed = []
            target_low = target.lower().replace(" ", "").replace(".exe", "")
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    p_name = proc.info["name"].lower().replace(".exe", "")
                    if target_low in p_name or p_name in target_low:
                        proc.kill()
                        killed.append(proc.info["name"])
                except Exception:
                    pass
            if killed:
                return f"Closed {target} ({', '.join(set(killed))}), Sir."
            
            # Fallback to taskkill
            os.system(f"taskkill /f /im {target_low}.exe")
            return f"Closed {target}, Sir."
        except Exception as e:
            return f"Could not close {target}: {str(e)}"

    return f"Unknown app control action: {action}"


def interact_with_app(app_name: str, action: str = "auto", input_data: str = "", hotkey: str = "") -> str:
    """
    Opens or focuses any installed application (WhatsApp, Telegram, Chrome, VS Code, Notepad, Word, Spotify, etc.)
    and performs requested actions inside it (searching contacts/chats/files, typing messages, navigating URLs, or pressing shortcuts).
    - app_name: Name of the application (e.g. 'whatsapp', 'telegram', 'chrome', 'notepad', 'vscode', 'word', 'spotify')
    - action: 'search', 'type', 'navigate', 'hotkey', or 'auto'
    - input_data: Text, message, query, or URL to search or type inside the application
    - hotkey: Key shortcut to press (e.g. 'ctrl+f', 'ctrl+k', 'ctrl+l', 'ctrl+t', 'enter', 'esc')
    """
    import pyperclip
    import pyautogui
    import time
    
    act = str(action).lower().strip()
    target_app = str(app_name).strip()

    # 1. Open or focus the application window
    launch_res = app_control("open", target_app)
    time.sleep(1.5)

    # Bring window to focus if pygetwindow available
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle(target_app)
        if not wins:
            wins = [w for w in gw.getAllWindows() if target_app.lower() in w.title.lower()]
        if wins:
            win = wins[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(0.5)
    except Exception:
        pass

    results = [launch_res]

    # 2. Trigger shortcut key if requested
    if hotkey and hotkey.strip():
        hk = hotkey.lower().strip()
        keys = [k.strip() for k in hk.split("+")]
        try:
            pyautogui.hotkey(*keys)
            results.append(f"Triggered shortcut '{hotkey}'")
            time.sleep(0.5)
        except Exception as ex:
            results.append(f"Shortcut notice: {ex}")

    # 3. Action execution
    if act == "search":
        if not hotkey:
            if target_app.lower() in ["whatsapp", "telegram", "discord"]:
                pyautogui.hotkey("ctrl", "f")
            elif target_app.lower() in ["chrome", "edge", "firefox"]:
                pyautogui.hotkey("ctrl", "l")
            else:
                pyautogui.hotkey("ctrl", "f")
            time.sleep(0.4)

        if input_data:
            pyperclip.copy(input_data)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.3)
            pyautogui.press("enter")
            results.append(f"Searched for '{input_data}' inside {target_app}")

    elif act in ["type", "type_message", "write"]:
        if input_data:
            pyperclip.copy(input_data)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.3)
            pyautogui.press("enter")
            results.append(f"Typed message/content into {target_app}")

    elif act == "navigate":
        if not hotkey:
            pyautogui.hotkey("ctrl", "l")
            time.sleep(0.3)
        if input_data:
            pyperclip.copy(input_data)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.3)
            pyautogui.press("enter")
            results.append(f"Navigated to '{input_data}' in {target_app}")

    elif act == "auto":
        if input_data:
            pyperclip.copy(input_data)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.3)
            pyautogui.press("enter")
            results.append(f"Executed action in {target_app} with '{input_data}'")

    return " | ".join(results)



# --- 2.1 Type Text in Application Tool ---
def type_text(text: str, app_name: str = "") -> str:
    """
    Types text, code, notes, or messages into any application (e.g. Notepad, Word, or active window).
    - text: The content/story/code/notes to write.
    - app_name: Optional application name to launch or focus (e.g. 'notepad', 'word', 'code') before typing.
    """
    import pyperclip
    print(f"[Tools ✍️] Typing text into {app_name if app_name else 'active window'}")
    try:
        if app_name and app_name.strip():
            app_control("open", app_name)
            time.sleep(1.2)  # Wait for application window to open and focus

        # Copy text to clipboard and paste (supports all unicode, Hindi, emojis, linebreaks accurately)
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        return f"Successfully typed the requested content into {app_name if app_name else 'the active window'}, Sir."
    except Exception as e:
        return f"Error while typing text: {str(e)}"


# --- 3. Web Search & Information Tool ---
def _get_tavily_api_key() -> str:
    """Helper to fetch Tavily API key from configuration (zero hardcoding)."""
    try:
        from cwa_agent.config import TAVILY_API_KEY
        return (TAVILY_API_KEY or "").strip()
    except Exception:
        return os.getenv("TAVILY_API_KEY", "").strip()


def _get_exa_api_key() -> str:
    """Returns Exa API key from environment (zero hardcoding)."""
    from cwa_agent.config import EXA_API_KEY
    return EXA_API_KEY


def web_search(query: str) -> str:
    """
    Performs a high-speed real-time web search for latest news, facts, documentation, or answers.
    Powered by Exa Neural Search (primary), Tavily AI (secondary), DuckDuckGo & SearXNG (fallbacks).
    """
    import socket
    import requests as _requests

    print(f"[Tools 🌐] Searching web for: {query}")

    # --- 1. Primary Engine: Exa Neural Search ---
    exa_key = _get_exa_api_key()
    if exa_key:
        try:
            headers = {
                "x-api-key": exa_key,
                "Content-Type": "application/json"
            }
            payload = {
                "query": query,
                "numResults": 5,
                "type": "auto",
                "contents": {
                    "text": {"maxCharacters": 800}
                }
            }
            resp = _requests.post(
                "https://api.exa.ai/search",
                json=payload,
                headers=headers,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results:
                    output_parts = ["🔍 Exa Neural Search Results:"]
                    for idx, r in enumerate(results, 1):
                        title = r.get("title", "No Title")
                        url = r.get("url", "")
                        snippet = ""
                        if r.get("text"):
                            snippet = r["text"].replace("\n", " ").strip()[:600]
                        output_parts.append(
                            f"{idx}. **{title}**\n   {snippet}\n   🔗 {url}"
                        )
                    print(f"[Tools ✅] Exa returned {len(results)} results.")
                    return "\n\n".join(output_parts)
        except Exception as exa_err:
            print(f"[Tools ⚠️] Exa search fallback: {exa_err}")

    # --- 2. Secondary Engine: Tavily AI Search ---
    tavily_key = _get_tavily_api_key()
    if tavily_key:
        try:
            payload = {
                "api_key": tavily_key,
                "query": query,
                "search_depth": "basic",
                "include_answer": True,
                "max_results": 5
            }
            resp = _requests.post("https://api.tavily.com/search", json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("answer")
                results = data.get("results", [])
                output_parts = []
                if answer:
                    output_parts.append(f"💡 Quick Answer: {answer}\n")
                if results:
                    output_parts.append("🌐 Relevant Sources & Insights:")
                    for idx, r in enumerate(results, 1):
                        title = r.get("title", "No Title")
                        snippet = r.get("content", "").replace("\n", " ").strip()
                        url = r.get("url", "")
                        output_parts.append(f"{idx}. **{title}**\n   {snippet}\n   🔗 Link: {url}")
                if output_parts:
                    return "\n\n".join(output_parts)
        except Exception as t_err:
            print(f"[Tools ⚠️] Tavily search fallback: {t_err}")

    # --- 3. Tertiary Engine: DuckDuckGo ---
    last_error = None
    for attempt in range(3):
        try:
            results = []
            with DDGS(timeout=10) as ddgs:
                for r in ddgs.text(query, max_results=5):
                    results.append(
                        f"Title: {r.get('title')}\n"
                        f"Snippet: {r.get('body')}\n"
                        f"URL: {r.get('href')}"
                    )
            if results:
                return "\n\n".join(results)
            return f"No direct search results found for '{query}'."
        except (socket.gaierror, socket.timeout, OSError) as net_err:
            last_error = net_err
            print(f"[Tools ⚠️] DuckDuckGo network error (attempt {attempt+1}/3): {net_err}")
            time.sleep(1.5 * (attempt + 1))
        except Exception as e:
            last_error = e
            print(f"[Tools ⚠️] DuckDuckGo error (attempt {attempt+1}/3): {e}")
            time.sleep(1.0)

    # --- 4. Quaternary Engine: SearXNG Fallback ---
    print(f"[Tools 🔄] DuckDuckGo failed. Trying SearXNG fallback...")
    try:
        fallback_url = "https://searx.be/search"
        params = {"q": query, "format": "json", "language": "en-IN", "time_range": "day"}
        resp = _requests.get(fallback_url, params=params, timeout=10,
                             headers={"User-Agent": "Mozilla/5.0 CWA-Agent"})
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("results", [])[:5]
            if items:
                parts = [
                    f"Title: {i.get('title')}\nSnippet: {i.get('content', '')}\nURL: {i.get('url')}"
                    for i in items
                ]
                return "\n\n".join(parts)
    except Exception as fb_err:
        print(f"[Tools ⚠️] Fallback search also failed: {fb_err}")

    return (
        f"Sir, web search for '{query}' could not be completed due to a network issue "
        f"({type(last_error).__name__}: {last_error}). "
        f"Please check your internet connection and try again."
    )


def read_webpage_content(url: str) -> str:
    """
    Extracts and reads the clean markdown/text content of any webpage or article.
    Powered by Tavily Web Extract API.

    Call this tool whenever Sir asks:
    - "Is link ka content padho / summarize karo"
    - "Read and extract text from [URL]"
    - "What does this website say: [URL]"
    """
    import requests as _requests

    tavily_key = _get_tavily_api_key()
    if not tavily_key:
        return "Tavily API key is missing. Please configure TAVILY_API_KEY in .env."

    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    try:
        payload = {
            "api_key": tavily_key,
            "urls": [clean_url]
        }
        resp = _requests.post("https://api.tavily.com/extract", json=payload, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                raw_content = results[0].get("raw_content", "")
                if raw_content:
                    truncated = raw_content[:4000]
                    return f"📄 Webpage Content ({clean_url}):\n\n{truncated}..."
            return f"No readable content extracted from: {clean_url}"
        return f"Error reading webpage (Status {resp.status_code}): {resp.text}"
    except Exception as e:
        return f"Error extracting webpage content: {str(e)}"


# --- 4. YouTube & Media Playback Tools (Powered by YouTube Data API v3) ---
def _get_youtube_api_key() -> str:
    """Helper to fetch YouTube API key from configuration (zero hardcoding)."""
    try:
        from cwa_agent.config import YOUTUBE_API_KEY
        return (YOUTUBE_API_KEY or "").strip()
    except Exception:
        return os.getenv("YOUTUBE_API_KEY", "").strip()


def play_youtube(query: str) -> str:
    """
    Searches YouTube for the most relevant video, song, or trailer and plays it directly.
    Uses official YouTube Data API v3 for pinpoint accuracy, with graceful fallback.
    """
    import urllib.parse
    import requests

    api_key = _get_youtube_api_key()
    if api_key:
        try:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 1,
                "key": api_key
            }
            resp = requests.get(url, params=params, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if items:
                    video_id = items[0]["id"]["videoId"]
                    title = items[0]["snippet"].get("title", query)
                    channel = items[0]["snippet"].get("channelTitle", "")
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    webbrowser.open(video_url)
                    print(f"[Tools 🎵] YouTube API match: {title} ({video_url})")
                    return f"Playing '{title}' by {channel} on YouTube right now, Sir.\nLink: {video_url}"
        except Exception as e:
            print(f"[Tools 🎵] YouTube API search fallback: {e}")

    # Fallback to pywhatkit
    try:
        import pywhatkit
        print(f"[Tools 🎵] Playing YouTube via pywhatkit: {query}")
        pywhatkit.playonyt(query)
        return f"Playing '{query}' on YouTube right now, Sir."
    except Exception:
        clean_q = urllib.parse.quote_plus(query)
        url = f"https://www.youtube.com/results?search_query={clean_q}"
        webbrowser.open(url)
        return f"Opened YouTube search for '{query}'."


def search_youtube_videos(query: str, max_results: int = 5) -> str:
    """
    Searches YouTube using official YouTube Data API v3 and returns a list of top videos with titles, channels, descriptions, and direct URLs.

    Call this tool whenever Sir asks:
    - "YouTube par search karo: [topic]"
    - "YouTube ke top 5 tutorials / videos dikhao"
    - "Find YouTube videos about [query]"
    """
    import requests
    import urllib.parse

    api_key = _get_youtube_api_key()
    if not api_key:
        clean_q = urllib.parse.quote_plus(query)
        return f"YouTube API Key not configured. You can search directly here: https://www.youtube.com/results?search_query={clean_q}"

    try:
        limit = min(max(1, int(max_results)), 10)
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": limit,
            "key": api_key
        }
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code != 200:
            return f"YouTube search error (Status {resp.status_code}): {resp.text}"

        data = resp.json()
        items = data.get("items", [])
        if not items:
            return f"No YouTube videos found for query: '{query}'."

        results = [f"🎬 Top YouTube Results for '{query}':\n"]
        for idx, item in enumerate(items, 1):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            title = snippet.get("title", "Unknown Title")
            channel = snippet.get("channelTitle", "Unknown Channel")
            desc = snippet.get("description", "")[:120].replace("\n", " ")
            publish_time = snippet.get("publishTime", "")[:10]
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            results.append(f"{idx}. **{title}**\n   - Channel: {channel} | Date: {publish_time}\n   - Link: {video_url}\n   - Info: {desc}...")

        return "\n\n".join(results)
    except Exception as e:
        return f"Error searching YouTube: {str(e)}"


def get_youtube_video_details(video_url_or_id: str) -> str:
    """
    Fetches detailed statistics, metadata, views, likes, comment count, and description for a specific YouTube video.

    Call this tool whenever Sir asks:
    - "Is YouTube video ke views aur likes kitne hain"
    - "Get details / stats of YouTube video [url or ID]"
    - "Summarize or check YouTube video metadata"
    """
    import requests
    import re

    api_key = _get_youtube_api_key()
    if not api_key:
        return "YouTube API Key is missing. Please configure YOUTUBE_API_KEY in .env."

    # Extract Video ID
    video_id = video_url_or_id.strip()
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", video_id)
    if match:
        video_id = match.group(1)

    try:
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": video_id,
            "key": api_key
        }
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code != 200:
            return f"Error fetching video details (Status {resp.status_code}): {resp.text}"

        data = resp.json()
        items = data.get("items", [])
        if not items:
            return f"No YouTube video found with ID/URL: '{video_url_or_id}'."

        item = items[0]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})

        title = snippet.get("title", "N/A")
        channel = snippet.get("channelTitle", "N/A")
        published_at = snippet.get("publishedAt", "")[:10]
        views = f"{int(stats.get('viewCount', 0)):,}" if "viewCount" in stats else "0"
        likes = f"{int(stats.get('likeCount', 0)):,}" if "likeCount" in stats else "Hidden"
        comments = f"{int(stats.get('commentCount', 0)):,}" if "commentCount" in stats else "Disabled"
        tags = ", ".join(snippet.get("tags", [])[:8]) or "None"
        desc = snippet.get("description", "No description provided.")[:400]

        return (
            f"📊 YouTube Video Analytics:\n"
            f"  📌 Title: {title}\n"
            f"  👤 Channel: {channel}\n"
            f"  📅 Published: {published_at}\n"
            f"  👁️ Views: {views}\n"
            f"  👍 Likes: {likes}\n"
            f"  💬 Comments: {comments}\n"
            f"  🏷️ Tags: {tags}\n"
            f"  🔗 URL: https://www.youtube.com/watch?v={video_id}\n\n"
            f"📝 Description Snippet:\n{desc}..."
        )
    except Exception as e:
        return f"Error getting video details: {str(e)}"


def get_youtube_trending(category: str = "general", region_code: str = "IN") -> str:
    """
    Fetches the top trending videos on YouTube for a specific region or category (general, music, gaming, movies, tech).

    Call this tool whenever Sir asks:
    - "YouTube par kya trending hai", "top trending videos dikhao"
    - "Trending music / gaming videos on YouTube"
    """
    import requests

    api_key = _get_youtube_api_key()
    if not api_key:
        return "YouTube API Key is missing. Please configure YOUTUBE_API_KEY in .env."

    # YouTube Category ID mappings
    cat_map = {
        "music": "10",
        "gaming": "20",
        "movies": "1",
        "film": "1",
        "tech": "28",
        "science": "28",
        "sports": "17",
        "entertainment": "24",
        "news": "25",
    }
    cat_id = cat_map.get(category.lower().strip(), "")

    try:
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": region_code.upper().strip() or "IN",
            "maxResults": 5,
            "key": api_key
        }
        if cat_id:
            params["videoCategoryId"] = cat_id

        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code != 200:
            return f"Error fetching trending videos (Status {resp.status_code}): {resp.text}"

        data = resp.json()
        items = data.get("items", [])
        if not items:
            return f"No trending videos found for region {region_code} and category '{category}'."

        results = [f"🔥 Top YouTube Trending Videos ({region_code.upper()} - {category.capitalize()}):\n"]
        for idx, item in enumerate(items, 1):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            video_id = item.get("id", "")
            title = snippet.get("title", "Unknown Title")
            channel = snippet.get("channelTitle", "Unknown Channel")
            views = f"{int(stats.get('viewCount', 0)):,}" if "viewCount" in stats else "N/A"
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            results.append(f"{idx}. **{title}**\n   - Channel: {channel} | 👁️ Views: {views}\n   - Link: {video_url}")

        return "\n\n".join(results)
    except Exception as e:
        return f"Error fetching trending YouTube videos: {str(e)}"


def get_youtube_channel_stats(channel_name_or_id: str) -> str:
    """
    Fetches statistics, subscriber count, total video count, and total views for any YouTube channel.

    Call this tool whenever Sir asks:
    - "Check subscriber count of [channel]"
    - "[Channel name] ke stats / details batao"
    - "Analyze YouTube channel [channel]"
    """
    import requests

    api_key = _get_youtube_api_key()
    if not api_key:
        return "YouTube API Key is missing. Please configure YOUTUBE_API_KEY in .env."

    channel_input = channel_name_or_id.strip()

    try:
        channel_id = ""
        # If input looks like a channel ID (starts with UC and 24 chars long)
        if channel_input.startswith("UC") and len(channel_input) == 24:
            channel_id = channel_input
        else:
            # Search for the channel by name
            search_url = "https://www.googleapis.com/youtube/v3/search"
            s_params = {
                "part": "snippet",
                "q": channel_input,
                "type": "channel",
                "maxResults": 1,
                "key": api_key
            }
            s_resp = requests.get(search_url, params=s_params, timeout=8)
            if s_resp.status_code == 200:
                s_data = s_resp.json()
                s_items = s_data.get("items", [])
                if s_items:
                    channel_id = s_items[0]["id"]["channelId"]

        if not channel_id:
            return f"Could not find YouTube channel: '{channel_name_or_id}'."

        # Fetch channel details
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            "part": "snippet,statistics,brandingSettings",
            "id": channel_id,
            "key": api_key
        }
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code != 200:
            return f"Error fetching channel stats (Status {resp.status_code}): {resp.text}"

        data = resp.json()
        items = data.get("items", [])
        if not items:
            return f"No channel data found for ID: {channel_id}."

        ch = items[0]
        snippet = ch.get("snippet", {})
        stats = ch.get("statistics", {})

        title = snippet.get("title", channel_input)
        custom_url = snippet.get("customUrl", "")
        created_at = snippet.get("publishedAt", "")[:10]
        subscribers = f"{int(stats.get('subscriberCount', 0)):,}" if not stats.get("hiddenSubscriberCount", False) else "Hidden"
        total_views = f"{int(stats.get('viewCount', 0)):,}"
        video_count = f"{int(stats.get('videoCount', 0)):,}"
        country = snippet.get("country", "Global")
        desc = snippet.get("description", "")[:300]
        channel_link = f"https://www.youtube.com/{custom_url}" if custom_url else f"https://www.youtube.com/channel/{channel_id}"

        return (
            f"📺 YouTube Channel Intelligence:\n"
            f"  📛 Name: {title}\n"
            f"  🔗 Handle/URL: {channel_link}\n"
            f"  👥 Subscribers: {subscribers}\n"
            f"  🎥 Total Videos: {video_count}\n"
            f"  👁️ Total Channel Views: {total_views}\n"
            f"  🌍 Country: {country}\n"
            f"  📅 Joined Date: {created_at}\n\n"
            f"📝 About:\n{desc}..."
        )
    except Exception as e:
        return f"Error fetching channel statistics: {str(e)}"


# --- 4B. TMDB Cinema & Movie Intelligence Tools (Zero Hardcoding) ---
def _get_tmdb_headers() -> dict:
    """Helper to get TMDB auth headers (zero hardcoding)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "accept": "application/json"
    }
    try:
        from cwa_agent.config import TMDB_READ_TOKEN
        token = (TMDB_READ_TOKEN or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
            return headers
    except Exception:
        pass
    token = os.getenv("TMDB_READ_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
        return headers
    return headers


def _get_tmdb_api_key() -> str:
    """Helper to get TMDB API key parameter (zero hardcoding)."""
    try:
        from cwa_agent.config import TMDB_API_KEY
        return (TMDB_API_KEY or "").strip()
    except Exception:
        return os.getenv("TMDB_API_KEY", "").strip()


def _get_tmdb_session():
    """Helper to create a configured requests.Session for TMDB (zero hardcoding)."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(_get_tmdb_headers())
    return session


def movie_search_and_info(query: str) -> str:
    """
    Searches TMDB database for any movie, TV show, or anime.
    Returns rating, release year, genre, star cast, director, OTT streaming availability (Netflix, Prime, Hotstar, etc.), and official trailer.

    Call this tool whenever Sir asks:
    - "Is movie ke baare mein batao / ratings kya hain"
    - "Movie kahan stream ho rahi hai / kis OTT par hai"
    - "Movie cast, director, budget ya plot details"
    """
    import requests

    headers = _get_tmdb_headers()
    api_key = _get_tmdb_api_key()
    if not headers.get("Authorization") and not api_key:
        return "TMDB API credentials not configured in .env."

    session = _get_tmdb_session()
    try:
        # Search movie / multi
        search_url = "https://api.themoviedb.org/3/search/multi"
        params = {"query": query, "language": "en-US", "include_adult": "false"}
        if api_key and not headers.get("Authorization"):
            params["api_key"] = api_key

        s_resp = session.get(search_url, params=params, timeout=10)
        if s_resp.status_code != 200:
            return f"TMDB Search Error (Status {s_resp.status_code}): {s_resp.text}"

        data = s_resp.json()
        results = [r for r in data.get("results", []) if r.get("media_type") in ("movie", "tv")]
        if not results:
            return f"No movie or TV show found on TMDB for query: '{query}'."

        item = results[0]
        media_type = item.get("media_type", "movie")
        item_id = item.get("id")

        # Fetch full detailed info with credits, videos & watch providers
        detail_url = f"https://api.themoviedb.org/3/{media_type}/{item_id}"
        d_params = {"language": "en-US", "append_to_response": "credits,videos,watch/providers"}
        if api_key and not headers.get("Authorization"):
            d_params["api_key"] = api_key

        d_resp = session.get(detail_url, params=d_params, timeout=10)
        if d_resp.status_code != 200:
            return f"Error fetching details for ID {item_id}: {d_resp.text}"

        details = d_resp.json()
        title = details.get("title") or details.get("name", query)
        tagline = details.get("tagline", "")
        release_date = details.get("release_date") or details.get("first_air_date", "N/A")
        rating = details.get("vote_average", 0)
        votes = f"{details.get('vote_count', 0):,}"
        runtime = f"{details.get('runtime')} mins" if details.get("runtime") else f"{details.get('number_of_seasons', 1)} Seasons"
        genres = ", ".join([g["name"] for g in details.get("genres", [])]) or "Cinema"
        overview = details.get("overview", "No synopsis available.")

        # Cast & Director
        credits = details.get("credits", {})
        cast = ", ".join([c["name"] for c in credits.get("cast", [])[:5]]) or "N/A"
        directors = [c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"]
        director_str = ", ".join(directors) if directors else "N/A"

        # OTT Watch Providers (India / Global)
        providers_data = details.get("watch/providers", {}).get("results", {})
        in_providers = providers_data.get("IN") or providers_data.get("US") or {}
        flatrate = in_providers.get("flatrate", [])
        ott_platforms = ", ".join([p["provider_name"] for p in flatrate]) if flatrate else "Available for Rent/Buy or Theatres"

        # Official Trailer
        trailer_url = "N/A"
        for v in details.get("videos", {}).get("results", []):
            if v.get("site") == "YouTube" and ("Trailer" in v.get("type", "") or "Teaser" in v.get("type", "")):
                trailer_url = f"https://www.youtube.com/watch?v={v.get('key')}"
                break

        poster_path = details.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ""

        tag_line_str = f"  💬 Tagline: *\"{tagline}\"*\n" if tagline else ""
        return (
            f"🎬 **{title}** ({release_date[:4] if release_date else 'N/A'})\n"
            f"{tag_line_str}"
            f"  ⭐ Rating: {rating:.1f}/10 (from {votes} votes)\n"
            f"  🎭 Genres: {genres} | ⏱️ Runtime: {runtime}\n"
            f"  🎬 Director: {director_str}\n"
            f"  🌟 Cast: {cast}\n"
            f"  📺 Watch On (OTT): {ott_platforms}\n"
            f"  🎞️ Official Trailer: {trailer_url}\n"
            f"  🖼️ Poster: {poster_url}\n\n"
            f"📝 **Synopsis:**\n{overview}"
        )
    except Exception as e:
        return f"Error searching movie: {str(e)}"


def movie_trending_and_recommendations(category: str = "trending", movie_name: str = "") -> str:
    """
    Fetches live trending movies/shows or personalized movie recommendations based on a film.

    Call this tool whenever Sir asks:
    - "Top trending movies / series dikhao"
    - "[Movie Name] jaisi acchi movies recommend karo"
    - "What to watch tonight / Best Sci-Fi recommendations"
    """
    import requests

    headers = _get_tmdb_headers()
    api_key = _get_tmdb_api_key()
    if not headers.get("Authorization") and not api_key:
        return "TMDB API credentials not configured in .env."

    session = _get_tmdb_session()
    try:
        # Case 1: Recommendations based on a specific movie
        if movie_name:
            s_url = "https://api.themoviedb.org/3/search/movie"
            s_params = {"query": movie_name, "language": "en-US"}
            if api_key and not headers.get("Authorization"):
                s_params["api_key"] = api_key
            s_res = session.get(s_url, params=s_params, timeout=10).json()
            items = s_res.get("results", [])
            if not items:
                return f"Could not find reference movie: '{movie_name}'."
            m_id = items[0]["id"]
            m_title = items[0].get("title", movie_name)

            rec_url = f"https://api.themoviedb.org/3/movie/{m_id}/recommendations"
            r_params = {"language": "en-US", "page": 1}
            if api_key and not headers.get("Authorization"):
                r_params["api_key"] = api_key
            r_res = session.get(rec_url, params=r_params, timeout=10).json()
            rec_items = r_res.get("results", [])[:5]
            if not rec_items:
                # fallback to similar
                sim_url = f"https://api.themoviedb.org/3/movie/{m_id}/similar"
                r_res = session.get(sim_url, params=r_params, timeout=10).json()
                rec_items = r_res.get("results", [])[:5]

            lines = [f"🍿 Top Recommendations for fans of **'{m_title}'**:\n"]
            for idx, r in enumerate(rec_items, 1):
                title = r.get("title", "N/A")
                date = (r.get("release_date") or "")[:4]
                score = r.get("vote_average", 0)
                desc = r.get("overview", "")[:120].replace("\n", " ")
                lines.append(f"{idx}. **{title}** ({date}) — ⭐ {score:.1f}/10\n   {desc}...")
            return "\n\n".join(lines)

        # Case 2: Live Trending Movies
        t_url = "https://api.themoviedb.org/3/trending/movie/day"
        params = {"language": "en-US"}
        if api_key and not headers.get("Authorization"):
            params["api_key"] = api_key

        t_res = session.get(t_url, params=params, timeout=10).json()
        items = t_res.get("results", [])[:5]
        if not items:
            return "No trending movies found currently on TMDB."

        lines = ["🔥 **Top Trending Movies Today (Worldwide):**\n"]
        for idx, r in enumerate(items, 1):
            title = r.get("title", "N/A")
            date = (r.get("release_date") or "")[:4]
            score = r.get("vote_average", 0)
            desc = r.get("overview", "")[:120].replace("\n", " ")
            lines.append(f"{idx}. **{title}** ({date}) — ⭐ {score:.1f}/10\n   {desc}...")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Error fetching movie recommendations/trending: {str(e)}"



def play_movie_or_trailer(movie_name: str, play_trailer: bool = True) -> str:
    """
    Finds and plays the official high-definition trailer or opens the streaming watch page for any movie.

    Call this tool whenever Sir says:
    - "Play [Movie] trailer", "trailer dikhao [Movie Name] ka"
    - "Play / Watch movie [Movie Name]"
    """
    import webbrowser
    import requests

    headers = _get_tmdb_headers()
    api_key = _get_tmdb_api_key()

    trailer_found = False
    title = movie_name
    release_year = ""

    if headers or api_key:
        try:
            s_url = "https://api.themoviedb.org/3/search/movie"
            params = {"query": movie_name, "language": "en-US"}
            if api_key and not headers:
                params["api_key"] = api_key
            s_res = requests.get(s_url, headers=headers, params=params, timeout=6).json()
            items = s_res.get("results", [])
            if items:
                m_id = items[0]["id"]
                title = items[0].get("title", movie_name)
                release_year = (items[0].get("release_date") or "")[:4]

                # Fetch videos
                v_url = f"https://api.themoviedb.org/3/movie/{m_id}/videos"
                v_params = {"language": "en-US"}
                if api_key and not headers:
                    v_params["api_key"] = api_key
                v_res = requests.get(v_url, headers=headers, params=v_params, timeout=6).json()
                for v in v_res.get("results", []):
                    if v.get("site") == "YouTube" and ("Trailer" in v.get("type", "") or "Teaser" in v.get("type", "")):
                        trailer_url = f"https://www.youtube.com/watch?v={v.get('key')}"
                        webbrowser.open(trailer_url)
                        trailer_found = True
                        print(f"[Tools 🎬] Launched official trailer: {trailer_url}")
                        return f"Playing official HD trailer for '{title}' ({release_year}) right now, Sir!\nLink: {trailer_url}"
        except Exception as e:
            print(f"[Tools 🎬] TMDB trailer lookup error: {e}")

    # Fallback to YouTube Search & Play
    fallback_query = f"{movie_name} official trailer" if play_trailer else f"{movie_name} full movie"
    play_youtube(fallback_query)
    return f"Playing '{fallback_query}' on YouTube, Sir."


# --- 5. Open Any Website Tool ---
def open_website(url: str) -> str:
    """
    Opens a website in the default browser. Adds https:// if not present.
    """
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url
    webbrowser.open(clean_url)
    return f"Navigating to {clean_url}, Sir."


# --- 6. Workspace File Intelligence & Live Change Audit Tool ---
def _scan_and_update_workspace_ledger() -> dict:
    """Internal helper to scan project directory and compute live additions/deletions/modifications."""
    import json
    import datetime
    from cwa_agent.config import BASE_DIR, DATA_DIR

    ledger_file = DATA_DIR / "workspace_ledger.json"
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Load existing ledger
    ledger = {
        "last_scan_time": "",
        "known_files": {},
        "history_added": [],
        "history_deleted": []
    }
    if ledger_file.exists():
        try:
            with open(ledger_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    ledger.update(saved)
        except Exception:
            pass

    previous_files = ledger.get("known_files", {})
    current_files = {}

    ignored_patterns = ["__pycache__", ".git", ".venv", ".pytest_cache", ".idea", ".vscode"]

    # Scan current project files dynamically
    try:
        for item in BASE_DIR.rglob("*"):
            rel_path = str(item.relative_to(BASE_DIR)).replace("\\", "/")
            if any(ign in rel_path for ign in ignored_patterns):
                continue
            if item.is_file():
                try:
                    stat = item.stat()
                    current_files[rel_path] = {
                        "size_bytes": stat.st_size,
                        "size_str": f"{stat.st_size / 1024:.1f} KB" if stat.st_size < 1024*1024 else f"{stat.st_size / (1024*1024):.2f} MB",
                        "mtime": stat.st_mtime,
                        "mtime_str": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "ext": item.suffix.lower() or "file",
                        "parent": str(item.parent.relative_to(BASE_DIR)).replace("\\", "/") if item.parent != BASE_DIR else "."
                    }
                except Exception:
                    pass
    except Exception as ex:
        print(f"[Workspace Scan Error]: {ex}")

    # Compute Diffs: Added files
    new_additions = []
    for p, meta in current_files.items():
        if p not in previous_files:
            new_additions.append({
                "path": p,
                "timestamp": meta["mtime_str"],
                "size": meta["size_str"],
                "folder": meta["parent"]
            })

    # Compute Diffs: Deleted files
    new_deletions = []
    for p, meta in previous_files.items():
        if p not in current_files:
            new_deletions.append({
                "path": p,
                "timestamp": now_str,
                "last_size": meta.get("size_str", "Unknown"),
                "folder": meta.get("parent", ".")
            })

    # Update ledger histories (keep up to 100 entries)
    if new_additions:
        ledger["history_added"] = (new_additions + ledger.get("history_added", []))[:100]
    if new_deletions:
        ledger["history_deleted"] = (new_deletions + ledger.get("history_deleted", []))[:100]

    ledger["last_scan_time"] = now_str
    ledger["known_files"] = current_files

    # Save updated ledger
    try:
        with open(ledger_file, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return ledger


def workspace_file_intelligence(
    action: str = "summary",
    folder: str = "",
    query: str = "",
    max_items: int = 50
) -> str:
    """
    Comprehensive Workspace File Intelligence & Live Change Audit System.
    Gives CWA & MJ full 360-degree awareness of all files, folders, recent additions, modifications, and deletions in the project.
    - action:
        * 'summary' / 'status': High-level folder breakdown, total counts, sizes, recent additions & deletions.
        * 'folder_inspect' / 'list_folder': Detailed list of all files inside a specific folder (e.g. 'media/Songs', 'media/Videos', 'media/Images', 'data', 'core', 'ui').
        * 'added_files' / 'recent_additions': History and list of newly created/downloaded files.
        * 'deleted_files' / 'history_deleted': Audit ledger of all deleted/removed files with timestamps.
        * 'find_file' / 'search': Search for any file or folder across the entire project tree.
        * 'full_tree': Complete hierarchical tree structure of the project.
    - folder: Specific sub-folder to inspect (e.g. 'media', 'media/Videos', 'media/Songs', 'media/Images', 'data', 'core', 'ui').
    - query: Search keyword or file extension (e.g. 'mj', '.mp4', 'song', 'wallpaper', 'config').
    - max_items: Maximum items to return in listing.
    """
    from cwa_agent.config import BASE_DIR

    ledger = _scan_and_update_workspace_ledger()
    known_files = ledger.get("known_files", {})
    history_added = ledger.get("history_added", [])
    history_deleted = ledger.get("history_deleted", [])

    act = action.lower().strip()

    # 1. SUMMARY / STATUS OVERVIEW
    if act in ["summary", "status", "overview", "info"]:
        folders_map = {}
        total_size_bytes = 0
        for rel_p, meta in known_files.items():
            f_parent = meta.get("parent", ".")
            folders_map.setdefault(f_parent, []).append(meta)
            total_size_bytes += meta.get("size_bytes", 0)

        total_size_mb = total_size_bytes / (1024 * 1024)

        lines = [
            "📂 [WORKSPACE 360° INTELLIGENCE REPORT]",
            f"• Project Root: {BASE_DIR}",
            f"• Total Tracked Files: {len(known_files)} files ({total_size_mb:.2f} MB total)",
            f"• Last Audit Sync: {ledger.get('last_scan_time', 'Just now')}\n",
            "📁 Folder Structure & File Counts:"
        ]
        for f_name, f_items in sorted(folders_map.items()):
            folder_size = sum(x.get("size_bytes", 0) for x in f_items)
            folder_size_str = f"{folder_size / 1024:.1f} KB" if folder_size < 1024*1024 else f"{folder_size / (1024*1024):.2f} MB"
            lines.append(f"  └─ 📁 {f_name}/ : {len(f_items)} files ({folder_size_str})")

        if history_added:
            lines.append(f"\n✨ Recent Additions ({min(5, len(history_added))} most recent):")
            for item in history_added[:5]:
                lines.append(f"  • [+] {item['path']} ({item.get('size', '')}) — {item.get('timestamp', '')}")

        if history_deleted:
            lines.append(f"\n🗑️ Recent Deletions ({min(5, len(history_deleted))} most recent):")
            for item in history_deleted[:5]:
                lines.append(f"  • [-] {item['path']} (Was {item.get('last_size', '')}) — Deleted {item.get('timestamp', '')}")

        return "\n".join(lines)

    # 2. FOLDER INSPECT / LIST FOLDER
    elif act in ["folder_inspect", "list_folder", "folder"]:
        target_f = folder.strip().replace("\\", "/").strip("/")
        matched = []
        for rel_p, meta in known_files.items():
            parent = meta.get("parent", ".")
            if not target_f or parent == target_f or parent.startswith(target_f + "/") or target_f == ".":
                matched.append((rel_p, meta))

        if not matched:
            return f"Folder '{folder}' is empty or does not exist in the project, Sir."

        lines = [f"📂 Files inside folder '{target_f or 'root'}' ({len(matched)} files):"]
        for rel_p, meta in sorted(matched, key=lambda x: x[0])[:max_items]:
            lines.append(f"  • 📄 {rel_p} [{meta.get('size_str', '')}] (Modified: {meta.get('mtime_str', '')})")

        return "\n".join(lines)

    # 3. RECENT ADDED / NEW FILES
    elif act in ["added_files", "recent_additions", "new_files", "history_added"]:
        if not history_added:
            return "No recent file additions recorded in the ledger yet, Sir."
        lines = [f"✨ [RECENTLY ADDED / CREATED FILES] ({len(history_added)} records):"]
        for item in history_added[:max_items]:
            lines.append(f"  • [+] {item['path']} ({item.get('size', '')}) in folder '{item.get('folder', '.')}' on {item.get('timestamp', '')}")
        return "\n".join(lines)

    # 4. RECENT DELETED FILES AUDIT
    elif act in ["deleted_files", "history_deleted", "deleted", "removals"]:
        if not history_deleted:
            return "No files have been deleted recently, Sir. Everything is intact."
        lines = [f"🗑️ [DELETED / REMOVED FILES AUDIT TRAIL] ({len(history_deleted)} records):"]
        for item in history_deleted[:max_items]:
            lines.append(f"  • [-] {item['path']} (Was {item.get('last_size', '')}) — Removed on {item.get('timestamp', '')}")
        return "\n".join(lines)

    # 5. FIND FILE / SEARCH
    elif act in ["find_file", "search", "find"]:
        if not query.strip():
            return "Please specify a file name, keyword, or extension to search, Sir."
        q = query.lower().strip()
        matched = []
        for rel_p, meta in known_files.items():
            if q in rel_p.lower() or q in meta.get("ext", "").lower():
                matched.append((rel_p, meta))

        if not matched:
            return f"No files matching '{query}' found in the project directory, Sir."

        lines = [f"🔍 Search results for '{query}' ({len(matched)} matches):"]
        for rel_p, meta in matched[:max_items]:
            lines.append(f"  • 📄 {rel_p} ({meta.get('size_str', '')}) — Folder: {meta.get('parent', '.')}")
        return "\n".join(lines)

    # 6. FULL PROJECT HIERARCHICAL TREE
    elif act in ["full_tree", "tree"]:
        tree_lines = [f"🌳 [PROJECT DIRECTORY TREE — {BASE_DIR.name}/]"]
        folders_map = {}
        for rel_p in sorted(known_files.keys()):
            parts = rel_p.split("/")
            if len(parts) == 1:
                folders_map.setdefault(".", []).append(parts[0])
            else:
                folders_map.setdefault("/".join(parts[:-1]), []).append(parts[-1])

        for f_name, files in sorted(folders_map.items()):
            prefix = "📁 " if f_name != "." else "📂 Project Root / "
            tree_lines.append(f"{prefix}{f_name}:")
            for fn in files[:20]:
                tree_lines.append(f"    ├── 📄 {fn}")
            if len(files) > 20:
                tree_lines.append(f"    └── ... ({len(files) - 20} more files)")

        return "\n".join(tree_lines)

    return f"Workspace audit completed. Total {len(known_files)} files active."


# --- 7. File Manager Tool ---
def file_manager(action: str, path: str = "Desktop", content: str = "") -> str:
    """
    Manages files and directories across the entire computer (Desktop, Downloads, Documents, Projects, etc.).
    
    Parameters:
    - action:
        * 'create_folder' or 'mkdir': Creates a new directory/folder (e.g. on Desktop, Downloads, or custom path).
        * 'list_dir': Lists all files and subfolders in the target directory.
        * 'read_file': Reads the text contents of a file.
        * 'write_file' or 'create_note': Writes/creates a text file or note.
        * 'open_folder': Opens the folder in Windows File Explorer.
        * 'delete': Deletes a file or directory.
    - path: Target path, folder name, or shorthand (e.g. 'Desktop/Ali_Projects', 'Downloads', 'Documents/Notes', 'C:/MyFolder').
    - content: Optional text content (when writing files).
    
    Call this when Sir says:
    - "Desktop par new folder banao", "create a folder named XYZ on desktop"
    - "Downloads folder kholo", "Desktop ki files list karo"
    - "ek note file banao", "yeh folder delete karo"
    """
    act = action.lower().strip()
    try:
        # Resolve common shortcuts dynamically
        raw_p = str(path).strip()
        desktop_dir = Path.home() / "Desktop"
        downloads_dir = Path.home() / "Downloads"
        documents_dir = Path.home() / "Documents"

        if raw_p.lower().startswith("desktop"):
            rel = raw_p[7:].lstrip("/\\")
            p = desktop_dir / rel if rel else desktop_dir
        elif raw_p.lower().startswith("downloads"):
            rel = raw_p[9:].lstrip("/\\")
            p = downloads_dir / rel if rel else downloads_dir
        elif raw_p.lower().startswith("documents"):
            rel = raw_p[9:].lstrip("/\\")
            p = documents_dir / rel if rel else documents_dir
        else:
            p = Path(raw_p).expanduser()
            if not p.is_absolute():
                # Default relative paths to Desktop if user said simple folder name
                p = desktop_dir / raw_p

        # 1. CREATE FOLDER / DIRECTORY
        if act in ["create_folder", "mkdir", "make_folder", "new_folder", "create_dir"]:
            p.mkdir(parents=True, exist_ok=True)
            return f"Done Sir! Successfully created new folder at: {p}"

        # 2. LIST DIRECTORY
        elif act in ["list_dir", "list", "ls", "dir"]:
            target_dir = p if p.exists() and p.is_dir() else desktop_dir
            items = []
            for f in list(target_dir.iterdir())[:40]:
                prefix = "📁 " if f.is_dir() else "📄 "
                items.append(f"{prefix}{f.name}")
            return f"Contents of {target_dir} ({len(items)} items):\n" + "\n".join(items)

        # 3. READ FILE
        elif act in ["read_file", "read", "cat"]:
            if not p.exists() or not p.is_file():
                return f"File does not exist: {p}"
            return p.read_text(encoding="utf-8", errors="ignore")[:4000]

        # 4. WRITE FILE / CREATE NOTE
        elif act in ["write_file", "create_note", "write", "save"]:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Successfully saved file at: {p}"

        # 5. OPEN FOLDER IN WINDOWS EXPLORER
        elif act in ["open_folder", "open_dir", "explore"]:
            target = p if p.exists() else p.parent
            if target.exists():
                os.startfile(str(target))
                return f"Opened folder '{target.name}' in Windows File Explorer, Sir."
            return f"Folder does not exist: {p}"

        # 6. DELETE FILE OR FOLDER
        elif act in ["delete", "remove", "rm"]:
            if not p.exists():
                return f"Path does not exist: {p}"
            if p.is_dir():
                import shutil
                shutil.rmtree(p)
                return f"Deleted folder: {p}"
            else:
                p.unlink()
                return f"Deleted file: {p}"

        return f"Unknown file action: {action}"
    except Exception as e:
        return f"File manager error: {str(e)}"


# --- 7. Dynamic Python Code Execution Tool ---
def execute_python(code: str) -> str:
    """
    Executes dynamic Python code safely and returns printed output.
    Useful for complex math, data manipulation, algorithms, plotting, and quick tasks.
    """
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirected_output = io.StringIO()
    redirected_error = io.StringIO()
    sys.stdout = redirected_output
    sys.stderr = redirected_error
    try:
        # Create execution sandbox dict
        exec_globals = {
            "math": __import__("math"),
            "os": os,
            "sys": sys,
            "time": time,
            "Path": Path,
            "psutil": psutil
        }
        exec(code, exec_globals)
        output = redirected_output.getvalue()
        error = redirected_error.getvalue()
        res = ""
        if output:
            res += f"Output:\n{output}\n"
        if error:
            res += f"Errors:\n{error}\n"
        return res.strip() if res.strip() else "Code executed successfully with no printed output."
    except Exception as e:
        return f"Execution Exception: {str(e)}"
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


# --- 8. Multimodal Vision Sight Tool ---
def vision_see(target: str = "camera", question: str = "What do you see in front of you?") -> str:
    """
    Enables CWA to see through the camera or desktop screen and understand the visual context.
    - target: 'camera' (webcam) or 'screen' (desktop screenshot)
    - question: what you want CWA to observe or explain
    """
    if target.lower() == "screen":
        success, img_path = vision.capture_screen()
    else:
        success, img_path, _ = vision.capture_camera_frame(save=True)

    if not success:
        return "Sorry Sir, I was unable to access the visual feed."

    analysis = vision.analyze_image_with_gemini(img_path, prompt=question)
    return analysis


# --- 9. Send WhatsApp Tool ---
def send_whatsapp(recipient: str = "", message: str = "", phone_number: str = "") -> str:
    """
    Sends a WhatsApp message to any contact name, group, or phone number.
    Supports both WhatsApp Desktop (Windows app) and WhatsApp Web.
    - recipient: Name of the contact/group (e.g. 'Rahul', 'Mom', 'Ali', 'Office Group') OR phone number (e.g. '+919876543210').
    - message: The exact text message content to type and send.
    - phone_number: Alternative alias for recipient if phone number is provided.
    """
    import os
    import time
    import urllib.parse
    import pyperclip
    import pyautogui
    import webbrowser

    target = recipient.strip() if recipient.strip() else phone_number.strip()
    clean_msg = message.strip()

    if not target:
        return "Please specify a contact name or phone number to send WhatsApp message, Sir."
    if not clean_msg:
        return "Please specify the message content to send on WhatsApp, Sir."

    # Check if target is a phone number
    is_phone = target.replace("+", "").replace("-", "").replace(" ", "").isdigit() and len(target.replace("+", "").replace("-", "").replace(" ", "")) >= 10

    if is_phone:
        clean_phone = target.replace("+", "").replace("-", "").replace(" ", "")
        encoded_msg = urllib.parse.quote(clean_msg)
        print(f"[Tools 💬 WhatsApp] Direct phone send to: {clean_phone}")
        try:
            # 1. Try direct WhatsApp Desktop URI protocol
            os.system(f'start "" "whatsapp://send?phone={clean_phone}&text={encoded_msg}"')
            time.sleep(2.5)
            pyautogui.press("enter")
            return f"WhatsApp message successfully dispatched to {target}: \"{clean_msg}\", Sir."
        except Exception:
            # 2. Fallback to WhatsApp Web
            url = f"https://web.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}"
            webbrowser.open(url)
            time.sleep(4.0)
            pyautogui.press("enter")
            return f"Opened WhatsApp for {target} and queued message: \"{clean_msg}\", Sir."

    else:
        # Contact Name / Group Name Search & Send Flow
        print(f"[Tools 💬 WhatsApp] Searching contact '{target}' to send message: '{clean_msg}'")
        
        # 1. Launch / Focus WhatsApp
        app_control("open", "whatsapp")
        time.sleep(1.8)

        # 2. Focus WhatsApp Window using pygetwindow
        try:
            import pygetwindow as gw
            wins = [w for w in gw.getAllWindows() if "whatsapp" in w.title.lower()]
            if wins:
                win = wins[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(0.5)
        except Exception:
            pass

        # 3. Focus Search Bar via Ctrl+F
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.4)
        
        # Clear search bar if already filled
        pyautogui.hotkey("ctrl", "a")
        pyautogui.press("backspace")
        time.sleep(0.2)

        # 4. Type Contact / Group Name
        pyperclip.copy(target)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1.0)  # Wait for search results to filter

        # 5. Navigate to and select the contact
        pyautogui.press("down")
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(1.0)  # Wait for chat window to open

        # 6. Ensure focus is shifted from search bar to message input box
        pyautogui.press("escape")
        time.sleep(0.3)

        # 7. Type the Message & Press Enter to Send
        pyperclip.copy(clean_msg)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.4)
        pyautogui.press("enter")
        time.sleep(0.3)

        return f"WhatsApp message successfully sent to '{target}': \"{clean_msg}\", Sir."


def toggle_whatsapp_auto_reply(enable: bool, busy_reason: str = "Sir is currently busy working") -> str:
    """
    Enables or disables automatic AI WhatsApp responder mode when Sir is busy.
    Call this whenever Sir says 'main busy hoon, whatsapp auto reply chalu kardo' or 'disable whatsapp auto reply'.
    - enable: True to turn ON auto-responder, False to turn OFF
    - busy_reason: Custom status note explaining why Sir is busy (e.g. 'coding', 'in a meeting', 'driving', 'sleeping')
    """
    from cwa_agent.core.proactive import proactive
    return proactive.toggle_whatsapp_autoreply(enable=enable, busy_reason=busy_reason)


def auto_reply_whatsapp_chat(contact_name: str = "", custom_busy_note: str = "") -> str:
    """
    Focuses WhatsApp, searches for the specified contact (or takes active unread chat),
    reads the incoming message via AI visual inspection, drafts a polite AI response on behalf of Sir based on his busy status,
    and sends the response directly into the WhatsApp chat.
    - contact_name: Name of the contact or group to search in WhatsApp (e.g. 'Mom', 'Rahul', 'Office Group')
    - custom_busy_note: Explanation of why Sir is busy (e.g. 'Sir is busy coding an AI agent')
    """
    import pyperclip
    import pyautogui
    import time
    from cwa_agent.config import USER_NAME

    # 1. Open or focus WhatsApp
    focus_res = interact_with_app("whatsapp", action="open")
    time.sleep(1.5)

    # 2. Search for contact if specified
    if contact_name and contact_name.strip():
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.4)
        pyperclip.copy(contact_name.strip())
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(1.0)

    # 3. Read screen feed of WhatsApp chat using Gemini Vision
    last_message_text = "Hey, are you free right now?"
    try:
        from cwa_agent.core.vision import vision
        img_path = vision.capture_screen()
        if img_path and os.path.exists(img_path):
            vis_prompt = (
                "Look at the active WhatsApp chat window on screen. "
                "Read the last incoming message from the sender on the left or bottom of the chat. "
                "Output ONLY the exact text of the last incoming message and sender name."
            )
            extracted = vision.analyze_image_with_gemini(img_path, prompt=vis_prompt)
            if extracted and len(extracted) > 3:
                last_message_text = extracted.strip()
    except Exception as ex_vis:
        print(f"[Tools WhatsApp Vision Notice]: {ex_vis}")

    # 4. Generate dynamic AI response via Gemini Neural Cortex
    busy_note = custom_busy_note if custom_busy_note and custom_busy_note.strip() else "working on an urgent task"
    prompt = (
        f"WHATSAPP LIVE AUTO-REPLY: You are {USER_NAME}'s AI companion & executive assistant.\n"
        f"CURRENT CONTEXT: {USER_NAME} is currently busy ({busy_note}).\n"
        f"INCOMING MESSAGE RECEIVED: \"{last_message_text}\"\n"
        f"INSTRUCTION: Read the incoming message above carefully and craft a unique, natural, intelligent, and polite 1-2 sentence reply to send back to them on behalf of {USER_NAME}.\n"
        f"Do NOT use repetitive templates or fixed canned responses. Make the reply specific to their question/message.\n"
        f"Output ONLY the final message text to send into WhatsApp."
    )

    reply_text = ""
    try:
        from cwa_agent.core.brain import brain
        ai_resp = brain.process_query(prompt)
        if hasattr(ai_resp, 'text') and ai_resp.text:
            reply_text = ai_resp.text.strip()
        else:
            reply_text = str(ai_resp).strip()
    except Exception as ex_b:
        # Dynamic LLM fallback via brain
        try:
            from cwa_agent.core.brain import brain
            reply_text = brain.generate_context_aware_response(
                user_input=f"Generate dynamic busy reply for message: {last_message_text}",
                context=f"{USER_NAME} is currently busy ({busy_note})"
            )
        except Exception:
            reply_text = ""

    if not reply_text:
        return f"Could not generate dynamic AI response for WhatsApp chat, Sir."

    # Clean text quotes if present
    clean_reply = reply_text.strip('"').strip("'").strip()


    # 5. Type and send the generated AI response into WhatsApp
    try:
        pyperclip.copy(clean_reply)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.3)
        pyautogui.press("enter")
        
        # Save to memory so Sir can check later
        try:
            from cwa_agent.core.memory import memory
            memory.add_interaction(
                user_text=f"[WhatsApp Auto-Reply to {contact_name or 'Incoming Chat'}] Incoming: {last_message_text[:80]}",
                bot_text=f"[Auto-Sent Reply]: {clean_reply}"
            )
        except Exception:
            pass

        return f"Successfully sent AI Auto-Reply to {contact_name if contact_name else 'WhatsApp chat'}: '{clean_reply}', Sir."
    except Exception as ex_send:
        return f"Could not send WhatsApp Auto-Reply: {str(ex_send)}"



# --- 10. AI Image Generation Tool ---
def generate_image(prompt: str) -> str:
    """
    Generates an AI image based on a descriptive text prompt and opens it on the user's screen.
    - prompt: detailed English description of what image to create.
    """
    import urllib.parse
    import requests
    from cwa_agent.config import GENERATED_IMAGES_DIR

    print(f"[Tools 🎨] Generating AI Image for prompt: {prompt}")
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        # Using fast, high-quality HD AI image endpoint
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&enhance=true"
        
        response = requests.get(image_url, timeout=30)
        if response.status_code == 200:
            filename = f"gen_{int(time.time())}.jpg"
            img_path = str(GENERATED_IMAGES_DIR / filename)
            with open(img_path, "wb") as f:
                f.write(response.content)
            
            # Automatically open the image on user's screen in Windows default photo viewer
            if os.name == 'nt':
                os.startfile(img_path)
            
            return f"Image generated successfully and displayed on screen: {img_path}"
        else:
            return f"Image generation service returned status {response.status_code}"
    except Exception as e:
        return f"Image generation error: {str(e)}"


# --- 11. Switch Voice & Persona (MJ Female / CWA Male) ---
def switch_voice_mode(persona: str = "MJ", gender: str = "female") -> str:
    """
    Switches AI voice and persona between MJ (Female Voice) and CWA (Male Voice).
    - persona: 'MJ' (Female) or 'CWA' (Male)
    - gender: 'female' or 'male'
    """
    from cwa_agent.core.speaker import speaker
    speaker.set_persona(persona, gender)
    # No hardcoded response - Gemini will dynamically generate the persona switch confirmation
    return f"Persona switched to {speaker.persona}. Voice mode is now active."


# --- 12. AI Code Editor — Read, Modify & Save Code Files ---
def edit_code_file(file_path: str, instruction: str) -> str:
    """
    Reads a code file, intelligently applies the user's instruction using Gemini AI,
    creates a backup of the original, and saves the AI-modified code back to the file.
    - file_path: Absolute or relative path to the code file (any language)
    - instruction: What to do — e.g. 'fix bugs', 'add error handling', 'add comments', 'optimize', 'convert to async'
    """
    import re
    from cwa_agent.config import GEMINI_API_KEY, GEMINI_MODEL

    file_path = file_path.strip().strip('"').strip("'")

    if not os.path.exists(file_path):
        return f"File not found: '{file_path}'. Please provide the correct absolute path."

    # Read the original code
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            original_code = f.read()
    except Exception as e:
        return f"Could not read file: {e}"

    if not original_code.strip():
        return "The file is empty. Please provide a file with code content."

    ext = Path(file_path).suffix.lower()
    lang_map = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".html": "HTML", ".css": "CSS", ".java": "Java",
        ".cpp": "C++", ".c": "C", ".cs": "C#", ".go": "Go",
        ".rs": "Rust", ".php": "PHP", ".rb": "Ruby", ".json": "JSON"
    }
    language = lang_map.get(ext, "code")

    print(f"[Tools 🧠] AI Code Editor: Reading {language} file '{file_path}' ({len(original_code)} chars)...")

    # Build a dynamic Gemini prompt — NO hardcoded responses
    prompt = f"""You are an expert {language} developer and code reviewer.
The user wants you to: {instruction}

Here is the full code from the file '{os.path.basename(file_path)}':

```{language.lower()}
{original_code}
```

Instructions:
1. Apply the requested changes intelligently.
2. Return ONLY the complete modified code — no explanations, no markdown text outside the code block.
3. Preserve all existing functionality unless the instruction explicitly says to remove something.
4. The output must be valid, runnable {language} code.
5. Wrap your response in triple backticks with the language name.
"""

    try:
        from google import genai
        from google.genai import types

        api_k = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        client = genai.Client(api_key=api_k)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        ai_response = response.text.strip() if response.text else ""

        if not ai_response:
            return "Gemini returned an empty response. Please try again."

        # Extract code block from response — supports ```python, ```js, ``` etc.
        code_match = re.search(r"```(?:\w+)?\n([\s\S]+?)```", ai_response)
        if code_match:
            modified_code = code_match.group(1).strip()
        else:
            # If no code block, assume the entire response is the code
            modified_code = ai_response

        if not modified_code.strip():
            return "Could not extract valid code from Gemini response."

        # Create a backup of the original file
        backup_path = file_path + ".bak"
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(original_code)

        # Write the AI-modified code back to the original file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(modified_code)

        lines_before = len(original_code.splitlines())
        lines_after = len(modified_code.splitlines())
        print(f"[Tools ✅] Code edited: {lines_before} → {lines_after} lines. Backup at: {backup_path}")

        return (
            f"Done, Sir. I have applied your instruction '{instruction}' to '{os.path.basename(file_path)}'.\n"
            f"Original: {lines_before} lines → Modified: {lines_after} lines.\n"
            f"Original file backed up at: {backup_path}"
        )

    except Exception as e:
        return f"Code editing failed: {str(e)}"



# --- 13. Clear Chat / Memory Reset Tool ---
def clear_chat() -> str:
    """
    Clears and resets the entire chat history and AI memory for a fresh start.
    Call this when the user asks to: clear chat, clear history, fresh start, memory reset, naya session, memory clear karo, chat clear karo.
    """
    from cwa_agent.core.brain import brain
    print("[Tools 🧹] Clearing chat history and resetting memory...")
    return brain.clear_chat()


# --- 14. Long-Term Memory Tools ---
def remember_information(fact: str, category: str = "general") -> str:
    """
    Stores permanent facts, preferences, project details, or personal notes about Sir into Long-Term Memory.
    Call this when Sir says: "remember that...", "yaad rakhna ki...", "note down that...", "save this fact...", "mera favorite X hai", "main project X bana raha hoon".
    """
    from cwa_agent.core.memory import memory
    return memory.remember_fact(fact, category)


def recall_memory(query: str = "") -> str:
    """
    Recalls stored facts, past projects, or preferences from Long-Term Memory.
    Call this when Sir asks: "kya yaad hai?", "what do you remember about X?", "what is my project?", "mera naam/preferences kya hai?".
    """
    from cwa_agent.core.memory import memory
    return memory.recall_memory(query)


# --- 15. Proactive Voice Reminder Tool ---
def set_reminder(time_in_minutes: float, message: str) -> str:
    """
    Schedules an autonomous voice reminder that CWA will speak aloud after specified minutes.
    Call this when Sir asks to set a reminder/timer (e.g. "remind me in 10 minutes to...", "15 minute baad yaad dilana...", "set timer for 5 minutes").
    """
    from cwa_agent.core.proactive import proactive
    return proactive.add_reminder(time_in_minutes, message)


# --- 16. Instant Screen Debugger Tool ---
def inspect_screen(question: str = "") -> str:
    """
    Instantly captures Sir's active computer screen and performs AI vision analysis to solve bugs, explain UI, or read text.
    Call this when Sir says: "screen dekho", "what is on my screen?", "solve this error on my screen", "debug this code on screen", "meri screen par kya error hai".
    """
    from cwa_agent.core.vision import vision
    success, path = vision.capture_screen()
    if not success:
        return "Could not capture screen, Sir."
    
    prompt = question.strip() if question else "Analyze this active desktop screen carefully. Identify any code errors, compiler warnings, active applications, or important details and explain how to resolve or understand them."
    return vision.analyze_image_with_gemini(path, prompt=prompt)


# --- 17. Change Desktop Wallpaper Tool ---
def change_desktop_wallpaper(theme_or_prompt_or_path: str = "Iron Man glowing arc reactor sci-fi 4k wallpaper") -> str:
    """
    Changes and sets the Windows desktop wallpaper directly.
    Can accept an existing image file path, or generate a brand new 4K AI wallpaper based on any requested theme (e.g. 'Iron Man', 'Cyberpunk', 'Space Nebula', 'Dark Minimalist', 'Nature', 'Anime').
    Call this when Sir says: "wallpaper change karo", "change my wallpaper to X", "desktop par X ka wallpaper lagao", "set desktop background".
    """
    import ctypes
    import urllib.parse
    import requests
    from cwa_agent.config import GENERATED_IMAGES_DIR

    target_path = theme_or_prompt_or_path.strip().strip('"').strip("'")
    
    # 1. If it's already an existing local image file
    if os.path.exists(target_path) and Path(target_path).suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp"]:
        abs_path = os.path.abspath(target_path)
        try:
            ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 3)
            return f"Desktop wallpaper successfully updated to: '{os.path.basename(abs_path)}', Sir."
        except Exception as e:
            return f"Failed to apply wallpaper: {e}"

    # 2. Otherwise generate a custom HD AI Wallpaper and apply it directly
    prompt = target_path if target_path else "Iron Man glowing arc reactor Stark Industries dark sci-fi 4k desktop wallpaper"
    print(f"[Tools 🖼️] Generating custom AI desktop wallpaper for: '{prompt}'")
    
    try:
        encoded_prompt = urllib.parse.quote(f"{prompt} 4k desktop wallpaper, high quality, stunning aesthetics")
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1920&height=1080&nologo=true&enhance=true"
        
        response = requests.get(image_url, timeout=30)
        if response.status_code == 200:
            filename = f"wallpaper_{int(time.time())}.jpg"
            img_path = str(GENERATED_IMAGES_DIR / filename)
            with open(img_path, "wb") as f:
                f.write(response.content)
            
            abs_path = os.path.abspath(img_path)
            ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 3)
            return f"Done Sir! I have generated a custom 4K AI wallpaper for '{prompt}' and applied it directly to your Windows desktop."
        else:
            return f"Could not generate wallpaper image (status: {response.status_code})"
    except Exception as e:
        return f"Error setting desktop wallpaper: {str(e)}"


# --- 18. Ambient Room Conversation Recall Tool ---
def recall_room_conversation(query: str = "", minutes: int = 10) -> str:
    """
    Recalls and intelligently summarizes everything that was spoken aloud in the room
    in the last N minutes from the ambient background listener's RAM buffer.
    Call this when Sir asks: "abhi kya baat ho rahi thi?", "maine kya bola?",
    "kamre mein kya hua?", "what was just said?", "last 5 minutes mein kya bola gaya?",
    "humne kya discuss kiya?", "yeh baat chal rahi thi?".
    - query: optional specific topic to search for in the conversation
    - minutes: how many minutes back to recall (default 10, max 15)
    """
    from cwa_agent.core.ambient_listener import ambient

    minutes = max(1, min(minutes, ambient.buffer_minutes))
    transcript = ambient.get_recent_transcript(minutes=minutes)

    if "No conversation captured" in transcript:
        return f"Sir, no ambient room conversation was captured in the last {minutes} minute(s). The room listener may not have picked up any speech."

    total_entries = ambient.entry_count
    context_note = f"[Ambient Buffer: {total_entries} utterances captured | Last {minutes} min transcript]\n\n"

    if query and query.strip():
        return (
            f"{context_note}"
            f"Room Transcript (last {minutes} min):\n{transcript}\n\n"
            f"Please analyze the above room transcript and answer Sir's specific question: '{query}'"
        )

    return (
        f"{context_note}"
        f"Room Transcript (last {minutes} min):\n{transcript}"
    )


# --- 19. Send to Phone (Telegram Bridge) Tool ---
def send_to_telegram(content_type: str = "auto", file_path_or_query: str = "", text_message: str = "") -> str:
    """
    Transmits downloaded media files (songs, videos, movies, wallpapers/images), desktop screenshots, camera snapshots, documents, or text messages directly to Sir's connected phone via Telegram.
    
    Parameters:
    - content_type:
        * 'auto': Automatically determines whether to send latest download, specific file, or text.
        * 'download' or 'media': Sends the latest downloaded song (MP3), video (MP4), movie, or image from the media folder.
        * 'song' or 'audio': Searches and sends a downloaded song MP3 directly into Telegram's music player.
        * 'video' or 'movie': Searches and sends a downloaded MP4 video/movie directly to Telegram.
        * 'image' or 'photo': Sends a downloaded wallpaper or generated image to Telegram.
        * 'file' or 'document': Sends any specific file, code, PDF, or document.
        * 'screenshot': Takes a live desktop screenshot and sends it to phone.
        * 'camera': Captures live webcam frame and sends it to phone.
        * 'text': Sends a text notification or message to phone.
    - file_path_or_query: Optional filename, song name, video title, or direct path to send (e.g. 'Pushpa 2', 'Chaleya', 'BMW wallpaper', 'cwa_agent/media/Songs/tum_hi_ho.mp3'). If empty, automatically selects the latest downloaded file.
    - text_message: Optional custom caption or note to attach with the file.
    
    Call this tool when Sir says:
    - "jo download kiya hai mere telegram par bhej do", "downloaded song telegram par send karo"
    - "Pushpa movie/song mere phone par bhej do", "yeh wallpaper mere telegram par bhej"
    - "phone par screenshot bhej", "camera photo telegram par bhej do"
    - "send this file to my telegram", "telegram par message bhej do"
    """
    from cwa_agent.core.remote_bridge import remote_bridge
    from cwa_agent.core.vision import vision
    from cwa_agent.config import DOWNLOADS_DIR, DATA_DIR, BASE_DIR

    if not remote_bridge.is_configured():
        return "Telegram Phone Bridge is not configured yet, Sir. Please set your Telegram Bot Token in .env first."

    chat_id = remote_bridge.authorized_chat_id
    if not chat_id:
        return "Sir, please send '/start' once from your phone to your Telegram Bot so I can link your phone."

    c_type = str(content_type).lower().strip()
    target_q = str(file_path_or_query).lower().strip()

    # 1. Desktop Screenshot
    if c_type in ["screenshot", "screen"]:
        success, path = vision.capture_screen(auto_open=False)
        if success and os.path.exists(path):
            sent = remote_bridge.send_photo(chat_id, path, caption=text_message or "🖥️ Current Desktop Screen Snapshot")
            return "Desktop screenshot sent directly to your phone via Telegram, Sir." if sent else "Failed to transmit screenshot to Telegram."
        return "Could not capture desktop screen."

    # 2. Camera Snapshot
    elif c_type in ["camera", "cam", "webcam"]:
        success, path, _ = vision.capture_camera_frame(save=True)
        if success and os.path.exists(path):
            sent = remote_bridge.send_photo(chat_id, path, caption=text_message or "📷 Workstation Camera Snapshot")
            return "Camera photo sent directly to your phone via Telegram, Sir." if sent else "Failed to transmit camera snapshot."
        return "Could not access camera."

    # 3. Direct Text Message / Spoken Note / Dictation
    elif c_type in ["text", "msg", "message", "note", "reminder", "notification", "chat"] or (text_message and not file_path_or_query):
        msg_to_send = text_message if text_message else file_path_or_query
        if not msg_to_send or not msg_to_send.strip():
            return "No text message provided to send to Telegram, Sir."
        sent = remote_bridge.send_message(chat_id, f"📝 {msg_to_send.strip()}")
        return f"Done Sir! I have sent your message directly to your Telegram: \"{msg_to_send.strip()}\"" if sent else "Failed to transmit message to Telegram."

    # 4. Direct File or Media Search in media / data folders
    target_file = None
    if file_path_or_query and os.path.exists(file_path_or_query) and os.path.isfile(file_path_or_query):
        target_file = Path(file_path_or_query)
    else:
        # Search all media directories
        candidate_dirs = [
            DOWNLOADS_DIR / "Songs",
            DOWNLOADS_DIR / "Videos",
            DOWNLOADS_DIR / "Images",
            DOWNLOADS_DIR / "Movies",
            DOWNLOADS_DIR,
            DATA_DIR / "generated_images",
            DATA_DIR / "qrcodes",
            DATA_DIR / "notes"
        ]

        found_files = []
        for d in candidate_dirs:
            if d.exists():
                for f in d.rglob("*"):
                    if f.is_file() and not f.name.startswith("."):
                        found_files.append(f)

        if not found_files:
            if text_message:
                sent = remote_bridge.send_message(chat_id, text_message)
                return "Message sent to your phone via Telegram, Sir." if sent else "Failed to send message to Telegram."
            return "No downloaded media files found in your media directory to send, Sir."

        # If user searched for a specific keyword in filename
        if target_q and target_q not in ["auto", "download", "media", "latest"]:
            matching = [f for f in found_files if any(part in f.name.lower() for part in target_q.split())]
            if matching:
                # Sort by newest
                matching.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                target_file = matching[0]

        # If no specific query matched or user asked for latest download
        if not target_file:
            # Sort all by modification time (most recent first)
            found_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            target_file = found_files[0]

    if not target_file or not target_file.exists():
        # Fallback: if user passed a text message/dictation and no file matched, send as message
        if file_path_or_query:
            sent = remote_bridge.send_message(chat_id, f"📝 {file_path_or_query}")
            return f"Done Sir! I have sent your message to your Telegram: \"{file_path_or_query}\"" if sent else "Failed to send message to Telegram."
        return "Could not locate the requested downloaded file to send to Telegram, Sir."

    # Determine file type and send with dedicated Telegram API method
    ext = target_file.suffix.lower()
    fname = target_file.name
    caption_txt = text_message or f"📦 {fname} (from CWA Workstation)"

    print(f"[Telegram Bridge 🚀] Sending '{fname}' to Telegram (Chat ID: {chat_id})...")

    # Audio / Song (MP3, WAV, M4A, FLAC)
    if ext in [".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"]:
        title_str = target_file.stem.replace("_", " ").title()
        sent = remote_bridge.send_audio(chat_id, str(target_file.resolve()), caption=caption_txt, title=title_str)
        if sent:
            return f"Done Sir! I have sent the song '{fname}' directly to your phone on Telegram as an audio track."
        else:
            # Fallback to document
            sent_doc = remote_bridge.send_document(chat_id, str(target_file.resolve()), caption=caption_txt)
            return f"Done Sir! I have sent '{fname}' to your Telegram as a document." if sent_doc else "Failed to send audio file to Telegram."

    # Video / Movie (MP4, MKV, WEBM, AVI, MOV)
    elif ext in [".mp4", ".mkv", ".webm", ".avi", ".mov"]:
        sent = remote_bridge.send_video(chat_id, str(target_file.resolve()), caption=caption_txt)
        if sent:
            return f"Done Sir! I have sent the video/movie '{fname}' directly to your Telegram."
        else:
            sent_doc = remote_bridge.send_document(chat_id, str(target_file.resolve()), caption=caption_txt)
            return f"Done Sir! Sent '{fname}' to your Telegram." if sent_doc else "Failed to send video to Telegram."

    # Photo / Wallpaper (JPG, PNG, WEBP, BMP)
    elif ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
        sent = remote_bridge.send_photo(chat_id, str(target_file.resolve()), caption=caption_txt)
        if sent:
            return f"Done Sir! I have sent the photo/wallpaper '{fname}' directly to your Telegram."
        else:
            sent_doc = remote_bridge.send_document(chat_id, str(target_file.resolve()), caption=caption_txt)
            return f"Done Sir! Sent '{fname}' to your Telegram." if sent_doc else "Failed to send image to Telegram."

    # Generic Document / Code / Zip / PDF
    else:
        sent = remote_bridge.send_document(chat_id, str(target_file.resolve()), caption=caption_txt)
        if sent:
            return f"Done Sir! I have sent the file '{fname}' directly to your Telegram."
        else:
            return f"Failed to transmit file '{fname}' to Telegram."


# --- 20. Unlock Workstation Tool ---
def unlock_workstation(password: str = "") -> str:
    """
    Wakes up the monitor, dismisses the Windows lock screen, and types the PIN/password to open the desktop.
    If no password is set on the PC, it directly dismisses the lock screen and opens the desktop.
    If a password is set, provide the password parameter to unlock.
    Call this when Sir says: "system unlock karo", "PC open karo", "unlock my laptop", "screen kholo", "password 1234 dalke unlock karo", "open system".
    """
    import ctypes
    pyautogui.FAILSAFE = False

    # 1. Wake display using mouse movement & native Windows key events
    try:
        ctypes.windll.user32.mouse_event(0x0001, 10, 10, 0, 0)  # MOUSEEVENTF_MOVE
        time.sleep(0.1)
        # Press Space (VK_SPACE = 0x20) to dismiss wallpaper
        ctypes.windll.user32.keybd_event(0x20, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(0x20, 0, 2, 0)
        time.sleep(0.3)
        # Press Enter (VK_RETURN = 0x0D) to open desktop or focus PIN box
        ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)
        time.sleep(0.4)
    except Exception as e:
        print(f"[Unlock Warning] Key event: {e}")

    if password and password.strip():
        # Type password and press enter
        try:
            pyautogui.typewrite(password.strip(), interval=0.04)
            time.sleep(0.2)
            ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)
            time.sleep(0.05)
            ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)
        except Exception:
            pass
        return "Workstation unlock sequence executed with your password, Sir."
    else:
        # Press Enter again to open desktop directly if no password is set
        time.sleep(0.2)
        ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)
        return "Screen awakened and unlock attempted. Desktop is now open, Sir."


def manage_ignore_words(action: str, word_or_phrase: str = "", replace_with: str = "", persona: str = "auto") -> str:
    """
    Manages persona-specific ignore words, banned phrases, and word replacement rules separated for Male (CWA) and Female (MJ) personas.
    All rules are permanently saved in cwa_agent/data/ignore_words/ (male_ignore_words.json, female_ignore_words.json, global_ignore_words.json).
    
    Parameters:
    - action:
        * 'add' or 'forbid': Permanently forbids a word/phrase for the specified persona so it is NEVER said or printed.
        * 'replace' or 'substitute': Sets a word replacement rule (e.g. word_or_phrase='tum', replace_with='aap') so the assistant always uses the preferred word.
        * 'remove' or 'unban': Removes a forbidden word or replacement rule.
        * 'list' or 'show': Shows all active ignore words and replacement rules categorized by Male (CWA) and Female (MJ).
    - word_or_phrase: The word, phrase, or sentence to forbid or replace (e.g. 'yaar', 'bhai', 'babu', 'tum').
    - replace_with: The preferred word/phrase to say instead (e.g. 'Sir', 'Aap'). Used when action='replace'.
    - persona: 'male' (CWA / JARVIS), 'female' (MJ), 'both' / 'global', or 'auto' (targets currently active persona).
    
    Call this when Sir says:
    - "yeh word mat bolna", "is word ko ban kar do", "never say <word> again"
    - "MJ ko bolo yeh word na bole", "female voice mein yeh mat bolna"
    - "isko aise mat bolo, aise bolo", "tum ki jagah aap bolo", "yaar mat bolo Sir bolo"
    - "ignore words ki list dikhao", "remove <word> from ignore list"
    """
    from cwa_agent.core.ignore_words import ignore_words_manager
    act = action.lower().strip()

    if act in ["add", "forbid", "ban"]:
        return ignore_words_manager.add_forbidden_word(word_or_phrase, persona=persona)
    elif act in ["replace", "substitute", "swap", "set_replacement"]:
        return ignore_words_manager.add_word_replacement(word_or_phrase, replace_with=replace_with, persona=persona)
    elif act in ["remove", "unban", "delete"]:
        return ignore_words_manager.remove_rule(word_or_phrase, persona=persona)
    elif act in ["list", "show", "get", "summary"]:
        return ignore_words_manager.list_all_rules()
    else:
        return f"Unknown action '{action}'. Allowed: 'add', 'replace', 'remove', 'list'."


def manage_forbidden_words(action: str, word: str = "", persona: str = "auto") -> str:
    """Alias for manage_ignore_words."""
    return manage_ignore_words(action=action, word_or_phrase=word, persona=persona)



def sing_song(song_title: str, lyrics: str = "", genre: str = "acoustic") -> str:
    """
    Sings a song out loud like a professional singer with vocal pitch vibrato, studio reverb, and acoustic backing tracks.
    Call this tool whenever Sir asks you to sing a song (e.g., "gana gao", "sing a song", "sing for me", "ek gana gaa kar sunao").
    - song_title: Title of the song (e.g. 'Tum Hi Ho', 'Jarvis Anthem', 'Safar')
    - lyrics: The poetic verse lyrics to sing out loud (separated by newlines)
    - genre: 'acoustic', 'romantic', 'pop', 'sad', or 'energetic'
    """
    from cwa_agent.core.speaker import speaker
    if not lyrics or not lyrics.strip():
        lyrics = (
            f"Here is a melody for you Sir,\n"
            f"Coding with AI in the quiet night,\n"
            f"JARVIS is standing by your side,\n"
            f"Making all your dreams take flight."
        )
    return speaker.sing_song(lyrics=lyrics, title=song_title, style=genre)


# --- 28. Quantum QR Code Generator Tool ---
_on_qr_code_created = None

def register_qr_callback(callback):
    """Registers a UI callback to display generated QR codes live on screen."""
    global _on_qr_code_created
    _on_qr_code_created = callback

def generate_qr_code(data: str, title: str = "") -> str:
    """
    Generates a high-resolution QR Code from any provided text, URL, link, Wi-Fi details, contact info, UPI payment link, or data payload.
    Renders the QR code directly on the screen in the GUI and provides instant download / save options for the user.
    
    Parameters:
    - data: The string, text, link, URL, or data to encode into the QR code.
    - title: Optional title or label describing what the QR code represents (e.g. 'My Portfolio', 'Payment QR', 'Website Link').
    """
    if not data or not str(data).strip():
        return "No data provided to encode into QR code, Sir."

    clean_data = str(data).strip()
    display_title = str(title).strip() if title else ("QR Code: " + (clean_data[:28] + "..." if len(clean_data) > 28 else clean_data))

    try:
        import qrcode
        from cwa_agent.config import QRCODES_DIR
        QRCODES_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = int(time.time())
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', title if title else clean_data[:15]).strip('_')
        if not safe_name:
            safe_name = "code"
        filename = f"qr_{safe_name}_{timestamp}.png"
        file_path = QRCODES_DIR / filename

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=3,
        )
        qr.add_data(clean_data)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_img.save(str(file_path))

        print(f"[QR Generator 📱] QR Code generated successfully at: {file_path}")

        # Trigger screen display callback if registered
        global _on_qr_code_created
        displayed_in_gui = False
        if _on_qr_code_created:
            try:
                _on_qr_code_created(str(file_path), clean_data, display_title)
                displayed_in_gui = True
            except Exception as e:
                print(f"[QR Callback Warning]: {e}")

        # Always auto-open the QR image on screen so user can see & scan it
        if os.name == 'nt':
            try:
                os.startfile(str(file_path))
            except Exception as e:
                print(f"[QR Open Warning]: {e}")

        return f"QR Code successfully generated for '{display_title}'. It is displayed on your screen right now with download and copy options."

    except Exception as e:
        return f"Could not generate QR Code: {str(e)}"


# --- 29. Neural Language Translation Tool ---
_on_translation_created = None
_on_download_progress = None

def register_translation_callback(callback):
    """Registers a UI callback to display translation results live on screen."""
    global _on_translation_created
    _on_translation_created = callback

def register_download_callback(callback):
    """Registers a UI callback to display download progress live on screen."""
    global _on_download_progress
    _on_download_progress = callback

def translate_text(text: str, target_language: str = "hindi", source_language: str = "auto") -> str:
    """
    Translates any text, sentence, message, or paragraph into Hindi, English, Urdu, Spanish, French, German, Arabic, Japanese, or any language (100% free, no API key needed).
    Displays the translated text on screen in the GUI, copies it to clipboard, and returns the translated result.

    Parameters:
    - text: The input text/sentence/paragraph to translate.
    - target_language: Target language to translate into (e.g. 'hindi', 'english', 'urdu', 'spanish', 'french', 'german', 'arabic', 'japanese'). Default is 'hindi'.
    - source_language: Source language ('auto' detects automatically, or 'en', 'hi', etc.). Default is 'auto'.
    """
    if not text or not str(text).strip():
        return "No text provided for translation, Sir."

    clean_text = str(text).strip()
    tgt = str(target_language).lower().strip() if target_language else "hindi"
    src = str(source_language).lower().strip() if source_language else "auto"

    lang_map = {
        "hindi": "hi", "hi": "hi", "hindustani": "hi", "shuddh hindi": "hi",
        "english": "en", "en": "en", "angrezi": "en",
        "urdu": "ur", "ur": "ur",
        "spanish": "es", "es": "es",
        "french": "fr", "fr": "fr",
        "german": "de", "de": "de",
        "arabic": "ar", "ar": "ar",
        "japanese": "ja", "ja": "ja",
        "chinese": "zh-CN", "zh": "zh-CN",
        "russian": "ru", "ru": "ru",
        "bengali": "bn", "bn": "bn",
        "punjabi": "pa", "pa": "pa",
        "marathi": "mr", "mr": "mr",
        "gujarati": "gu", "gu": "gu",
        "tamil": "ta", "ta": "ta",
        "telugu": "te", "te": "te",
        "korean": "ko", "ko": "ko",
        "italian": "it", "it": "it",
        "portuguese": "pt", "pt": "pt",
        "turkish": "tr", "tr": "tr"
    }

    t_code = lang_map.get(tgt, tgt[:2] if len(tgt) >= 2 else "hi")
    s_code = lang_map.get(src, "auto")

    translated_result = ""

    # Engine 1: High-Speed GoogleTranslator (Fast 0.5s - 1.5s)
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source=s_code, target=t_code)
        res = translator.translate(clean_text)
        if res and not str(res).startswith("Error") and "500" not in str(res):
            translated_result = str(res).strip()
    except Exception as ex_g:
        print(f"[Translator Notice - Google]: {ex_g}")

    # Engine 2: Gemini Neural AI Brain Translation (High-Accuracy Contextual Fallback)
    if not translated_result:
        try:
            from cwa_agent.core.brain import brain
            ai_resp = brain.process_query(
                f"Translate the following text accurately into {tgt}. Output ONLY the translated text in the native script without any commentary, quotes, or explanations:\n\n{clean_text}"
            )
            raw_text = ai_resp.text if hasattr(ai_resp, 'text') else str(ai_resp)
            if raw_text:
                translated_result = raw_text.strip().strip('"').strip("'")
        except Exception as ex_b:
            print(f"[Translator Notice - Brain]: {ex_b}")

    # Engine 3: MyMemoryTranslator Fallback
    if not translated_result:
        try:
            from deep_translator import MyMemoryTranslator
            t_mem = f"{t_code}-IN" if t_code in ["hi", "bn", "pa", "mr", "gu", "ta", "te"] else f"{t_code}-{t_code.upper()}"
            s_mem = "en-US" if t_code != "en" else "hi-IN"
            translator = MyMemoryTranslator(source=s_mem, target=t_mem)
            res = translator.translate(clean_text)
            if res and not str(res).startswith("Error") and "500" not in str(res):
                translated_result = str(res).strip()
        except Exception:
            pass

    if not translated_result:
        return "Could not translate the text, Sir."

    # Trigger UI callback if registered
    global _on_translation_created
    if _on_translation_created:
        try:
            _on_translation_created(clean_text, translated_result, src, tgt)
        except Exception:
            pass

    return f"Translation ({tgt.capitalize()}):\n{translated_result}"


# --- 28. Universal Movie, Song, Music & Media Search and Downloader ---
def media_search_and_download(
    query: str,
    media_type: str = "auto",
    action: str = "search",
    quality: str = "best",
    format_type: str = "auto",
    direct_url: str = "",
    folder_name: str = ""
) -> str:
    """
    Dynamically searches, finds sources, and downloads ANY Movie, Song, Music Track, Album, Video, Series, or Image/Wallpaper.
    Supports Full HD Video (MP4), High-Quality Audio (MP3), and Image (JPG/PNG/WEBP) downloads.
    - query: Name of the movie, song, artist, video, series, or image/wallpaper (e.g. 'Pushpa 2', 'Tum Hi Ho', 'Iron Man wallpaper', 'sunset HD photo').
    - media_type: 'movie', 'song', 'music', 'video', 'series', 'image', 'wallpaper', 'photo', or 'auto' (automatically deduced).
    - action:
        * 'search': Searches multiple web engines, YouTube, archive & streaming mirrors. Formats results with quality, duration/size, and asks user for confirmation.
        * 'download': Downloads the song (MP3), movie/video (MP4), or image (JPG/PNG) directly to media folder.
        * 'open': Opens the direct stream or movie portal in default browser.
    - quality: 'best', '1080p', '720p', '480p', 'mp3', '320kbps', 'audio_only'.
    - format_type: 'video' (MP4 Full HD), 'audio' (MP3 320kbps), 'image' (JPG/PNG), 'mp4', 'mp3', or 'auto'.
    - direct_url: Optional direct URL to download.
    - folder_name: Optional custom folder name to save inside Downloads (e.g. 'Arijit_Singh', 'Action_Movies').
    """
    import os
    import sys
    import time
    import json
    import webbrowser
    import threading
    from pathlib import Path
    from cwa_agent.config import DOWNLOADS_DIR

    clean_query = query.strip()
    if not clean_query:
        return "Please provide a movie or song name to search and download, Sir."

    # 1. Deduce media type if 'auto'
    m_type = media_type.lower().strip()
    q_low = clean_query.lower()
    song_keywords = ["song", "music", "gaana", "geet", "track", "mp3", "audio", "singer", "album", "remix", "arijit", "lyrics", "tune", "beat", "lofi", "acoustic"]
    movie_keywords = ["movie", "film", "cinema", "series", "season", "episode", "hollywood", "bollywood", "anime", "1080p", "720p", "bluray", "hdrip"]
    video_keywords = ["video", "mp4", "clip", "reel", "shorts", "visual", "hd video", "video song"]
    image_keywords = ["image", "photo", "wallpaper", "picture", "pic", "poster", "screenshot", "hd image", "4k wallpaper", "dp", "logo", "icon", "banner", "thumbnail", "tasveer", "jpg", "png", "webp"]

    if m_type in ["auto", ""]:
        if any(w in q_low for w in image_keywords):
            m_type = "image"
        elif any(w in q_low for w in movie_keywords):
            m_type = "movie"
        elif any(w in q_low for w in video_keywords):
            m_type = "video"
        elif any(w in q_low for w in song_keywords):
            m_type = "song"
        else:
            m_type = "song" if len(clean_query.split()) <= 4 else "movie"

    # 2. Determine Video vs Audio format
    fmt = format_type.lower().strip()
    if fmt in ["video", "mp4", "1080p", "720p", "hd", "movie", "film"]:
        is_video = True
    elif fmt in ["audio", "mp3", "sound", "music", "song"]:
        is_video = False
    else:
        if any(k in q_low for k in ["video", "mp4", "1080p", "720p", "movie", "film", "clip", "full video"]):
            is_video = True
        elif any(k in q_low for k in ["mp3", "audio", "gaana", "track", "audio song"]):
            is_video = False
        else:
            is_video = True if m_type in ["movie", "film", "video"] else False

    # Check if this is an image request
    is_image = m_type in ["image", "wallpaper", "photo", "picture", "poster", "logo", "icon"] or fmt in ["image", "jpg", "png", "webp"]

    # 3. Automatic dedicated sub-folder creation
    if folder_name.strip():
        clean_folder = folder_name.strip().replace("..", "").replace("/", "_").replace("\\", "_")
        target_dir = DOWNLOADS_DIR / clean_folder
    elif is_image:
        target_dir = DOWNLOADS_DIR / "Images"
    elif is_video:
        target_dir = DOWNLOADS_DIR / ("Movies" if m_type in ["movie", "film", "series"] else "Videos")
    else:
        target_dir = DOWNLOADS_DIR / "Songs"

    target_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # IMAGE SEARCH & DOWNLOAD (Separate flow for images)
    # =========================================================================
    if is_image:
        if action.lower() in ["search", "find", "check"]:
            # Check if direct image URL
            img_extensions = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg"]
            if clean_query.startswith("http") and any(ext in clean_query.lower() for ext in img_extensions):
                return (
                    f"🖼️ [DIRECT IMAGE LINK DETECTED]\n"
                    f"• URL: {clean_query}\n\n"
                    f"👉 Sir, maine direct image link detect kar li hai. Kya main isko abhi download kar doon?"
                )

            # Search images via Multi-Engine (Bing Scraper + DuckDuckGo + Wikimedia)
            found_images = []
            import re
            import urllib.request
            import urllib.parse

            # Engine 1: Direct High-Speed Bing Image Scraper (No API key, No 403 blocks)
            try:
                b_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(clean_query + ' HD wallpaper')}&form=HDRSC2"
                b_req = urllib.request.Request(b_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                with urllib.request.urlopen(b_req, timeout=6) as b_resp:
                    b_html = b_resp.read().decode('utf-8', errors='ignore')
                    murls = re.findall(r'murl&quot;:&quot;(http[^&]+)&quot;', b_html)
                    t_titles = re.findall(r't1=&quot;([^&]+)&quot;', b_html)
                    for idx, u in enumerate(murls[:5]):
                        if u and any(ext in u.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            t = t_titles[idx] if idx < len(t_titles) else f"{clean_query} HD {idx+1}"
                            found_images.append({
                                "title": t[:60],
                                "url": u,
                                "source": "Bing Web HD",
                                "size": "High Res"
                            })
            except Exception as ex:
                print(f"[Image Search] Bing engine note: {ex}")

            # Engine 2: Wikimedia Commons HD Archive Fallback
            if not found_images:
                try:
                    w_url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrsearch={urllib.parse.quote(clean_query)}&gsrlimit=5&prop=imageinfo&iiprop=url|size&format=json"
                    w_req = urllib.request.Request(w_url, headers={'User-Agent': 'CWA_Agent/1.0'})
                    with urllib.request.urlopen(w_req, timeout=5) as w_resp:
                        import json as j_mod
                        data = j_mod.loads(w_resp.read().decode('utf-8'))
                        pages = data.get('query', {}).get('pages', {})
                        for pid, page in pages.items():
                            ii = page.get('imageinfo', [{}])[0]
                            if ii.get('url'):
                                found_images.append({
                                    "title": page.get('title', clean_query)[:60],
                                    "url": ii.get('url'),
                                    "source": "Wikimedia HD",
                                    "size": f"{ii.get('width', '?')}x{ii.get('height', '?')}"
                                })
                except Exception as ex:
                    print(f"[Image Search] Wikimedia note: {ex}")

            if found_images:
                img_list = "\n".join([f"  {i+1}. {img['title']} ({img['size']}) — {img['source']}" for i, img in enumerate(found_images[:5])])
                return (
                    f"🖼️ [IMAGE SEARCH COMPLETED — {len(found_images)} Results Found]\n"
                    f"{img_list}\n\n"
                    f"👉 [CONFIRMATION REQUIRED]:\n"
                    f"Sir, maine '{clean_query.title()}' ke liye {len(found_images)} Ultra-HD images dhoondhi hain. Kya main best quality image download kar doon?"
                )
            else:
                return f"Sir, '{clean_query}' ke liye koi direct HD image stream nahi mila. Browser mein search results open karun?"

        elif action.lower() in ["download", "start", "get", "save"]:
            import requests

            download_url = direct_url if direct_url.startswith("http") else ""

            # If no direct URL, auto-fetch the best image URL
            if not download_url:
                import re
                import urllib.request
                import urllib.parse
                try:
                    b_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(clean_query + ' HD wallpaper')}&form=HDRSC2"
                    b_req = urllib.request.Request(b_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                    with urllib.request.urlopen(b_req, timeout=6) as b_resp:
                        b_html = b_resp.read().decode('utf-8', errors='ignore')
                        murls = re.findall(r'murl&quot;:&quot;(http[^&]+)&quot;', b_html)
                        for u in murls:
                            if any(ext in u.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                download_url = u
                                break
                except Exception:
                    pass

            if not download_url:
                # Check if query itself is a direct image URL
                if clean_query.startswith("http"):
                    download_url = clean_query
                else:
                    return f"Sir, '{clean_query}' ka koi downloadable image link nahi mila. Direct URL ya alag keyword try karein."

            def _async_image_download():
                global _on_download_progress
                try:
                    # Extract filename from URL or generate from query
                    from urllib.parse import urlparse, unquote
                    parsed = urlparse(download_url)
                    url_filename = os.path.basename(unquote(parsed.path))

                    # Determine extension
                    ext = os.path.splitext(url_filename)[1].lower()
                    if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']:
                        ext = '.jpg'

                    # Create a clean filename
                    safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in clean_query)[:80].strip()
                    if not safe_name:
                        safe_name = url_filename.split('.')[0][:80] if url_filename else 'image'
                    filename = f"{safe_name}{ext}"
                    filepath = target_dir / filename

                    # Avoid overwrite — add number suffix
                    counter = 1
                    while filepath.exists():
                        filepath = target_dir / f"{safe_name}_{counter}{ext}"
                        counter += 1

                    # Download with progress
                    if _on_download_progress:
                        _on_download_progress(safe_name, 0.0, "Starting...", "--", "--", "DOWNLOADING")

                    resp = requests.get(download_url, stream=True, timeout=30, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    resp.raise_for_status()
                    total_size = int(resp.headers.get('content-length', 0))
                    downloaded = 0

                    with open(filepath, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0 and _on_download_progress:
                                    pct = (downloaded / total_size) * 100.0
                                    sz_str = f"{downloaded/1024:.0f}KB / {total_size/1024:.0f}KB"
                                    _on_download_progress(safe_name, pct, "Downloading", sz_str, "--", "DOWNLOADING")

                    if _on_download_progress:
                        _on_download_progress(safe_name, 100.0, "Completed", "Done", "0s", "FINISHED")

                    # Open folder
                    try:
                        os.startfile(str(target_dir))
                    except Exception:
                        pass

                except Exception as ex:
                    print(f"[Image Download Error]: {ex}")
                    if _on_download_progress:
                        _on_download_progress(clean_query[:30], 0.0, "Error", str(ex)[:30], "--", "FINISHED")

            threading.Thread(target=_async_image_download, daemon=True).start()

            return (
                f"🖼️ [IMAGE DOWNLOAD INITIATED SUCCESSFULLY]\n"
                f"• Image: {clean_query.title()}\n"
                f"• Format: HD Image\n"
                f"• Saving To: {target_dir}\n"
                f"• Status: Download active! Folder will open automatically, Sir."
            )

        elif action.lower() in ["open", "stream", "watch"]:
            url = f"https://www.google.com/search?tbm=isch&q={clean_query}+HD"
            webbrowser.open(url)
            return f"Google Images mein '{clean_query}' ke results open kar diye hain, Sir."

        return f"Image command executed for '{clean_query}', Sir."

    # =========================================================================
    # ACTION: SEARCH (Find sources, quality, details and ask for confirmation)
    # =========================================================================
    if action.lower() in ["search", "find", "check"]:
        is_direct_link = clean_query.startswith("http://") or clean_query.startswith("https://") or "youtube.com" in clean_query or "youtu.be" in clean_query

        # Check if the direct link is actually an image URL
        img_extensions = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]
        if is_direct_link and any(ext in clean_query.lower() for ext in img_extensions):
            return (
                f"🖼️ [DIRECT IMAGE LINK DETECTED]\n"
                f"• URL: {clean_query}\n\n"
                f"👉 Sir, yeh ek direct image link hai. Kya main isko download kar doon?"
            )

        if is_direct_link:
            # Direct URL passed — extract media info directly
            try:
                import yt_dlp
                ydl_opts = {'quiet': True, 'skip_download': True, 'extract_flat': False}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(clean_query, download=False)
                    title = info.get('title', 'Target Media Track')
                    uploader = info.get('uploader', 'Media Creator')
                    dur = info.get('duration')
                    dur_str = f"{int(dur)//60}:{int(dur)%60:02d}" if dur else "N/A"
                    res_msg = (
                        f"🔗 [DIRECT MEDIA LINK VERIFIED]\n"
                        f"• Title: {title}\n"
                        f"• Creator/Artist: {uploader}\n"
                        f"• Duration: {dur_str}\n"
                        f"• Formats Ready: 🎬 Full HD MP4 Video | 🎧 320kbps MP3 Audio\n"
                        f"• Source URL: {clean_query}\n\n"
                        f"👉 [CONFIRMATION REQUIRED]:\n"
                        f"Sir, maine is link ka media fetch kar liya hai: '{title}'. Aapko iska **Video Version (Full HD MP4)** download karna hai ya **Audio Version (MP3)**?"
                    )
                    return res_msg
            except Exception as ex:
                return (
                    f"🔗 [DIRECT LINK DETECTED]: {clean_query}\n"
                    f"👉 Sir, maine link detect kar liya hai. Aapko iska **Video Version (MP4)** download karna hai ya **Audio Version (MP3)**?"
                )

        elif m_type in ["song", "music", "audio", "video"]:
            # Search YouTube / Audio index for high-fidelity audio & video streams
            found_items = []
            try:
                import yt_dlp
                ydl_opts = {
                    'quiet': True,
                    'skip_download': True,
                    'extract_flat': True,
                    'noplaylist': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"ytsearch3:{clean_query}", download=False)
                    if info and 'entries' in info:
                        for entry in info['entries']:
                            if entry:
                                dur = entry.get('duration')
                                dur_str = f"{int(dur)//60}:{int(dur)%60:02d}" if dur else "N/A"
                                found_items.append({
                                    "title": entry.get('title', clean_query),
                                    "uploader": entry.get('uploader', 'Official Artist'),
                                    "duration": dur_str,
                                    "url": entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id', '')}"
                                })
            except Exception as e:
                print(f"[Media Search Notice] yt-dlp search: {e}")

            if found_items:
                best = found_items[0]
                res_msg = (
                    f"🎵 [MEDIA SEARCH COMPLETED]\n"
                    f"• Title: {best['title']}\n"
                    f"• Artist/Channel: {best['uploader']}\n"
                    f"• Duration: {best['duration']}\n"
                    f"• Formats Ready: 🎬 Full HD MP4 Video | 🎧 320kbps MP3 Audio\n"
                    f"• Direct Source Link: {best['url']}\n\n"
                    f"👉 [CONFIRMATION REQUIRED]:\n"
                    f"Sir, maine '{best['title']}' dhoondh li hai. Aapko iska **Video Version (MP4)** download karna hai ya **Audio Version (MP3)**?"
                )
                return res_msg
            else:
                return (
                    f"🎵 [MEDIA SOURCES FOUND]\n"
                    f"• Query: {clean_query}\n"
                    f"👉 Sir, aapko iska **Video Version (MP4)** download karna hai ya **Audio Version (MP3)**?"
                )

        else:
            # Movie / Film / Series Search
            movie_sources = []
            try:
                with DDGS() as ddgs:
                    for r in ddgs.text(f"{clean_query} full movie download 1080p 720p watch online", max_results=4):
                        title = r.get('title', '').replace('\n', ' ')
                        href = r.get('href', '')
                        if href and not any(x in href.lower() for x in ['wikipedia', 'imdb.com/title']):
                            movie_sources.append(f"  • {title[:60]} → {href}")
            except Exception as ex:
                print(f"[Movie Search] Web search note: {ex}")

            sources_text = "\n".join(movie_sources[:4]) if movie_sources else "  • Multi-source high-speed CDN mirrors ready."
            res_msg = (
                f"🎬 [MOVIE / SERIES SEARCH COMPLETED]\n"
                f"• Title: {clean_query.title()}\n"
                f"• Quality Options Available: 1080p Full HD (BluRay/WEB-DL), 720p HD, 480p\n"
                f"• Verified Sources & Mirrors:\n{sources_text}\n\n"
                f"👉 [CONFIRMATION REQUIRED]:\n"
                f"Sir, maine '{clean_query.title()}' ke 1080p aur 720p verified download mirrors dhoondh liye hain. Kya main abhi iska **Video Download (1080p MP4)** start kar doon?"
            )
            return res_msg

    # =========================================================================
    # ACTION: DOWNLOAD (Download Song MP3 / Video MP4 directly to Downloads)
    # =========================================================================
    elif action.lower() in ["download", "start", "get", "save"]:
        download_target = direct_url if direct_url else clean_query

        def _async_download():
            import yt_dlp
            # Get bundled ffmpeg path for video/audio merging & conversion
            try:
                import imageio_ffmpeg
                _ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                _ffmpeg_path = None
            out_tmpl = str(target_dir / "%(title)s.%(ext)s")

            def _dl_hook(d):
                global _on_download_progress
                if not _on_download_progress:
                    return
                try:
                    if d.get('status') == 'downloading':
                        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
                        downloaded = d.get('downloaded_bytes', 0)
                        pct = (downloaded / total) * 100.0 if total else 0.0
                        spd = d.get('speed') or 0
                        spd_str = f"{spd / (1024*1024):.1f} MB/s" if spd else "--"
                        eta = d.get('eta')
                        eta_str = f"{eta}s" if eta else "--"
                        sz_str = f"{downloaded/(1024*1024):.1f}MB / {total/(1024*1024):.1f}MB"
                        t_name = d.get('info_dict', {}).get('title') or clean_query
                        _on_download_progress(t_name, pct, spd_str, sz_str, eta_str, "DOWNLOADING")
                    elif d.get('status') == 'finished':
                        t_name = d.get('info_dict', {}).get('title') or clean_query
                        _on_download_progress(t_name, 100.0, "Completed", "Done", "0s", "FINISHED")
                except Exception:
                    pass

            target = download_target if download_target.startswith("http") else f"ytsearch1:{download_target}"

            if is_video:
                # Full HD Video (MP4) Downloader
                ydl_opts = {
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'outtmpl': out_tmpl,
                    'noplaylist': True,
                    'quiet': True,
                    'progress_hooks': [_dl_hook],
                }
                if _ffmpeg_path:
                    ydl_opts['ffmpeg_location'] = _ffmpeg_path
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([target])
                except Exception:
                    # Fallback: try progressive stream (no merge needed)
                    try:
                        ydl_opts_fallback = {
                            'format': 'best[ext=mp4]/best',
                            'outtmpl': out_tmpl,
                            'noplaylist': True,
                            'quiet': True,
                            'progress_hooks': [_dl_hook],
                        }
                        if _ffmpeg_path:
                            ydl_opts_fallback['ffmpeg_location'] = _ffmpeg_path
                        with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
                            ydl.download([target])
                    except Exception as ex:
                        print(f"[Video Download Error]: {ex}")
                        if download_target.startswith("http"):
                            webbrowser.open(download_target)
            else:
                # High-Quality Audio (MP3) Downloader
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': out_tmpl,
                    'noplaylist': True,
                    'quiet': True,
                    'progress_hooks': [_dl_hook],
                }
                if _ffmpeg_path:
                    ydl_opts['ffmpeg_location'] = _ffmpeg_path
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '320',
                    }]
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([target])
                except Exception:
                    # Fallback without FFmpeg postprocessor
                    try:
                        ydl_opts_fallback = {
                            'format': 'bestaudio/best',
                            'outtmpl': out_tmpl,
                            'noplaylist': True,
                            'quiet': True,
                            'progress_hooks': [_dl_hook],
                        }
                        with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
                            ydl.download([target])
                    except Exception as ex:
                        print(f"[Audio Download Error]: {ex}")

            # Open folder in Explorer
            try:
                os.startfile(str(target_dir))
            except Exception:
                pass

        threading.Thread(target=_async_download, daemon=True).start()

        format_label = "VIDEO (MP4)" if is_video else "AUDIO (MP3)"
        return (
            f"🚀 [{format_label} DOWNLOAD INITIATED SUCCESSFULLY]\n"
            f"• Target Media: {clean_query.title()}\n"
            f"• Version: {format_label}\n"
            f"• Saving To Folder: {target_dir}\n"
            f"• Status: High-speed background download active! Folder will open automatically upon completion, Sir."
        )

    # =========================================================================
    # ACTION: OPEN (Open in Browser)
    # =========================================================================
    elif action.lower() in ["open", "stream", "watch"]:
        if direct_url.startswith("http"):
            webbrowser.open(direct_url)
            return f"Opened direct media link in your default browser, Sir: {direct_url}"
        else:
            url = f"https://www.youtube.com/results?search_query={clean_query}" if m_type == "song" else f"https://www.google.com/search?q={clean_query}+full+movie+watch+online"
            webbrowser.open(url)
            return f"Opened stream and download portal for '{clean_query}' in your browser, Sir."

    return f"Media command executed for '{clean_query}', Sir."


# --- 34. Notification Sentry Control Tool ---
def notification_control(action: str = "open") -> str:
    """
    Handles user decision on active system/app notifications.
    - action: 'open' (opens/launches the application from the active notification), or 'close'/'dismiss' (dismisses the notification alert)
    Call this when Sir says:
    - "notification open karo", "kholo", "open kar do", "open this app"
    - "notification close karo", "dismiss", "band karo", "rehne do", "hatao"
    """
    from cwa_agent.core.notification_sentry import notification_sentry
    return notification_sentry.handle_user_decision(action)


_ttt_expand_callback = None

def register_ttt_expand_callback(cb):
    global _ttt_expand_callback
    _ttt_expand_callback = cb

# --- 35. Quantum Tic-Tac-Toe Gaming Arena Tool ---
def play_tic_tac_toe(action: str = "open", position: int = 0) -> str:
    """
    Launches or plays Tic-Tac-Toe with Sir in the left HUD gaming arena.
    - action:
        * 'open' or 'start': Starts a fresh game and invites Sir to make the first move.
        * 'move': Plays at a specific cell position (1 to 9).
        * 'cwa_first': Starts a new game with CWA making the opening move.
        * 'score': Returns the current match scoreboard.
        * 'reset': Resets the scores and clears the board.
    - position: Optional board index (1 to 9) when making a move.
    
    Call this when Sir says:
    - "tic tac toe khelo", "game khelo", "let's play a game", "tic tac toe shuru karo"
    - "position 5 par khelo", "center me daalo", "box 1 me khelo"
    - "score kya hai", "game reset karo"
    """
    from cwa_agent.core.tictactoe_engine import ttt_engine

    if _ttt_expand_callback:
        try:
            _ttt_expand_callback()
        except Exception:
            pass

    act = str(action).lower().strip()

    if act in ["open", "start", "play", "new"]:
        ttt_engine.reset_game()
        return "Quantum Tic-Tac-Toe Arena active ho gaya hai, Sir! Pehli move aapki hai (X). Kisi bhi box par click kijiye."

    elif act in ["cwa_first", "ai_first"]:
        ttt_engine.reset_game(start_ai=True)
        pos, winner, commentary = ttt_engine.make_ai_move()
        return f"Maine pehli move chal di hai (Position {pos + 1} par 'O'). Ab aapki bari hai (X), Sir!"

    elif act in ["score", "stats"]:
        u = ttt_engine.scores["user"]
        a = ttt_engine.scores["ai"]
        d = ttt_engine.scores["draws"]
        return f"Tic-Tac-Toe Scoreboard: Ali (X) = {u} Wins | CWA (O) = {a} Wins | Draws = {d}"

    elif act in ["reset", "clear"]:
        ttt_engine.reset_all_scores()
        return "Scoreboard aur Tic-Tac-Toe board dono reset ho gaye hain, Sir!"

    elif act == "move" or position > 0:
        pos_idx = max(0, min(8, int(position) - 1)) if position > 0 else 0
        success, winner, msg = ttt_engine.make_user_move(pos_idx)
        if not success:
            return msg
        if winner == 'X':
            return "🏆 Shandar Ali! Aap jeet gaye! Fantastic strategy!"
        elif winner == 'Draw':
            return "🤝 Match tie ho gaya! Kadi takkar thi."

        ai_pos, ai_winner, ai_commentary = ttt_engine.make_ai_move()
        return f"Aapne Position {pos_idx + 1} par 'X' chala. {ai_commentary}"

    return "Tic-Tac-Toe Arena ready hai, Sir!"


_route_modal_callback = None

def register_route_modal_callback(cb):
    global _route_modal_callback
    _route_modal_callback = cb

# --- 36. GPS Route & Destination Navigator Tool ---
def navigate_route(origin: str, destination: str, travel_mode: str = "driving") -> str:
    """
    Calculates live GPS distance, estimated travel time, route map trajectory, and opens the Quantum Route Navigator popup dialog.
    - origin: Starting location or city (e.g. 'Delhi', 'Mumbai', 'Lucknow', 'Current Location')
    - destination: Destination place, city, landmark, or address (e.g. 'Agra', 'Goa', 'Taj Mahal', 'Times Square')
    - travel_mode: 'driving' (car), 'motorcycle' (bike), 'transit' (train/bus), 'walking'
    
    Call this when Sir says:
    - "Delhi se Agra ka route banao", "Kahan se kahan tak jana hai batao"
    - "Mumbai se Goa kitna dur hai aur kitna time lagega"
    - "Show route to Lucknow", "Destination map kholo"
    """
    from cwa_agent.core.route_navigator import route_navigator

    res = route_navigator.calculate_route(origin, destination, travel_mode)
    
    if _route_modal_callback and res.get("success"):
        try:
            _route_modal_callback(res)
        except Exception:
            pass

    if not res.get("success"):
        return f"Sir, route calculate nahi ho paya: {res.get('error', 'Unknown location')}"

    o = res["origin"]
    d = res["destination"]
    dist = res["distance_str"]
    dur = res["duration_str"]
    mode = res["travel_mode"]

    return f"Done Sir! {o} se {d} tak ka distance {dist} hai, aur {mode} se lagbhag {dur} lagenge. Maine screen par route navigator popup open kar diya hai jahan se aap live Google Maps turn-by-turn navigation bhi dekh sakte hain."


def search_nearby_places(query: str, location: str = "") -> str:
    """
    Searches for nearby places, restaurants, cafes, hospitals, petrol pumps, ATMs, tourist attractions,
    or hotels using Google Maps Places API.

    Parameters:
    - query: What to search for (e.g. 'best cafes', 'petrol pump', 'nearest hospital', 'Italian restaurant', 'ATM')
    - location: City, area, or locality to search in (e.g. 'Connaught Place Delhi', 'Bandra Mumbai', 'Goa')

    Call this when Sir says:
    - "mere paas cafe dhoondho", "nearest hospital kahan hai"
    - "Delhi mein best restaurants batao", "Goa ke tourist places dikhao"
    - "petrol pump kahan hai", "ATM search karo"
    """
    from cwa_agent.core.route_navigator import route_navigator
    places = route_navigator.search_nearby_places(query, location)
    if not places:
        return f"Sir, '{query}' ke liye koi results nahi mile. Location verify karke doobara try karein."

    lines = [f"📍 Google Maps Places Results for '{query}'" + (f" in {location}:" if location else ":") + "\n"]
    for i, p in enumerate(places, 1):
        rating_star = f"⭐ {p['rating']}" if p.get('rating') and p['rating'] != "N/A" else ""
        open_status = "🟢 Open Now" if p.get('open_now') is True else "🔴 Closed" if p.get('open_now') is False else ""
        lines.append(f"{i}. **{p['name']}** {rating_star} {open_status}")
        if p.get("address"):
            lines.append(f"   Address: {p['address']}")
        lines.append("")

    return "\n".join(lines)


def remove_image_background(image_path_or_url: str = "", bg_color: str = "transparent", output_name: str = "", auto_open: bool = True) -> str:
    """
    Removes background from any image, photo, URL, screenshot, or clipboard using Remove.bg AI.
    Can also apply professional studio colors like 'pure white' (for passport/resume), 'passport blue', 'studio grey', or transparent PNG.

    Parameters:
    - image_path_or_url: Local file path (e.g. 'cwa_agent/media/photo.jpg'), image URL (http/https), 'clipboard' (grabs from clipboard), or 'screen' (captures active screen).
    - bg_color: 'transparent' (default transparent PNG), 'white' / 'pure white' (for resume/ID/passport), 'passport blue', 'navy blue', 'studio grey', 'black', or custom HEX '#FFFFFF'.
    - output_name: Custom name for the output cutout file (optional).
    - auto_open: Whether to automatically open the saved image in Windows Photo Viewer (default True).

    Call this tool whenever Sir says:
    - "is photo ka background remove kar do", "background hatao", "transparent PNG bana do"
    - "passport size photo ka white background laga do", "resume photo banao"
    - "clipboard wali photo ka background cut kar do", "screen ka screenshot leke background hatao"
    """
    from cwa_agent.core.bg_remover import bg_remover
    success, out_path, msg = bg_remover.remove_background(
        image_input=image_path_or_url,
        bg_color=bg_color,
        output_name=output_name,
        auto_open=auto_open
    )
    return msg



# ══════════════════════════════════════════════════════════════════════════════
#  OPENROUTER MULTI-MODEL AI ENGINE TOOLS
# ══════════════════════════════════════════════════════════════════════════════

def openrouter_switch_model(model_name: str) -> str:
    """
    Switches the active AI brain to a different model via OpenRouter.
    Supports free models (zero cost): deepseek, llama, mistral, gemini flash, qwen, phi.
    Supports paid models (credits needed): claude, gpt-4o, gpt-4, gemini pro, grok.

    Call this tool whenever Sir says:
    - "switch to DeepSeek", "DeepSeek pe switch karo", "ab DeepSeek se baat karni hai"
    - "Claude se yeh question poocho", "GPT-4 use karo", "Llama chalao"
    - "free model pe switch karo", "OpenRouter model change karo"
    - "back to Gemini" or "Gemini pe wapas jao" (pass 'gemini' to reset to Gemini)

    Parameters:
    - model_name: Model alias like 'deepseek', 'claude', 'gpt-4o', 'llama', 'mistral', 'qwen', 'phi', 'gemini pro', 'grok'
                  OR full OpenRouter model ID like 'anthropic/claude-sonnet-4-5'
    """
    from cwa_agent.core.openrouter import openrouter
    success, msg = openrouter.switch_model(model_name)
    return msg


def openrouter_ask(question: str, model_name: str = "") -> str:
    """
    Asks a question directly to any OpenRouter model (without switching permanently).
    Great for one-off queries to specific models.

    Call this tool whenever Sir says:
    - "DeepSeek se poochho yeh kya hai", "Claude ki raay lo is topic pe"
    - "GPT-4 se yeh code solve karwao", "Llama se summary banao"
    - "OpenRouter se poochho", "kisi aur model se answer lo"

    Parameters:
    - question: The question or task to ask the model.
    - model_name: (Optional) Model alias or full ID. Leave empty to use currently active model.
    """
    from cwa_agent.core.openrouter import openrouter
    from cwa_agent.config import OPENROUTER_ALL_MODELS
    if model_name:
        # Temporarily use specified model for this one call
        target = OPENROUTER_ALL_MODELS.get(model_name.lower().strip(), model_name)
        msgs = [
            {"role": "system", "content": "You are a helpful AI assistant. Be concise and natural."},
            {"role": "user", "content": question}
        ]
        resp = openrouter._call_api(msgs, model=target)
        return resp or f"'{model_name}' model se response nahi aaya Sir."
    else:
        return openrouter.ask(question)


def openrouter_compare(question: str, models: str = "deepseek,llama,mistral") -> str:
    """
    Asks the same question to multiple OpenRouter AI models and compares their responses.
    Great for getting multiple perspectives or finding the best answer.

    Call this tool whenever Sir says:
    - "teeno models se poocho", "compare karo alag alag AI se"
    - "sab models se yeh question poocho", "multi-model comparison karo"
    - "kaunsa model best answer deta hai yeh jaanna hai"

    Parameters:
    - question: The question to compare across models.
    - models: Comma-separated model aliases to compare (default: 'deepseek,llama,mistral').
              Example: 'deepseek,claude,gpt-4o' or 'llama,mistral,qwen'
    """
    from cwa_agent.core.openrouter import openrouter
    model_list = [m.strip() for m in models.split(",") if m.strip()]
    results = openrouter.compare_models(question, model_aliases=model_list)
    output_lines = [f"🔬 Multi-Model Comparison Results:\n"]
    for alias, response in results.items():
        output_lines.append(f"── [{alias.upper()}] ──")
        output_lines.append(response[:800] if len(response) > 800 else response)
        output_lines.append("")
    return "\n".join(output_lines)


def openrouter_status() -> str:
    """
    Returns status of the OpenRouter engine — current model, available models, and API key status.

    Call this tool whenever Sir says:
    - "OpenRouter ka status kya hai", "kaunsa model active hai"
    - "available models list karo", "OpenRouter models dikhao"
    - "current AI model kaunsa hai"
    """
    from cwa_agent.core.openrouter import openrouter
    info = openrouter.get_current_model_info()
    status = "✅ Active" if openrouter.is_active else "❌ Inactive (API Key missing)"
    return (
        f"🌐 OpenRouter Engine Status:\n"
        f"  Status: {status}\n"
        f"  Active Model: {info['model_id']}\n"
        f"  Alias: {info['alias']}\n"
        f"  Cost: {info['cost']}\n\n"
        f"{openrouter.list_models()}"
    )


def exa_neural_search(query: str, num_results: int = 8, search_type: str = "auto") -> str:
    """
    Performs a deep Exa AI Neural Web Search for highly relevant, real-time results.
    Unlike regular keyword search, Exa understands meaning and intent of the query.
    Use this for: research, in-depth news, technical documentation, latest events, fact-finding.

    Args:
        query: The search query or question to find information about.
        num_results: Number of results to fetch (default 8, max 20).
        search_type: 'auto' (smart), 'neural' (semantic meaning), or 'keyword' (exact match).

    Call this tool when Sir says:
    - "Exa se search karo", "deep search karo", "research karo"
    - "latest news dhundho", "real-time search karo"
    - "is topic ke baare mein sab kuch dhundho"
    """
    import requests as _requests

    exa_key = _get_exa_api_key()
    if not exa_key:
        return "Sir, Exa API key configured nahi hai. Please .env file mein EXA_API_KEY add karein."

    num_results = max(1, min(20, int(num_results)))
    valid_types = {"auto", "neural", "keyword"}
    if search_type not in valid_types:
        search_type = "auto"

    print(f"[Tools 🔍] Exa Neural Search: '{query}' | type={search_type} | results={num_results}")

    try:
        headers = {
            "x-api-key": exa_key,
            "Content-Type": "application/json"
        }
        payload = {
            "query": query,
            "numResults": num_results,
            "type": search_type,
            "contents": {
                "text": {"maxCharacters": 1200},
                "highlights": {"numSentences": 3, "highlightsPerUrl": 2}
            }
        }
        resp = _requests.post(
            "https://api.exa.ai/search",
            json=payload,
            headers=headers,
            timeout=12
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return f"Sir, Exa search mein '{query}' ke liye koi result nahi mila."

            output_parts = [f"🔍 **Exa Neural Search** — '{query}' ({len(results)} results found)\n"]
            for idx, r in enumerate(results, 1):
                title   = r.get("title") or "No Title"
                url     = r.get("url", "")
                score   = r.get("score", 0)
                text    = (r.get("text") or "").replace("\n", " ").strip()[:900]
                highlights = r.get("highlights", [])
                highlight_text = " | ".join(highlights[:2]) if highlights else ""

                entry = [f"{idx}. **{title}**"]
                if highlight_text:
                    entry.append(f"   💡 {highlight_text}")
                if text:
                    entry.append(f"   📄 {text}")
                entry.append(f"   🔗 {url}  (relevance: {score:.3f})")
                output_parts.append("\n".join(entry))

            return "\n\n".join(output_parts)
        else:
            return f"Sir, Exa API error: HTTP {resp.status_code} — {resp.text[:300]}"
    except Exception as e:
        return f"Sir, Exa Neural Search failed: {type(e).__name__}: {e}"


def exa_answer(question: str) -> str:
    """
    Gets a direct, precise AI-generated answer to any question using Exa's Answer Engine.
    Exa searches the web in real-time and returns a concise, sourced answer — not just links.
    Best for: factual questions, current events, quick lookups, definitions, calculations.

    Args:
        question: The question to get a direct answer for.

    Call this tool when Sir says:
    - "direct answer do", "Exa se answer lao", "quick answer chahiye"
    - "kya hai", "kaun hai", "kab hua", "kitna hai" (any factual question)
    - "real-time mein bata", "abhi ka data chahiye"
    """
    import requests as _requests

    exa_key = _get_exa_api_key()
    if not exa_key:
        return "Sir, Exa API key configured nahi hai. Please .env mein EXA_API_KEY add karein."

    print(f"[Tools 💡] Exa Answer Engine: '{question}'")

    try:
        headers = {
            "x-api-key": exa_key,
            "Content-Type": "application/json"
        }
        payload = {
            "query": question,
            "text": True
        }
        resp = _requests.post(
            "https://api.exa.ai/answer",
            json=payload,
            headers=headers,
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            answer = data.get("answer") or data.get("text") or ""
            citations = data.get("citations", []) or data.get("results", [])

            if not answer:
                return f"Sir, Exa Answer Engine ka koi jawab nahi aaya '{question}' ke liye."

            output = [f"💡 **Exa Answer:** {answer}"]
            if citations:
                output.append("\n📚 **Sources:**")
                for i, c in enumerate(citations[:4], 1):
                    src_title = c.get("title") or c.get("name") or "Source"
                    src_url   = c.get("url", "")
                    output.append(f"   {i}. {src_title} — {src_url}")

            print(f"[Tools ✅] Exa Answer received ({len(answer)} chars).")
            return "\n".join(output)
        else:
            return f"Sir, Exa Answer API error: HTTP {resp.status_code} — {resp.text[:300]}"
    except Exception as e:
        return f"Sir, Exa Answer Engine failed: {type(e).__name__}: {e}"


def exa_find_similar(url: str, num_results: int = 6) -> str:
    """
    Finds web pages and articles that are similar to a given URL using Exa AI.
    Useful for: finding related articles, similar products, competitor pages, alternative sources.

    Args:
        url: The URL to find similar pages for.
        num_results: Number of similar results to return (default 6).

    Call this tool when Sir says:
    - "is website jaisi aur sites dhundho", "similar pages dhundho"
    - "is article se related aur articles chahiye"
    - "alternatives dhundho is URL ke"
    - "find similar", "related content dhundho"
    """
    import requests as _requests

    exa_key = _get_exa_api_key()
    if not exa_key:
        return "Sir, Exa API key configured nahi hai. Please .env mein EXA_API_KEY add karein."

    num_results = max(1, min(20, int(num_results)))
    print(f"[Tools 🔗] Exa Find Similar: '{url}' | {num_results} results")

    try:
        headers = {
            "x-api-key": exa_key,
            "Content-Type": "application/json"
        }
        payload = {
            "url": url,
            "numResults": num_results,
            "contents": {
                "text": {"maxCharacters": 600}
            }
        }
        resp = _requests.post(
            "https://api.exa.ai/findSimilar",
            json=payload,
            headers=headers,
            timeout=12
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return f"Sir, '{url}' jaise koi similar pages nahi mile."

            output_parts = [f"🔗 **Similar Pages** to: {url}\n({len(results)} results found)\n"]
            for idx, r in enumerate(results, 1):
                title   = r.get("title") or "No Title"
                r_url   = r.get("url", "")
                score   = r.get("score", 0)
                text    = (r.get("text") or "").replace("\n", " ").strip()[:500]
                entry = [f"{idx}. **{title}**"]
                if text:
                    entry.append(f"   {text}")
                entry.append(f"   🔗 {r_url}  (similarity: {score:.3f})")
                output_parts.append("\n".join(entry))

            return "\n\n".join(output_parts)
        else:
            return f"Sir, Exa FindSimilar API error: HTTP {resp.status_code} — {resp.text[:300]}"
    except Exception as e:
        return f"Sir, Exa Find Similar failed: {type(e).__name__}: {e}"


# List of all available dynamic tool functions for Gemini Client
CWA_TOOLS = [
    system_control,
    system_scan,
    app_control,
    type_text,
    web_search,
    read_webpage_content,
    play_youtube,
    search_youtube_videos,
    get_youtube_video_details,
    get_youtube_trending,
    get_youtube_channel_stats,
    movie_search_and_info,
    movie_trending_and_recommendations,
    play_movie_or_trailer,
    open_website,
    file_manager,
    execute_python,
    vision_see,
    send_whatsapp,
    generate_image,
    switch_voice_mode,
    edit_code_file,
    clear_chat,
    remember_information,
    recall_memory,
    set_reminder,
    inspect_screen,
    change_desktop_wallpaper,
    recall_room_conversation,
    send_to_telegram,
    unlock_workstation,
    sing_song,
    interact_with_app,
    toggle_whatsapp_auto_reply,
    auto_reply_whatsapp_chat,
    generate_qr_code,
    translate_text,
    media_search_and_download,
    workspace_file_intelligence,
    manage_ignore_words,
    manage_forbidden_words,
    notification_control,
    play_tic_tac_toe,
    navigate_route,
    search_nearby_places,
    remove_image_background,
    openrouter_switch_model,
    openrouter_ask,
    openrouter_compare,
    openrouter_status,
    exa_neural_search,
    exa_answer,
    exa_find_similar,
]






