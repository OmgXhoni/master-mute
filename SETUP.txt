MasterMute - Setup Instructions
================================

MasterMute turns any key (or key combo) into a smart mute button.
Short press = mute mic + Discord. Long press = full deafen (mic + speakers + Discord).
Press again to unmute everything. Works with Razer keyboards for LED feedback.


WHAT YOU NEED
-------------
- Windows 10 or 11
- Discord desktop app
- Razer Synapse 4 with Chroma SDK enabled (for LED effects, optional)


STEP 1: SET YOUR KEYBINDS
---------------------------
Double-click KeybindSetup.exe in this folder.

A window opens where you set three keybinds:

    Mute Button     - The key you'll press to mute/deafen
    Discord Mute    - A unique key combo for Discord's mute toggle
    Discord Deafen  - A unique key combo for Discord's deafen toggle

Click each field and press the keys you want. Hit "Save & Restart" when done.

The Discord keybinds should be combos you'd never press by accident
(the defaults CTRL+SHIFT+ALT+F8 and CTRL+SHIFT+ALT+F9 work well).


STEP 2: SET UP DISCORD
-----------------------
Open Discord and go to: Settings > Keybinds

Add two keybinds that MATCH what you set in Step 1:

    Toggle Mute   -> (same as "Discord Mute" from setup)
    Toggle Deafen -> (same as "Discord Deafen" from setup)

This is how MasterMute talks to Discord - it sends these key combos
in the background when you press your mute button.


STEP 3: RUN IT
--------------
Double-click MasterMute.exe in this folder.

The MasterMute icon appears in your system tray (bottom-right of taskbar).
Press your mute button to test.

    Short press   = mute (mic muted + Discord muted)
    Long press    = deafen (mic + speakers muted + Discord deafened)
    Press again   = unmute everything


AUTO-START WITH WINDOWS
-----------------------
1. Right-click MasterMute.exe > Create shortcut
2. Press Win+R, type:  shell:startup  and press Enter
3. Move the shortcut into that folder

MasterMute will now start automatically when you log in.


TRAY MENU (right-click the tray icon)
--------------------------------------
- Status          - Shows current state (Unmuted / Muted / Deafened)
- Pause           - Disables the mute button temporarily
- Change Keybinds - Opens the keybind setup window
- Open Config     - Opens config.toml for advanced settings
- Quit            - Shuts down MasterMute


RAZER KEYBOARD LED EFFECTS
---------------------------
If you have a Razer keyboard with Synapse 4:
- Mute   = entire keyboard turns red
- Deafen = keyboard goes dark
- Unmute = keyboard returns to your Synapse lighting profile

To disable LED effects, open config.toml and set:  enabled = false
under [chroma].

The deafen highlight automatically follows whatever key you set as your
mute button. If your key is model-specific and the highlight lands on
the wrong spot, you can manually override it in config.toml by adding:
    mute_button_row = <number>
    mute_button_col = <number>
Ask Xhoni for help finding the correct values for your keyboard.


TROUBLESHOOTING
---------------
- Button not detected: Try running MasterMute.exe as administrator
- Discord won't mute: Make sure Discord keybinds match what you set in KeybindSetup
- No LED effects: Check Chroma SDK is enabled in Synapse 4
- Check master-mute.log in this folder for error details
