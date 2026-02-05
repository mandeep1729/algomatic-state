"""Logging setup helper."""

from pathlib import Path

from config.settings import get_settings
from src.utils.logging import setup_logging, get_logger


def setup_script_logging(verbose: bool, logger_name: str, log_file: str | Path | None = None):
    """Setup logging and return logger.

    Args:
        verbose: Enable debug logging if True
        logger_name: Name for the logger
        log_file: Optional log file path. If None, uses default from settings.

    Returns:
        Configured logger instance
    """
    settings = get_settings()

    # Use provided log_file or default from settings
    file_path = log_file if log_file is not None else settings.logging.file

    setup_logging(
        level="DEBUG" if verbose else "INFO",
        format="text",
        file=file_path,
        rotate_size_mb=settings.logging.rotate_size_mb,
        retain_count=settings.logging.retain_count,
    )
    return get_logger(logger_name)
