"""
Comprehensive logging configuration system with verbosity control and multiple handlers.

This module provides configurable logging with support for:
- Multiple output handlers (console, file, syslog, rotating files)
- Verbosity levels and filtering
- Structured and text formatting options
- Environment-based configuration
- Runtime reconfiguration
"""

import logging
import logging.handlers
import os
import sys
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from pathlib import Path

from pipedoc.app_logger import AppLogger, LogContext, StandardAppLogger


class LogHandler(Enum):
    """Available log handler types."""

    CONSOLE = "console"
    FILE = "file"
    ROTATING_FILE = "rotating_file"
    SYSLOG = "syslog"
    NULL = "null"


class LogFormat(Enum):
    """Available log format types."""

    STRUCTURED = "structured"  # JSON format
    SIMPLE = "simple"  # Human-readable text
    DETAILED = "detailed"  # Detailed text with timestamps


class VerbosityLevel(Enum):
    """Verbosity levels for controlling log output."""

    SILENT = 0  # No output (CRITICAL only)
    QUIET = 1  # Errors and warnings only
    NORMAL = 2  # Info, warnings, errors
    VERBOSE = 3  # Debug, info, warnings, errors
    VERY_VERBOSE = 4  # All levels with detailed context


@dataclass
class HandlerConfig:
    """Configuration for a single log handler."""

    type: LogHandler
    level: Optional[str] = None  # If None, uses global level
    format: Optional[LogFormat] = None  # If None, uses global format

    # File handler specific options
    filename: Optional[str] = None
    max_bytes: int = 10 * 1024 * 1024  # 10MB default
    backup_count: int = 5

    # Syslog specific options
    facility: str = "local0"
    address: Union[str, tuple] = "/dev/log"  # Unix socket or (host, port) tuple

    # Console specific options
    stream: str = "stderr"  # "stdout" or "stderr"

    # Formatting options
    date_format: str = "%Y-%m-%d %H:%M:%S"
    message_format: Optional[str] = None


@dataclass
class LoggingConfig:
    """Complete logging configuration."""

    # Global settings
    verbosity: VerbosityLevel = VerbosityLevel.NORMAL
    global_level: str = "INFO"
    global_format: LogFormat = LogFormat.STRUCTURED
    logger_name: str = "pipedoc"

    # Handler configurations
    handlers: List[HandlerConfig] = field(
        default_factory=lambda: [HandlerConfig(type=LogHandler.CONSOLE)]
    )

    # Component-specific overrides
    component_levels: Dict[str, str] = field(default_factory=dict)

    # Filtering options
    exclude_components: List[str] = field(default_factory=list)
    include_only_components: Optional[List[str]] = None

    # Performance options
    async_logging: bool = False
    buffer_size: int = 1000

    def __post_init__(self):
        """Validate and normalize configuration."""
        self._normalize_levels()

    def _normalize_levels(self):
        """Normalize log levels based on verbosity."""
        verbosity_to_level = {
            VerbosityLevel.SILENT: "CRITICAL",
            VerbosityLevel.QUIET: "WARNING",
            VerbosityLevel.NORMAL: "INFO",
            VerbosityLevel.VERBOSE: "DEBUG",
            VerbosityLevel.VERY_VERBOSE: "DEBUG",
        }

        if self.global_level == "INFO":  # Default wasn't overridden
            self.global_level = verbosity_to_level[self.verbosity]


