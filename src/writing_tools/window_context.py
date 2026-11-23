"""
Cross-platform active window inspection, focus verification (#23),
per-application copy/paste shortcut resolution (#99), and fullscreen /
application blacklist detection (#113).

Zero external dependencies — uses Win32 `ctypes` on Windows and `xprop` on
Linux X11, degrading gracefully to `None` when headless or unavailable.
"""

from __future__ import annotations

import ctypes
import fnmatch
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable, Optional

DEFAULT_COPY_CHORD = "ctrl+c"
DEFAULT_PASTE_CHORD = "ctrl+v"

# Common terminal emulators where Ctrl+C sends SIGINT instead of copying text (#99)
DEFAULT_TERMINAL_PATTERNS = (
    "kitty",
    "alacritty",
    "wezterm",
    "gnome-terminal",
    "konsole",
    "tilix",
    "xfce4-terminal",
    "mate-terminal",
    "lxterminal",
    "xterm",
    "uxterm",
    "foot",
    "terminator",
    "urxvt",
    "rxvt",
    "ghostty",
    "tabby",
    "hyper",
    "rio",
    "windowsterminal",
)

# Windows virtual-key codes for standard ASCII letters so non-Latin layouts work reliably
_WIN_VK_LETTERS = {chr(c): c - 32 for c in range(ord("a"), ord("z") + 1)}


@dataclass(frozen=True)
class ActiveWindowInfo:
    window_id: str
    app_name: str
    title: str
    is_fullscreen: bool = False


