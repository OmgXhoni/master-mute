"""Global hotkey listener with short/long press detection and Discord hotkey simulation.
Uses keyboard lib for both listening and Discord hotkey sending."""

import logging
import threading
import time
from typing import Callable, Optional

import keyboard

log = logging.getLogger(__name__)


class HotkeyListener:
    """Listens for a hotkey and distinguishes short vs long press."""

    def __init__(
        self,
        listen_hotkey: str,
        long_press_ms: int,
        on_short_press: Callable,
        on_long_press: Callable,
    ):
        self.listen_hotkey = listen_hotkey
        self.long_press_threshold = long_press_ms / 1000.0
        self.on_short_press = on_short_press
        self.on_long_press = on_long_press
        self._key_down_time: Optional[float] = None
        self._long_press_fired = False
        self._timer: Optional[threading.Timer] = None
        self._hook = None
        self._paused = False
        self._trigger_key = self._parse_trigger_key(listen_hotkey)
        self._modifier_keys = self._parse_modifiers(listen_hotkey)

    @property
    def paused(self) -> bool:
        return self._paused

    def pause(self):
        self._paused = True
        log.info("Listener paused")

    def resume(self):
        self._paused = False
        log.info("Listener resumed")

    @staticmethod
    def _parse_trigger_key(hotkey: str) -> str:
        parts = [p.strip().lower() for p in hotkey.split("+")]
        for part in parts:
            if part not in ("ctrl", "shift", "alt", "left ctrl", "right ctrl",
                            "left shift", "right shift", "left alt", "right alt"):
                return part
        return parts[-1]

    @staticmethod
    def _parse_modifiers(hotkey: str) -> set:
        parts = [p.strip().lower() for p in hotkey.split("+")]
        mods = set()
        for part in parts:
            if "ctrl" in part:
                mods.add("ctrl")
            elif "shift" in part:
                mods.add("shift")
            elif "alt" in part:
                mods.add("alt")
        return mods

    def _check_modifiers(self) -> bool:
        for mod in self._modifier_keys:
            if mod == "ctrl" and not (keyboard.is_pressed("left ctrl") or keyboard.is_pressed("right ctrl")):
                return False
            if mod == "shift" and not (keyboard.is_pressed("left shift") or keyboard.is_pressed("right shift")):
                return False
            if mod == "alt" and not (keyboard.is_pressed("left alt") or keyboard.is_pressed("right alt")):
                return False
        return True

    def _on_long_press_timer(self):
        self._long_press_fired = True
        log.info("Long press detected (held >= %.0fms)", self.long_press_threshold * 1000)
        self.on_long_press()

    def _on_key_event(self, event: keyboard.KeyboardEvent):
        if self._paused:
            return
        if event.name != self._trigger_key:
            return

        if event.event_type == keyboard.KEY_DOWN:
            if self._key_down_time is None and self._check_modifiers():
                self._key_down_time = time.monotonic()
                self._long_press_fired = False
                self._timer = threading.Timer(
                    self.long_press_threshold, self._on_long_press_timer
                )
                self._timer.daemon = True
                self._timer.start()
                log.debug("Hotkey down, timer started")

        elif event.event_type == keyboard.KEY_UP:
            if self._key_down_time is not None:
                duration = time.monotonic() - self._key_down_time
                self._key_down_time = None
                if self._timer is not None:
                    self._timer.cancel()
                    self._timer = None
                log.debug("Key released after %.0fms", duration * 1000)
                if not self._long_press_fired:
                    log.info("Short press detected (%.0fms)", duration * 1000)
                    self.on_short_press()

    def start(self):
        self._hook = keyboard.hook(self._on_key_event, suppress=False)
        log.info("Hotkey listener started for '%s'", self.listen_hotkey)

    def stop(self):
        if self._timer is not None:
            self._timer.cancel()
        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
        log.info("Hotkey listener stopped")


def send_discord_hotkey(hotkey: str) -> None:
    try:
        keyboard.send(hotkey)
        log.info("Sent Discord hotkey: %s", hotkey)
    except Exception as e:
        log.warning("Failed to send Discord hotkey '%s': %s", hotkey, e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Press Ctrl+Shift+Alt+F8 to test (short or long press).")
    print("Press Esc to quit.\n")

    listener = HotkeyListener(
        listen_hotkey="ctrl+shift+alt+f8",
        long_press_ms=300,
        on_short_press=lambda: print(">>> SHORT PRESS"),
        on_long_press=lambda: print(">>> LONG PRESS"),
    )
    listener.start()
    keyboard.wait("esc")
    listener.stop()
    print("Done.")
