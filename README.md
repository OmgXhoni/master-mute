# MasterMute

Intercepts the Razer BlackWidow V4's mute button and turns it into a smart mic mute / deafen toggle.

**Short press** = mic mute (system + Discord). The button's native red LED lights up.
**Long press** (hold >300ms) = full deafen (mic + audio + Discord deafen). Entire keyboard pulses red.
**Short press** from either state = unmute everything.

## How it works

The mute button stays set to **Audio Mute** in Synapse — this preserves the built-in red LED toggle. MasterMute intercepts the volume mute keystroke before Windows processes it, so your audio never actually mutes. Instead, the script mutes your microphone and triggers Discord's mute/deafen hotkeys.

## Prerequisites

- Windows 10/11
- Python 3.11+
- Razer Synapse 4 with Chroma SDK enabled
- Discord desktop app

## Setup

### 1. Install dependencies

```bash
cd master-mute
pip install -r requirements.txt
```

### 2. Synapse — keep the default

Make sure the mute button (rightmost media key) is set to **Mute Volume** in Synapse. This is the default — don't change it.

### 3. Discord keybinds

1. Open Discord → Settings → Keybinds
2. Add keybind: **Toggle Mute** → `Ctrl + Shift + Alt + F9`
3. Add keybind: **Toggle Deafen** → `Ctrl + Shift + Alt + F10`
4. Save

### 4. Run MasterMute

```bash
python main.py
```

A green system tray icon appears. Press the mute button to test.

## Auto-start with Windows

### Option A: Startup folder

1. Press `Win + R`, type `shell:startup`, press Enter
2. Create a shortcut:
   - Target: `pythonw.exe "C:\path\to\master-mute\main.py"`
   - Start in: `C:\path\to\master-mute\`

### Option B: Task Scheduler

1. Open Task Scheduler → Create Basic Task
2. Name: "MasterMute"
3. Trigger: "When I log on"
4. Action: Start a program
   - Program: `pythonw.exe`
   - Arguments: `"C:\path\to\master-mute\main.py"`
   - Start in: `C:\path\to\master-mute\`

## Configuration

Right-click tray icon → "Open Config" or edit `config.toml` directly.

```toml
[hotkeys]
discord_mute = "ctrl+shift+alt+f9"      # Discord Toggle Mute keybind
discord_deafen = "ctrl+shift+alt+f10"    # Discord Toggle Deafen keybind

[timing]
long_press_ms = 300                      # Hold threshold for deafen (ms)

[chroma]
enabled = true                           # Whole-keyboard pulse on deafen
deafen_color = "#AD0014"                 # Pulse color (hex RGB)
pulse_interval_ms = 500                  # Pulse speed (ms)

[logging]
level = "INFO"                           # DEBUG for verbose output
file = "master-mute.log"
```

## Tray menu

- **Status** — current state (Unmuted / Muted / Deafened)
- **Pause** — disables interception, mute button works normally again
- **Resume** — re-enables interception
- **Open Config** — opens config.toml in your default editor
- **Quit** — shuts down MasterMute

## Troubleshooting

### Mute button not detected
- Make sure the button is set to **Mute Volume** (default) in Synapse
- Try running the script as administrator
- Check `master-mute.log`

### Discord doesn't mute/unmute
- Verify Discord keybinds: `Ctrl+Shift+Alt+F9` for mute, `Ctrl+Shift+Alt+F10` for deafen
- Discord must be running

### Audio actually mutes when pressing the button
- The script isn't running or isn't intercepting. Check tray icon is present
- If paused (via tray menu), the button passes through normally — resume it

### Keyboard doesn't pulse on deafen
- Check Chroma SDK is enabled in Synapse
- Check `chroma.enabled = true` in config.toml
- Check `master-mute.log` for Chroma connection errors
