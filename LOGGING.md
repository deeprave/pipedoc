# Logging Configuration Guide

Pipedoc provides comprehensive logging capabilities with configurable verbosity levels, multiple output handlers, and component-based filtering.

## Quick Start

### Basic Usage

```bash
# Default logging (INFO level, simple format, console output)
pipedoc ~/my-docs

# Verbose logging
pipedoc ~/my-docs --verbose              # -v for DEBUG level
pipedoc ~/my-docs -vv                    # -vv for VERY_VERBOSE

# Quiet logging (warnings and errors only)
pipedoc ~/my-docs --quiet
```

### File Logging

```bash
# Log to file in addition to console
pipedoc ~/my-docs --log-file pipedoc.log

# Use rotating file handler
pipedoc ~/my-docs --log-handlers console,rotating --log-file logs/pipedoc.log
```

### Custom Configuration

```bash
# JSON format with DEBUG level
pipedoc ~/my-docs --log-level DEBUG --log-format json

# Using the --json alias
pipedoc ~/my-docs --json --log-level DEBUG

# Detailed format with timestamp
pipedoc ~/my-docs --log-format detailed --verbose

# Multiple handlers
pipedoc ~/my-docs --log-handlers console,file,syslog --log-file /var/log/pipedoc.log
```

## Verbosity Levels

| Level | CLI Option | Environment | Description |
|-------|------------|-------------|-------------|
| SILENT | N/A | `PIPEDOC_LOG_VERBOSITY=silent` | Critical errors only |
| QUIET | `--quiet` | `PIPEDOC_LOG_VERBOSITY=quiet` | Warnings and errors |
| NORMAL | (default) | `PIPEDOC_LOG_VERBOSITY=normal` | Info, warnings, errors |
| VERBOSE | `-v` | `PIPEDOC_LOG_VERBOSITY=verbose` | Debug and above |
| VERY_VERBOSE | `-vv` | `PIPEDOC_LOG_VERBOSITY=very_verbose` | All levels with detailed context |

## Output Formats

### Simple Format (Default)
```
INFO: Connection accepted for immediate processing [ConnectionManager] (connection_id=conn_1)
```

### JSON Format
```json
{
  "message": "Connection accepted for immediate processing",
  "timestamp": 1753858660.407,
  "component": "ConnectionManager",
  "operation": "_process_connection_immediately",
  "additional": {
    "connection_id": "conn_1",
    "active_connections": 1
  }
}
```

### Detailed Format
```
2025-07-30 16:57:40 [INFO] pipedoc: Connection accepted [ConnectionManager] (connection_id=conn_1)
```

## Output Handlers

### Console Handler
Default handler that outputs to stderr.

```bash
pipedoc ~/docs --log-handlers console
```

### File Handler
Writes logs to a single file.

```bash
pipedoc ~/docs --log-handlers file --log-file app.log
```

### Rotating File Handler
Automatically rotates log files when they reach size limit.

```bash
pipedoc ~/docs --log-handlers rotating --log-file logs/app.log
```

Configuration:
- Max file size: 10MB
- Backup count: 5 files
- Files: `app.log`, `app.log.1`, `app.log.2`, etc.

### Syslog Handler
Sends logs to system syslog daemon.

```bash
pipedoc ~/docs --log-handlers syslog
```

### Multiple Handlers
```bash
# Console + rotating file
pipedoc ~/docs --log-handlers console,rotating --log-file logs/app.log

# Console + syslog
pipedoc ~/docs --log-handlers console,syslog
```

## Component Filtering

### Exclude Components
```bash
# Exclude noisy components
pipedoc ~/docs --log-exclude WorkerPool,MetricsCollector
```

### Include Only Specific Components
```bash
# Only log from ConnectionManager
pipedoc ~/docs --log-include-only ConnectionManager
```

## Environment Variables

All CLI options can be configured via environment variables:

```bash
export PIPEDOC_LOG_VERBOSITY=verbose
export PIPEDOC_LOG_FORMAT=json
export PIPEDOC_LOG_HANDLERS=console,rotating
export PIPEDOC_LOG_FILE=logs/pipedoc.log
export PIPEDOC_LOG_EXCLUDE=WorkerPool
export PIPEDOC_LOG_INCLUDE_ONLY=ConnectionManager,PipeManager
```

## Programmatic Configuration

### Quick Setup Functions

