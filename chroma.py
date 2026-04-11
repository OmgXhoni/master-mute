"""Razer Chroma SDK REST API wrapper — CHROMA_CUSTOM for mute/deafen states."""

import logging
import threading
import time

import requests

log = logging.getLogger(__name__)

CHROMA_BASE = "http://localhost:54235/razer/chromasdk"
HEARTBEAT_INTERVAL = 10  # seconds
GRID_ROWS = 6
GRID_COLS = 22
EFFECT_REFRESH_INTERVAL = 0.2  # seconds between re-sends to hold effect


# Standard Razer Chroma 6x22 grid key positions.
KEY_GRID_MAP = {
    # Row 0: Esc, F1-F12, PrtSc, ScrLk, Pause, media keys
    "esc": (0, 1), "f1": (0, 3), "f2": (0, 4), "f3": (0, 5), "f4": (0, 6),
    "f5": (0, 7), "f6": (0, 8), "f7": (0, 9), "f8": (0, 10), "f9": (0, 11),
    "f10": (0, 12), "f11": (0, 13), "f12": (0, 14),
    "print screen": (0, 15), "scroll lock": (0, 16), "pause": (0, 17),
    # Row 1
    "`": (1, 1), "1": (1, 2), "2": (1, 3), "3": (1, 4), "4": (1, 5),
    "5": (1, 6), "6": (1, 7), "7": (1, 8), "8": (1, 9), "9": (1, 10),
    "0": (1, 11), "-": (1, 12), "=": (1, 13), "backspace": (1, 14),
    "insert": (1, 15), "home": (1, 16), "page up": (1, 17),
    "num lock": (1, 18), "num /": (1, 19), "num *": (1, 20), "num -": (1, 21),
    # Row 2
    "tab": (2, 1), "q": (2, 2), "w": (2, 3), "e": (2, 4), "r": (2, 5),
    "t": (2, 6), "y": (2, 7), "u": (2, 8), "i": (2, 9), "o": (2, 10),
    "p": (2, 11), "[": (2, 12), "]": (2, 13), "\\": (2, 14),
    "delete": (2, 15), "end": (2, 16), "page down": (2, 17),
    "num 7": (2, 18), "num 8": (2, 19), "num 9": (2, 20), "num +": (2, 21),
    # Row 3
    "caps lock": (3, 1), "a": (3, 2), "s": (3, 3), "d": (3, 4), "f": (3, 5),
    "g": (3, 6), "h": (3, 7), "j": (3, 8), "k": (3, 9), "l": (3, 10),
    ";": (3, 11), "'": (3, 12), "enter": (3, 14),
    "num 4": (3, 18), "num 5": (3, 19), "num 6": (3, 20),
    # Row 4
    "left shift": (4, 1), "shift": (4, 1),
    "z": (4, 2), "x": (4, 3), "c": (4, 4), "v": (4, 5), "b": (4, 6),
    "n": (4, 7), "m": (4, 8), ",": (4, 9), ".": (4, 10), "/": (4, 11),
    "right shift": (4, 14), "up": (4, 16),
    "num 1": (4, 18), "num 2": (4, 19), "num 3": (4, 20), "num enter": (4, 21),
    # Row 5
    "left ctrl": (5, 1), "ctrl": (5, 1), "left windows": (5, 2),
    "left alt": (5, 3), "alt": (5, 3), "space": (5, 7),
    "right alt": (5, 11), "right windows": (5, 12),
    "menu": (5, 13), "right ctrl": (5, 14),
    "left": (5, 15), "down": (5, 16), "right": (5, 17),
    "num 0": (5, 18), "num .": (5, 20),
}


def resolve_key_position(key_name: str | None,
                         override_row: int | None,
                         override_col: int | None) -> tuple[int, int] | None:
    if override_row is not None and override_col is not None:
        return (override_row, override_col)
    if key_name:
        pos = KEY_GRID_MAP.get(key_name.lower())
        if pos:
            return pos
    return None


def hex_to_bgr(hex_color: str) -> int:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (b << 16) | (g << 8) | r


