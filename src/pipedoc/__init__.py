"""
Pipedoc - A Python utility that serves concatenated markdown files through a named pipe.

This package provides functionality to recursively find markdown files in a directory,
concatenate them with clear file separators, and serve the content to multiple processes
simultaneously through a named pipe.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .content_processor import ContentProcessor
from .file_finder import MarkdownFileFinder
from .pipe_manager import PipeManager
from .server import MarkdownPipeServer

__all__ = [
    "ContentProcessor",
    "MarkdownFileFinder",
    "MarkdownPipeServer",
    "PipeManager",
]
