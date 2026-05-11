"""Best-effort playback control (Linux-oriented; documented limitations)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path


def _format_profile_flag(profile_dir: Path) -> str:
    p = profile_dir.expanduser().resolve()
    return f"--user-data-dir={p}"


def find_chromium_pids_for_profile(profile_dir: Path) -> list[int]:
    """Return PIDs whose command line includes this Chromium profile path."""
    flag = _format_profile_flag(profile_dir)
    pids: list[int] = []
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["wmic", "process", "where", "name='chrome.exe' or name='chromium.exe'", "get", "processid,commandline"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=20,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return []
        for line in out.splitlines():
            if flag.lower() in line.lower():
                parts = line.split()
                if parts:
                    try:
                        pids.append(int(parts[-1]))
                    except ValueError:
                        continue
        return pids

    # POSIX: scan /proc when available
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return _pgrep_fallback(flag)

    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        cmdline = entry / "cmdline"
        try:
            raw = cmdline.read_bytes()
        except OSError:
            continue
        if not raw:
            continue
        joined = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace")
        if flag in joined or flag.replace("=", "= ") in joined:
            pids.append(int(entry.name))
    return pids or _pgrep_fallback(flag)


def _pgrep_fallback(flag: str) -> list[int]:
    try:
        out = subprocess.check_output(["pgrep", "-af", "chromium"], text=True, timeout=5)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        try:
            out = subprocess.check_output(["pgrep", "-af", "chrome"], text=True, timeout=5)
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return []
    pids: list[int] = []
    for line in out.splitlines():
        if flag in line:
            head = line.split(None, 1)[0]
            if head.isdigit():
                pids.append(int(head))
    return pids


def stop_profile_sessions(profile_dir: Path, *, signal_preference: str = "term") -> tuple[int, list[str]]:
    """
    Send SIGTERM (default) or SIGKILL to processes using this profile.

    Reliable only in the sense that it terminates those browser instances—
    it is not a negotiated pause with Audible's player.
    """
    log: list[str] = []
    pids = find_chromium_pids_for_profile(profile_dir)
    if not pids:
        log.append(
            "No matching Chromium/Chrome processes found for this user-data-dir. "
            "If playback is in another profile or app, this command cannot stop it."
        )
        return 0, log
    sig = signal.SIGKILL if signal_preference == "kill" else signal.SIGTERM
    stopped = 0
    for pid in sorted(set(pids)):
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                )
            else:
                os.kill(pid, sig)
            stopped += 1
        except ProcessLookupError:
            log.append(f"PID {pid} already exited.")
        except PermissionError:
            log.append(f"No permission to signal PID {pid} (try the same user that launched Chromium).")
    log.append(f"Signaled {stopped} process(es) for profile {profile_dir}.")
    return stopped, log


def pause_resume_mpris_hint() -> str:
    return (
        "MPRIS control is not wired in this MVP. If your desktop exposes an MPRIS player "
        "for Chromium, you can use playerctl or dbus-send; document the player name in "
        "your environment and script against it."
    )
