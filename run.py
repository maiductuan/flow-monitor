"""
FlowMonitor - Entry point.
Supports both Python script and PyInstaller EXE.

Usage:
  python run.py [--background] [--stop] [--config path]
  FlowMonitor.exe [--background] [--stop] [--config path]
"""

import argparse
import subprocess
import sys
import os


def get_app_dir():
    """Get the directory where the app lives (works for both .py and .exe)."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller EXE
        return os.path.dirname(sys.executable)
    else:
        # Running as Python script
        return os.path.dirname(os.path.abspath(__file__))


def get_executable():
    """Get the executable path for re-launching (works for both .py and .exe)."""
    if getattr(sys, 'frozen', False):
        return [sys.executable]  # The EXE itself
    else:
        return [sys.executable, os.path.abspath(__file__)]  # python run.py


def main():
    parser = argparse.ArgumentParser(
        description="FlowMonitor - Lightweight background activity monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  FlowMonitor.exe                          # Run in foreground
  FlowMonitor.exe --background             # Run as background process  
  FlowMonitor.exe --stop                   # Stop background process
  FlowMonitor.exe --install                # Auto-start with Windows
  FlowMonitor.exe --uninstall              # Remove from auto-start
  FlowMonitor.exe --config my_config.json  # Use custom config file
        """
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to config.json (default: auto-detect)"
    )
    parser.add_argument(
        "--background", "-b",
        action="store_true",
        help="Run as a detached background process"
    )
    parser.add_argument(
        "--stop", "-s",
        action="store_true",
        help="Stop any running background FlowMonitor process"
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Add FlowMonitor to Windows startup (auto-start on login)"
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove FlowMonitor from Windows startup"
    )

    args = parser.parse_args()

    # Handle --install
    if args.install:
        install_startup()
        return

    # Handle --uninstall
    if args.uninstall:
        uninstall_startup()
        return

    # Handle --stop
    if args.stop:
        stop_background()
        return

    # Handle --background: re-launch self as detached process
    if args.background:
        launch_background(args.config)
        return

    # Normal foreground run
    run_foreground(args.config)


def run_foreground(config_path: str = None):
    """Run FlowMonitor in the foreground."""
    from flowmonitor.monitor import FlowMonitor
    monitor = FlowMonitor(config_path=config_path)
    monitor.start()


def launch_background(config_path: str = None):
    """Launch FlowMonitor as a detached background process."""
    app_dir = get_app_dir()
    pid_file = os.path.join(app_dir, "data", "flowmonitor.pid")

    cmd = get_executable()
    if config_path:
        cmd.extend(["--config", config_path])

    # When a PyInstaller EXE spawns another process, we must strip _MEIPASS2
    # so they don't share the same temp directory (otherwise parent fails to clean it up)
    env = os.environ.copy()
    env.pop("_MEIPASS2", None)

    if sys.platform == "win32":
        # Windows: use CREATE_NO_WINDOW flag for truly hidden process
        CREATE_NO_WINDOW = 0x08000000
        DETACHED_PROCESS = 0x00000008
        process = subprocess.Popen(
            cmd,
            creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            cwd=app_dir,
            env=env,
        )
    else:
        # Linux/Mac: use nohup-style
        process = subprocess.Popen(
            cmd,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            cwd=app_dir,
            env=env,
        )

    # Save PID for later stop
    os.makedirs(os.path.dirname(pid_file), exist_ok=True)
    with open(pid_file, "w") as f:
        f.write(str(process.pid))

    print(f"FlowMonitor launched in background (PID: {process.pid})")
    print(f"PID file: {pid_file}")
    print(f"To stop: FlowMonitor.exe --stop")


def stop_background():
    """Stop a background FlowMonitor process."""
    app_dir = get_app_dir()
    pid_file = os.path.join(app_dir, "data", "flowmonitor.pid")

    if not os.path.exists(pid_file):
        print("No running FlowMonitor process found (no PID file).")
        return

    with open(pid_file, "r") as f:
        pid = int(f.read().strip())

    try:
        if sys.platform == "win32":
            # Windows: use taskkill
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True
            )
        else:
            import signal
            os.kill(pid, signal.SIGTERM)

        os.remove(pid_file)
        print(f"FlowMonitor (PID: {pid}) stopped successfully.")
    except ProcessLookupError:
        os.remove(pid_file)
        print(f"Process {pid} not found (already stopped). Cleaned up PID file.")
    except Exception as e:
        print(f"Error stopping process {pid}: {e}")


def install_startup():
    """Register FlowMonitor to start with Windows."""
    from flowmonitor.startup import enable_startup, is_startup_enabled

    if is_startup_enabled():
        print("FlowMonitor is already registered to start with Windows.")
        return

    if enable_startup():
        print("[OK] FlowMonitor added to Windows startup.")
        print("  It will auto-start when you log in.")
        print("  To remove: FlowMonitor.exe --uninstall")
    else:
        print("[FAIL] Failed to add to Windows startup.")


def uninstall_startup():
    """Remove FlowMonitor from Windows startup."""
    from flowmonitor.startup import disable_startup, is_startup_enabled

    if not is_startup_enabled():
        print("FlowMonitor is not in Windows startup.")
        return

    if disable_startup():
        print("[OK] FlowMonitor removed from Windows startup.")
    else:
        print("[FAIL] Failed to remove from Windows startup.")


if __name__ == "__main__":
    main()