def _get_active_window_windows() -> Optional[ActiveWindowInfo]:
    """Query the active foreground window on Windows using Win32 ctypes."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        # Window title
        length = user32.GetWindowTextLengthW(hwnd)
        title_buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buf, length + 1)
        title = title_buf.value or ""

        # Process executable name
        app_name = ""
        pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value:
            # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(0x1000, False, pid.value)
            if handle:
                try:
                    buf_size = ctypes.c_ulong(512)
                    path_buf = ctypes.create_unicode_buffer(512)
                    if kernel32.QueryFullProcessImageNameW(handle, 0, path_buf, ctypes.byref(buf_size)):
                        app_name = os.path.splitext(os.path.basename(path_buf.value))[0]
                finally:
                    kernel32.CloseHandle(handle)

        # Fullscreen heuristic: window rect covers the entire monitor rect
        is_fullscreen = False
        try:
            class _RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            class _MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", _RECT),
                    ("rcWork", _RECT),
                    ("dwFlags", ctypes.c_ulong),
                ]

            rect = _RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                # MONITOR_DEFAULTTONEAREST = 2
                monitor = user32.MonitorFromWindow(hwnd, 2)
                if monitor:
                    mi = _MONITORINFO()
                    mi.cbSize = ctypes.sizeof(_MONITORINFO)
                    if user32.GetMonitorInfoW(monitor, ctypes.byref(mi)):
                        mon = mi.rcMonitor
                        is_fullscreen = (
                            rect.left <= mon.left
                            and rect.top <= mon.top
                            and rect.right >= mon.right
                            and rect.bottom >= mon.bottom
                            and (rect.right - rect.left) >= (mon.right - mon.left)
                            and (rect.bottom - rect.top) >= (mon.bottom - mon.top)
                        )
        except Exception:
            is_fullscreen = False

        return ActiveWindowInfo(
            window_id=hex(hwnd),
            app_name=app_name,
            title=title,
            is_fullscreen=is_fullscreen,
        )
    except Exception as e:
        logging.debug(f"Windows active window inspection failed: {e}")
        return None


def _get_active_window_x11() -> Optional[ActiveWindowInfo]:
    """Query the active window on Linux X11 via `xprop` (with strict short timeout)."""
    if not os.environ.get("DISPLAY"):
        return None
    try:
        root_out = subprocess.check_output(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.35,
        )
        match = re.search(r"0x[0-9a-fA-F]+", root_out)
        if not match or match.group(0) == "0x0":
            return None
        win_id = match.group(0).lower()

        props_out = subprocess.check_output(
            ["xprop", "-id", win_id, "WM_CLASS", "_NET_WM_NAME", "WM_NAME", "_NET_WM_STATE"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.35,
        )

        app_name = ""
        title = ""
        is_fullscreen = "_NET_WM_STATE_FULLSCREEN" in props_out

        for line in props_out.splitlines():
            if line.startswith("WM_CLASS"):
                quoted = re.findall(r'"([^"]+)"', line)
                if quoted:
                    app_name = quoted[-1]
            elif line.startswith("_NET_WM_NAME") and not title:
                m = re.search(r'=\s*"(.*)"', line)
                if m:
                    title = m.group(1)
            elif line.startswith("WM_NAME") and not title:
                m = re.search(r'=\s*"(.*)"', line)
                if m:
                    title = m.group(1)

        return ActiveWindowInfo(
            window_id=win_id,
            app_name=app_name,
            title=title,
            is_fullscreen=is_fullscreen,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError) as e:
        logging.debug(f"X11 active window inspection unavailable: {e}")
        return None


def get_active_window() -> Optional[ActiveWindowInfo]:
    """Return information about the currently focused desktop window, or None if unavailable."""
    if sys.platform.startswith("win32"):
        return _get_active_window_windows()
    if sys.platform.startswith("linux"):
        return _get_active_window_x11()
    return None


def parse_blacklist(raw: str | Iterable[str] | None) -> list[str]:
    """Parse a comma/newline-separated blacklist string or list into normalized patterns."""
    if not raw:
        return []
    if isinstance(raw, str):
        tokens = re.split(r"[\n,;]+", raw)
    else:
        tokens = [str(x) for x in raw]
    return [t.strip().lower() for t in tokens if t and t.strip()]


def _matches_pattern(info: ActiveWindowInfo, pattern: str) -> bool:
    pat = (pattern or "").strip().lower()
    if not pat:
        return False
    haystacks = [
        (info.app_name or "").lower(),
        (info.title or "").lower(),
    ]
    has_wildcard = any(ch in pat for ch in "*?[]")
    for text in haystacks:
        if not text:
            continue
        if has_wildcard:
            if fnmatch.fnmatch(text, pat):
                return True
        elif pat in text:
            return True
    return False


def is_window_blacklisted(
    info: Optional[ActiveWindowInfo],
    blacklist_patterns: str | Iterable[str] | None,
) -> bool:
    """Return True if `info` matches any configured blacklist pattern (#113)."""
    if info is None:
        return False
    for pat in parse_blacklist(blacklist_patterns):
        if _matches_pattern(info, pat):
            return True
    return False


def parse_app_shortcut_rules(raw: str | dict | None) -> dict[str, tuple[str, str]]:
    """
    Parse per-application copy/paste keybinding rules (#99).

    Accepts either:
    - Multiline string: `kitty=ctrl+shift+c,ctrl+shift+v`
      (if only one chord is given, e.g. `emacs=alt+w`, paste defaults to `ctrl+v`)
    - Dict mapping pattern -> `[copy, paste]` or `{"copy": ..., "paste": ...}`.
    """
    rules: dict[str, tuple[str, str]] = {}
    if not raw:
        return rules

    if isinstance(raw, dict):
        for pat, val in raw.items():
            key = str(pat).strip().lower()
            if not key:
                continue
            if isinstance(val, dict):
                copy_c = str(val.get("copy") or DEFAULT_COPY_CHORD).strip().lower()
                paste_c = str(val.get("paste") or DEFAULT_PASTE_CHORD).strip().lower()
                rules[key] = (copy_c, paste_c)
            elif isinstance(val, (list, tuple)) and len(val) >= 1:
                copy_c = str(val[0] or DEFAULT_COPY_CHORD).strip().lower()
                paste_c = str(val[1] if len(val) > 1 and val[1] else DEFAULT_PASTE_CHORD).strip().lower()
                rules[key] = (copy_c, paste_c)
        return rules

    for line in str(raw).splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#") or "=" not in cleaned:
            continue
        pat, chords = cleaned.split("=", 1)
        pat = pat.strip().lower()
        if not pat:
            continue
        parts = [p.strip().lower() for p in chords.split(",") if p.strip()]
        if not parts:
            continue
        copy_c = parts[0]
        paste_c = parts[1] if len(parts) > 1 else DEFAULT_PASTE_CHORD
        rules[pat] = (copy_c, paste_c)
    return rules


def format_app_shortcut_rules(rules: dict[str, tuple[str, str]]) -> str:
    """Serialize parsed shortcut rules back to a clean multiline text representation."""
    return "\n".join(f"{pat}={copy_c},{paste_c}" for pat, (copy_c, paste_c) in rules.items())


def resolve_copy_paste_chords(
    info: Optional[ActiveWindowInfo],
    custom_rules: str | dict | None = None,
    enable_terminal_defaults: bool = True,
) -> tuple[str, str]:
    """
    Resolve `(copy_chord, paste_chord)` for the focused window (#99).
    User-defined rules take precedence over built-in terminal defaults.
    """
    if info is None:
        return DEFAULT_COPY_CHORD, DEFAULT_PASTE_CHORD

    parsed_custom = parse_app_shortcut_rules(custom_rules)
    for pat, chords in parsed_custom.items():
        if _matches_pattern(info, pat):
            return chords

    if enable_terminal_defaults:
        for term_pat in DEFAULT_TERMINAL_PATTERNS:
            if _matches_pattern(info, term_pat):
                return "ctrl+shift+c", "ctrl+shift+v"

    return DEFAULT_COPY_CHORD, DEFAULT_PASTE_CHORD


def parse_chord(chord: str) -> tuple[list[str], str]:
    """
    Parse a chord like `'ctrl+shift+c'` into `(modifiers, main_key)`.
    Normalizes aliases (`control` -> `ctrl`, `super`/`win` -> `cmd`).
    """
    alias_map = {
        "control": "ctrl",
        "super": "cmd",
        "win": "cmd",
        "meta": "cmd",
    }
    mod_names = {"ctrl", "shift", "alt", "cmd"}
    tokens = [alias_map.get(t.strip().lower(), t.strip().lower()) for t in (chord or "").split("+") if t.strip()]
    if not tokens:
        return ["ctrl"], "c"
    modifiers = [t for t in tokens[:-1] if t in mod_names]
    main_key = tokens[-1]
    return modifiers, main_key


def windows_vk_for_key(key_name: str) -> Optional[int]:
    """Return Windows virtual key code for ASCII letters so non-Latin layouts stay accurate."""
    return _WIN_VK_LETTERS.get((key_name or "").lower())
