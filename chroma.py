"""Razer Chroma SDK REST API wrapper — per-key CHROMA_CUSTOM for mute/deafen states."""

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


def hex_to_bgr(hex_color: str) -> int:
    """Convert '#RRGGBB' hex color to BGR integer for Chroma SDK."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (b << 16) | (g << 8) | r


class ChromaSession:
    """Manages a Chroma SDK session for per-key keyboard effects."""

    def __init__(self, mute_color_hex: str, deafen_color_hex: str,
                 mute_button_row: int = 0, mute_button_col: int = 21,
                 pulse_interval_ms: int = 500):
        self.mute_color_bgr = hex_to_bgr(mute_color_hex)
        self.deafen_color_bgr = hex_to_bgr(deafen_color_hex)
        self.mute_button_row = mute_button_row
        self.mute_button_col = mute_button_col
        self.pulse_interval = pulse_interval_ms / 1000.0
        self.session_uri = None
        self.connected = False
        self._heartbeat_thread = None
        self._heartbeat_stop = threading.Event()
        self._effect_thread = None
        self._effect_stop = threading.Event()

    def connect(self) -> bool:
        """Initialize a Chroma SDK session."""
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
        """All keys off (let Synapse handle them), mute button red."""
        grid = [[0] * GRID_COLS for _ in range(GRID_ROWS)]
        grid[self.mute_button_row][self.mute_button_col] = self.mute_color_bgr
        return grid

    def _build_deafen_grid_on(self) -> list:
        """All keys black, mute button red."""
        grid = [[0] * GRID_COLS for _ in range(GRID_ROWS)]
        grid[self.mute_button_row][self.mute_button_col] = self.deafen_color_bgr
        return grid

    def _build_deafen_grid_off(self) -> list:
        """All keys black, mute button also black."""
        return [[0] * GRID_COLS for _ in range(GRID_ROWS)]

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
        """Blackout keyboard with mute button flashing red."""
        self._stop_effect()
        if not self._ensure_connected():
            return
        self._effect_stop.clear()
        self._effect_thread = threading.Thread(
            target=self._deafen_flash_loop, daemon=True
        )
        self._effect_thread.start()
        log.info("Keyboard set to deafen (blackout + mute button flashing)")

    def _deafen_flash_loop(self):
        """Flash mute button red on/off against a blacked-out keyboard."""
        grid_on = self._build_deafen_grid_on()
        grid_off = self._build_deafen_grid_off()
        on = True
        while not self._effect_stop.is_set():
            self._send_grid(grid_on if on else grid_off)
            on = not on
            self._effect_stop.wait(self.pulse_interval)

    def release(self) -> None:
        """Release keyboard back to Synapse profile by killing the session."""
        self._stop_effect()
        self._heartbeat_stop.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
            self._heartbeat_thread = None
        if self.connected and self.session_uri:
            try:
                requests.delete(self.session_uri, timeout=5)
                log.debug("Chroma session deleted — keyboard released to Synapse")
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
        mute_color_hex="#AD0014", deafen_color_hex="#AD0014",
        mute_button_row=0, mute_button_col=21,
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
