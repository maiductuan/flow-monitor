# FlowMonitor 🖥️

A super lightweight background activity monitor tool for Windows.

## ✨ Features

- **📸 Auto Screenshots** - Captures a compressed JPG every N seconds (default 5s).
- **⌨️ Keystroke Logging** - Monitors all keyboard activity and cleans up IME artifacts automatically.
- **🎥 Timelapse Video** - Periodically compiles screenshots into an H.264 MP4 video.
- **⚙️ Flexible Configuration** - Fully customizable via `config.json`.
- **👻 Stealth Mode** - Runs completely hidden in the background (no window, no taskbar icon).
- **🧹 Self-Cleaning** - Limits maximum screenshots stored and auto-deletes old files.

## 🚀 Installation

```bash
pip install -r requirements.txt
```

## 📖 Usage

### Run in foreground (shows logs)
```bash
python run.py
```

### Run in background (completely hidden)
```bash
python run.py --background
```

### Stop a running background process
```bash
python run.py --stop
```

### Add to Windows Startup (auto-start on login)
```bash
python run.py --install
# To remove: python run.py --uninstall
```

### Specify a custom config file
```bash
python run.py --config path/to/config.json
```

## ⚙️ Configuration (`config.json`)

```json
{
    "screenshot": {
        "enabled": true,           // Enable/disable screenshots
        "interval_seconds": 5,     // Delay between captures (seconds)
        "output_dir": "data/screenshots",  // Output directory
        "format": "jpg",           // Format: jpg or png
        "quality": 60,             // JPG Quality (1-100, lower = smaller size)
        "max_files": 1000          // Max file limit (auto deletes oldest)
    },
    "keylogger": {
        "enabled": true,           // Enable/disable keylogging
        "output_dir": "data/keylogs",  // Log directory
        "flush_interval_seconds": 10   // Write to disk every N seconds
    },
    "video": {
        "auto_generate": true,         // Auto compile screenshots into video
        "output_dir": "data/videos",   // Video directory
        "fps": 4,                      // Frames per second
        "interval_minutes": 30,        // Generate video every N minutes
        "max_width": 1280,             // Max width of output video
        "delete_screenshots_after": false // Delete images after compiling
    },
    "general": {
        "log_file": "data/flowmonitor.log",  // System log file
        "run_on_startup": false,   // If true, app auto-registers to Windows Startup on launch
        "hotkey_stop": "ctrl+shift+q",  // Hotkey to stop process
        "minimize_to_tray": true   // Minimize to system tray
    }
}
```

## 📁 Data Structure

```
flow-monitor/
├── config.json              # Configuration file
├── run.py                   # Entry point
├── requirements.txt         # Dependencies
├── flowmonitor/
│   ├── __init__.py
│   ├── config_loader.py     # Config parser
│   ├── logger.py            # Logger utility
│   ├── monitor.py           # Main orchestrator
│   ├── screenshot.py        # Screenshot module
│   ├── video.py             # Video generation module
│   ├── startup.py           # Windows startup manager
│   └── keylogger.py         # Keylogger module
└── data/                    # Auto-created at runtime
    ├── screenshots/         # Captured images
    │   ├── screen_20260509_003000_123.jpg
    │   └── ...
    ├── keylogs/             # Keystroke logs
    │   ├── keys_20260509_00.log
    │   └── ...
    ├── videos/              # Timelapse videos
    ├── flowmonitor.log      # System log
    └── flowmonitor.pid      # PID file (for background mode)
```

## 🔧 Technical Notes

- **mss** instead of Pillow ImageGrab → ~5x faster.
- **JPG quality 60** → ~30-50KB per file instead of 2-5MB PNGs.
- **PyAV & FFmpeg** → Reliable and lightweight H.264 video compilation.
- **Smart IME Cleanup** → Automatically removes typing artifacts from Vietnamese IMEs (Unikey/EVKey) in logs.
- `CREATE_NO_WINDOW` flag → Completely invisible on Windows.

## 📦 Build Executable (EXE)

### Install PyInstaller
```bash
pip install pyinstaller
```

### Build
```bash
pyinstaller FlowMonitor.spec --clean
```

### Output
```
dist/
├── FlowMonitor.exe     # ~18MB, standalone executable
```

### Using the EXE
```bash
# Copy config.json into the same directory as the EXE
copy config.json dist\

# Run hidden
dist\FlowMonitor.exe --background

# Add to Windows Startup (auto-start)
dist\FlowMonitor.exe --install

# Stop running process
dist\FlowMonitor.exe --stop
```

### Deploy to another machine
You only need to copy 2 files:
1. `FlowMonitor.exe`
2. `config.json` (customize before copying)

The `data/` directory will be automatically created next to the EXE when executed.
