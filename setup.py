"""MasterMute — Keybind Setup UI (tkinter + keyboard lib)."""

import os
import sys
import threading
import time
import tkinter as tk
import tomllib

import keyboard
import requests

def _app_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

APP_DIR = _app_dir()
CONFIG_PATH = os.path.join(APP_DIR, "config.toml")
ICON_PATH = os.path.join(APP_DIR, "icon.ico")


def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def save_hotkeys(listen: str, discord_mute: str, discord_deafen: str,
                 mute_button_row: int | None = None,
                 mute_button_col: int | None = None):
    """Rewrite config.toml preserving all sections but updating hotkeys."""
    cfg = load_config()

    lines = []
    lines.append("[hotkeys]")
    lines.append(f'listen = "{listen.lower() if listen else ""}"')
    lines.append(f'discord_mute = "{discord_mute.lower() if discord_mute else ""}"')
    lines.append(f'discord_deafen = "{discord_deafen.lower() if discord_deafen else ""}"')
    lines.append("")

    timing = cfg.get("timing", {})
    lines.append("[timing]")
    lines.append(f'long_press_ms = {timing.get("long_press_ms", 300)}')
    lines.append(f'deafen_audio_delay_ms = {timing.get("deafen_audio_delay_ms", 500)}')
    lines.append("")

    chroma = cfg.get("chroma", {})
    lines.append("[chroma]")
    lines.append(f'enabled = {"true" if chroma.get("enabled", True) else "false"}')
    lines.append(f'unmute_color = "{chroma.get("unmute_color", "#FFFFFF")}"')
    lines.append(f'mute_color = "{chroma.get("mute_color", "#FF0000")}"')
    lines.append(f'deafen_color = "{chroma.get("deafen_color", "#FF0000")}"')
    if mute_button_row is not None and mute_button_col is not None:
        lines.append(f'mute_button_row = {mute_button_row}')
        lines.append(f'mute_button_col = {mute_button_col}')
    lines.append(f'pulse_interval_ms = {chroma.get("pulse_interval_ms", 500)}')
    lines.append("")

    log_cfg = cfg.get("logging", {})
    lines.append("[logging]")
    lines.append(f'level = "{log_cfg.get("level", "INFO")}"')
    lines.append(f'file = "{log_cfg.get("file", "master-mute.log")}"')
    lines.append("")

    with open(CONFIG_PATH, "w") as f:
        f.write("\n".join(lines))


CHROMA_BASE = "http://localhost:54235/razer/chromasdk"
GRID_ROWS = 6
GRID_COLS = 22
CHROMA_WHITE = 0xFFFFFF


