# Pipedoc

A Python utility that serves concatenated markdown files through a named pipe to multiple processes simultaneously.

## Features

- **SOLID Architecture**: Refactored with Single Responsibility Principle, Open/Closed Principle, and Dependency Inversion
- **Click CLI Interface**: Modern command-line interface with extensible commands
- **Enterprise Logging System**: Comprehensive logging with multiple handlers, formats, and configuration options
- **Version Management**: Detailed version information with multiple output formats and development tracking
- **Comprehensive Testing**: Full test suite with pytest integration
- **Package Structure**: Proper Python package with entry points for easy installation
- **Recursive File Discovery**: Finds all markdown files in directory structure
- **Content Processing**: Concatenates files with clear separators showing file paths
- **Named Pipe Serving**: Creates named pipes for inter-process communication
- **Multi-Client Support**: Serves content to multiple processes simultaneously using threads
- **Connection Queueing**: FIFO queue for handling bursts of simultaneous connections
- **Graceful Shutdown**: Handles signals and cleans up resources properly

## Installation

### From Source (Development)

```bash
# Clone or navigate to the project directory
cd pipedoc

# Install in development mode with uv
uv sync

# Or install with pip
pip install -e .
```

### From Package

```bash
# Install from PyPI (when published)
pip install pipedoc

# Or with uv
uv add pipedoc
```

## Usage

### Basic Usage

```bash
# Serve markdown files from a directory
pipedoc ~/path/to/my/docs

# With verbose output
pipedoc ~/path/to/my/docs --verbose

# Show version
pipedoc --version

# Show help
pipedoc --help
```

### Advanced Commands

```bash
# Get information about markdown files without serving
pipedoc info ~/path/to/my/docs

# Alternative serve command
pipedoc serve ~/path/to/my/docs

# Version management
pipedoc version                    # Show version information
pipedoc version --verbose          # Detailed version with Python and platform info
pipedoc version --json             # Machine-readable JSON output
```

### Logging Options

```bash
# Verbosity levels
pipedoc ~/docs --quiet             # Warnings and errors only
pipedoc ~/docs --verbose           # Debug level (-v)
pipedoc ~/docs -vv                 # Very verbose with detailed context

# Output formats
pipedoc ~/docs --json              # JSON structured logging
pipedoc ~/docs --log-format detailed  # Timestamped detailed format

# File logging
pipedoc ~/docs --log-file app.log  # Log to file in addition to console
pipedoc ~/docs --log-handlers rotating --log-file logs/app.log  # Rotating files

# Component filtering
pipedoc ~/docs --log-exclude WorkerPool,MetricsCollector  # Exclude noisy components
pipedoc ~/docs --log-include-only ConnectionManager       # Only specific components
```

### Environment Configuration

```bash
# Configure logging via environment variables
export PIPEDOC_LOG_VERBOSITY=verbose
export PIPEDOC_LOG_FORMAT=json
export PIPEDOC_LOG_FILE=logs/pipedoc.log
export PIPEDOC_LOG_HANDLERS=console,rotating
pipedoc ~/docs  # Uses environment configuration
```

### Reading from the Pipe

Once the server is running, you can read from the named pipe in other terminals:

```bash
# Terminal 1 (start the server)
pipedoc ~/my-documentation

# Terminal 2 (read from the pipe)
cat /tmp/pipedoc_12345  # Use the actual pipe path shown by the server

# Terminal 3 (another reader)
less /tmp/pipedoc_12345  # Each reader gets the full content independently

# Terminal 4 (process with a script)
python -c "
with open('/tmp/pipedoc_12345', 'r') as f:
    content = f.read()
    print(f'Read {len(content)} characters')
"
```

## Architecture

The project follows SOLID principles with a clean component-based architecture. For detailed technical documentation, see [ARCHITECTURE.md](ARCHITECTURE.md).

### Core Components

- **`MarkdownFileFinder`**: Discovers and filters markdown files (SRP)
- **`ContentProcessor`**: Reads and processes file contents (SRP)
- **`PipeManager`**: Orchestrates specialized pipe management components (SRP)
  - **`MetricsCollector`**: Thread-safe connection statistics, queue metrics, and monitoring
  - **`WorkerPool`**: Enhanced ThreadPoolExecutor wrapper with capacity management
  - **`PipeResource`**: Named pipe lifecycle management
  - **`ConnectionManager`**: Race condition prevention with always-ready writer pattern and FIFO connection queueing
- **`MarkdownPipeServer`**: Orchestrates all components (SRP + DIP)
- **`CLI`**: Click-based command-line interface (SRP)

### Package Structure

