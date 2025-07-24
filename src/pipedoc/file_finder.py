"""
File finder module for discovering markdown files.

This module implements the Single Responsibility Principle by focusing solely
on finding and filtering markdown files in a directory structure.
"""

import glob
from pathlib import Path
from typing import ClassVar, List


class MarkdownFileFinder:
    """
    Responsible for finding markdown files in a directory structure.

    This class follows the Single Responsibility Principle by handling
    only the discovery and filtering of markdown files.
    """

    MARKDOWN_EXTENSIONS: ClassVar[List[str]] = [
        "*.md",
        "*.markdown",
        "*.mdown",
        "*.mkd",
    ]

    def __init__(self, base_directory: str):
        """
        Initialize the file finder with a base directory.

        Args:
            base_directory: The root directory to search for markdown files
        """
        self.base_directory = Path(base_directory).expanduser().resolve()

    def find_markdown_files(self) -> List[str]:
        """
        Find all markdown files in the directory recursively.

        Returns:
            List of absolute paths to markdown files, sorted for consistent ordering

        Raises:
            FileNotFoundError: If the base directory doesn't exist
            PermissionError: If the directory is not accessible
        """
        if not self.base_directory.exists():
            raise FileNotFoundError(f"Directory {self.base_directory} does not exist")

        if not self.base_directory.is_dir():
            raise NotADirectoryError(f"{self.base_directory} is not a directory")

        markdown_files = []

        for extension in self.MARKDOWN_EXTENSIONS:
            # Use recursive glob to find files
            pattern = str(self.base_directory / "**" / extension)
            markdown_files.extend(glob.glob(pattern, recursive=True))

        # Sort files for consistent ordering
        return sorted(markdown_files)

    def get_relative_path(self, file_path: str) -> str:
        """
        Get the relative path of a file from the base directory.

        Args:
            file_path: Absolute path to the file

        Returns:
            Relative path from the base directory
        """
        # Resolve both paths to handle symlinks (e.g., /var -> /private/var on macOS)
        file_path_resolved = Path(file_path).resolve()
        base_path_resolved = Path(self.base_directory).resolve()
        return str(file_path_resolved.relative_to(base_path_resolved))

    def validate_directory(self) -> None:
        """
        Validate that the base directory exists and is accessible.

        Raises:
            FileNotFoundError: If the directory doesn't exist
            NotADirectoryError: If the path is not a directory
            PermissionError: If the directory is not accessible
        """
        if not self.base_directory.exists():
            raise FileNotFoundError(f"Directory {self.base_directory} does not exist")

        if not self.base_directory.is_dir():
            raise NotADirectoryError(f"{self.base_directory} is not a directory")

        # Test if we can read the directory
        try:
            list(self.base_directory.iterdir())
        except PermissionError as e:
            raise PermissionError(f"Cannot access directory {self.base_directory}: {e}")
