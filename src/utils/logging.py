"""Structured logging for algomatic-state.

Provides JSON-formatted logging with context support for
trade tracking, debugging, and monitoring.
"""

import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(self, include_extras: bool = True):
        """Initialize JSON formatter.

        Args:
            include_extras: Include extra fields in output
        """
        super().__init__()
        self._include_extras = include_extras

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted string
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add location info
        if record.pathname:
            log_data["location"] = {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if self._include_extras:
            extras = {}
            for key, value in record.__dict__.items():
                if key not in (
                    "name", "msg", "args", "created", "filename",
                    "funcName", "levelname", "levelno", "lineno",
                    "module", "msecs", "pathname", "process",
                    "processName", "relativeCreated", "stack_info",
                    "thread", "threadName", "exc_info", "exc_text",
                    "message", "taskName",
                ):
                    try:
                        json.dumps(value)  # Check if serializable
                        extras[key] = value
                    except (TypeError, ValueError):
                        extras[key] = str(value)

            if extras:
                log_data["context"] = extras

        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Text formatter with context support."""

    def __init__(self):
        """Initialize text formatter."""
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text.

        Args:
            record: Log record to format

        Returns:
            Formatted string
        """
        # Get base formatted message
        base = super().format(record)

        # Add context if present
        extras = []
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "created", "filename",
                "funcName", "levelname", "levelno", "lineno",
                "module", "msecs", "pathname", "process",
                "processName", "relativeCreated", "stack_info",
                "thread", "threadName", "exc_info", "exc_text",
                "message", "asctime", "taskName",
            ):
                extras.append(f"{key}={value}")

        if extras:
            return f"{base} | {' '.join(extras)}"

        return base


class TradeLogger:
    """Specialized logger for trade-related events.

    Provides methods for logging trade lifecycle events
    with structured context.

    Example:
        >>> logger = TradeLogger("strategy.momentum")
        >>> logger.signal_generated(
        ...     symbol="AAPL",
        ...     direction="long",
        ...     strength=0.8,
        ... )
    """

    def __init__(self, name: str):
        """Initialize trade logger.

        Args:
            name: Logger name
        """
        self._logger = logging.getLogger(name)

    def signal_generated(
        self,
        symbol: str,
        direction: str,
        strength: float,
        **context: Any,
    ) -> None:
        """Log signal generation.

        Args:
            symbol: Asset symbol
            direction: Signal direction
            strength: Signal strength
            **context: Additional context
        """
        self._logger.info(
            f"Signal generated: {symbol} {direction}",
            extra={
                "event": "signal_generated",
                "symbol": symbol,
                "direction": direction,
                "strength": strength,
                **context,
            },
        )

    def signal_filtered(
        self,
        symbol: str,
        reason: str,
        **context: Any,
    ) -> None:
        """Log signal filtering.

        Args:
            symbol: Asset symbol
            reason: Filter reason
            **context: Additional context
        """
        self._logger.info(
            f"Signal filtered: {symbol} - {reason}",
            extra={
                "event": "signal_filtered",
                "symbol": symbol,
                "reason": reason,
                **context,
            },
        )

    def order_submitted(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        **context: Any,
    ) -> None:
        """Log order submission.

        Args:
            symbol: Asset symbol
            side: Buy or sell
            quantity: Order quantity
            order_type: Order type
            **context: Additional context
        """
        self._logger.info(
            f"Order submitted: {side} {quantity} {symbol}",
            extra={
                "event": "order_submitted",
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": order_type,
                **context,
            },
        )

    def order_filled(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        **context: Any,
    ) -> None:
        """Log order fill.

        Args:
            symbol: Asset symbol
            side: Buy or sell
            quantity: Filled quantity
            price: Fill price
            **context: Additional context
        """
        self._logger.info(
            f"Order filled: {side} {quantity} {symbol} @ {price}",
            extra={
                "event": "order_filled",
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                **context,
            },
        )

    def position_opened(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        **context: Any,
    ) -> None:
        """Log position opening.

        Args:
            symbol: Asset symbol
            quantity: Position quantity
            entry_price: Entry price
            **context: Additional context
        """
        self._logger.info(
            f"Position opened: {symbol} qty={quantity} @ {entry_price}",
            extra={
                "event": "position_opened",
                "symbol": symbol,
                "quantity": quantity,
                "entry_price": entry_price,
                **context,
            },
        )

    def position_closed(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
        pnl: float,
        **context: Any,
    ) -> None:
        """Log position closing.

        Args:
            symbol: Asset symbol
            quantity: Position quantity
            entry_price: Entry price
            exit_price: Exit price
            pnl: Realized P&L
            **context: Additional context
        """
        self._logger.info(
            f"Position closed: {symbol} pnl={pnl:.2f}",
            extra={
                "event": "position_closed",
                "symbol": symbol,
                "quantity": quantity,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                **context,
            },
        )

    def regime_change(
        self,
        old_regime: int,
        new_regime: int,
        **context: Any,
    ) -> None:
        """Log regime change.

        Args:
            old_regime: Previous regime label
            new_regime: New regime label
            **context: Additional context
        """
        self._logger.info(
            f"Regime change: {old_regime} -> {new_regime}",
            extra={
                "event": "regime_change",
                "old_regime": old_regime,
                "new_regime": new_regime,
                **context,
            },
        )

    def error(self, message: str, **context: Any) -> None:
        """Log error.

        Args:
            message: Error message
            **context: Additional context
        """
        self._logger.error(message, extra={"event": "error", **context})

    def warning(self, message: str, **context: Any) -> None:
        """Log warning.

        Args:
            message: Warning message
            **context: Additional context
        """
        self._logger.warning(message, extra={"event": "warning", **context})


def setup_logging(
    level: str = "INFO",
    format: str = "json",
    file: str | Path | None = None,
    rotate_size_mb: int = 10,
    retain_count: int = 5,
) -> None:
    """Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format: Log format ('json' or 'text')
        file: Log file path (None for stdout only)
        rotate_size_mb: Log rotation size in MB
        retain_count: Number of rotated files to retain
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create formatter
    if format == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if file:
        file_path = Path(file)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=rotate_size_mb * 1024 * 1024,
            backupCount=retain_count,
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Configure uvicorn loggers to propagate to root (so they go to file handler)
    for uvicorn_logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def get_trade_logger(name: str) -> TradeLogger:
    """Get a trade logger instance.

    Args:
        name: Logger name

    Returns:
        TradeLogger instance
    """
    return TradeLogger(name)
