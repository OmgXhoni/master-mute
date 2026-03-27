"""MasterMute — intercepts Ctrl+Shift+Alt+F8 (rebound mute button) and turns
it into a smart mic mute / deafen toggle with whole-keyboard LED feedback."""

import atexit
import enum
import logging
import os
import signal
import sys
import tomllib
import threading

import comtypes
from PIL import Image, ImageDraw
import pystray

import audio
import chroma
import hotkey

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class State(enum.Enum):
    UNMUTED = "unmuted"
    MUTED = "muted"
    DEAFENED = "deafened"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.toml")


def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


# ---------------------------------------------------------------------------
# Tray icons — speaker-mute style matching the app icon
# ---------------------------------------------------------------------------

def _draw_speaker(draw: ImageDraw.Draw, size: int, color: str):
    """Draw a speaker silhouette (body + cone + waves)."""
    s = size
    cx, cy = s // 2, s // 2
    rect_w = int(s * 0.12)
    rect_h = int(s * 0.22)
    rect_left = cx - int(s * 0.18)
    rect_top = cy - rect_h // 2
    draw.rectangle([rect_left, rect_top, rect_left + rect_w, rect_top + rect_h],
                   fill=color)
    cone_tip_x = rect_left + rect_w
    cone_end_x = cx + int(s * 0.08)
    cone_half_h = int(s * 0.28)
    draw.polygon([
        (cone_tip_x, rect_top),
        (cone_tip_x, rect_top + rect_h),
        (cone_end_x, cy + cone_half_h),
        (cone_end_x, cy - cone_half_h),
    ], fill=color)
    wave_x = cone_end_x + int(s * 0.06)
    for radius in [int(s * 0.10), int(s * 0.18)]:
        arc_bbox = [wave_x - radius, cy - radius, wave_x + radius, cy + radius]
        width = max(2, int(s * 0.035))
        draw.arc(arc_bbox, start=-45, end=45, fill=color, width=width)


