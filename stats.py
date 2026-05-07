"""
esp32s3_stats.py
================
System statistics collector for the ESP32-S3 running MicroPython.

Collects and serializes to JSON:
    - CPU frequency
    - Internal chip temperature
    - Heap (RAM) usage
    - Internal flash usage
    - SD card usage (default mount: /sd)
    - System uptime
    - Last reset cause
    - Wi-Fi network status

Usage::

    from esp32s3_stats import SystemStats

    stats = SystemStats(sd_mount="/sd")

    # Collect once and get a JSON string
    print(stats.to_json())

    # Get a plain dict instead
    data = stats.collect()

    # Pretty-print to console (debug)
    stats.report()

    # Continuous polling every 10 s
    import time
    while True:
        print(stats.to_json())
        time.sleep(10)
"""

import gc
import json
import machine
import os
import sys
import time

# ── Optional platform modules ─────────────────────────────────────────────────

try:
    import esp32 as _esp32
    _HAS_ESP32 = True
except ImportError:
    _esp32 = None
    _HAS_ESP32 = False

try:
    import network as _network
    _HAS_NETWORK = True
except ImportError:
    _network = None
    _HAS_NETWORK = False


# ── Internal helpers ──────────────────────────────────────────────────────────

def _to_mb(b: int) -> float:
    return round(b / 1_048_576, 2)


def _to_kb(b: int) -> float:
    return round(b / 1024, 2)


def _statvfs(path: str) -> dict:
    """
    Return filesystem statistics for *path* using os.statvfs().

    statvfs tuple layout:
        [0] f_bsize   - block size in bytes
        [2] f_blocks  - total data blocks
        [3] f_bfree   - free blocks
    """
    try:
        st          = os.statvfs(path)
        block_size  = st[0]
        total_bytes = st[2] * block_size
        free_bytes  = st[3] * block_size
        used_bytes  = total_bytes - free_bytes
        used_pct    = round(used_bytes / total_bytes * 100, 1) if total_bytes else 0.0
        return {
            "mounted":      True,
            "path":         path,
            "block_size_b": block_size,
            "total_mb":     _to_mb(total_bytes),
            "used_mb":      _to_mb(used_bytes),
            "free_mb":      _to_mb(free_bytes),
            "used_pct":     used_pct,
        }
    except OSError as exc:
        return {"mounted": False, "path": path, "error": str(exc)}


# ── Main class ────────────────────────────────────────────────────────────────

