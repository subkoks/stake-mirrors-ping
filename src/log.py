"""Structured logging setup for stake-mirrors-ping.

Rich console handles user-facing output (tables, progress bars).
This module handles internal debug/error logging via the standard logging module.

Usage:
    from .log import logger
    logger.debug("resolving DNS for %s", domain)
    logger.error("API request failed: %s", err)
"""

import logging
import sys


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure and return the project logger."""
    log = logging.getLogger("stake_mirrors")
    if log.handlers:
        return log

    level = logging.DEBUG if verbose else logging.WARNING
    log.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    fmt = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(fmt)
    log.addHandler(handler)

    return log


logger = setup_logging()
