"""
Application-specific logger interface independent from the event system.

This module provides structured logging capabilities that can be safely used
within event dispatchers and other components without causing circular dependencies.
"""

import logging
import json
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional, Protocol
from dataclasses import dataclass, asdict


class LogLevel(Enum):
    """Log levels for application logging."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LogContext:
    """Structured log context information."""

    component: str
    operation: Optional[str] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        result = asdict(self)
        # Remove None values
        return {k: v for k, v in result.items() if v is not None}


class AppLogger(Protocol):
    """Protocol for application logging interface."""

    def debug(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> None:
        """Log debug message."""
        ...

    def info(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> None:
        """Log info message."""
        ...

    def warning(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> None:
        """Log warning message."""
        ...

    def error(
        self,
        message: str,
        context: Optional[LogContext] = None,
        exc_info: bool = False,
        **kwargs,
    ) -> None:
        """Log error message."""
        ...

    def critical(
        self,
        message: str,
        context: Optional[LogContext] = None,
        exc_info: bool = False,
        **kwargs,
    ) -> None:
        """Log critical message."""
        ...


class StandardAppLogger:
    """Standard implementation using Python's logging module."""

    def __init__(self, logger_name: str = "pipedoc", format_type: str = "structured"):
        """
        Initialise the standard app logger.

        Args:
            logger_name: Name of the underlying Python logger
            format_type: "structured" for JSON format, "simple" for text format
        """
        self._logger = logging.getLogger(logger_name)
        self._format_type = format_type

    def _format_message(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> str:
        """Format message with context and metadata."""
        if self._format_type == "structured":
            log_data = {
                "message": message,
                "timestamp": time.time(),
            }

            if context:
                log_data.update(context.to_dict())

            if kwargs:
                log_data["additional"] = kwargs

            return json.dumps(log_data)
        else:
            # Simple text format
            parts = [message]

            if context:
                if context.component:
                    parts.append(f"[{context.component}]")
                if context.operation:
                    parts.append(f"({context.operation})")
                if context.correlation_id:
                    parts.append(f"corr_id={context.correlation_id}")

            if kwargs:
                metadata_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
                parts.append(f"[{metadata_str}]")

            return " ".join(parts)

    def debug(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> None:
        """Log debug message."""
        formatted = self._format_message(message, context, **kwargs)
        self._logger.debug(formatted)

    def info(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> None:
        """Log info message."""
        formatted = self._format_message(message, context, **kwargs)
        self._logger.info(formatted)

    def warning(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> None:
        """Log warning message."""
        formatted = self._format_message(message, context, **kwargs)
        self._logger.warning(formatted)

    def error(
        self,
        message: str,
        context: Optional[LogContext] = None,
        exc_info: bool = False,
        **kwargs,
    ) -> None:
        """Log error message."""
        formatted = self._format_message(message, context, **kwargs)
        self._logger.error(formatted, exc_info=exc_info)

    def critical(
        self,
        message: str,
        context: Optional[LogContext] = None,
        exc_info: bool = False,
        **kwargs,
    ) -> None:
        """Log critical message."""
        formatted = self._format_message(message, context, **kwargs)
        self._logger.critical(formatted, exc_info=exc_info)


class NullAppLogger:
    """Null object implementation for testing or disabled logging."""

    def debug(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> None:
        pass

    def info(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> None:
        pass

    def warning(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> None:
        pass

    def error(
        self,
        message: str,
        context: Optional[LogContext] = None,
        exc_info: bool = False,
        **kwargs,
    ) -> None:
        pass

    def critical(
        self,
        message: str,
        context: Optional[LogContext] = None,
        exc_info: bool = False,
        **kwargs,
    ) -> None:
        pass


# Default logger instance for convenience
_default_logger: Optional[AppLogger] = None


def get_default_logger() -> AppLogger:
    """Get the default application logger instance."""
    global _default_logger
    if _default_logger is None:
        # Try to create from environment first, fallback to simple logger
        try:
            from pipedoc.logging_config import create_logger_from_env

            _default_logger = create_logger_from_env()
        except ImportError:
            # Fallback if logging_config is not available
            _default_logger = StandardAppLogger()
    return _default_logger


def set_default_logger(logger: AppLogger) -> None:
    """Set the default application logger instance."""
    global _default_logger
    _default_logger = logger


def configure_default_logger_from_env() -> AppLogger:
    """Configure default logger from environment variables and return it."""
    try:
        from pipedoc.logging_config import create_logger_from_env

        logger = create_logger_from_env()
        set_default_logger(logger)
        return logger
    except ImportError:
        # Fallback to standard logger
        logger = StandardAppLogger()
        set_default_logger(logger)
        return logger


# Convenience functions using default logger
def debug(message: str, component: str, **kwargs) -> None:
    """Log debug message using default logger."""
    context = LogContext(component=component)
    get_default_logger().debug(message, context, **kwargs)


def info(message: str, component: str, **kwargs) -> None:
    """Log info message using default logger."""
    context = LogContext(component=component)
    get_default_logger().info(message, context, **kwargs)


def warning(message: str, component: str, **kwargs) -> None:
    """Log warning message using default logger."""
    context = LogContext(component=component)
    get_default_logger().warning(message, context, **kwargs)


def error(message: str, component: str, exc_info: bool = False, **kwargs) -> None:
    """Log error message using default logger."""
    context = LogContext(component=component)
    get_default_logger().error(message, context, exc_info=exc_info, **kwargs)


def critical(message: str, component: str, exc_info: bool = False, **kwargs) -> None:
    """Log critical message using default logger."""
    context = LogContext(component=component)
    get_default_logger().critical(message, context, exc_info=exc_info, **kwargs)
