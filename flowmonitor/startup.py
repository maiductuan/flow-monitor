"""
Windows startup manager - add/remove FlowMonitor from Windows auto-start.
Uses the Registry Run key (per-user, no admin required).
"""

import sys
import os

if sys.platform == "win32":
    import winreg

APP_NAME = "FlowMonitor"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def get_exe_path() -> str:
    """Get the full path to the current executable (works for both .py and .exe)."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller EXE
        return sys.executable
    else:
        # Running as Python script
        return f'"{sys.executable}" "{os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "run.py"))}"'


def is_startup_enabled() -> bool:
    """Check if FlowMonitor is in Windows startup."""
    if sys.platform != "win32":
        return False

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ
        )
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except WindowsError:
        return False


def enable_startup() -> bool:
    """Add FlowMonitor to Windows startup (runs on login, no admin needed).
    
    Returns:
        True if successful, False otherwise.
    """
    if sys.platform != "win32":
        return False

    try:
        exe_path = get_exe_path()
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
        return True
    except WindowsError as e:
        print(f"Failed to enable startup: {e}")
        return False


def disable_startup() -> bool:
    """Remove FlowMonitor from Windows startup.
    
    Returns:
        True if successful, False otherwise.
    """
    if sys.platform != "win32":
        return False

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE
        )
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass  # Already removed
        winreg.CloseKey(key)
        return True
    except WindowsError as e:
        print(f"Failed to disable startup: {e}")
        return False