class ChromaSession:
    """Manages a Chroma SDK session for per-key keyboard effects."""

    def __init__(self, unmute_color_hex: str, mute_color_hex: str,
                 deafen_color_hex: str,
                 mute_key_name: str | None = None,
                 mute_button_row: int | None = None,
                 mute_button_col: int | None = None,
                 pulse_interval_ms: int = 500):
        self.unmute_color_bgr = hex_to_bgr(unmute_color_hex)
        self.mute_color_bgr = hex_to_bgr(mute_color_hex)
        self.deafen_color_bgr = hex_to_bgr(deafen_color_hex)
        self.mute_key_pos = resolve_key_position(
            mute_key_name, mute_button_row, mute_button_col
        )
        self.pulse_interval = pulse_interval_ms / 1000.0
        self.session_uri = None
        self.connected = False
        self._heartbeat_thread = None
        self._heartbeat_stop = threading.Event()
        self._effect_thread = None
        self._effect_stop = threading.Event()

    def connect(self) -> bool:
        payload = {
            "title": "MasterMute",
            "description": "Mic mute LED controller",
            "author": {"name": "MasterMute", "contact": "https://github.com"},
            "device_supported": ["keyboard"],
            "category": "application",
        }
        try:
            resp = requests.post(CHROMA_BASE, json=payload, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            self.session_uri = data.get("uri")
            if not self.session_uri:
                log.warning("Chroma SDK returned no session URI: %s", data)
                return False
            self.connected = True
            time.sleep(0.5)
            self._start_heartbeat()
            log.info("Chroma SDK session established: %s", self.session_uri)
            return True
        except (requests.ConnectionError, requests.Timeout) as e:
            log.warning("Cannot connect to Chroma SDK: %s", e)
            return False
        except Exception as e:
            log.warning("Chroma SDK init failed: %s", e)
            return False

    def _start_heartbeat(self):
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._heartbeat_thread.start()

    def _heartbeat_loop(self):
        while not self._heartbeat_stop.wait(HEARTBEAT_INTERVAL):
            if not self.connected or not self.session_uri:
                break
            try:
                requests.put(f"{self.session_uri}/heartbeat", timeout=5)
            except Exception as e:
                log.warning("Heartbeat failed: %s", e)

    def _send_grid(self, grid: list) -> bool:
        """Send a CHROMA_CUSTOM effect (6x22 grid) to the keyboard."""
        if not self.connected or not self.session_uri:
            return False
        try:
            resp = requests.put(
                f"{self.session_uri}/keyboard",
                json={"effect": "CHROMA_CUSTOM", "param": grid},
                timeout=5,
            )
            return resp.status_code == 200
        except Exception as e:
            log.warning("Failed to send grid effect: %s", e)
            return False

    def _build_mute_grid(self) -> list:
        """All keys red."""
        return [[self.mute_color_bgr] * GRID_COLS for _ in range(GRID_ROWS)]

    def _build_deafen_grid(self) -> list:
        """All keys black, mute button red (if position known)."""
        grid = [[0] * GRID_COLS for _ in range(GRID_ROWS)]
        if self.mute_key_pos:
            row, col = self.mute_key_pos
            grid[row][col] = self.deafen_color_bgr
        return grid

    def _ensure_connected(self) -> bool:
        if not self.connected:
            return self.connect()
        return True

    def _stop_effect(self):
        if self._effect_thread and self._effect_thread.is_alive():
            self._effect_stop.set()
            self._effect_thread.join(timeout=2)
            self._effect_thread = None

    def _effect_loop(self, grid: list):
        """Repeatedly send a grid to hold the effect against Synapse."""
        while not self._effect_stop.is_set():
            self._send_grid(grid)
            self._effect_stop.wait(EFFECT_REFRESH_INTERVAL)

    def set_solid(self) -> None:
        """Set the entire keyboard to solid mute color."""
        self._stop_effect()
        if not self._ensure_connected():
            return
        grid = self._build_mute_grid()
        self._effect_stop.clear()
        self._effect_thread = threading.Thread(
            target=self._effect_loop, args=(grid,), daemon=True
        )
        self._effect_thread.start()
        log.info("Keyboard set to solid mute color (all red)")

    def set_deafen(self) -> None:
        """Blackout keyboard with mute button solid red."""
        self._stop_effect()
        if not self._ensure_connected():
            return
        grid = self._build_deafen_grid()
        self._effect_stop.clear()
        self._effect_thread = threading.Thread(
            target=self._effect_loop, args=(grid,), daemon=True
        )
        self._effect_thread.start()
        log.info("Keyboard set to deafen (blackout + mute button red)")

    def clear(self) -> None:
        """Delete session so Synapse regains keyboard at full brightness.
        Reconnect is deferred to next mute/deafen via _ensure_connected()."""
        self._stop_effect()
        self.release()
        log.info("Session released — Synapse has full control")

    def release(self) -> None:
        """Full teardown: stop effects, kill heartbeat, delete session."""
        self._stop_effect()
        self._heartbeat_stop.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
            self._heartbeat_thread = None
        if self.connected and self.session_uri:
            try:
                requests.delete(self.session_uri, timeout=5)
                log.debug("Chroma session deleted")
            except Exception as e:
                log.warning("Failed to delete Chroma session: %s", e)
        self.connected = False
        self.session_uri = None

    def disconnect(self) -> None:
        """Clean up: stop threads and delete the session."""
        self.release()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    session = ChromaSession(
        mute_color_hex="#FF0000", deafen_color_hex="#FF0000",
        unmute_color_hex="#00FF00",
        mute_key_name="f7",
    )

    if not session.connect():
        print("Could not connect to Chroma SDK.")
        exit(1)

    print("Test 1: Solid red (mute) — all keys red for 4 seconds...")
    session.set_solid()
    time.sleep(4)

    print("Test 2: Deafen — blackout + mute button red for 4 seconds...")
    session.set_deafen()
    time.sleep(4)

    print("Releasing back to Synapse profile...")
    session.release()
    time.sleep(1)
    session.disconnect()
    print("Done.")
