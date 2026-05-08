"""
Screenshot capture module - uses mss for ultra-fast screen capture.
"""

import os
import time
import threading
from datetime import datetime
from pathlib import Path

try:
    import mss
    import mss.tools
except ImportError:
    mss = None

try:
    from PIL import Image
    import io
except ImportError:
    Image = None


class ScreenshotCapture:
    """Captures screenshots at configurable intervals."""

    def __init__(self, config: dict, base_dir: Path, logger):
        self.config = config["screenshot"]
        self.base_dir = base_dir
        self.logger = logger
        self.output_dir = base_dir / self.config["output_dir"]
        self.interval = self.config["interval_seconds"]
        self.format = self.config.get("format", "jpg")
        self.quality = self.config.get("quality", 60)
        self.max_files = self.config.get("max_files", 1000)
        self._running = False
        self._thread = None

    def _cleanup_old_files(self):
        """Remove oldest screenshots if exceeding max_files limit."""
        try:
            files = sorted(
                self.output_dir.glob(f"*.{self.format}"),
                key=lambda f: f.stat().st_mtime
            )
            excess = len(files) - self.max_files
            if excess > 0:
                for f in files[:excess]:
                    f.unlink()
                self.logger.debug(f"Cleaned up {excess} old screenshot(s)")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")

    def _capture_single(self):
        """Capture a single screenshot."""
        if mss is None:
            self.logger.error("mss not installed. Run: pip install mss")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"screen_{timestamp}.{self.format}"
        filepath = self.output_dir / filename

        try:
            with mss.mss() as sct:
                # Capture entire screen (monitor 0 = all monitors combined)
                monitor = sct.monitors[1]  # Primary monitor
                raw = sct.grab(monitor)

                if self.format == "png":
                    # Direct PNG save via mss (fastest)
                    mss.tools.to_png(raw.rgb, raw.size, output=str(filepath))
                else:
                    # Use PIL for JPG compression (smaller files)
                    if Image:
                        img = Image.frombytes("RGB", raw.size, raw.rgb)
                        # Pillow uses "JPEG" not "JPG"
                        pil_format = "JPEG" if self.format.lower() in ("jpg", "jpeg") else self.format.upper()
                        img.save(str(filepath), pil_format, quality=self.quality, optimize=True)
                    else:
                        # Fallback to PNG if PIL not available
                        filepath = filepath.with_suffix(".png")
                        mss.tools.to_png(raw.rgb, raw.size, output=str(filepath))

            self.logger.debug(f"Screenshot saved: {filename}")

        except Exception as e:
            self.logger.error(f"Screenshot capture failed: {e}")

    def _capture_loop(self):
        """Main capture loop running in background thread."""
        self.logger.info(
            f"Screenshot capture started (every {self.interval}s, "
            f"format={self.format}, quality={self.quality})"
        )

        while self._running:
            self._capture_single()
            self._cleanup_old_files()

            # Sleep in small increments for responsive shutdown
            for _ in range(int(self.interval * 10)):
                if not self._running:
                    break
                time.sleep(0.1)

    def start(self):
        """Start capturing screenshots in a background thread."""
        if not self.config["enabled"]:
            self.logger.info("Screenshot capture is disabled in config.")
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="screenshot-thread")
        self._thread.start()

    def stop(self):
        """Stop the capture loop."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self.logger.info("Screenshot capture stopped.")
