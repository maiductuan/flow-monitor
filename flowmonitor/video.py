"""
Video generator - compiles screenshots into a timelapse MP4 video.
Uses PyAV when available, falls back to ffmpeg subprocess.
"""

import os
import time
import subprocess
import threading
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Try PyAV first
try:
    import av
    HAS_AV = True
except ImportError:
    HAS_AV = False


def _has_ffmpeg() -> bool:
    """Check if ffmpeg is available on PATH."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, timeout=5
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


class VideoGenerator:
    """Generates timelapse videos from screenshot folders."""

    def __init__(self, config: dict, base_dir: Path, logger):
        self.config = config.get("video", {})
        self.screenshot_config = config["screenshot"]
        self.base_dir = base_dir
        self.logger = logger

        self.screenshot_dir = base_dir / self.screenshot_config["output_dir"]
        self.output_dir = base_dir / self.config.get("output_dir", "data/videos")
        self.fps = self.config.get("fps", 4)
        self.auto_generate = self.config.get("auto_generate", True)
        self.interval_minutes = self.config.get("interval_minutes", 30)
        self.max_width = self.config.get("max_width", 1280)
        self.delete_after_video = self.config.get("delete_screenshots_after", False)

        self._running = False
        self._thread = None
        self._last_frame_count = 0

    def _get_screenshots(self) -> list:
        """Get sorted list of screenshot files."""
        if not self.screenshot_dir.exists():
            return []

        img_format = self.screenshot_config.get("format", "jpg")
        files = sorted(
            self.screenshot_dir.glob(f"*.{img_format}"),
            key=lambda f: f.name
        )
        return files

    def _load_and_resize(self, img_path: str):
        """Load image, resize if needed, ensure even dimensions."""
        img = Image.open(img_path).convert("RGB")

        if img.width > self.max_width:
            ratio = self.max_width / img.width
            new_size = (self.max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        # Ensure even dimensions (H.264 requirement)
        w, h = img.size
        w = w - (w % 2)
        h = h - (h % 2)
        if (w, h) != img.size:
            img = img.crop((0, 0, w, h))

        return img

    def generate_video(self, output_name: str = None) -> str:
        """Generate MP4 video from screenshots. Auto-selects best method."""
        screenshots = self._get_screenshots()
        if len(screenshots) < 2:
            self.logger.info(f"Need at least 2 screenshots (found {len(screenshots)}).")
            return None

        self.output_dir.mkdir(parents=True, exist_ok=True)

        if output_name is None:
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"timelapse_{now}.mp4"

        output_path = self.output_dir / output_name

        self.logger.info(
            f"Generating video: {len(screenshots)} frames, "
            f"{self.fps} fps → {output_name}"
        )

        result = None

        # Method 1: PyAV (best quality, no external deps)
        if HAS_AV and HAS_PIL:
            result = self._generate_with_pyav(screenshots, output_path)

        # Method 2: ffmpeg subprocess
        if result is None and _has_ffmpeg():
            result = self._generate_with_ffmpeg(screenshots, output_path)

        # Method 3: PIL-only GIF fallback
        if result is None and HAS_PIL:
            gif_path = output_path.with_suffix(".gif")
            result = self._generate_gif_fallback(screenshots, gif_path)

        if result is None:
            self.logger.error(
                "No video backend available. Install: pip install av"
            )

        return result

    def _generate_with_pyav(self, screenshots: list, output_path: Path) -> str:
        """Generate video using PyAV (bundled codecs)."""
        try:
            first_img = self._load_and_resize(str(screenshots[0]))
            width, height = first_img.size
            first_img.close()

            container = av.open(str(output_path), mode="w")
            stream = container.add_stream("libx264", rate=self.fps)
            stream.width = width
            stream.height = height
            stream.pix_fmt = "yuv420p"
            stream.options = {"crf": "23", "preset": "fast"}

            written = 0
            for i, img_path in enumerate(screenshots):
                try:
                    pil_img = self._load_and_resize(str(img_path))
                    if pil_img.size != (width, height):
                        pil_img = pil_img.resize((width, height), Image.LANCZOS)

                    frame = av.VideoFrame.from_ndarray(
                        np.array(pil_img), format="rgb24"
                    )
                    pil_img.close()

                    for packet in stream.encode(frame):
                        container.mux(packet)
                    written += 1

                    if (i + 1) % 100 == 0:
                        self.logger.info(f"  Progress: {i+1}/{len(screenshots)}")
                except Exception as e:
                    self.logger.warning(f"  Skip {img_path.name}: {e}")
                    continue

            for packet in stream.encode():
                container.mux(packet)
            container.close()

            return self._report_result(output_path, written)

        except Exception as e:
            self.logger.warning(f"PyAV failed: {e}, trying next method...")
            return None

    def _generate_with_ffmpeg(self, screenshots: list, output_path: Path) -> str:
        """Generate video using ffmpeg subprocess (concat demuxer)."""
        try:
            # Create a temporary file list for ffmpeg
            list_file = self.output_dir / "_filelist.txt"
            frame_duration = 1.0 / self.fps

            with open(list_file, "w", encoding="utf-8") as f:
                for img_path in screenshots:
                    # ffmpeg concat format
                    escaped = str(img_path).replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")
                    f.write(f"duration {frame_duration}\n")

            # Scale to max_width, ensure even dimensions
            scale_filter = (
                f"scale='min({self.max_width},iw):-2'"
            )

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-vf", scale_filter,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "23",
                "-preset", "fast",
                str(output_path)
            ]

            result = subprocess.run(
                cmd, capture_output=True, timeout=300
            )

            # Cleanup temp file
            list_file.unlink(missing_ok=True)

            if result.returncode != 0:
                self.logger.warning(f"ffmpeg error: {result.stderr.decode()[-200:]}")
                return None

            return self._report_result(output_path, len(screenshots))

        except Exception as e:
            self.logger.warning(f"ffmpeg failed: {e}")
            return None

    def _generate_gif_fallback(self, screenshots: list, output_path: Path) -> str:
        """Last resort: generate animated GIF using PIL."""
        try:
            frames = []
            for img_path in screenshots:
                try:
                    img = self._load_and_resize(str(img_path))
                    # Reduce size more for GIF
                    if img.width > 640:
                        ratio = 640 / img.width
                        img = img.resize(
                            (640, int(img.height * ratio)), Image.LANCZOS
                        )
                    frames.append(img)
                except Exception:
                    continue

            if len(frames) < 2:
                return None

            frame_duration = int(1000 / self.fps)  # ms per frame
            frames[0].save(
                str(output_path),
                save_all=True,
                append_images=frames[1:],
                duration=frame_duration,
                loop=0,
                optimize=True,
            )

            return self._report_result(output_path, len(frames))

        except Exception as e:
            self.logger.error(f"GIF fallback failed: {e}")
            return None

    def _report_result(self, output_path: Path, frame_count: int) -> str:
        """Log the result of video generation."""
        file_size = output_path.stat().st_size / (1024 * 1024)
        duration = frame_count / self.fps

        self.logger.info(
            f"✓ Video saved: {output_path.name} "
            f"({file_size:.1f} MB, {duration:.0f}s, {frame_count} frames)"
        )

        if self.delete_after_video:
            screenshots = self._get_screenshots()
            for f in screenshots:
                f.unlink()
            self.logger.info(f"Deleted {len(screenshots)} source screenshots.")

        return str(output_path)

    def _auto_generate_loop(self):
        """Periodically generate videos from accumulated screenshots."""
        while self._running:
            for _ in range(int(self.interval_minutes * 60)):
                if not self._running:
                    return
                time.sleep(1)

            screenshots = self._get_screenshots()
            if len(screenshots) > self._last_frame_count and len(screenshots) >= 10:
                self.generate_video()
                self._last_frame_count = len(screenshots)

    def start(self):
        """Start auto-generating videos periodically."""
        if not self.auto_generate:
            self.logger.info("Auto video generation is disabled.")
            return

        if not HAS_AV and not _has_ffmpeg():
            self.logger.warning(
                "No video backend available. Install: pip install av"
            )
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._auto_generate_loop, daemon=True, name="video-gen-thread"
        )
        self._thread.start()

        backend = "PyAV" if HAS_AV else "ffmpeg"
        self.logger.info(
            f"Auto video generation started ({backend}, "
            f"every {self.interval_minutes} min, {self.fps} fps)"
        )

    def stop(self):
        """Stop auto generation and create a final video."""
        self._running = False

        screenshots = self._get_screenshots()
        if screenshots and len(screenshots) >= 2:
            self.logger.info("Generating final video before shutdown...")
            self.generate_video()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=30)

        self.logger.info("Video generator stopped.")