```python
from pipedoc.logging_config import setup_console_logging, setup_file_logging, setup_dual_logging
from pipedoc.logging_config import VerbosityLevel, LogFormat

# Console only
logger = setup_console_logging(verbosity=VerbosityLevel.VERBOSE, format_type=LogFormat.SIMPLE)

# File only
logger = setup_file_logging("app.log", verbosity=VerbosityLevel.NORMAL, rotating=True)

# Console + File
logger = setup_dual_logging("app.log", verbosity=VerbosityLevel.VERBOSE)
```

### Custom Configuration

```python
from pipedoc.logging_config import LoggingConfig, HandlerConfig, LogHandler, LogFormat, VerbosityLevel, ConfigurableAppLogger
from pipedoc.app_logger import AppLogger, StandardAppLogger, LogContext

config = LoggingConfig(
    verbosity=VerbosityLevel.VERBOSE,
    global_format=LogFormat.STRUCTURED,  # JSON format
    handlers=[
        HandlerConfig(
            type=LogHandler.CONSOLE,
            format=LogFormat.SIMPLE,
            level="INFO"
        ),
        HandlerConfig(
            type=LogHandler.ROTATING_FILE,
            filename="logs/app.log",
            format=LogFormat.STRUCTURED,
            max_bytes=20 * 1024 * 1024,  # 20MB
            backup_count=10
        )
    ],
    exclude_components=["NoisyComponent"],
    component_levels={
        "ImportantComponent": "DEBUG",
        "QuietComponent": "ERROR"
    }
)

logger = ConfigurableAppLogger(config)
```

### Runtime Reconfiguration

```python
# Change configuration at runtime
new_config = LoggingConfig(verbosity=VerbosityLevel.QUIET)
logger.reconfigure(new_config)
```

### Using the Application Logger Interface

```python
from pipedoc.app_logger import LogContext, get_default_logger

# Get the default configured logger
logger = get_default_logger()

# Simple logging with component context
logger.info("Connection established", LogContext(component="ConnectionManager"))

# Structured logging with metadata
context = LogContext(
    component="ConnectionManager",
    operation="handle_connection",
    correlation_id="conn_123"
)
logger.info("Processing connection", context, client_id="user_456", timeout=30.0)

# Convenience functions (uses default logger)
from pipedoc import app_logger
app_logger.info("Task completed", "WorkerPool", task_id="task_789")
app_logger.error("Connection failed", "ConnectionManager", exc_info=True, error_code="CONN_REFUSED")
```

## Log Components

The following components generate logs:

| Component | Description | Typical Volume |
|-----------|-------------|----------------|
| `ConnectionManager` | Connection lifecycle, queuing | High |
| `WorkerPool` | Task management, capacity | Medium |
| `PipeManager` | Pipe operations, serving | Medium |
| `Server` | Application lifecycle | Low |
| `ContentProcessor` | File processing | Low |
| `EventManager` | Event dispatching | Low |

## Performance Considerations

- **Null Handler**: For maximum performance, use null handler in production
- **Async Logging**: Future feature for high-throughput scenarios
- **Component Filtering**: Reduce log volume by excluding verbose components
- **File vs Console**: File logging is generally faster than console

## Troubleshooting

### High Log Volume
```bash
# Reduce verbosity
pipedoc ~/docs --quiet

# Exclude verbose components
pipedoc ~/docs --log-exclude WorkerPool,ConnectionManager
```

### Missing Logs
```bash
# Increase verbosity
pipedoc ~/docs -vv

# Check specific components
pipedoc ~/docs --log-include-only ConnectionManager --verbose
```

### File Permission Issues
```bash
# Ensure directory exists and is writable
mkdir -p logs
chmod 755 logs

# Use different location
pipedoc ~/docs --log-file /tmp/pipedoc.log
```

### Syslog Issues
```bash
# Test syslog connectivity
logger "Test message"

# Use TCP syslog for remote servers
# (requires custom configuration)
```

## Examples

### Development Environment
```bash
# Verbose console logging with JSON format
pipedoc ~/docs -vv --log-format json

# Using the --json alias
pipedoc ~/docs -vv --json
```

### Production Environment
```bash
# Quiet file logging with rotation
pipedoc ~/docs --quiet --log-handlers rotating --log-file /var/log/pipedoc/app.log
```

### Debugging Connection Issues
```bash
# Focus on connection-related components
pipedoc ~/docs --log-include-only ConnectionManager,WorkerPool --verbose --log-format detailed
```

### Performance Monitoring
```bash
# Exclude debug info, focus on performance metrics
pipedoc ~/docs --quiet --log-include-only MetricsCollector,Server
```
