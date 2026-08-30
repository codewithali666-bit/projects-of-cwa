import os
import platform
import socket
import datetime
import psutil
from pathlib import Path


class SystemScanner:
    """
    Stark Industries System Intelligence Scanner.
    Performs a deep full-system scan on boot and returns a structured report.
    All data is dynamically collected at runtime — zero hardcoding.
    """

    def __init__(self):
        self._cached_report = None
        self._scan_timestamp = None

    def full_scan(self, progress_callback=None) -> dict:
        """
        Lightweight, non-blocking system scan.
        All heavy blocking calls replaced with instant non-blocking equivalents.
        Emits percentage progress via progress_callback(percent, status) if provided.
        """
        report = {}

        def _report_pct(pct: int, msg: str):
            if progress_callback:
                try:
                    progress_callback(pct, msg)
                except Exception:
                    pass

        _report_pct(5, "Initializing scanner...")

        # Pre-warm cpu_percent non-blocking (first call always returns 0.0, that's fine)
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

        # --- OS & Machine Info ---
        _report_pct(15, "Reading OS & Host info...")
        try:
            report["os"] = {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "hostname": socket.gethostname(),
                "username": os.environ.get("USERNAME", "Unknown"),
                "boot_time": datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception:
            report["os"] = {}

        # --- CPU & RAM (non-blocking — no sleep/interval) ---
        _report_pct(28, "Reading CPU & Memory...")
        try:
            freq = psutil.cpu_freq()
            report["cpu"] = {
                "physical_cores": psutil.cpu_count(logical=False),
                "logical_cores": psutil.cpu_count(logical=True),
                "usage_percent": psutil.cpu_percent(interval=None),  # non-blocking
                "frequency_mhz": round(freq.current, 1) if freq else "N/A",
            }
        except Exception:
            report["cpu"] = {}

        try:
            vm = psutil.virtual_memory()
            report["ram"] = {
                "total_gb": round(vm.total / (1024 ** 3), 2),
                "available_gb": round(vm.available / (1024 ** 3), 2),
                "used_gb": round(vm.used / (1024 ** 3), 2),
                "usage_percent": vm.percent,
            }
        except Exception:
            report["ram"] = {}

        # --- Storage Disks (skip CD-ROM & unmounted) ---
        _report_pct(42, "Scanning drives...")
        try:
            disks = []
            for part in psutil.disk_partitions(all=False):  # all=False skips virtual/CD drives
                if not part.mountpoint or part.fstype in ("", "squashfs", "tmpfs"):
                    continue
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append({
                        "drive": part.mountpoint,
                        "fs": part.fstype,
                        "total_gb": round(usage.total / (1024 ** 3), 2),
                        "free_gb": round(usage.free / (1024 ** 3), 2),
                        "used_percent": usage.percent,
                    })
                except (PermissionError, OSError):
                    pass
            report["disks"] = disks
        except Exception:
            report["disks"] = []

        # --- Battery (fast, no blocking) ---
        try:
            batt = psutil.sensors_battery()
            if batt:
                report["battery"] = {
                    "percent": round(batt.percent, 1),
                    "plugged": batt.power_plugged,
                    "secs_left": batt.secsleft if batt.secsleft != -1 else "Charging",
                }
            else:
                report["battery"] = {"percent": 100, "plugged": True, "secs_left": "Desktop"}
        except Exception:
            report["battery"] = {}

        # --- Network (fast, no DNS lookup) ---
        _report_pct(58, "Scanning network interfaces...")
        try:
            net = psutil.net_io_counters()
            addrs = psutil.net_if_addrs()
            active_interfaces = []
            for iface, addr_list in addrs.items():
                for addr in addr_list:
                    if addr.family == socket.AF_INET and addr.address != "127.0.0.1":
                        active_interfaces.append({"interface": iface, "ip": addr.address})
            report["network"] = {
                "active_interfaces": active_interfaces[:3],
                "bytes_sent_mb": round(net.bytes_sent / (1024 ** 2), 2),
                "bytes_recv_mb": round(net.bytes_recv / (1024 ** 2), 2),
            }
        except Exception:
            report["network"] = {}

        # --- Top 5 Processes by RAM (memory_percent is instant, no CPU blocking) ---
        _report_pct(80, "Reading running processes...")
        try:
            procs = []
            for proc in psutil.process_iter(["pid", "name", "memory_percent"]):
                try:
                    mem = proc.info.get("memory_percent") or 0
                    if mem > 0.1:  # skip idle/empty processes
                        procs.append({
                            "pid": proc.info["pid"],
                            "name": proc.info["name"],
                            "mem": round(mem, 1),
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            procs.sort(key=lambda x: x["mem"], reverse=True)
            report["top_processes"] = procs[:5]
        except Exception:
            report["top_processes"] = []

        report["scan_timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._cached_report = report
        self._scan_timestamp = report["scan_timestamp"]
        _report_pct(100, "Scan Complete — System Ready")
        return report

    def scan_installed_applications(self, progress_callback=None) -> dict:
        """
        Dynamically scans all installed applications from Windows Registry keys,
        Start Menu shortcuts, and Program Files directories — zero hardcoding.
        Returns a dict mapping normalized app names to application metadata.
        """
        apps = {}
        import winreg

        if progress_callback:
            try:
                progress_callback(10, "Querying Windows Registry uninstall keys...")
            except Exception:
                pass

        # 1. Registry Scan (HKLM & HKCU Uninstall keys)
        reg_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
            (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'),
            (winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Uninstall')
        ]
        for root, subkey in reg_keys:
            try:
                with winreg.OpenKey(root, subkey) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            s_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, s_name) as s_key:
                                try:
                                    display_name, _ = winreg.QueryValueEx(s_key, 'DisplayName')
                                except Exception:
                                    continue
                                
                                if display_name and isinstance(display_name, str) and display_name.strip():
                                    clean_name = display_name.strip()
                                    norm_key = clean_name.lower()
                                    
                                    install_loc = ""
                                    try:
                                        install_loc, _ = winreg.QueryValueEx(s_key, 'InstallLocation')
                                    except Exception:
                                        pass
                                        
                                    display_icon = ""
                                    try:
                                        display_icon, _ = winreg.QueryValueEx(s_key, 'DisplayIcon')
                                    except Exception:
                                        pass

                                    apps[norm_key] = {
                                        "name": clean_name,
                                        "path": display_icon.split(",")[0].strip('"') if display_icon else install_loc,
                                        "source": "Registry"
                                    }
                        except Exception:
                            pass
            except Exception:
                pass

        if progress_callback:
            try:
                progress_callback(60, f"Discovered {len(apps)} apps in Registry. Scanning Start Menu...")
            except Exception:
                pass

        # 2. Start Menu Shortcuts Scan (.lnk files)
        start_menu_paths = [
            os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs'),
            os.path.expandvars(r'%ProgramData%\Microsoft\Windows\Start Menu\Programs')
        ]
        for sm_path in start_menu_paths:
            if os.path.exists(sm_path):
                for r_dir, _, files in os.walk(sm_path):
                    for f in files:
                        if f.endswith('.lnk'):
                            app_title = os.path.splitext(f)[0]
                            clean_title = app_title.strip()
                            norm_key = clean_title.lower()
                            full_lnk = os.path.join(r_dir, f)

                            if norm_key not in apps:
                                apps[norm_key] = {
                                    "name": clean_title,
                                    "path": full_lnk,
                                    "source": "StartMenu"
                                }

        if progress_callback:
            try:
                progress_callback(100, f"Discovered {len(apps)} total applications!")
            except Exception:
                pass

        return apps


    def get_system_context_string(self) -> str:
        """
        Converts the full scan into a readable context string to inject into Gemini's neural cortex.
        """
        if not self._cached_report:
            self.full_scan()

        r = self._cached_report
        lines = [f"SYSTEM SCAN REPORT [{r.get('scan_timestamp', 'N/A')}]"]

        # OS
        os_info = r.get("os", {})
        if os_info:
            lines.append(
                f"OS: {os_info.get('system')} {os_info.get('release')} | "
                f"Host: {os_info.get('hostname')} | User: {os_info.get('username')} | "
                f"Booted: {os_info.get('boot_time')}"
            )

        # CPU
        cpu = r.get("cpu", {})
        if cpu:
            lines.append(
                f"CPU: {cpu.get('logical_cores')} logical cores @ {cpu.get('frequency_mhz')} MHz | "
                f"Usage: {cpu.get('usage_percent')}%"
            )

        # RAM
        ram = r.get("ram", {})
        if ram:
            lines.append(
                f"RAM: {ram.get('total_gb')} GB total | {ram.get('available_gb')} GB free | "
                f"Usage: {ram.get('usage_percent')}%"
            )

        # Disks
        for disk in r.get("disks", []):
            lines.append(
                f"Disk [{disk.get('drive')}]: {disk.get('total_gb')} GB total, "
                f"{disk.get('free_gb')} GB free ({disk.get('used_percent')}% used)"
            )

        # Battery
        batt = r.get("battery", {})
        if batt:
            plugged_str = "Charging" if batt.get("plugged") else "On Battery"
            lines.append(f"Battery: {batt.get('percent')}% ({plugged_str})")

        # Network
        net = r.get("network", {})
        if net:
            ifaces = net.get("active_interfaces", [])
            if ifaces:
                iface_str = ", ".join([f"{i['interface']}={i['ip']}" for i in ifaces])
                lines.append(f"Network: {iface_str}")

        # Top Processes
        procs = r.get("top_processes", [])
        if procs:
            proc_str = ", ".join([f"{p['name']}({p.get('mem', 0)}% RAM)" for p in procs[:5]])
            lines.append(f"Top Processes: {proc_str}")

        return "\n".join(lines)


# Global Scanner Singleton
scanner = SystemScanner()

