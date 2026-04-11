# MasterMute: Streaming Toggle + Per-Key LED Indicators

## Context
Two changes to MasterMute:
1. **Streaming toggle** — The rewind button on the BlackWidow V4 (remapped to `Ctrl+Shift+Alt+F6` via Synapse, which Discord also listens on for stream toggle) should be tracked by MasterMute for LED + tray feedback.
2. **Per-key LED instead of full keyboard takeover** — Only indicator keys light up. Synapse/Wallpaper Engine keeps control of all other keys.

## Key Technical Decision: `CHROMA_CUSTOM_KEY`
Switch from `CHROMA_CUSTOM` to `CHROMA_CUSTOM_KEY` effect. This effect uses a 6x22 grid where each cell has an "active" flag (bit `0x01000000`). Only cells with this flag set are overridden by Chroma — all others fall through to Synapse/Wallpaper Engine.

## LED Behavior

| State | Mute button (0,21) | Stream button (0,18) | Rest of keyboard |
|-------|-------------------|---------------------|-----------------|
| Unmuted, not streaming | Green | Off (Synapse) | Synapse |
| Unmuted, streaming | Green | Green | Synapse |
| Muted, not streaming | Red | Off (Synapse) | Synapse |
| Muted, streaming | Red | Green | Synapse |
| Deafened, not streaming | Orange | Off (Synapse) | Synapse |
| Deafened, streaming | Orange | Green | Synapse |

**Color logic:** Green = good/active, Red = muted, Orange = deafened. Stream button is green when streaming.

## Tray Icon Behavior

| State | Icon |
|-------|------|
| Unmuted, not streaming | Solid green circle |
| Unmuted, streaming | Green circle + small red dot center |
| Muted, not streaming | Solid red circle |
| Muted, streaming | Red circle + small white dot center |
| Deafened, not streaming | Solid orange circle |
| Deafened, streaming | Orange circle + small white dot center |

Recording dot is red on green background, white on red/orange (for visibility).

## Files to Modify

### 1. `config.toml` — add streaming config
```toml
[hotkeys]
stream_listen = "ctrl+shift+alt+f6"

[chroma]
unmute_indicator_color = "#00FF00"   # green — mic is live
mute_indicator_color = "#FF0000"     # red — mic is muted
deafen_indicator_color = "#FF8800"   # orange — fully deafened
stream_indicator_color = "#00FF00"   # green — streaming active
stream_button_row = 0
stream_button_col = 18
```

### 2. `chroma.py` — switch to CHROMA_CUSTOM_KEY + per-key indicators
- Add `ACTIVE_FLAG = 0x01000000` constant
- Add `stream_key_pos`, `stream_indicator_color_bgr`, `unmute_indicator_color_bgr` to `ChromaSession.__init__`
- Replace `_build_mute_grid` / `_build_deafen_grid_on` / `_build_deafen_grid_off` with a single `_build_indicator_grid(mute_state, streaming)` method that:
  - Starts with all-zero grid (Synapse fallthrough)
  - Sets mute button color based on state: green (unmuted), red (muted), orange (deafened) — all with `| ACTIVE_FLAG`
  - Sets stream button = green | ACTIVE_FLAG if streaming
- Change `_send_grid` to use `"effect": "CHROMA_CUSTOM_KEY"` instead of `"CHROMA_CUSTOM"`
- Replace `set_solid()` / `set_deafen()` with a single `update_indicators(mute_state, streaming)` method
- Keep `clear()` / `release()` as-is (release session = Synapse regains full control)

### 3. `main.py` — add streaming state + second listener
- Add `self.streaming: bool = False` to `MasterMuteApp`
- Add `_on_stream_press()` callback: toggles `self.streaming`, updates LED + tray
- Create a second `HotkeyListener` (short-press only, long_press_ms=99999 to effectively disable) for `stream_listen`
- Update `_update_led()` to call `chroma_session.update_indicators(self.state, self.streaming)`
- Update `_update_tray()` to use new composite icons (circle + optional recording dot)
- Update tray icon generation: `_make_status_icon(color, recording_dot=False, dot_color)`
- Update config reload to handle new stream hotkey + chroma settings
- Stop stream listener on shutdown

### 4. `hotkey.py` — no changes needed
Existing `HotkeyListener` works for streaming — use high `long_press_ms` so every press is a "short press."

### 5. `setup.py` — skip for now
Streaming keybind configurable via config.toml directly. Setup UI update can be a follow-up.

## Implementation Order
1. Update `config.toml` with new fields
2. Refactor `chroma.py` → `CHROMA_CUSTOM_KEY` + `update_indicators()`
3. Update `main.py` — streaming state, second listener, composite tray icons
4. Test locally by running `python main.py`

## Verification
1. Run `python main.py`
2. On startup → mute key (0,21) is green (unmuted), rest of keyboard = Synapse
3. Press mute → mute key turns red, rest unchanged
4. Press mute again → mute key back to green
5. Long press mute → mute key turns orange (deafened)
6. Press stream button → stream key (0,18) turns green
7. Press stream again → stream key back to off (Synapse)
8. Combine states: mute + stream → mute key red + stream key green, rest unchanged
9. Tray icon shows correct circle color + recording dot when streaming
10. Verify Wallpaper Engine / Synapse lighting stays active on all non-indicator keys
