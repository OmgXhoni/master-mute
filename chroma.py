"""Razer Chroma SDK REST API wrapper — CHROMA_STATIC for mute/deafen states."""

import logging
import threading
import time

import requests

log = logging.getLogger(__name__)

CHROMA_BASE = "http://localhost:54235/razer/chromasdk"
HEARTBEAT_INTERVAL = 10  # seconds


def hex_to_bgr(hex_color: str) -> int:
    """Convert '#RRGGBB' hex color to BGR integer for Chroma SDK."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (b << 16) | (g << 8) | r


class ChromaSession:
    """Manages a Chroma SDK session for whole-keyboard effects."""

    def __init__(self, mute_color_hex: str, deafen_color_hex: str,
                 pulse_interval_ms: int = 500):
        self.mute_color_bgr = hex_to_bgr(mute_color_hex)
        self.deafen_color_bgr = hex_to_bgr(deafen_color_hex)
        self.pulse_interval = pulse_interval_ms / 1000.0
        self.session_uri = None
        self.connected = False
        self._heartbeat_thread = None
        self._heartbeat_stop = threading.Event()
        self._pulse_thread = None
        self._pulse_stop = threading.Event()

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
            # Small delay to let session stabilize
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

    def _send_static(self, color_bgr: int) -> bool:
        """Send a CHROMA_STATIC effect to the keyboard."""
        if not self.connected or not self.session_uri:
            return False
        try:
            resp = requests.put(
                f"{self.session_uri}/keyboard",
                json={"effect": "CHROMA_STATIC", "param": {"color": color_bgr}},
                timeout=5,
            )
            return resp.status_code == 200
        except Exception as e:
            log.warning("Failed to send static effect: %s", e)
            return False

    def _ensure_connected(self) -> bool:
        """Reconnect if session was released."""
        if not self.connected:
            return self.connect()
        return True

    def set_solid(self) -> None:
        """Set the entire keyboard to solid mute color."""
        self._stop_pulse()
        if not self._ensure_connected():
            return
        self._send_static(self.mute_color_bgr)
        log.info("Keyboard set to solid mute color")

    def set_pulsing(self) -> None:
        """Start pulsing the entire keyboard with deafen color."""
        self._stop_pulse()
        if not self._ensure_connected():
            return
        self._pulse_stop.clear()
        self._pulse_thread = threading.Thread(
            target=self._pulse_loop, daemon=True
        )
        self._pulse_thread.start()
        log.info("Started pulsing keyboard")

    def _pulse_loop(self):
        on = True
        while not self._pulse_stop.is_set():
            if on:
                self._send_static(self.deafen_color_bgr)
            else:
                self._send_static(0)  # Black / off
            on = not on
            self._pulse_stop.wait(self.pulse_interval)

    def _stop_pulse(self):
        if self._pulse_thread and self._pulse_thread.is_alive():
            self._pulse_stop.set()
            self._pulse_thread.join(timeout=2)
            self._pulse_thread = None

    def release(self) -> None:
        """Release keyboard back to Synapse profile by killing the session."""
        self._stop_pulse()
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
    print("Testing Chroma SDK — whole keyboard pulse for 6 seconds...")

    session = ChromaSession(
        mute_color_hex="#AD0014", deafen_color_hex="#AD0014", pulse_interval_ms=500
    )

    if session.connect():
        print("Solid red (mute)...")
        session.set_solid()
        time.sleep(3)
        print("Pulsing red (deafen)...")
        session.set_pulsing()
        time.sleep(4)
        print("Releasing...")
        session.release()
        time.sleep(1)
        session.disconnect()
        print("Done.")
    else:
        print("Could not connect to Chroma SDK.")
