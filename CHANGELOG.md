# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unknown] - [Unknown]

### Changed
- **Major Architecture Refactor**: Transformed monolithic PipeManager (735 lines) into component-based architecture following Single Responsibility Principle
- **Component Design**: Split functionality into focused components: MetricsCollector, WorkerPool, PipeResource, ConnectionManager, and orchestrating PipeManager
- **Enhanced Thread Management**: Replaced manual thread handling with enhanced ThreadPoolExecutor wrapper providing better capacity management and error recovery
- **Race Condition Prevention**: Implemented always-ready writer pattern through ConnectionManager to eliminate client connection race conditions
- **Improved Error Handling**: Added component-level error isolation preventing system-wide failures
- **Test Architecture**: Streamlined from 40 legacy tests to 20 focused tests covering component functionality and integration
- **Performance Optimisation**: Reduced component communication overhead and optimised thread pool utilisation

### Added
- **ARCHITECTURE.md**: Comprehensive technical documentation covering system design, component responsibilities, and architecture decisions
- **Component Test Suites**: Individual test files for each component ensuring isolated testing and better coverage
- **Integration Test Suites**: Comprehensive testing of component interactions, error handling, and performance validation
- **Enhanced Metrics**: Thread-safe metrics collection with detailed connection statistics and performance monitoring
- **Connection Management**: Advanced connection lifecycle management with overload protection
- **Connection Queueing System**: FIFO queue for handling connection bursts when worker pool is at capacity
- **Queue Configuration**: Configurable queue size and timeout parameters via PipeManager constructor
- **Queue Metrics**: Comprehensive queue statistics including depth, timeouts, and wait times (PD-005)
- **Background Queue Processor**: Dedicated background worker for processing queued connections (PD-005)
- **Timeout Management**: Automatic cleanup of expired connections with configurable timeout periods (PD-005)
- **Connection Lifecycle Events**: Event-driven architecture for monitoring and responding to connection lifecycle (PD-006)
- **Event System**: General-purpose event system with structured logging and event handlers (PD-006)
- **Event Handlers**: Built-in handlers for logging, statistics, and file output with JSON support (PD-006)

### Enhanced
- **ConnectionManager**: Extended with queue support while maintaining always-ready writer pattern (PD-005)
- **MetricsCollector**: Added queue-specific metrics (queued connections, timeouts, wait times, utilisation) (PD-005)
- **PipeManager**: Added queue configuration parameters with sensible defaults (queue_size=10, queue_timeout=30s) (PD-005)
- **Documentation**: Updated ARCHITECTURE.md and README.md with detailed queue system documentation (PD-005)
- **Event Integration**: ConnectionManager and PipeManager emit lifecycle events for monitoring (PD-006)
- **Structured Logging**: Replaced print statements with structured event-based logging throughout (PD-006)

### Fixed
- **ThreadPoolExecutor Deadlock**: Resolved callback deadlock issues with separate locking strategy
- **Thread Safety**: Eliminated race conditions in component state management and metrics collection
- **Resource Management**: Improved cleanup and lifecycle management across all components

### Technical Notes (PD-005)
- **Queue Type**: Python `queue.Queue` with configurable size limits
- **Processing Model**: FIFO background processor with WorkerPool capacity monitoring  
- **Thread Safety**: Dedicated queue locks to prevent deadlocks with ThreadPoolExecutor
- **Error Handling**: Graceful handling of queue overflow, timeouts, and worker failures
- **Performance**: Minimal overhead for immediate connections, efficient queue processing

## [1.0.0] - 2024-07-24

### Added
- Initial release with SOLID architecture
- Click-based CLI interface for easy command-line usage
- Comprehensive test suite with 72% code coverage
- Package structure with proper entry points
- Multi-client named pipe serving capability
- Graceful shutdown and cleanup handling
- Ruff-based linting and formatting (replaces black, isort, flake8, mypy)
- Justfile-based development workflow (replaces Makefile)
- Coverage reporting with pytest-cov
- Support for multiple markdown file extensions (.md, .markdown, .mdown, .mkd)
- Recursive file discovery in directory structures
- Content processing with clear file separators
- Thread-based multi-client support
- Signal handling for graceful shutdown

### Technical Details
- Python 3.8+ support
- Unix-like system compatibility (for named pipes)
- SOLID principles implementation:
  - Single Responsibility Principle (SRP)
  - Open/Closed Principle (OCP)
  - Dependency Inversion Principle (DIP)
- Comprehensive error handling and logging
- Cross-platform path handling with symlink resolution

### Development Tools
- pytest for testing framework
- pytest-cov for coverage reporting
- ruff for unified linting and formatting
- justfile for development task automation
- UV for dependency management
- Comprehensive development workflow with quality checks

