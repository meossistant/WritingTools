"""
Unified global hotkey listener supporting both simultaneous key combinations
(e.g., `ctrl+space`, `ctrl+shift+p`) and sequential double-tap modifier hotkeys
(e.g., `ctrl+ctrl`, `alt+alt`, `shift+shift`, `cmd+cmd`) — Issue #248.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, Optional

from pynput import keyboard as pykeyboard

_MODIFIER_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "ctrl_l": "ctrl",
    "ctrl_r": "ctrl",
    "alt": "alt",
    "alt_l": "alt",
    "alt_r": "alt",
    "alt_gr": "alt",
    "shift": "shift",
    "shift_l": "shift",
    "shift_r": "shift",
    "cmd": "cmd",
    "cmd_l": "cmd",
    "cmd_r": "cmd",
    "super": "cmd",
    "win": "cmd",
    "meta": "cmd",
}


def is_double_tap_hotkey(hotkey_str: str) -> Optional[str]:
    """
    If `hotkey_str` specifies a double-tap modifier (e.g., `ctrl+ctrl`, `alt+alt`,
    `shift+shift`, `cmd+cmd`), return the canonical modifier name (`'ctrl'`, `'alt'`,
    `'shift'`, `'cmd'`). Otherwise return `None`.
    """
    parts = [p.strip().lower() for p in (hotkey_str or "").split("+") if p.strip()]
    if len(parts) != 2:
        return None
    m1 = _MODIFIER_ALIASES.get(parts[0])
    m2 = _MODIFIER_ALIASES.get(parts[1])
    if m1 and m1 == m2:
        return m1
    return None


def to_pynput_hotkey(hotkey_str: str) -> str:
    """
    Convert a user-facing combo hotkey string (`'ctrl+j'`, `'Ctrl + Shift + P'`) to
    pynput's `<ctrl>+j` / `<ctrl>+<shift>+p` format.
    """
    parts = [t.strip().lower() for t in (hotkey_str or "").split("+") if t.strip()]
    return "+".join(t if len(t) <= 1 else f"<{t}>" for t in parts)


def validate_hotkey(hotkey_str: str) -> tuple[bool, Optional[str]]:
    """
    Validate either a double-tap modifier hotkey (`ctrl+ctrl`) or a standard
    pynput combo hotkey (`ctrl+space`). Returns `(is_valid, error_message)`.
    """
    cleaned = (hotkey_str or "").strip()
    if not cleaned:
        return True, None
    if is_double_tap_hotkey(cleaned) is not None:
        return True, None
    try:
        parsed = to_pynput_hotkey(cleaned)
        pykeyboard.HotKey.parse(parsed)
        return True, None
    except Exception as e:
        return False, (
            f"'{cleaned}' is not a valid hotkey.\n\n"
            f"Use '+' between keys (e.g. ctrl+space, ctrl+shift+p) or a double-tap "
            f"modifier (ctrl+ctrl, alt+alt, shift+shift).\n({e})"
        )


def canonical_modifier_for_key(key) -> Optional[str]:
    """Map a `pynput.keyboard.Key` (or canonical string in tests) to `'ctrl'|'alt'|'shift'|'cmd'`."""
    if isinstance(key, str):
        return _MODIFIER_ALIASES.get(key.strip().lower())
    name = getattr(key, "name", None)
    if name:
        return _MODIFIER_ALIASES.get(name.lower())
    return None


class DoubleTapTracker:
    """
    Zero-false-positive double-tap modifier state machine (#248).

    Fires on a clean `press(M) -> release(M) -> press(M) -> release(M)` sequence
    within `interval` seconds. Any intervening key press (such as `Ctrl+C` followed
    rapidly by `Ctrl+V`) or key hold longer than `hold_threshold` cancels the sequence.
    """

    def __init__(
        self,
        callbacks: Dict[str, Callable[[], None]],
        interval: float = 0.40,
        hold_threshold: float = 0.35,
    ):
        self.callbacks = dict(callbacks)
        self.interval = interval
        self.hold_threshold = hold_threshold

        self._held_mod: Optional[str] = None
        self._press_time: float = 0.0
        self._second_tap_mod: Optional[str] = None
        self._interrupted: bool = False
        self._last_tap_mod: Optional[str] = None
        self._last_tap_time: float = 0.0

    def reset(self):
        self._held_mod = None
        self._press_time = 0.0
        self._second_tap_mod = None
        self._interrupted = False
        self._last_tap_mod = None
        self._last_tap_time = 0.0

    def on_press(self, key, now: Optional[float] = None):
        ts = time.monotonic() if now is None else now
        mod = canonical_modifier_for_key(key)

        if mod is None or mod not in self.callbacks:
            # Any non-registered key interrupts an in-progress tap sequence
            self._interrupted = True
            self._last_tap_mod = None
            self._second_tap_mod = None
            return

        # Ignore OS auto-repeat events while the same modifier is already held
        if self._held_mod == mod:
            return

        # Another modifier was pressed while one was already held -> chord, not tap
        if self._held_mod is not None and self._held_mod != mod:
            self._interrupted = True
            self._last_tap_mod = None
            self._second_tap_mod = None
            return

        self._held_mod = mod
        self._press_time = ts
        self._interrupted = False

        if self._last_tap_mod == mod and (ts - self._last_tap_time) <= self.interval:
            self._second_tap_mod = mod
        else:
            self._second_tap_mod = None

    def on_release(self, key, now: Optional[float] = None):
        ts = time.monotonic() if now is None else now
        mod = canonical_modifier_for_key(key)

        if mod is None or mod != self._held_mod:
            return

        held_duration = ts - self._press_time
        was_interrupted = self._interrupted
        was_second = self._second_tap_mod == mod

        self._held_mod = None
        self._second_tap_mod = None
        self._interrupted = False

        if was_interrupted or held_duration > self.hold_threshold:
            self._last_tap_mod = None
            return

        if was_second:
            self._last_tap_mod = None
            cb = self.callbacks.get(mod)
            if cb is not None:
                try:
                    cb()
                except Exception as e:
                    logging.error(f"Error in double-tap callback for {mod}: {e}")
        else:
            self._last_tap_mod = mod
            self._last_tap_time = ts


class UnifiedHotkeyListener:
    """
    Single `pynput.keyboard.Listener` driving both standard combo hotkeys and
    double-tap modifier hotkeys simultaneously.
    """

    def __init__(
        self,
        combo_map: Dict[str, Callable[[], None]],
        double_tap_map: Dict[str, Callable[[], None]],
        double_tap_interval: float = 0.40,
    ):
        self._hotkeys = [
            pykeyboard.HotKey(pykeyboard.HotKey.parse(combo), cb)
            for combo, cb in combo_map.items()
        ]
        self._double_tap = (
            DoubleTapTracker(double_tap_map, interval=double_tap_interval)
            if double_tap_map
            else None
        )
        self._listener: Optional[pykeyboard.Listener] = None

    def _on_press(self, key):
        canonical = self._listener.canonical(key) if self._listener else key
        for hk in self._hotkeys:
            try:
                hk.press(canonical)
            except Exception as e:
                logging.debug(f"HotKey press error: {e}")
        if self._double_tap is not None:
            self._double_tap.on_press(key)

    def _on_release(self, key):
        canonical = self._listener.canonical(key) if self._listener else key
        for hk in self._hotkeys:
            try:
                hk.release(canonical)
            except Exception as e:
                logging.debug(f"HotKey release error: {e}")
        if self._double_tap is not None:
            self._double_tap.on_release(key)

    def start(self):
        self._listener = pykeyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

    def stop(self):
        if self._listener is not None:
            try:
                self._listener.stop()
            finally:
                self._listener = None
