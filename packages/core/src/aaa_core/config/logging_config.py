"""
Application logging configuration.

Provides file-based logging alongside the colored console output from console.py.
Log files are written to logs/app/ with a symlink at logs/app.log for quick access.
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return _ANSI_ESCAPE_RE.sub("", text)


def setup_logging(log_dir: str = "logs/app", level: int = logging.DEBUG) -> Path:
    """
    Configure root logger with a timestamped file handler.

    Call once at application startup, before importing modules that use
    console.py or logging.getLogger(__name__).

    Args:
        log_dir: Directory for log files (created if needed)
        level: Minimum log level for the file handler

    Returns:
        Path to the created log file
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_path / f"app_{timestamp}.log"

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # File handler — captures everything at DEBUG level
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Stderr handler — only WARNING+ for Python logging calls
    # (console.py already handles terminal output via print())
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.WARNING)
    stderr_formatter = logging.Formatter("[%(levelname)s] %(name)s - %(message)s")
    stderr_handler.setFormatter(stderr_formatter)
    root_logger.addHandler(stderr_handler)

    # Create/update symlink at logs/app.log pointing to latest log file
    symlink_path = log_path.parent / "app.log"
    try:
        if symlink_path.is_symlink() or symlink_path.exists():
            symlink_path.unlink()
        # Use relative path so the symlink works if the project is moved
        os.symlink(os.path.relpath(log_file, symlink_path.parent), symlink_path)
    except OSError:
        pass  # Symlinks may not be supported (e.g. some Windows configs)

    return log_file
