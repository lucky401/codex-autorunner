import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict

from .config import LogConfig

_LOGGER_CACHE: Dict[str, logging.Logger] = {}


def setup_rotating_logger(name: str, log_config: LogConfig) -> logging.Logger:
    """
    Configure (or retrieve) an isolated rotating logger for the given name.
    Each logger owns a single handler to avoid shared handlers across hub/repos.
    """
    if name in _LOGGER_CACHE:
        return _LOGGER_CACHE[name]

    log_path: Path = log_config.path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path,
        maxBytes=log_config.max_bytes,
        backupCount=log_config.backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False

    _LOGGER_CACHE[name] = logger
    return logger