class SystemStats:
    """
    Collects system statistics for the ESP32-S3 and serializes them to JSON.

    Parameters
    ----------
    sd_mount : str
        Mount point of the SD card (default ``"/sd"``).
    """

    # Maps machine.reset_cause() integer codes to human-readable labels.
    _RESET_CAUSES: dict = {
        machine.PWRON_RESET:     "power_on",
        machine.HARD_RESET:      "hard_reset",
        machine.WDT_RESET:       "watchdog",
        machine.DEEPSLEEP_RESET: "deep_sleep_wakeup",
        machine.SOFT_RESET:      "soft_reset",
    }

    def __init__(self, sd_mount: str = "/sd") -> None:
        self.sd_mount = sd_mount

    # ── Private collectors ────────────────────────────────────────────────────

    def _collect_system(self) -> dict:
        """Platform and MicroPython version information."""
        info: dict = {
            "platform":    sys.platform,
            "version":     sys.version,
            "micropython": True,
        }
        try:
            impl = sys.implementation
            info["implementation"] = {
                "name":    impl.name,
                "version": list(impl.version),
            }
        except AttributeError:
            pass
        return info

    def _collect_cpu(self) -> dict:
        """CPU clock frequency."""
        try:
            freq_hz = machine.freq()
            return {
                "freq_hz":  freq_hz,
                "freq_mhz": freq_hz // 1_000_000,
            }
        except Exception as exc:
            return {"error": str(exc)}

    def _collect_temperature(self) -> dict:
        """
        Internal chip temperature.

        Primary source: ``esp32.raw_temperature()`` (returns degrees Fahrenheit
        on most MicroPython builds).
        Fallback: raw ADC reading (approximate, pin-dependent).
        """
        if _HAS_ESP32:
            try:
                temp_c  = _esp32.mcu_temperature()
                temp_f = (temp_c * 9/5) + 32
                return {
                    "celsius": round(float(temp_c), 1),
                    "fahrenheit": round(float(temp_f), 1),
                    "source":     "esp32.mcu_temperature",
                }
            except Exception as exc:
                return {"error": str(exc), "celsius": None}

        # Fallback — adjust pin number for your board layout
        try:
            adc = machine.ADC(machine.Pin(4))
            adc.atten(machine.ADC.ATTN_11DB)
            return {
                "raw_adc": adc.read(),
                "source":  "fallback_adc",
                "celsius": None,
            }
        except Exception as exc:
            return {"error": str(exc), "celsius": None}

    def _collect_ram(self) -> dict:
        """Heap memory usage. Triggers a GC cycle first for accuracy."""
        gc.collect()
        free  = gc.mem_free()
        alloc = gc.mem_alloc()
        total = free + alloc
        return {
            "total_kb": _to_kb(total),
            "used_kb":  _to_kb(alloc),
            "free_kb":  _to_kb(free),
            "used_pct": round(alloc / total * 100, 1) if total else 0.0,
        }

    def _collect_flash(self) -> dict:
        """Internal flash usage (root VFS partition)."""
        return _statvfs("/")

    def _collect_sd(self) -> dict:
        """SD card usage at ``self.sd_mount``."""
        return _statvfs(self.sd_mount)

    def _collect_uptime(self) -> dict:
        """
        System uptime since last reset.

        Note: ``time.ticks_ms()`` wraps at ~49 days. For long-running
        deployments, consider an RTC-backed counter instead.
        """
        ticks_ms = time.ticks_ms()
        total_s  = ticks_ms // 1000
        days     =  total_s // 86400
        hours    = (total_s % 86400) // 3600
        minutes  = (total_s % 3600)  // 60
        seconds  =  total_s % 60
        return {
            "total_seconds": total_s,
            "ticks_ms":      ticks_ms,
            "formatted":     "{:d}d {:02d}h {:02d}m {:02d}s".format(
                                 days, hours, minutes, seconds),
        }

    def _collect_reset_cause(self) -> str:
        """Human-readable label for the last reset cause."""
        try:
            code = machine.reset_cause()
            return self._RESET_CAUSES.get(code, "unknown({})".format(code))
        except Exception:
            return "unknown"

    def _collect_network(self) -> dict:
        """Wi-Fi STA and AP interface status."""
        if not _HAS_NETWORK:
            return {"available": False}

        result: dict = {"available": True}

        # Station interface
        try:
            sta      = _network.WLAN(_network.STA_IF)
            sta_info = {
                "active":    sta.active(),
                "connected": sta.isconnected(),
            }
            if sta.isconnected():
                ip, mask, gw, dns = sta.ifconfig()
                sta_info["ip"]      = ip
                sta_info["netmask"] = mask
                sta_info["gateway"] = gw
                sta_info["dns"]     = dns
            result["sta"] = sta_info
        except Exception as exc:
            result["sta"] = {"error": str(exc)}

        # Access-point interface
        try:
            ap      = _network.WLAN(_network.AP_IF)
            ap_info = {"active": ap.active()}
            if ap.active():
                ap_info["ip"] = ap.ifconfig()[0]
            result["ap"] = ap_info
        except Exception as exc:
            result["ap"] = {"error": str(exc)}

        return result

    # ── Public API ────────────────────────────────────────────────────────────

    def collect(self) -> dict:
        """
        Gather all statistics and return them as a plain ``dict``.

        Returns
        -------
        dict
            Snapshot with keys: ``timestamp_ms``, ``system``, ``cpu``,
            ``uptime``, ``reset_cause``, ``temperature``, ``ram``,
            ``flash_internal``, ``sd_card``, ``network``.
        """
        gc.collect()
        return {
            "timestamp_ms":   time.ticks_ms(),
            "system":         self._collect_system(),
            "cpu":            self._collect_cpu(),
            "uptime":         self._collect_uptime(),
            "reset_cause":    self._collect_reset_cause(),
            "temperature":    self._collect_temperature(),
            "ram":            self._collect_ram(),
            "flash_internal": self._collect_flash(),
            "sd_card":        self._collect_sd(),
            "network":        self._collect_network(),
        }

    def to_json(self) -> str:
        """
        Collect statistics and return a compact JSON string.

        Returns
        -------
        str
            JSON-serialized statistics snapshot.
        """
        return json.dumps(self.collect())

    def report(self) -> None:
        """
        Print a human-readable statistics report to stdout.
        Intended for interactive REPL debugging.
        """
        data = self.collect()
        sep  = "=" * 44

        print(sep)
        print("  ESP32-S3  -  System Statistics Report")
        print(sep)

        cpu = data["cpu"]
        print("  CPU          : {} MHz".format(cpu.get("freq_mhz", "?")))
        print("  Uptime       : {}".format(data["uptime"]["formatted"]))
        print("  Last reset   : {}".format(data["reset_cause"]))

        temp = data["temperature"]
        if temp.get("celsius") is not None:
            print("  Temperature  : {} C  /  {} F".format(
                temp["celsius"], temp.get("fahrenheit", "?")))
        else:
            print("  Temperature  : unavailable ({})".format(
                temp.get("error", temp.get("source", "?"))))

        print("")

        ram = data["ram"]
        print("  RAM total    : {} KB".format(ram["total_kb"]))
        print("  RAM used     : {} KB  ({}%)".format(ram["used_kb"], ram["used_pct"]))
        print("  RAM free     : {} KB".format(ram["free_kb"]))

        print("")

        fl = data["flash_internal"]
        if fl["mounted"]:
            print("  Flash (int.) : {} MB total  {} MB used  {} MB free".format(
                fl["total_mb"], fl["used_mb"], fl["free_mb"]))
        else:
            print("  Flash (int.) : error - {}".format(fl.get("error")))

        sd = data["sd_card"]
        if sd["mounted"]:
            print("  SD card      : {} MB total  {} MB used  {} MB free  ({}%)".format(
                sd["total_mb"], sd["used_mb"], sd["free_mb"], sd["used_pct"]))
        else:
            print("  SD card      : not mounted at {}  - {}".format(
                sd["path"], sd.get("error", "unknown error")))

        print("")

        net = data["network"]
        if not net.get("available"):
            print("  Network      : module unavailable")
        else:
            sta = net.get("sta", {})
            if sta.get("connected"):
                print("  Wi-Fi STA    : connected  IP={}  GW={}".format(
                    sta.get("ip", "?"), sta.get("gateway", "?")))
            elif sta.get("active"):
                print("  Wi-Fi STA    : active, not connected")
            else:
                print("  Wi-Fi STA    : inactive")

            ap = net.get("ap", {})
            if ap.get("active"):
                print("  Wi-Fi AP     : active  IP={}".format(ap.get("ip", "?")))
            else:
                print("  Wi-Fi AP     : inactive")

        print(sep)


# ── Module entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    stats = SystemStats(sd_mount="/sd")
    stats.report()
    print("")
    print("-- Compact JSON --")
    print(stats.to_json())
