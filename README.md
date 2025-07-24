# Pipedoc

A Python utility that serves concatenated markdown files through a named pipe to multiple processes simultaneously.

## Features

- **SOLID Architecture**: Refactored with Single Responsibility Principle, Open/Closed Principle, and Dependency Inversion
- **Click CLI Interface**: Modern command-line interface with extensible commands
- **Comprehensive Testing**: Full test suite with pytest integration
- **Package Structure**: Proper Python package with entry points for easy installation
- **Recursive File Discovery**: Finds all markdown files in directory structure
- **Content Processing**: Concatenates files with clear separators showing file paths
- **Named Pipe Serving**: Creates named pipes for inter-process communication
- **Multi-Client Support**: Serves content to multiple processes simultaneously using threads
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

The project follows SOLID principles with a clean separation of concerns:

### Core Components

- **`MarkdownFileFinder`**: Discovers and filters markdown files (SRP)
- **`ContentProcessor`**: Reads and processes file contents (SRP)
- **`PipeManager`**: Manages named pipe operations (SRP)
- **`MarkdownPipeServer`**: Orchestrates all components (SRP + DIP)
- **`CLI`**: Click-based command-line interface (SRP)

### Package Structure

```
src/pipedoc/
├── __init__.py          # Package exports
├── cli.py              # Click-based CLI interface
├── server.py           # Main server orchestration
├── file_finder.py      # File discovery logic
├── content_processor.py # Content processing logic
└── pipe_manager.py     # Named pipe management

tests/
├── conftest.py         # Shared test fixtures
├── test_file_finder.py # File finder tests
├── test_content_processor.py # Content processor tests
├── test_pipe_manager.py # Pipe manager tests
└── test_server.py      # Server integration tests
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
3. **Named Pipe Creation**: Creates a FIFO pipe for inter-process communication
4. **Multi-Threading**: Each connecting process gets its own thread
5. **Concurrent Serving**: Multiple processes can read simultaneously without interference
6. **Signal Handling**: Graceful shutdown on SIGINT/SIGTERM with proper cleanup

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

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed release notes and version history.
