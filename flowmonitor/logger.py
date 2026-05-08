"""
Simple file logger for FlowMonitor.
"""

import logging
import os
from pathlib import Path


def setup_logger(log_file: str, base_dir: Path = None) -> logging.Logger:
    """Setup a rotating file logger."""
    if base_dir:
        log_path = base_dir / log_file
    else:
        log_path = Path(log_file)

    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("flowmonitor")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # File handler
    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setLevel(logging.DEBUG)

    # Console handler (minimal)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger
