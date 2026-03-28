"""MasterMute — Key Position Finder (GUI).

Tkinter UI to navigate the Razer Chroma 6x22 grid with arrow keys.
Displays coordinates live. Press Enter or click Select to confirm.
"""

import os
import sys
import threading
import time
import tkinter as tk

import requests

CHROMA_BASE = "http://localhost:54235/razer/chromasdk"
GRID_ROWS = 6
GRID_COLS = 22
WHITE = 0xFFFFFF
RESEND_MS = 200


def _app_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


ICON_PATH = os.path.join(_app_dir(), "icon.ico")


class KeyFinderWindow:
    def __init__(self):
        self.session_uri = None
        self.row = 0
        self.col = 0
        self._alive = True

        self.root = tk.Tk()
        self.root.title("MasterMute - Key Finder")
        self.root.configure(bg="#ffffff")
        self.root.resizable(False, False)

        if os.path.exists(ICON_PATH):
            self.root.iconbitmap(ICON_PATH)

        # Title
        tk.Label(self.root, text="MasterMute", font=("Segoe UI Bold", 16),
                 bg="#ffffff", fg="#000000").grid(row=0, column=0, columnspan=2,
                                                  pady=(16, 4))

        tk.Label(self.root, text="Find your key's LED grid position",
                 font=("Segoe UI", 9), bg="#ffffff", fg="#666666").grid(
            row=1, column=0, columnspan=2, pady=(0, 12))

        # Status label (connecting / connected / error)
        self.status_label = tk.Label(self.root, text="Connecting to Chroma SDK...",
                                     font=("Segoe UI", 10), bg="#ffffff", fg="#666666")
        self.status_label.grid(row=2, column=0, columnspan=2, pady=(0, 8))

        # Instructions
        self.instructions = tk.Label(
            self.root,
            text="Use ARROW KEYS to move the light\nPress ENTER or click Select to confirm",
            font=("Segoe UI", 9), bg="#ffffff", fg="#666666", justify="center")
        self.instructions.grid(row=3, column=0, columnspan=2, pady=(0, 12))

        # Position display
        pos_frame = tk.Frame(self.root, bg="#ffffff")
        pos_frame.grid(row=4, column=0, columnspan=2, pady=(0, 4))

        tk.Label(pos_frame, text="Row:", font=("Segoe UI", 11),
                 bg="#ffffff", fg="#000000").pack(side="left", padx=(20, 4))
        self.row_display = tk.Label(pos_frame, text="0", font=("Segoe UI Semibold", 14),
                                    bg="#e8e8e8", fg="#000000", width=4,
                                    relief="flat", padx=8, pady=2)
        self.row_display.pack(side="left", padx=(0, 16))

        tk.Label(pos_frame, text="Col:", font=("Segoe UI", 11),
                 bg="#ffffff", fg="#000000").pack(side="left", padx=(0, 4))
        self.col_display = tk.Label(pos_frame, text="0", font=("Segoe UI Semibold", 14),
                                    bg="#e8e8e8", fg="#000000", width=4,
                                    relief="flat", padx=8, pady=2)
        self.col_display.pack(side="left", padx=(0, 20))

        # Select button
        self.select_btn = tk.Button(
            self.root, text="Select", font=("Segoe UI Semibold", 12),
            bg="#22CC22", fg="#000000", activebackground="#33DD33",
            relief="flat", cursor="hand2", padx=20, pady=6,
            command=self._on_select, state="disabled",
        )
        self.select_btn.grid(row=5, column=0, columnspan=2, pady=(16, 20))

        # Bind arrow keys and enter
        self.root.bind("<Left>", lambda e: self._move(0, -1))
        self.root.bind("<Right>", lambda e: self._move(0, 1))
        self.root.bind("<Up>", lambda e: self._move(-1, 0))
        self.root.bind("<Down>", lambda e: self._move(1, 0))
        self.root.bind("<Return>", lambda e: self._on_select())

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Center window
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")

        # Connect in background thread
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
            data = resp.json()
            self.session_uri = data.get("uri")
        except Exception:
            self.root.after(0, lambda: self.status_label.config(
                text="Failed to connect. Is Razer Synapse running?", fg="#cc0000"))
            return

        if not self.session_uri:
            self.root.after(0, lambda: self.status_label.config(
                text="No session — check Chroma SDK", fg="#cc0000"))
            return

        time.sleep(0.3)
        self._send_grid()

        def _ready():
            self.status_label.config(text="Connected — move with arrow keys", fg="#22aa22")
            self.select_btn.config(state="normal")
            self.root.focus_set()

        self.root.after(0, _ready)

        # Start resend loop
        self._resend_loop()

    def _send_grid(self):
        if not self.session_uri:
            return
        grid = [[0] * GRID_COLS for _ in range(GRID_ROWS)]
        grid[self.row][self.col] = WHITE
        try:
            requests.put(
                f"{self.session_uri}/keyboard",
                json={"effect": "CHROMA_CUSTOM", "param": grid},
                timeout=2,
            )
        except Exception:
            pass

    def _resend_loop(self):
        """Re-send grid every 200ms to hold against Synapse override."""
        while self._alive and self.session_uri:
            self._send_grid()
            # Heartbeat every ~10s
            try:
                requests.put(f"{self.session_uri}/heartbeat", timeout=2)
            except Exception:
                pass
            time.sleep(RESEND_MS / 1000)

    def _move(self, drow: int, dcol: int):
        if not self.session_uri:
            return
        self.row = (self.row + drow) % GRID_ROWS
        self.col = (self.col + dcol) % GRID_COLS
        self.row_display.config(text=str(self.row))
        self.col_display.config(text=str(self.col))
        self._send_grid()

    def _on_select(self):
        if not self.session_uri:
            return

        self.status_label.config(
            text=f"Selected:  row = {self.row}   col = {self.col}", fg="#000000")
        self.instructions.config(
            text=f"mute_button_row = {self.row}\nmute_button_col = {self.col}",
            font=("Consolas", 10), fg="#000000")
        self.select_btn.config(state="disabled")

        # Unbind navigation
        self.root.unbind("<Left>")
        self.root.unbind("<Right>")
        self.root.unbind("<Up>")
        self.root.unbind("<Down>")
        self.root.unbind("<Return>")

        # Flash the key in a thread
        threading.Thread(target=self._flash, daemon=True).start()

    def _flash(self):
        for _ in range(6):
            try:
                requests.put(
                    f"{self.session_uri}/keyboard",
                    json={"effect": "CHROMA_CUSTOM",
                          "param": [[0] * GRID_COLS for _ in range(GRID_ROWS)]},
                    timeout=2,
                )
            except Exception:
                pass
            time.sleep(0.2)
            self._send_grid()
            time.sleep(0.2)

    def _cleanup(self):
        self._alive = False
        if self.session_uri:
            try:
                requests.put(
                    f"{self.session_uri}/keyboard",
                    json={"effect": "CHROMA_NONE"},
                    timeout=2,
                )
                requests.delete(self.session_uri, timeout=5)
            except Exception:
                pass

    def _on_close(self):
        threading.Thread(target=self._cleanup, daemon=True).start()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    KeyFinderWindow().run()
