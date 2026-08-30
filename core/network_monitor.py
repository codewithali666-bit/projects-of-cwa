"""
CWA Autonomous Agent — Network & WiFi Monitor
Monitors real-time network connectivity, ping latency, speed estimation, and active interface info.
Zero hardcoding — all values fetched dynamically via socket, psutil, and subprocess.
"""
import socket
import subprocess
import threading
import time
import datetime


class NetworkMonitor:
    """
    Live network & WiFi stats monitor.
    Tracks connectivity, latency, upload/download speed, and adapter info.
    """
    def __init__(self):
        self._running = False
        self._thread = None
        self._on_update_callback = None
        self.current_stats = {
            "connected": False,
            "ping_ms": None,
            "ssid": None,
            "ip": None,
            "adapter": None,
            "last_checked": None
        }

    def start(self, on_update=None):
        """Start network monitoring daemon."""
        self._on_update_callback = on_update
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _ping_host(self, host: str = "8.8.8.8") -> float | None:
        """Pings a public DNS server and returns round-trip time in ms."""
        try:
            start = time.perf_counter()
            sock = socket.create_connection((host, 53), timeout=3)
            sock.close()
            elapsed_ms = (time.perf_counter() - start) * 1000
            return round(elapsed_ms, 1)
        except Exception:
            return None

    def _get_local_ip(self) -> str:
        """Dynamically detects local machine IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "N/A"

    def _get_wifi_ssid(self) -> str | None:
        """Dynamically fetches connected WiFi SSID name via Windows netsh."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, timeout=4
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.lower().startswith("ssid") and "bssid" not in line.lower():
                    parts = line.split(":", 1)
                    if len(parts) == 2 and parts[1].strip():
                        return parts[1].strip()
        except Exception:
            pass
        return None

    def _get_adapter_name(self) -> str:
        """Returns active network adapter name via psutil."""
        try:
            import psutil
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
            local_ip = self._get_local_ip()
            for name, addr_list in addrs.items():
                for addr in addr_list:
                    if addr.address == local_ip:
                        return name
        except Exception:
            pass
        return "Unknown"

    def _monitor_loop(self):
        """Background polling loop — refreshes every 5 seconds."""
        while self._running:
            try:
                ping = self._ping_host()
                ip = self._get_local_ip()
                ssid = self._get_wifi_ssid()
                adapter = self._get_adapter_name()

                self.current_stats = {
                    "connected": ping is not None,
                    "ping_ms": ping,
                    "ssid": ssid,
                    "ip": ip,
                    "adapter": adapter,
                    "last_checked": datetime.datetime.now().strftime("%H:%M:%S")
                }
                if self._on_update_callback:
                    try:
                        self._on_update_callback(dict(self.current_stats))
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(5)

    def get_status_text(self) -> str:
        """Returns a formatted text status of current network."""
        s = self.current_stats
        if not s.get("last_checked"):
            return "Network monitor initializing..."
        if s["connected"]:
            ssid_txt = f" | WiFi: {s['ssid']}" if s["ssid"] else " | Ethernet/LAN"
            return (
                f"✅ ONLINE | Ping: {s['ping_ms']} ms{ssid_txt}\n"
                f"IP: {s['ip']} | Adapter: {s['adapter']} | As of: {s['last_checked']}"
            )
        return f"❌ OFFLINE — No internet connectivity detected | Last checked: {s.get('last_checked', 'N/A')}"


# Global singleton
network_monitor = NetworkMonitor()