class KeyFinderPopup:
    """Modal popup to find a key's position in the Chroma 6x22 grid."""

    def __init__(self, parent, on_confirm):
        self._on_confirm = on_confirm
        self._session_uri = None
        self._alive = True
        self._row = 0
        self._col = 0

        self.win = tk.Toplevel(parent)
        self.win.title("Key Finder")
        self.win.configure(bg="#ffffff")
        self.win.resizable(False, False)
        self.win.grab_set()
        self.win.focus_set()

        if os.path.exists(ICON_PATH):
            self.win.iconbitmap(ICON_PATH)

        tk.Label(self.win, text="Key Finder", font=("Segoe UI Bold", 14),
                 bg="#ffffff", fg="#000000").grid(row=0, column=0, columnspan=3,
                                                  pady=(16, 4))

        self.status_label = tk.Label(self.win, text="Connecting to Chroma SDK...",
                                     font=("Segoe UI", 9), bg="#ffffff", fg="#666666")
        self.status_label.grid(row=1, column=0, columnspan=3, pady=(0, 8))

        self.instructions = tk.Label(
            self.win, text="Use ARROW KEYS to move the light",
            font=("Segoe UI", 9), bg="#ffffff", fg="#666666")
        self.instructions.grid(row=2, column=0, columnspan=3, pady=(0, 12))

        # Position display
        pos_frame = tk.Frame(self.win, bg="#ffffff")
        pos_frame.grid(row=3, column=0, columnspan=3, pady=(0, 8))

        tk.Label(pos_frame, text="Row:", font=("Segoe UI", 11),
                 bg="#ffffff", fg="#000000").pack(side="left", padx=(20, 4))
        self.row_display = tk.Label(pos_frame, text="0",
                                    font=("Segoe UI Semibold", 14),
                                    bg="#e8e8e8", fg="#000000", width=4,
                                    relief="flat", padx=8, pady=2)
        self.row_display.pack(side="left", padx=(0, 16))

        tk.Label(pos_frame, text="Col:", font=("Segoe UI", 11),
                 bg="#ffffff", fg="#000000").pack(side="left", padx=(0, 4))
        self.col_display = tk.Label(pos_frame, text="0",
                                    font=("Segoe UI Semibold", 14),
                                    bg="#e8e8e8", fg="#000000", width=4,
                                    relief="flat", padx=8, pady=2)
        self.col_display.pack(side="left", padx=(0, 20))

        # Buttons
        btn_frame = tk.Frame(self.win, bg="#ffffff")
        btn_frame.grid(row=4, column=0, columnspan=3, pady=(8, 20))

        self.select_btn = tk.Button(
            btn_frame, text="Select", font=("Segoe UI Semibold", 11),
            bg="#22CC22", fg="#000000", activebackground="#33DD33",
            relief="flat", cursor="hand2", padx=16, pady=4,
            command=self._confirm, state="disabled",
        )
        self.select_btn.pack(side="left", padx=(0, 8))

        tk.Button(
            btn_frame, text="Cancel", font=("Segoe UI Semibold", 11),
            bg="#e8e8e8", fg="#000000", activebackground="#d0d0d0",
            relief="flat", cursor="hand2", padx=16, pady=4,
            command=self._close,
        ).pack(side="left")

        self.win.bind("<Left>", lambda e: self._move(0, -1))
        self.win.bind("<Right>", lambda e: self._move(0, 1))
        self.win.bind("<Up>", lambda e: self._move(-1, 0))
        self.win.bind("<Down>", lambda e: self._move(1, 0))
        self.win.bind("<Return>", lambda e: self._confirm())
        self.win.bind("<Escape>", lambda e: self._close())
        self.win.protocol("WM_DELETE_WINDOW", self._close)

        # Center on parent
        self.win.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        self.win.geometry(f"+{px - w // 2}+{py - h // 2}")

        threading.Thread(target=self._connect, daemon=True).start()

    def _connect(self):
        payload = {
            "title": "MasterMute Key Finder",
            "description": "Finds key grid positions",
            "author": {"name": "MasterMute", "contact": "https://github.com"},
            "device_supported": ["keyboard"],
            "category": "application",
        }
        try:
            resp = requests.post(CHROMA_BASE, json=payload, timeout=5)
            resp.raise_for_status()
            self._session_uri = resp.json().get("uri")
        except Exception:
            self.win.after(0, lambda: self.status_label.config(
                text="Failed — is Razer Synapse running?", fg="#cc0000"))
            return

        if not self._session_uri:
            self.win.after(0, lambda: self.status_label.config(
                text="No session — check Chroma SDK", fg="#cc0000"))
            return

        time.sleep(0.3)
        self._send_grid()

        def _ready():
            self.status_label.config(text="Connected", fg="#22aa22")
            self.select_btn.config(state="normal")
            self.win.focus_set()

        self.win.after(0, _ready)
        self._resend_loop()

    def _send_grid(self):
        if not self._session_uri:
            return
        grid = [[0] * GRID_COLS for _ in range(GRID_ROWS)]
        grid[self._row][self._col] = CHROMA_WHITE
        try:
            requests.put(f"{self._session_uri}/keyboard",
                         json={"effect": "CHROMA_CUSTOM", "param": grid},
                         timeout=2)
        except Exception:
            pass

    def _resend_loop(self):
        while self._alive and self._session_uri:
            self._send_grid()
            try:
                requests.put(f"{self._session_uri}/heartbeat", timeout=2)
            except Exception:
                pass
            time.sleep(0.2)

    def _move(self, drow, dcol):
        if not self._session_uri:
            return
        self._row = (self._row + drow) % GRID_ROWS
        self._col = (self._col + dcol) % GRID_COLS
        self.row_display.config(text=str(self._row))
        self.col_display.config(text=str(self._col))
        self._send_grid()

    def _confirm(self):
        if not self._session_uri:
            return
        self._on_confirm(self._row, self._col)
        self._close()

    def _close(self):
        self._alive = False
        self._cleanup()
        self.win.grab_release()
        self.win.destroy()

    def _cleanup(self):
        if self._session_uri:
            try:
                requests.put(f"{self._session_uri}/keyboard",
                             json={"effect": "CHROMA_NONE"}, timeout=2)
                requests.delete(self._session_uri, timeout=5)
            except Exception:
                pass


