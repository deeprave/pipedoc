# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
It is read in addition to the global [CLAUDE.md]($HOME/.claude/CLAUDE.md) file.
Also read [README.md](../README.md) in this project's root to provide additional context.

## Overview

Pipedoc is a Python utility that serves concatenated markdown files through a named pipe to multiple processes simultaneously. It follows SOLID principles with a clean separation of concerns.

## Architecture

The codebase follows SOLID principles with these core components:

- **MarkdownFileFinder** (`file_finder.py`): Discovers markdown files recursively
- **ContentProcessor** (`content_processor.py`): Reads and concatenates file contents
- **PipeManager** (`pipe_manager.py`): Manages named pipe lifecycle and client connections
- **MarkdownPipeServer** (`server.py`): Orchestrates all components using dependency inversion
- **C/quitLI** (`cli.py`): Click-based command interface

## Key Development Notes

- Python 3.11+ is required
- Uses `uv` for package management
- Uses `ruff` for both linting and formatting
- Tests use `pytest` with fixtures defined in `conftest.py`
- The project uses Click for CLI functionality with extensible commands
- Named pipes require Unix-like systems (Linux, macOS)

## Issue management

This project uses a Trello Kanban project for this project.
The columns it has are:
### Backlog
Where cards are placed initially as they are created
### To-Do
When the implementation plan is developed they are added here and ready to be picked up
### Doing
When cards are picked up they are moved here and iterated TDD style
### Done
When the implementation is complete (both plan and acceptance criteria), the card is moved here

## Testing Strategy

- Each component has its own test file with comprehensive unit tests
- Tests use mocking to isolate components
- Fixtures in `conftest.py` provide reusable test data and functionality
- Coverage reports help identify untested code paths
