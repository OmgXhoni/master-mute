# Claude Code Prompt: Repurpose Razer BlackWidow V4 Mute Button → Mic Mute with Discord Integration

## Context

I have a **Razer BlackWidow V4** keyboard and a **SteelSeries Arctis Nova Pro** headset. The BlackWidow V4 has 4 dedicated media buttons in the top-right corner (play/pause, stop, skip back, skip forward) plus a multi-function roller. The **rightmost circular media button** is currently mapped to Windows audio mute — when pressed it mutes all audio and the button turns red. When unmuted, it returns to its previous color.

I want to **repurpose that button to toggle my microphone mute instead** (not audio mute — I still want to hear everything). The built-in red LED behavior on that button is ideal, I just need to change what the button actually does.

## What should happen when I press the button

Two things should happen **simultaneously**:

1. **Discord mute toggles** — so I hear Discord's mute/unmute sound cue and my Discord mute state changes.
2. **System microphone mute toggles** — so my mic is also muted at the OS level, covering in-game voice chat (e.g., Valorant, CS2, Helldivers) and any other app that uses the mic directly rather than going through Discord.

This is **microphone input mute only**. Never touch audio output/speakers/headphones volume.

## Two-part solution needed

### Part 1: Synapse rebind (instructions only)

First, give me step-by-step instructions for rebinding that rightmost media button in Razer Synapse. The button currently sends a Windows audio mute command. I need to rebind it so that instead of audio mute, it sends an obscure key combination that my Python script will intercept — something like `Ctrl+Shift+Alt+F24` or similar that won't conflict with anything.

**Important**: Check whether rebinding the media button in Synapse preserves its built-in red LED toggle behavior. If rebinding it kills the red light behavior, then we'll need the Python script to handle the LED color via the Chroma SDK REST API instead. Document both scenarios.

### Part 2: Python background script

Build a Python script that:

1. **Listens for the obscure hotkey** that the Synapse-rebound button now sends (e.g., `Ctrl+Shift+Alt+F24`).
2. **Toggles system mic mute** using the Windows Core Audio API (via `pycaw` or `comtypes` + MMDevice API). This mutes/unmutes the default recording (input) device at the OS level.
3. **Simulates Discord's mute hotkey** — I will configure Discord's "Toggle Mute" keybind to another obscure combo like `Ctrl+Shift+Alt+F23`. The script simulates that keystroke so Discord toggles its mute and plays its audio cue.
4. **If the Synapse rebind kills the red LED behavior**: Use the Razer Chroma SDK REST API to set the media button's LED to red (`#AD0014` in hex, which is `0x1400AD` in BGR) when muted, and release it back to default when unmuted.

## Razer Chroma SDK REST API reference (for LED control if needed)

- Base URI: `http://localhost:54235/razer/chromasdk`
- POST to base URI with app info JSON → returns a session URI
- Use `CHROMA_CUSTOM_KEY` effect type on the keyboard endpoint to control individual key colors
- Requires a heartbeat PUT request every ~10 seconds to keep session alive
- On exit, send DELETE to session URI to clean up
- Key color format is BGR integer
- Docs: https://assets.razerzone.com/dev_portal/REST/html/index.html
- The media buttons may use a different key identifier than standard keys — check the Chroma SDK key mapping for the BlackWidow V4's media keys. They might be mapped under a different device category or use special key codes.

## Technical requirements

- Python 3.10+ on Windows
- Config file (TOML) for:
  - `listen_hotkey`: the hotkey the Synapse button sends (default: `ctrl+shift+alt+F24`)
  - `discord_hotkey`: the keystroke to simulate for Discord mute (default: `ctrl+shift+alt+F23`)
  - `mute_color`: hex color when muted (default: `#AD0014`)
  - `chroma_led_control`: boolean — whether the script handles LED color (default: `false`, set to `true` if Synapse rebind kills the LED)
- Run as a **system tray app** using `pystray`:
  - Tray icon shows mute state (red = muted, green = unmuted)
  - Tray menu: "Muted/Unmuted" status, "Open Config", "Quit"
- On startup:
  - Read current mic mute state and sync everything (tray icon, LED if enabled)
  - Flash the key color briefly so I know the script connected successfully
- Graceful shutdown: clean up Chroma SDK session on exit (SIGINT, tray quit, window close)
- Log to file for debugging
- Include `requirements.txt` and a `README.md` with setup instructions covering both the Synapse rebind and Discord keybind configuration

## Project structure

```
razer-mic-mute/
├── config.toml
├── requirements.txt
├── README.md
├── main.py              # Entry point, tray app, orchestration
├── chroma.py            # Razer Chroma SDK REST API wrapper (LED control)
├── audio.py             # Windows mic mute toggle via Core Audio API
├── hotkey.py            # Global hotkey listener + Discord hotkey simulator
```

## Edge cases to handle

- If Discord isn't running, the system mic mute should still work (just skip the Discord hotkey simulation or let it fail silently).
- If Synapse/Chroma SDK isn't running and `chroma_led_control` is true, log a warning but don't crash.
- If the mic is already muted when the script starts, sync the state correctly on startup.
- The script should not interfere with the headset's hardware mute (that's separate and handled by the headset itself).

## README should explain

1. How to rebind the BlackWidow V4 media button in Synapse (with screenshots path suggestions)
2. How to set Discord's Toggle Mute keybind to the configured `discord_hotkey`
3. How to install and run the Python script
4. How to set it to auto-start with Windows (Task Scheduler or startup folder)
5. Troubleshooting: what to do if the LED doesn't change, if Discord doesn't respond, etc.
