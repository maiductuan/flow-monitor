"""
Configuration loader - reads and validates config.json
"""

import json
import os
import sys
from pathlib import Path


# Default configuration values
DEFAULTS = {
    "screenshot": {
        "enabled": True,
        "interval_seconds": 5,
        "output_dir": "data/screenshots",
        "format": "jpg",
        "quality": 60,
        "max_files": 1000
    },
    "keylogger": {
        "enabled": True,
        "output_dir": "data/keylogs",
        "flush_interval_seconds": 10
    },
    "video": {
        "auto_generate": True,
        "output_dir": "data/videos",
        "fps": 4,
        "interval_minutes": 30,
        "max_width": 1280,
        "delete_screenshots_after": False
    },
    "general": {
        "log_file": "data/flowmonitor.log",
        "run_on_startup": False,
        "hotkey_stop": "ctrl+shift+q",
        "minimize_to_tray": True
    }
}


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def find_config_file() -> Path:
    """Find config.json relative to the executable or working directory."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller EXE - look next to the .exe file
        exe_dir = Path(os.path.dirname(sys.executable))
    else:
        # Running as Python script
        exe_dir = Path(os.path.dirname(os.path.abspath(sys.argv[0])))

    candidates = [
        exe_dir / "config.json",
        Path.cwd() / "config.json",
    ]

    # Only add __file__ based path when not frozen
    if not getattr(sys, 'frozen', False):
        candidates.append(Path(__file__).parent.parent / "config.json")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]  # Return default path even if not found


def load_config(config_path: str = None) -> dict:
    """Load configuration from JSON file, merging with defaults."""
    if config_path:
        path = Path(config_path)
    else:
        path = find_config_file()

    config = DEFAULTS.copy()

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            config = deep_merge(DEFAULTS, user_config)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARN] Failed to load config from {path}: {e}")
            print("[WARN] Using default configuration.")
    else:
        print(f"[INFO] Config file not found at {path}, using defaults.")
        # Create default config file
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, indent=4)
        print(f"[INFO] Created default config at {path}")

    return config


def ensure_directories(config: dict, base_dir: Path = None):
    """Create all required output directories."""
    if base_dir is None:
        base_dir = find_config_file().parent

    dirs_to_create = [
        config["screenshot"]["output_dir"],
        config["keylogger"]["output_dir"],
        os.path.dirname(config["general"]["log_file"]),
    ]

    for d in dirs_to_create:
        if d:
            full_path = base_dir / d
            full_path.mkdir(parents=True, exist_ok=True)
