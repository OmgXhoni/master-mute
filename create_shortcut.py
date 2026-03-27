"""Create MasterMute Windows shortcut (.lnk) on Desktop with custom icon.

Run once after generating icon.ico.
Uses Windows COM via win32com to create a proper .lnk file.
"""

import os
import sys
import subprocess

def find_pythonw() -> str:
    """Find pythonw.exe path from the current Python installation."""
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    if os.path.exists(pythonw):
        return pythonw
    # Fallback: same dir as python.exe but named pythonw
    return "pythonw.exe"


def create_shortcut():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(project_dir, "icon.ico")
    main_py = os.path.join(project_dir, "main.py")
    pythonw = find_pythonw()

    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    shortcut_path = os.path.join(desktop, "MasterMute.lnk")

    # Use PowerShell to create the .lnk (avoids needing pywin32 installed)
    ps_script = f"""
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut('{shortcut_path}')
$sc.TargetPath = '{pythonw}'
$sc.Arguments = '"{main_py}"'
$sc.WorkingDirectory = '{project_dir}'
$sc.IconLocation = '{icon_path},0'
$sc.Description = 'MasterMute — mic mute toggle with LED feedback'
$sc.Save()
"""

    subprocess.run(["powershell", "-Command", ps_script], check=True)
    print(f"Created shortcut: {shortcut_path}")
    print(f"  Target: {pythonw} \"{main_py}\"")
    print(f"  Icon: {icon_path}")
    print("\nRight-click the shortcut on your Desktop -> 'Show more options' -> 'Pin to taskbar'")

    # Remove old VBS shortcut from Desktop if it exists
    old_vbs = os.path.join(desktop, "MasterMute.vbs")
    if os.path.exists(old_vbs):
        os.remove(old_vbs)
        print(f"Removed old shortcut: {old_vbs}")


if __name__ == "__main__":
    create_shortcut()
