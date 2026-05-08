"""
FlowMonitor - Main orchestrator.
Manages all monitoring modules and handles graceful shutdown.
"""

import signal
import sys
import time
import threading
from pathlib import Path

from .config_loader import load_config, ensure_directories, find_config_file
from .logger import setup_logger
from .screenshot import ScreenshotCapture
from .keylogger import KeyboardMonitor
from .video import VideoGenerator


class FlowMonitor:
    """Main application class that orchestrates all monitoring modules."""

    def __init__(self, config_path: str = None):
        self.config = load_config(config_path)
        self.base_dir = find_config_file().parent if not config_path else Path(config_path).parent
        ensure_directories(self.config, self.base_dir)

        self.logger = setup_logger(
            self.config["general"]["log_file"],
            self.base_dir
        )

        self.screenshot = ScreenshotCapture(self.config, self.base_dir, self.logger)
        self.keymon = KeyboardMonitor(self.config, self.base_dir, self.logger)
        self.video = VideoGenerator(self.config, self.base_dir, self.logger)

        self._running = False
        self._stop_event = threading.Event()

    def _setup_signals(self):
        """Register signal handlers for graceful shutdown."""
        import threading
        if threading.current_thread() is not threading.main_thread():
            self.logger.debug("Not main thread, skipping signal setup.")
            return

        def handle_signal(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down...")
            self.stop()

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        # Windows-specific: handle CTRL+BREAK
        if sys.platform == "win32":
            try:
                signal.signal(signal.SIGBREAK, handle_signal)
            except (AttributeError, OSError):
                pass

    def start(self):
        """Start all monitoring modules."""
        self._running = True
        self._setup_signals()

        self.logger.info("=" * 50)
        self.logger.info("FlowMonitor v1.0.0 starting...")
        self.logger.info(f"Base directory: {self.base_dir}")
        self.logger.info(f"Screenshot: {'ON' if self.config['screenshot']['enabled'] else 'OFF'}")
        self.logger.info(f"Keylogger:  {'ON' if self.config['keylogger']['enabled'] else 'OFF'}")
        video_cfg = self.config.get('video', {})
        self.logger.info(f"Video:      {'ON' if video_cfg.get('auto_generate', True) else 'OFF'}")
        self.logger.info("=" * 50)

        # Start modules
        self.screenshot.start()
        self.keymon.start()
        self.video.start()

        # Sync startup setting with Windows registry
        self._sync_startup()

        self.logger.info("All modules started. Running in background...")
        self.logger.info(f"Press Ctrl+C or use hotkey ({self.config['general']['hotkey_stop']}) to stop.")

        # Keep main thread alive and watch for stop signal file
        stop_file = self.base_dir / "data" / "stop.cmd"
        if stop_file.exists():
            try:
                stop_file.unlink()
            except OSError:
                pass

        try:
            while self._running and not self._stop_event.is_set():
                if stop_file.exists():
                    self.logger.info("Stop command received via file.")
                    try:
                        stop_file.unlink()
                    except OSError:
                        pass
                    break
                self._stop_event.wait(timeout=1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        """Gracefully stop all modules."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        self.logger.info("Stopping all modules...")
        self.screenshot.stop()
        self.keymon.stop()
        self.video.stop()
        self.logger.info("FlowMonitor stopped cleanly.")

    def _sync_startup(self):
        """Sync the run_on_startup config with Windows registry."""
        if sys.platform != "win32":
            return

        try:
            from .startup import enable_startup, disable_startup, is_startup_enabled

            should_start = self.config["general"].get("run_on_startup", False)
            currently_enabled = is_startup_enabled()

            if should_start and not currently_enabled:
                if enable_startup():
                    self.logger.info("Startup: registered (will auto-start with Windows)")
                else:
                    self.logger.warning("Startup: failed to register")
            elif not should_start and currently_enabled:
                if disable_startup():
                    self.logger.info("Startup: unregistered (removed from auto-start)")
            elif should_start and currently_enabled:
                self.logger.info("Startup: already registered")

        except Exception as e:
            self.logger.warning(f"Startup sync failed: {e}")

    def status(self) -> dict:
        """Get current status of all modules."""
        from .startup import is_startup_enabled

        return {
            "running": self._running,
            "screenshot_enabled": self.config["screenshot"]["enabled"],
            "keylogger_enabled": self.config["keylogger"]["enabled"],
            "startup_enabled": is_startup_enabled(),
            "base_dir": str(self.base_dir),
        }
