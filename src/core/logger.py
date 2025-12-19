import logging
import os
from typing import Optional

_DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

def _get_level_from_env(default: str = "INFO") -> int:
    level_name = os.environ.get("LOG_LEVEL", default).upper()
    return getattr(logging, level_name, logging.INFO)

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Create or fetch a module-level logger with sane defaults.
    - Level can be configured via env LOG_LEVEL (default INFO)
    - Uses a simple StreamHandler to stdout with timestamp
    - Prevents handler duplication across imports
    """
    logger = logging.getLogger(name or "app")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(_DEFAULT_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(_get_level_from_env())
    logger.propagate = False
    return logger