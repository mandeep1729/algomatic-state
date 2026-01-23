"""Logging setup helper."""

from src.utils.logging import setup_logging, get_logger


def setup_script_logging(verbose: bool, logger_name: str):
    """Setup logging and return logger.

    Args:
        verbose: Enable debug logging if True
        logger_name: Name for the logger

    Returns:
        Configured logger instance
    """
    setup_logging(
        level="DEBUG" if verbose else "INFO",
        format="text",
    )
    return get_logger(logger_name)
