"""MasterMute — Keybind Setup UI (tkinter + keyboard lib)."""

import os
import sys
import tkinter as tk
import tomllib

import keyboard
from PIL import Image, ImageTk

def _app_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

APP_DIR = _app_dir()
CONFIG_PATH = os.path.join(APP_DIR, "config.toml")
ICON_PATH = os.path.join(APP_DIR, "icon.ico")
LOGO_PATH = os.path.join(APP_DIR, "logo.png")


def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def save_hotkeys(listen: str, discord_mute: str, discord_deafen: str):
    """Rewrite config.toml preserving all sections but updating hotkeys."""
    cfg = load_config()

    lines = []
    lines.append("[hotkeys]")
    lines.append(f'listen = "{listen.lower()}"')
    lines.append(f'discord_mute = "{discord_mute.lower()}"')
    lines.append(f'discord_deafen = "{discord_deafen.lower()}"')
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
    lines.append("")
    lines.append(f'mute_button_row = {chroma.get("mute_button_row", 0)}')
    lines.append(f'mute_button_col = {chroma.get("mute_button_col", 21)}')
    lines.append(f'pulse_interval_ms = {chroma.get("pulse_interval_ms", 500)}')
    lines.append("")

    log_cfg = cfg.get("logging", {})
    lines.append("[logging]")
    lines.append(f'level = "{log_cfg.get("level", "INFO")}"')
    lines.append(f'file = "{log_cfg.get("file", "master-mute.log")}"')
    lines.append("")

    with open(CONFIG_PATH, "w") as f:
        f.write("\n".join(lines))


class KeybindEntry:
    """A label + capture button for one keybind."""

    def __init__(self, parent, label_text: str, initial_value: str, row: int):
        self.value = initial_value
        self._capturing = False
        self._pressed_keys = set()
        self._hook = None

        lbl = tk.Label(parent, text=label_text, font=("Segoe UI", 11),
                       anchor="w", bg="#ffffff", fg="#000000")
        lbl.grid(row=row, column=0, sticky="w", padx=(20, 10), pady=8)

        self.btn = tk.Button(
            parent, text=initial_value.upper(), font=("Segoe UI Semibold", 11),
            width=28, bg="#e8e8e8", fg="#000000", activebackground="#d0d0d0",
            activeforeground="#000000", relief="flat", cursor="hand2",
            command=self._start_capture,
        )
        self.btn.grid(row=row, column=1, padx=(0, 20), pady=8)

    def _start_capture(self):
        if self._capturing:
            return
        self._capturing = True
        self._pressed_keys = set()
        self.btn.config(text="PRESS KEYS...", bg="#ffe0e0")
        self._hook = keyboard.hook(self._on_key, suppress=True)

    def _on_key(self, event: keyboard.KeyboardEvent):
        if event.event_type == keyboard.KEY_DOWN:
            name = event.name.lower()
            if name in ("left ctrl", "right ctrl"):
                name = "ctrl"
            elif name in ("left shift", "right shift"):
                name = "shift"
            elif name in ("left alt", "right alt"):
                name = "alt"
            self._pressed_keys.add(name)
        elif event.event_type == keyboard.KEY_UP:
            if self._pressed_keys:
                self._finish_capture()

    def _finish_capture(self):
        if not self._capturing:
            return
        self._capturing = False
        if self._hook:
            keyboard.unhook(self._hook)
            self._hook = None

        mods = []
        main_key = None
        mod_names = {"ctrl", "shift", "alt"}
        for k in self._pressed_keys:
            if k in mod_names:
                mods.append(k)
            else:
                main_key = k

        if main_key is None and mods:
            main_key = mods.pop()

        parts = sorted(mods, key=lambda m: ["ctrl", "shift", "alt"].index(m)
                       if m in ["ctrl", "shift", "alt"] else 99)
        if main_key:
            parts.append(main_key)

        combo = "+".join(parts) if parts else self.value
        self.value = combo
        self.btn.config(text=combo.upper(), bg="#e8e8e8")


class KeybindSetupWindow:
    def __init__(self, on_save=None):
        self.on_save = on_save
        cfg = load_config()
        hotkeys = cfg.get("hotkeys", {})

        self.root = tk.Tk()
        self.root.title("MasterMute - Keybind Setup")
        self.root.configure(bg="#ffffff")
        self.root.resizable(False, False)

        # Window icon (title bar)
        if os.path.exists(ICON_PATH):
            self.root.iconbitmap(ICON_PATH)

        # Header row: logo + title
        header = tk.Frame(self.root, bg="#ffffff")
        header.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 4))

        # Logo in top-left
        self._logo_img = None
        if os.path.exists(LOGO_PATH):
            logo = Image.open(LOGO_PATH).resize((40, 40), Image.LANCZOS)
            self._logo_img = ImageTk.PhotoImage(logo)
            logo_lbl = tk.Label(header, image=self._logo_img, bg="#ffffff")
            logo_lbl.pack(side="left", padx=(0, 10))

        title = tk.Label(header, text="MasterMute", font=("Segoe UI Bold", 16),
                         bg="#ffffff", fg="#000000")
        title.pack(side="left")

        subtitle = tk.Label(self.root, text="Click a keybind to change it",
                            font=("Segoe UI", 9), bg="#ffffff", fg="#666666")
        subtitle.grid(row=1, column=0, columnspan=2, pady=(0, 12))

        self.listen_entry = KeybindEntry(
            self.root, "Mute Button:", hotkeys.get("listen", "ctrl+shift+alt+f7"), row=2
        )
        self.discord_mute_entry = KeybindEntry(
            self.root, "Discord Mute:", hotkeys.get("discord_mute", "ctrl+shift+alt+f8"), row=3
        )
        self.discord_deafen_entry = KeybindEntry(
            self.root, "Discord Deafen:", hotkeys.get("discord_deafen", "ctrl+shift+alt+f9"), row=4
        )

        save_btn = tk.Button(
            self.root, text="Save & Restart", font=("Segoe UI Semibold", 12),
            bg="#22CC22", fg="#000000", activebackground="#33DD33",
            relief="flat", cursor="hand2", padx=20, pady=6,
            command=self._save,
        )
        save_btn.grid(row=5, column=0, columnspan=2, pady=(16, 20))

        # Center window on screen
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")

    def _save(self):
        save_hotkeys(
            self.listen_entry.value,
            self.discord_mute_entry.value,
            self.discord_deafen_entry.value,
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
