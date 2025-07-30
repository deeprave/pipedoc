"""
Pipedoc - A Python utility that serves concatenated markdown files through a named pipe.

This package provides functionality to recursively find markdown files in a directory,
concatenate them with clear file separators, and serve the content to multiple processes
simultaneously through a named pipe.
"""

__version__ = "2.0.0"
__author__ = "David L Nugent"
__email__ = "davidn@uniquode.io"

from .content_processor import ContentProcessor
from .file_finder import MarkdownFileFinder
from .pipe_manager import PipeManager
from .server import MarkdownPipeServer

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "ContentProcessor",
    "MarkdownFileFinder",
    "MarkdownPipeServer",
    "PipeManager",
]