```
src/pipedoc/
├── __init__.py              # Package exports and version management
├── cli.py                  # Click-based CLI interface with logging options
├── server.py               # Main server orchestration
├── file_finder.py          # File discovery logic
├── content_processor.py    # Content processing logic
├── pipe_manager.py         # Enhanced pipe manager (orchestrator)
├── metrics_collector.py    # Thread-safe connection metrics
├── worker_pool.py          # Enhanced ThreadPoolExecutor wrapper
├── pipe_resource.py        # Named pipe lifecycle management
├── connection_manager.py   # Race condition prevention
├── app_logger.py           # Application logger interface and implementations
├── logging_config.py       # Comprehensive logging configuration system
├── connection_events.py    # Connection lifecycle events
├── event_handlers.py       # Event handler implementations
└── event_system.py         # General-purpose event system

tests/
├── conftest.py                           # Shared test fixtures
├── test_file_finder.py                   # File finder tests
├── test_content_processor.py             # Content processor tests
├── test_pipe_manager.py                  # Enhanced pipe manager tests
├── test_metrics_collector.py             # Metrics component tests
├── test_worker_pool.py                   # Worker pool component tests
├── test_pipe_resource.py                 # Pipe resource component tests
├── test_connection_manager.py            # Connection manager component tests
├── test_enhanced_pipe_manager_integration.py # Integration tests
├── test_enhanced_error_handling.py       # Error handling tests
├── test_performance_integration.py       # Performance tests
└── test_server.py                        # Server integration tests
```

## Development

### Setup Development Environment

```bash
# Setup with uv (recommended)
uv sync --dev

# Or install in development mode
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run tests
pytest tests/

# Run tests with coverage
pytest tests/ --cov --cov-report=term-missing --cov-report=html

# Using justfile (recommended)
just test           # Run tests only
just coverage       # Run tests with coverage
just coverage-html  # Open coverage report in browser
```

### Code Quality

```bash
# Linting and formatting with ruff
ruff check src/ tests/
ruff check src/ tests/ --fix  # Auto-fix issues
ruff format src/ tests/
ruff format --check src/ tests/  # Check formatting

# Using justfile (recommended)
just lint           # Check linting
just lint-fix       # Fix linting issues
just format         # Format code
just format-check   # Check formatting
just quality        # Run all quality checks
```

### Development Workflow

```bash
# See all available commands
just                    # Show simple recipe list
just help               # Show detailed help with categories and examples

# Common development tasks
just dev-install        # Install with dev dependencies
just quality            # Run linting, formatting, and tests
just coverage           # Generate coverage report
just status             # Show project status
just clean              # Clean up generated files
just setup              # Setup development environment from scratch
```

## Supported File Extensions

- `.md`
- `.markdown`
- `.mdown`
- `.mkd`

## How it Works

1. **File Discovery**: Uses `glob` to recursively find markdown files
2. **Content Processing**: Reads and concatenates files with clear separators
3. **Component Architecture**: Uses specialized components for different responsibilities:
   - **PipeResource**: Creates and manages FIFO pipes
   - **WorkerPool**: Manages ThreadPoolExecutor with capacity control
   - **ConnectionManager**: Prevents race conditions with always-ready writer pattern and connection queueing
   - **MetricsCollector**: Tracks connection statistics and queue metrics thread-safely
4. **Multi-Threading**: Enhanced thread pool serves multiple processes concurrently
5. **Connection Queueing**: FIFO queue handles connection bursts when worker pool is at capacity
6. **Race-Free Serving**: Always-ready writer pattern eliminates connection timing issues
7. **Error Isolation**: Component failures don't cascade across the system
8. **Signal Handling**: Graceful shutdown on SIGINT/SIGTERM with proper cleanup

## Examples

### Example Output Format

When files are concatenated, they include clear separators:

```
============================================================
FILE: README.md
============================================================

# My Project

This is the main readme file.

============================================================
FILE: docs/guide.md
============================================================

# User Guide

Detailed usage instructions here.
```

### Integration with Other Tools

```bash
# Use with grep to search across all files
pipedoc ~/docs | grep "TODO"

# Use with word count
pipedoc ~/docs | wc -w

# Use with a custom processor
pipedoc ~/docs | python my_processor.py
```

## Requirements

- Python 3.8+
- Unix-like system (for named pipes)
- Click 8.0+ (for CLI functionality)

## Development Dependencies

- pytest 8.0+ (testing)
- pytest-cov 6.0+ (coverage reporting)
- ruff 0.12+ (linting and formatting)
- just (command runner, optional but recommended)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes following SOLID principles
4. Add comprehensive tests
5. Ensure code quality checks pass
6. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Detailed technical architecture and component design
- **[CHANGELOG.md](CHANGELOG.md)**: Release notes and version history
- **[LOGGING.md](LOGGING.md)**: Comprehensive logging configuration guide
- **[EVENTS.md](EVENTS.md)**: Event system documentation and lifecycle monitoring
