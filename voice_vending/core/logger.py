"""
Structured Logger for Voice Vending Machine.

Provides consistent, structured logging across all modules.
Outputs human-readable format to console and JSON Lines to file.
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "voice_vending",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Configure and return a structured logger.

    Args:
        name: Logger name (used as prefix in log output).
        level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional path to write JSON logs.

    Returns:
        Configured Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # ── Console handler ─────────────────────────────────────
    console_fmt = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_fmt)
    logger.addHandler(console_handler)

    # ── File handler (optional) ─────────────────────────────
    if log_file:
        file_fmt = logging.Formatter(
            fmt='{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"module":"%(name)s","message":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)

    return logger