def _make_tray_icon(bg_color: str, speaker_color: str,
                    slash: bool = False, slash_color: str = "#ff2244",
                    size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = int(size * 0.04)
    draw.ellipse([margin, margin, size - margin, size - margin], fill=bg_color)
    _draw_speaker(draw, size, speaker_color)
    if slash:
        slash_w = max(2, int(size * 0.06))
        pad = int(size * 0.16)
        draw.line([pad, pad, size - pad, size - pad], fill=slash_color, width=slash_w)
    return img


ICON_UNMUTED = _make_tray_icon("#1a3d1a", "#22CC22")
ICON_MUTED = _make_tray_icon("#3d1a1a", "#CC0000", slash=True, slash_color="#FF4444")
ICON_DEAFENED = _make_tray_icon("#1a1a2e", "#CC0000", slash=True, slash_color="#FFFFFF")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class MasterMuteApp:
    def __init__(self, config: dict):
        self.config = config
        self.state = State.UNMUTED
        self._lock = threading.Lock()
        self._com_initialized_threads: set = set()
        self.tray_icon: pystray.Icon = None
        self.chroma_session: chroma.ChromaSession = None
        self.listener: hotkey.HotkeyListener = None
        self._shutting_down = False

    def _ensure_com(self):
        tid = threading.current_thread().ident
        if tid not in self._com_initialized_threads:
            comtypes.CoInitialize()
            self._com_initialized_threads.add(tid)

    # --- State transitions ---

    def _on_short_press(self):
        self._ensure_com()
        with self._lock:
            if self.state == State.UNMUTED:
                audio.set_mic_mute(True)
                hotkey.send_discord_hotkey(self.config["hotkeys"]["discord_mute"])
                self.state = State.MUTED
                self._update_led()
                self._update_tray()
                log.info("State -> MUTED")

            elif self.state == State.MUTED:
                audio.set_mic_mute(False)
                hotkey.send_discord_hotkey(self.config["hotkeys"]["discord_mute"])
                self.state = State.UNMUTED
                self._update_led()
                self._update_tray()
                log.info("State -> UNMUTED")

            elif self.state == State.DEAFENED:
                audio.set_mic_mute(False)
                audio.set_speaker_mute(False)
                hotkey.send_discord_hotkey(self.config["hotkeys"]["discord_deafen"])
                self.state = State.UNMUTED
                self._update_led()
                self._update_tray()
                log.info("State -> UNMUTED (from deafened)")

    def _on_long_press(self):
        self._ensure_com()
        with self._lock:
            if self.state != State.UNMUTED:
                log.debug("Long press ignored in %s state", self.state.value)
                return

            audio.set_mic_mute(True)
            hotkey.send_discord_hotkey(self.config["hotkeys"]["discord_deafen"])
            delay = self.config.get("timing", {}).get("deafen_audio_delay_ms", 500) / 1000.0
            import time
            time.sleep(delay)
            audio.set_speaker_mute(True)
            self.state = State.DEAFENED
            self._update_led()
            self._update_tray()
            log.info("State -> DEAFENED")

    # --- LED ---

    def _update_led(self):
        if self.chroma_session is None:
            return
        if self.state == State.UNMUTED:
            self.chroma_session.clear()
        elif self.state == State.MUTED:
            self.chroma_session.set_solid()
        elif self.state == State.DEAFENED:
            self.chroma_session.set_deafen()

    # --- Tray ---

    def _update_tray(self):
        if self.tray_icon is None:
            return
        if self.state == State.UNMUTED:
            self.tray_icon.icon = ICON_UNMUTED
            self.tray_icon.title = "MasterMute: Unmuted"
        elif self.state == State.MUTED:
            self.tray_icon.icon = ICON_MUTED
            self.tray_icon.title = "MasterMute: Muted"
        elif self.state == State.DEAFENED:
            self.tray_icon.icon = ICON_DEAFENED
            self.tray_icon.title = "MasterMute: Deafened"

    def _get_status_text(self, item=None):
        return f"Status: {self.state.value.title()}"

    def _get_pause_text(self, item=None):
        if self.listener and self.listener.paused:
            return "Resume (currently paused)"
        return "Pause (pass-through mode)"

    def _toggle_pause(self):
        if self.listener is None:
            return
        if self.listener.paused:
            self.listener.resume()
        else:
            self.listener.pause()
        self.tray_icon.update_menu()

    def _open_config(self):
        os.startfile(CONFIG_PATH)

    def _quit(self, icon=None, item=None):
        if not self._shutting_down:
            log.info("Shutting down...")
            self.shutdown()

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(self._get_status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self._get_pause_text, lambda: self._toggle_pause()),
            pystray.MenuItem("Open Config", lambda: self._open_config()),
            pystray.MenuItem("Quit", self._quit),
        )

    # --- Lifecycle ---

    def start(self):
        comtypes.CoInitialize()
        self._com_initialized_threads.add(threading.current_thread().ident)

        # Sync initial state: force everything to unmuted on startup
        # This ensures Discord, OS mic, and the script are all in sync
        audio.set_mic_mute(False)
        audio.set_speaker_mute(False)
        self.state = State.UNMUTED
        log.info("Startup: forced unmuted state for sync")

        # Chroma SDK
        chroma_cfg = self.config.get("chroma", {})
        if chroma_cfg.get("enabled", False):
            self.chroma_session = chroma.ChromaSession(
                unmute_color_hex=chroma_cfg.get("unmute_color", "#FFFFFF"),
                mute_color_hex=chroma_cfg.get("mute_color", "#FF0000"),
                deafen_color_hex=chroma_cfg.get("deafen_color", "#FF0000"),
                mute_button_row=chroma_cfg.get("mute_button_row", 0),
                mute_button_col=chroma_cfg.get("mute_button_col", 21),
                pulse_interval_ms=chroma_cfg.get("pulse_interval_ms", 500),
            )
            if self.chroma_session.connect():
                log.info("Chroma SDK connected (Synapse still in control)")
            else:
                log.warning("Chroma SDK not available — LED control disabled")
                self.chroma_session = None

        # Hotkey listener
        timing = self.config.get("timing", {})
        self.listener = hotkey.HotkeyListener(
            listen_hotkey=self.config["hotkeys"]["listen"],
            long_press_ms=timing.get("long_press_ms", 300),
            on_short_press=self._on_short_press,
            on_long_press=self._on_long_press,
        )
        self.listener.start()

        # System tray
        icon_map = {
            State.UNMUTED: ICON_UNMUTED,
            State.MUTED: ICON_MUTED,
            State.DEAFENED: ICON_DEAFENED,
        }
        self.tray_icon = pystray.Icon(
            "MasterMute",
            icon=icon_map[self.state],
            title=f"MasterMute: {self.state.value.title()}",
            menu=self._build_menu(),
        )

        atexit.register(self.shutdown)
        signal.signal(signal.SIGINT, lambda *_: self._quit())

        log.info("MasterMute running.")
        self.tray_icon.run()

    def shutdown(self):
        if self._shutting_down:
            return
        self._shutting_down = True

        if self.listener:
            self.listener.stop()
            self.listener = None

        if self.chroma_session:
            self.chroma_session.release()
            self.chroma_session.disconnect()
            self.chroma_session = None

        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None

        comtypes.CoUninitialize()
        log.info("MasterMute shut down.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

log = logging.getLogger("MasterMute")


def main():
    config = load_config()

    log_cfg = config.get("logging", {})
    log_file = log_cfg.get("file", "master-mute.log")
    log_level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), log_file)
            ),
            logging.StreamHandler(),
        ],
    )

    log.info("MasterMute starting...")
    log.info("Config loaded from %s", CONFIG_PATH)

    app = MasterMuteApp(config)
    app.start()


if __name__ == "__main__":
    main()
