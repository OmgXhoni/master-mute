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

def _app_dir() -> str:
    """Return the directory where the app lives — works for both script and PyInstaller exe."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

APP_DIR = _app_dir()
CONFIG_PATH = os.path.join(APP_DIR, "config.toml")


def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


# ---------------------------------------------------------------------------
# Tray icon — loaded from mastermute.png source
# ---------------------------------------------------------------------------

def _make_circle_icon(color: str, size: int = 64) -> Image.Image:
    """Draw a solid colored circle for the tray icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, size - 4, size - 4], fill=color)
    return img

ICON_UNMUTED = _make_circle_icon("#22CC22")   # Green
ICON_MUTED = _make_circle_icon("#FF0000")     # Red
ICON_DEAFENED = _make_circle_icon("#FF8800")   # Orange


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
        self._config_mtime = 0.0
        self._config_watcher: threading.Timer = None

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
            if self.state == State.DEAFENED:
                log.debug("Long press ignored in deafened state")
                return

            if self.state == State.MUTED:
                # Already muted — just need to deafen Discord and mute speakers
                hotkey.send_discord_hotkey(self.config["hotkeys"]["discord_mute"])   # unmute Discord first
                hotkey.send_discord_hotkey(self.config["hotkeys"]["discord_deafen"]) # then deafen
                delay = self.config.get("timing", {}).get("deafen_audio_delay_ms", 500) / 1000.0
                import time
                time.sleep(delay)
                audio.set_speaker_mute(True)
                self.state = State.DEAFENED
                self._update_led()
                self._update_tray()
                log.info("State -> DEAFENED (from muted)")
                return

            # From UNMUTED
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

    def _open_keybind_setup(self):
        """Launch the keybind setup UI."""
        import subprocess
        if getattr(sys, 'frozen', False):
            setup_exe = os.path.join(APP_DIR, "KeybindSetup.exe")
            subprocess.Popen([setup_exe], cwd=APP_DIR)
        else:
            setup_py = os.path.join(APP_DIR, "setup.py")
            subprocess.Popen([sys.executable, setup_py], cwd=APP_DIR)

    def _quit(self, icon=None, item=None):
        if not self._shutting_down:
            log.info("Shutting down...")
            self.shutdown()

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(self._get_status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self._get_pause_text, lambda: self._toggle_pause()),
            pystray.MenuItem("Change Keybinds", lambda: self._open_keybind_setup()),
            pystray.MenuItem("Open Config", lambda: self._open_config()),
            pystray.MenuItem("Quit", self._quit),
        )

    # --- Config hot-reload ---

    def _watch_config(self):
        """Poll config.toml for changes and reload hotkeys if modified."""
        if self._shutting_down:
            return
        try:
            mtime = os.path.getmtime(CONFIG_PATH)
            if mtime > self._config_mtime:
                self._config_mtime = mtime
                self._reload_config()
        except Exception as e:
            log.debug("Config watch error: %s", e)
        self._config_watcher = threading.Timer(1.0, self._watch_config)
        self._config_watcher.daemon = True
        self._config_watcher.start()

    def _reload_config(self):
        """Re-read config and re-register hotkey listener."""
        try:
            new_config = load_config()
        except Exception as e:
            log.warning("Failed to reload config: %s", e)
            return

        old_listen = self.config.get("hotkeys", {}).get("listen", "")
        new_listen = new_config.get("hotkeys", {}).get("listen", "")

        self.config = new_config

        if old_listen != new_listen:
            log.info("Hotkey changed: '%s' -> '%s', re-registering", old_listen, new_listen)
            if self.listener:
                self.listener.stop()
            timing = self.config.get("timing", {})
            self.listener = hotkey.HotkeyListener(
                listen_hotkey=new_listen,
                long_press_ms=timing.get("long_press_ms", 300),
                on_short_press=self._on_short_press,
                on_long_press=self._on_long_press,
            )
            self.listener.start()

        # Always update chroma key position on config change
        if self.chroma_session:
            chroma_cfg = self.config.get("chroma", {})
            listen = new_listen or old_listen
            new_key = hotkey.HotkeyListener._parse_trigger_key(listen)
            self.chroma_session.mute_key_pos = chroma.resolve_key_position(
                new_key,
                chroma_cfg.get("mute_button_row"),
                chroma_cfg.get("mute_button_col"),
            )
            log.info("Chroma key position updated: %s", self.chroma_session.mute_key_pos)

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
            # Extract the main (non-modifier) key from the listen hotkey
            listen_key = hotkey.HotkeyListener._parse_trigger_key(
                self.config["hotkeys"]["listen"]
            )
            self.chroma_session = chroma.ChromaSession(
                unmute_color_hex=chroma_cfg.get("unmute_color", "#FFFFFF"),
                mute_color_hex=chroma_cfg.get("mute_color", "#FF0000"),
                deafen_color_hex=chroma_cfg.get("deafen_color", "#FF0000"),
                mute_key_name=listen_key,
                mute_button_row=chroma_cfg.get("mute_button_row"),
                mute_button_col=chroma_cfg.get("mute_button_col"),
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

        # Config file watcher for hot-reload
        self._config_mtime = os.path.getmtime(CONFIG_PATH)
        self._watch_config()

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

        if self._config_watcher:
            self._config_watcher.cancel()
            self._config_watcher = None

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
                os.path.join(APP_DIR, log_file)
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