class KeybindEntry:
    """A label + capture button for one keybind."""

    CLEAR_TEXT = " [clear] "

    def __init__(self, parent, label_text: str, initial_value: str, row: int,
                 on_change=None):
        self.value = initial_value
        self._is_cleared = False
        self._capturing = False
        self._pressed_keys = set()
        self._hook = None
        self._on_change = on_change

        lbl = tk.Label(parent, text=label_text, font=("Segoe UI", 11),
                       anchor="w", bg="#ffffff", fg="#000000")
        lbl.grid(row=row, column=0, sticky="w", padx=(20, 10), pady=8)

        btn_frame = tk.Frame(parent, bg="#ffffff")
        btn_frame.grid(row=row, column=1, padx=(0, 20), pady=8)

        self.btn = tk.Button(
            btn_frame, text=initial_value.upper(), font=("Segoe UI Semibold", 11),
            width=28, bg="#e8e8e8", fg="#000000", activebackground="#d0d0d0",
            activeforeground="#000000", relief="flat", cursor="hand2",
            command=self._start_capture,
        )
        self.btn.pack(side="left")

        self.clear_btn = tk.Button(
            btn_frame, text="\u2715", font=("Segoe UI", 10),
            bg="#ffffff", fg="#cc0000", activebackground="#ffffff",
            activeforeground="#ff0000", relief="flat", cursor="hand2",
            bd=0, padx=4, command=self._clear,
        )
        self.clear_btn.pack(side="left", padx=(4, 0))

    def _clear(self):
        """Clear the keybind."""
        if self._capturing:
            return
        self.value = ""
        self._is_cleared = True
        self.btn.config(text=self.CLEAR_TEXT, fg="#000000", bg="#e8e8e8")
        if self._on_change:
            self._on_change()

    def _start_capture(self):
        if self._capturing:
            return
        self._capturing = True
        self._pressed_keys = set()
        self.btn.config(text="PRESS KEYS...", bg="#ffe0e0", fg="#000000")
        self._hook = keyboard.hook(self._on_key, suppress=True)

    def _on_key(self, event: keyboard.KeyboardEvent):
        if event.event_type == keyboard.KEY_DOWN:
            name = event.name.lower()
            self._pressed_keys.add(name)
        elif event.event_type == keyboard.KEY_UP:
            if self._pressed_keys:
                self._finish_capture()

    @staticmethod
    def _is_modifier(key: str) -> bool:
        return key in ("ctrl", "shift", "alt",
                       "left ctrl", "right ctrl",
                       "left shift", "right shift",
                       "left alt", "right alt")

    @staticmethod
    def _mod_sort_key(key: str) -> int:
        order = {"ctrl": 0, "left ctrl": 0, "right ctrl": 1,
                 "shift": 2, "left shift": 2, "right shift": 3,
                 "alt": 4, "left alt": 4, "right alt": 5}
        return order.get(key, 99)

    def _finish_capture(self):
        if not self._capturing:
            return
        self._capturing = False
        if self._hook:
            keyboard.unhook(self._hook)
            self._hook = None

        mods = []
        main_key = None
        for k in self._pressed_keys:
            if self._is_modifier(k):
                mods.append(k)
            else:
                main_key = k

        if main_key is None and mods:
            main_key = mods.pop()

        parts = sorted(mods, key=self._mod_sort_key)
        if main_key:
            parts.append(main_key)

        combo = "+".join(parts) if parts else self.value
        changed = combo != self.value
        self.value = combo
        self._is_cleared = False
        self.btn.config(text=combo.upper(), bg="#e8e8e8", fg="#000000")
        if changed and self._on_change:
            self._on_change()