class ConfigurableAppLogger:
    """Configurable application logger with multiple handlers and verbosity control."""

    def __init__(self, config: Optional[LoggingConfig] = None):
        """
        Initialize configurable logger.

        Args:
            config: Logging configuration. If None, uses default configuration.
        """
        self.config = config or LoggingConfig()
        self._python_logger: Optional[logging.Logger] = None
        self._handlers: List[logging.Handler] = []
        self._setup_logging()

    def _setup_logging(self):
        """Set up Python logging based on configuration."""
        # Create logger
        self._python_logger = logging.getLogger(self.config.logger_name)
        self._python_logger.setLevel(self.config.global_level)

        # Clear existing handlers
        self._python_logger.handlers.clear()
        self._handlers.clear()

        # Add configured handlers
        for handler_config in self.config.handlers:
            handler = self._create_handler(handler_config)
            if handler:
                self._handlers.append(handler)
                self._python_logger.addHandler(handler)

        # Prevent propagation to root logger to avoid duplicate messages
        self._python_logger.propagate = False

    def _create_handler(self, config: HandlerConfig) -> Optional[logging.Handler]:
        """Create a logging handler from configuration."""
        try:
            if config.type == LogHandler.CONSOLE:
                return self._create_console_handler(config)
            elif config.type == LogHandler.FILE:
                return self._create_file_handler(config)
            elif config.type == LogHandler.ROTATING_FILE:
                return self._create_rotating_file_handler(config)
            elif config.type == LogHandler.SYSLOG:
                return self._create_syslog_handler(config)
            elif config.type == LogHandler.NULL:
                return logging.NullHandler()
            else:
                raise ValueError(f"Unknown handler type: {config.type}")
        except Exception as e:
            # Fallback to console if handler creation fails
            print(
                f"Warning: Failed to create {config.type.value} handler: {e}",
                file=sys.stderr,
            )
            if config.type != LogHandler.CONSOLE:
                return self._create_console_handler(
                    HandlerConfig(type=LogHandler.CONSOLE)
                )
            return None

    def _create_console_handler(self, config: HandlerConfig) -> logging.StreamHandler:
        """Create console handler."""
        stream = sys.stdout if config.stream == "stdout" else sys.stderr
        handler = logging.StreamHandler(stream)
        self._configure_handler(handler, config)
        return handler

    def _create_file_handler(self, config: HandlerConfig) -> logging.FileHandler:
        """Create file handler."""
        if not config.filename:
            raise ValueError("File handler requires filename")

        # Ensure directory exists
        Path(config.filename).parent.mkdir(parents=True, exist_ok=True)

        handler = logging.FileHandler(config.filename)
        self._configure_handler(handler, config)
        return handler

    def _create_rotating_file_handler(
        self, config: HandlerConfig
    ) -> logging.handlers.RotatingFileHandler:
        """Create rotating file handler."""
        if not config.filename:
            raise ValueError("Rotating file handler requires filename")

        # Ensure directory exists
        Path(config.filename).parent.mkdir(parents=True, exist_ok=True)

        handler = logging.handlers.RotatingFileHandler(
            filename=config.filename,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
        )
        self._configure_handler(handler, config)
        return handler

    def _create_syslog_handler(
        self, config: HandlerConfig
    ) -> logging.handlers.SysLogHandler:
        """Create syslog handler."""
        # Convert facility name to facility constant
        facility = getattr(
            logging.handlers.SysLogHandler,
            f"LOG_{config.facility.upper()}",
            logging.handlers.SysLogHandler.LOG_LOCAL0,
        )

        handler = logging.handlers.SysLogHandler(
            address=config.address, facility=facility
        )
        self._configure_handler(handler, config)
        return handler

    def _configure_handler(self, handler: logging.Handler, config: HandlerConfig):
        """Configure handler with level and formatter."""
        # Set level (use handler-specific or global)
        level = config.level or self.config.global_level
        handler.setLevel(level)

        # Set formatter
        format_type = config.format or self.config.global_format
        formatter = self._create_formatter(format_type, config)
        handler.setFormatter(formatter)

    def _create_formatter(
        self, format_type: LogFormat, config: HandlerConfig
    ) -> logging.Formatter:
        """Create formatter based on format type."""
        if config.message_format:
            # Use custom format
            return logging.Formatter(
                fmt=config.message_format, datefmt=config.date_format
            )

        if format_type == LogFormat.STRUCTURED:
            # JSON format - let our AppLogger handle formatting
            return logging.Formatter("%(message)s")
        elif format_type == LogFormat.SIMPLE:
            return logging.Formatter("%(levelname)s: %(message)s")
        elif format_type == LogFormat.DETAILED:
            return logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt=config.date_format,
            )
        else:
            return logging.Formatter("%(message)s")

    def should_log_component(self, component: str) -> bool:
        """Check if a component should be logged based on filters."""
        # Check exclude list
        if component in self.config.exclude_components:
            return False

        # Check include-only list
        if self.config.include_only_components:
            return component in self.config.include_only_components

        return True

    def get_component_level(self, component: str) -> str:
        """Get effective log level for a component."""
        return self.config.component_levels.get(component, self.config.global_level)

    def reconfigure(self, new_config: LoggingConfig):
        """Reconfigure logging with new settings."""
        self.config = new_config
        self._setup_logging()

    def debug(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> None:
        """Log debug message."""
        if context and not self.should_log_component(context.component):
            return
        formatted = self._format_message(message, context, **kwargs)
        self._python_logger.debug(formatted)

    def info(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> None:
        """Log info message."""
        if context and not self.should_log_component(context.component):
            return
        formatted = self._format_message(message, context, **kwargs)
        self._python_logger.info(formatted)

    def warning(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> None:
        """Log warning message."""
        if context and not self.should_log_component(context.component):
            return
        formatted = self._format_message(message, context, **kwargs)
        self._python_logger.warning(formatted)

    def error(
        self,
        message: str,
        context: Optional[LogContext] = None,
        exc_info: bool = False,
        **kwargs,
    ) -> None:
        """Log error message."""
        if context and not self.should_log_component(context.component):
            return
        formatted = self._format_message(message, context, **kwargs)
        self._python_logger.error(formatted, exc_info=exc_info)

    def critical(
        self,
        message: str,
        context: Optional[LogContext] = None,
        exc_info: bool = False,
        **kwargs,
    ) -> None:
        """Log critical message."""
        if context and not self.should_log_component(context.component):
            return
        formatted = self._format_message(message, context, **kwargs)
        self._python_logger.critical(formatted, exc_info=exc_info)

    def _format_message(
        self, message: str, context: Optional[LogContext] = None, **kwargs
    ) -> str:
        """Format message based on global format setting."""
        format_type = self.config.global_format

        if format_type == LogFormat.STRUCTURED:
            # Use StandardAppLogger formatting
            temp_logger = StandardAppLogger(format_type="structured")
            return temp_logger._format_message(message, context, **kwargs)
        else:
            # Use StandardAppLogger text formatting
            temp_logger = StandardAppLogger(format_type="simple")
            return temp_logger._format_message(message, context, **kwargs)


def create_logger_from_env() -> AppLogger:
    """Create logger from environment variables."""
    config = LoggingConfig()

    # Read verbosity from environment
    verbosity_str = os.getenv("PIPEDOC_LOG_VERBOSITY", "normal").lower()
    verbosity_map = {
        "silent": VerbosityLevel.SILENT,
        "quiet": VerbosityLevel.QUIET,
        "normal": VerbosityLevel.NORMAL,
        "verbose": VerbosityLevel.VERBOSE,
        "very_verbose": VerbosityLevel.VERY_VERBOSE,
        "v": VerbosityLevel.VERBOSE,
        "vv": VerbosityLevel.VERY_VERBOSE,
    }
    config.verbosity = verbosity_map.get(verbosity_str, VerbosityLevel.NORMAL)

    # Read log level override
    if level := os.getenv("PIPEDOC_LOG_LEVEL"):
        config.global_level = level.upper()

    # Read format preference
    format_str = os.getenv("PIPEDOC_LOG_FORMAT", "json").lower()
    format_map = {
        "json": LogFormat.STRUCTURED,
        "simple": LogFormat.SIMPLE,
        "detailed": LogFormat.DETAILED,
    }
    config.global_format = format_map.get(format_str, LogFormat.STRUCTURED)

    # Configure handlers from environment
    handlers_str = os.getenv("PIPEDOC_LOG_HANDLERS", "console")
    handler_configs = []

    for handler_name in handlers_str.split(","):
        handler_name = handler_name.strip().lower()
        if handler_name == "console":
            handler_configs.append(HandlerConfig(type=LogHandler.CONSOLE))
        elif handler_name == "file":
            filename = os.getenv("PIPEDOC_LOG_FILE", "logs/pipedoc.log")
            handler_configs.append(
                HandlerConfig(type=LogHandler.FILE, filename=filename)
            )
        elif handler_name == "rotating":
            filename = os.getenv("PIPEDOC_LOG_FILE", "logs/pipedoc.log")
            handler_configs.append(
                HandlerConfig(type=LogHandler.ROTATING_FILE, filename=filename)
            )
        elif handler_name == "syslog":
            handler_configs.append(HandlerConfig(type=LogHandler.SYSLOG))
        elif handler_name == "null":
            handler_configs.append(HandlerConfig(type=LogHandler.NULL))

    if handler_configs:
        config.handlers = handler_configs

    # Component filtering
    if exclude := os.getenv("PIPEDOC_LOG_EXCLUDE"):
        config.exclude_components = [c.strip() for c in exclude.split(",")]

    if include := os.getenv("PIPEDOC_LOG_INCLUDE_ONLY"):
        config.include_only_components = [c.strip() for c in include.split(",")]

    return ConfigurableAppLogger(config)


def create_logger_from_config(config_dict: Dict[str, Any]) -> AppLogger:
    """Create logger from configuration dictionary."""
    # Convert dict to LoggingConfig
    # This would typically parse a YAML/JSON config file
    # For now, we'll implement basic conversion

    config = LoggingConfig()

    if "verbosity" in config_dict:
        verbosity_str = str(config_dict["verbosity"]).lower()
        verbosity_map = {
            "silent": VerbosityLevel.SILENT,
            "quiet": VerbosityLevel.QUIET,
            "normal": VerbosityLevel.NORMAL,
            "verbose": VerbosityLevel.VERBOSE,
            "very_verbose": VerbosityLevel.VERY_VERBOSE,
        }
        config.verbosity = verbosity_map.get(verbosity_str, VerbosityLevel.NORMAL)

    if "level" in config_dict:
        config.global_level = str(config_dict["level"]).upper()

    if "format" in config_dict:
        format_str = str(config_dict["format"]).lower()
        format_map = {
            "structured": LogFormat.STRUCTURED,
            "simple": LogFormat.SIMPLE,
            "detailed": LogFormat.DETAILED,
        }
        config.global_format = format_map.get(format_str, LogFormat.STRUCTURED)

    # Parse handlers
    if "handlers" in config_dict:
        handler_configs = []
        for handler_dict in config_dict["handlers"]:
            handler_type = LogHandler(handler_dict["type"])
            handler_config = HandlerConfig(type=handler_type)

            # Apply handler-specific configuration
            for key, value in handler_dict.items():
                if hasattr(handler_config, key) and key != "type":
                    setattr(handler_config, key, value)

            handler_configs.append(handler_config)

        config.handlers = handler_configs

    return ConfigurableAppLogger(config)


# Quick setup functions for common scenarios
def setup_console_logging(
    verbosity: VerbosityLevel = VerbosityLevel.NORMAL,
    format_type: LogFormat = LogFormat.STRUCTURED,
) -> AppLogger:
    """Quick setup for console-only logging."""
    config = LoggingConfig(
        verbosity=verbosity,
        global_format=format_type,
        handlers=[HandlerConfig(type=LogHandler.CONSOLE)],
    )
    return ConfigurableAppLogger(config)


def setup_file_logging(
    filename: str,
    verbosity: VerbosityLevel = VerbosityLevel.NORMAL,
    rotating: bool = True,
) -> AppLogger:
    """Quick setup for file logging."""
    handler_type = LogHandler.ROTATING_FILE if rotating else LogHandler.FILE
    config = LoggingConfig(
        verbosity=verbosity,
        handlers=[HandlerConfig(type=handler_type, filename=filename)],
    )
    return ConfigurableAppLogger(config)


def setup_dual_logging(
    log_file: str, verbosity: VerbosityLevel = VerbosityLevel.NORMAL
) -> AppLogger:
    """Quick setup for both console and file logging."""
    config = LoggingConfig(
        verbosity=verbosity,
        handlers=[
            HandlerConfig(type=LogHandler.CONSOLE, format=LogFormat.SIMPLE),
            HandlerConfig(
                type=LogHandler.ROTATING_FILE,
                filename=log_file,
                format=LogFormat.STRUCTURED,
            ),
        ],
    )
    return ConfigurableAppLogger(config)
