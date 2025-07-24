# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