class KeybindSetupWindow:
    def __init__(self, on_save=None):
        self.on_save = on_save
        cfg = load_config()
        hotkeys = cfg.get("hotkeys", {})
        chroma = cfg.get("chroma", {})

        self.root = tk.Tk()
        self.root.title("MasterMute - Keybind Setup")
        self.root.configure(bg="#ffffff")
        self.root.resizable(False, False)

        # Window icon (title bar)
        if os.path.exists(ICON_PATH):
            self.root.iconbitmap(ICON_PATH)

        # Title
        title = tk.Label(self.root, text="MasterMute", font=("Segoe UI Bold", 16),
                         bg="#ffffff", fg="#000000")
        title.grid(row=0, column=0, columnspan=2, pady=(16, 4))

        subtitle = tk.Label(self.root, text="Click a keybind to change it",
                            font=("Segoe UI", 9), bg="#ffffff", fg="#666666")
        subtitle.grid(row=1, column=0, columnspan=2, pady=(0, 12))

        self.listen_entry = KeybindEntry(
            self.root, "Mute Button:", hotkeys.get("listen", "ctrl+shift+alt+f7"), row=2,
            on_change=self._on_listen_changed,
        )
        self.discord_mute_entry = KeybindEntry(
            self.root, "Discord Mute:", hotkeys.get("discord_mute", "ctrl+shift+alt+f8"), row=3,
        )
        self.discord_deafen_entry = KeybindEntry(
            self.root, "Discord Deafen:", hotkeys.get("discord_deafen", "ctrl+shift+alt+f9"), row=4,
        )

        # Show cleared state for empty config values
        for entry in (self.listen_entry, self.discord_mute_entry, self.discord_deafen_entry):
            if not entry.value:
                entry._is_cleared = True
                entry.btn.config(text=KeybindEntry.CLEAR_TEXT, fg="#000000")

        # LED override fields (optional)
        led_label = tk.Label(self.root, text="LED Position Override (optional)",
                             font=("Segoe UI", 9), bg="#ffffff", fg="#666666")
        led_label.grid(row=5, column=0, columnspan=2, pady=(12, 2))

        led_frame = tk.Frame(self.root, bg="#ffffff")
        led_frame.grid(row=6, column=0, columnspan=2, pady=(0, 4))

        tk.Label(led_frame, text="Row:", font=("Segoe UI", 10),
                 bg="#ffffff", fg="#000000").pack(side="left", padx=(20, 4))
        self.row_entry = tk.Entry(led_frame, width=5, font=("Segoe UI", 10),
                                  justify="center", relief="flat", bg="#e8e8e8")
        self.row_entry.pack(side="left", padx=(0, 16))

        tk.Label(led_frame, text="Col:", font=("Segoe UI", 10),
                 bg="#ffffff", fg="#000000").pack(side="left", padx=(0, 4))
        self.col_entry = tk.Entry(led_frame, width=5, font=("Segoe UI", 10),
                                  justify="center", relief="flat", bg="#e8e8e8")
        self.col_entry.pack(side="left", padx=(0, 20))

        # Pre-populate from config if set
        if "mute_button_row" in chroma:
            self.row_entry.insert(0, str(chroma["mute_button_row"]))
        if "mute_button_col" in chroma:
            self.col_entry.insert(0, str(chroma["mute_button_col"]))

        find_btn = tk.Button(
            self.root, text="Find Key", font=("Segoe UI Semibold", 10),
            bg="#e8e8e8", fg="#000000", activebackground="#d0d0d0",
            relief="flat", cursor="hand2", padx=12, pady=2,
            command=self._open_key_finder,
        )
        find_btn.grid(row=7, column=0, columnspan=2, pady=(4, 0))

        save_btn = tk.Button(
            self.root, text="Save", font=("Segoe UI Semibold", 12),
            bg="#22CC22", fg="#000000", activebackground="#33DD33",
            relief="flat", cursor="hand2", padx=20, pady=6,
            command=self._save,
        )
        save_btn.grid(row=8, column=0, columnspan=2, pady=(16, 20))

        # Center window on screen
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")

    def _open_key_finder(self):
        """Open the Key Finder popup to select LED position."""
        def _on_found(row, col):
            self.row_entry.delete(0, tk.END)
            self.row_entry.insert(0, str(row))
            self.col_entry.delete(0, tk.END)
            self.col_entry.insert(0, str(col))

        KeyFinderPopup(self.root, on_confirm=_on_found)

    def _on_listen_changed(self):
        """Clear LED override when the mute button keybind changes."""
        self.row_entry.delete(0, tk.END)
        self.col_entry.delete(0, tk.END)

    def _save(self):
        # Parse row/col if both are filled in and valid
        row_val = self.row_entry.get().strip()
        col_val = self.col_entry.get().strip()
        mute_row = None
        mute_col = None
        if row_val and col_val:
            try:
                mute_row = int(row_val)
                mute_col = int(col_val)
            except ValueError:
                pass

        save_hotkeys(
            self.listen_entry.value,
            self.discord_mute_entry.value,
            self.discord_deafen_entry.value,
            mute_button_row=mute_row,
            mute_button_col=mute_col,
        )
        if self.on_save:
            self.on_save()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    def _on_save():
        print("Keybinds saved to config.toml")

    win = KeybindSetupWindow(on_save=_on_save)
    win.run()
