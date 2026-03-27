"""MasterMute — Keybind Setup UI (tkinter + keyboard lib)."""

import os
import sys
import tkinter as tk
import tomllib

import keyboard

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


class KeybindEntry:
    """A label + capture button for one keybind."""

    def __init__(self, parent, label_text: str, initial_value: str, row: int,
                 on_change=None):
        self.value = initial_value
        self._capturing = False
        self._pressed_keys = set()
        self._hook = None
        self._on_change = on_change

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
        self.btn.config(text=combo.upper(), bg="#e8e8e8")
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
            self.root, "Discord Mute:", hotkeys.get("discord_mute", "ctrl+shift+alt+f8"), row=3
        )
        self.discord_deafen_entry = KeybindEntry(
            self.root, "Discord Deafen:", hotkeys.get("discord_deafen", "ctrl+shift+alt+f9"), row=4
        )

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

        save_btn = tk.Button(
            self.root, text="Save", font=("Segoe UI Semibold", 12),
            bg="#22CC22", fg="#000000", activebackground="#33DD33",
            relief="flat", cursor="hand2", padx=20, pady=6,
            command=self._save,
        )
        save_btn.grid(row=7, column=0, columnspan=2, pady=(16, 20))

        # Center window on screen
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")

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
