"""Logging setup and configuration."""

import logging
from pathlib import Path
from typing import Optional


def setup_logging(log_dir: Optional[Path] = None) -> logging.Logger:
    """Set up application logging."""
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / "storage" / "logs"
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module."""
    return logging.getLogger(name)

