"""
Shared test fixtures and configuration for pipedoc tests.

This module provides common fixtures and utilities used across
all test modules in the pipedoc test suite.
"""

import tempfile
from pathlib import Path
from typing import Generator, List

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Create a temporary directory for testing.

    Yields:
        Path to the temporary directory
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_markdown_files(temp_dir: Path) -> List[Path]:
    """
    Create sample markdown files for testing.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        List of paths to created markdown files
    """
    files = []

    # Create a simple markdown file
    file1 = temp_dir / "readme.md"
    file1.write_text("# README\n\nThis is a sample readme file.\n")
    files.append(file1)

    # Create another markdown file in a subdirectory
    subdir = temp_dir / "docs"
    subdir.mkdir()
    file2 = subdir / "guide.markdown"
    file2.write_text("# User Guide\n\n## Getting Started\n\nWelcome to the guide.\n")
    files.append(file2)

    # Create a file with different extension
    file3 = temp_dir / "notes.mdown"
    file3.write_text("# Notes\n\n- Important note 1\n- Important note 2\n")
    files.append(file3)

    # Create a non-markdown file (should be ignored)
    non_md = temp_dir / "config.txt"
    non_md.write_text("This is not a markdown file")

    return files


@pytest.fixture
def empty_dir(temp_dir: Path) -> Path:
    """
    Create an empty directory for testing.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        Path to the empty directory
    """
    empty = temp_dir / "empty"
    empty.mkdir()
    return empty


@pytest.fixture
def non_existent_dir(temp_dir: Path) -> Path:
    """
    Return a path to a non-existent directory.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        Path to a non-existent directory
    """
    return temp_dir / "does_not_exist"


@pytest.fixture
def sample_content() -> str:
    """
    Return sample markdown content for testing.

    Returns:
        Sample markdown content string
    """
    return """# Test Document

This is a test document with some content.

## Section 1

Some content here.

## Section 2

More content here.
"""


@pytest.fixture
def mock_pipe_path(temp_dir: Path) -> Path:
    """
    Create a mock pipe path for testing.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        Path where a pipe could be created
    """
    return temp_dir / "test_pipe"


class MockPipeManager:
    """Mock pipe manager for testing without creating actual pipes."""

    def __init__(self):
        self.pipe_path = None
        self.running = False
        self.threads = []
        self.served_content = None

    def create_named_pipe(self) -> str:
        self.pipe_path = "/tmp/mock_pipe_12345"
        return self.pipe_path

    def serve_client(self, client_id: int, content: str) -> None:
        self.served_content = content

    def start_serving(self, content: str) -> None:
        self.running = True
        self.served_content = content

    def stop_serving(self) -> None:
        self.running = False

    def cleanup(self) -> None:
        self.running = False
        self.threads.clear()

    def get_pipe_path(self) -> str:
        return self.pipe_path

    def is_running(self) -> bool:
        return self.running


@pytest.fixture
def mock_pipe_manager() -> MockPipeManager:
    """
    Create a mock pipe manager for testing.

    Returns:
        Mock pipe manager instance
    """
    return MockPipeManager()
