"""Diagnostic utility to find a key's position in the Chroma SDK 6x22 grid.

Run this script, then watch your keyboard. Each cell in the grid will light up
white one at a time. When you see the mute button light up, note the [row, col]
printed in the console and put those values in config.toml.

Press Ctrl+C to stop early.
"""

import time
import requests
import sys

CHROMA_BASE = "http://localhost:54235/razer/chromasdk"
GRID_ROWS = 6
GRID_COLS = 22
WHITE = 0xFFFFFF  # BGR white
PAUSE = 0.3  # seconds per cell


def main():
    print("Connecting to Chroma SDK...")
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
        session_uri = data.get("uri")
    except Exception as e:
        print(f"Failed to connect to Chroma SDK: {e}")
        print("Make sure Razer Synapse is running with Chroma enabled.")
        sys.exit(1)

    if not session_uri:
        print(f"No session URI returned: {data}")
        sys.exit(1)

    print(f"Connected! Session: {session_uri}")
    time.sleep(0.5)
    print(f"Scanning {GRID_ROWS}x{GRID_COLS} grid ({GRID_ROWS * GRID_COLS} cells)...")
    print("Watch your keyboard — when the mute button lights up, note the [row, col].\n")

    try:
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                # Build grid with single lit cell
                grid = [[0] * GRID_COLS for _ in range(GRID_ROWS)]
                grid[row][col] = WHITE

                try:
                    requests.put(
                        f"{session_uri}/keyboard",
                        json={"effect": "CHROMA_CUSTOM", "param": grid},
                        timeout=2,
                    )
                except Exception:
                    pass

                sys.stdout.write(f"\r  Scanning [row={row}, col={col}]  ")
                sys.stdout.flush()
                time.sleep(PAUSE)

                # Heartbeat to keep session alive
                if (row * GRID_COLS + col) % 20 == 0:
                    try:
                        requests.put(f"{session_uri}/heartbeat", timeout=2)
                    except Exception:
                        pass

    except KeyboardInterrupt:
        print("\n\nStopped early.")
    else:
        print("\n\nScan complete!")

    print("\nIf you saw the mute button light up, update config.toml with the")
    print("row and col values. If you didn't see it, the media button may not")
    print("be addressable via the Chroma SDK grid.\n")

    # Cleanup
    try:
        requests.put(
            f"{session_uri}/keyboard",
            json={"effect": "CHROMA_NONE"},
            timeout=2,
        )
        requests.delete(session_uri, timeout=5)
    except Exception:
        pass

    print("Session closed.")


if __name__ == "__main__":
    main()
