"""
Content processor module for reading and concatenating markdown files.

This module implements the Single Responsibility Principle by focusing solely
on reading file contents and formatting them for output.
"""

from pathlib import Path
from typing import List, Optional

from pipedoc.app_logger import get_default_logger, LogContext


class ContentProcessor:
    """
    Responsible for reading and processing markdown file contents.

    This class follows the Single Responsibility Principle by handling
    only the reading and formatting of file contents.
    """

    def __init__(self, base_directory: str):
        """
        Initialise the content processor with a base directory.

        Args:
            base_directory: The root directory for relative path calculations
        """
        self.base_directory = Path(base_directory).expanduser().resolve()
        self._logger = get_default_logger()
        self._log_context = LogContext(component="ContentProcessor")

    def read_file_content(self, file_path: str) -> Optional[str]:
        """
        Read the content of a single file.

        Args:
            file_path: Path to the file to read

        Returns:
            File content as string, or None if reading failed
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                return f.read()
        except (OSError, UnicodeDecodeError) as e:
            self._logger.error(
                "Error reading file",
                context=self._log_context,
                file_path=file_path,
                error=str(e),
            )
            return None

    def create_file_separator(self, file_path: str) -> str:
        """
        Create a separator header for a file.

        Args:
            file_path: Absolute path to the file

        Returns:
            Formatted separator string
        """
        # Resolve both paths to handle symlinks (e.g., /var -> /private/var on macOS)
        file_path_resolved = Path(file_path).resolve()
        base_path_resolved = Path(self.base_directory).resolve()
        relative_path = str(file_path_resolved.relative_to(base_path_resolved))

        separator = f"\n\n{'=' * 60}\n"
        separator += f"FILE: {relative_path}\n"
        separator += f"{'=' * 60}\n\n"
        return separator

    def process_file(self, file_path: str) -> Optional[str]:
        """
        Process a single file by reading its content and adding a separator.

        Args:
            file_path: Path to the file to process

        Returns:
            Processed content with separator, or None if processing failed
        """
        content = self.read_file_content(file_path)
        if content is None:
            return None

        separator = self.create_file_separator(file_path)
        return separator + content

    def concatenate_files(self, file_paths: List[str]) -> str:
        """
        Read and concatenate multiple markdown files.

        Args:
            file_paths: List of file paths to process

        Returns:
            Concatenated content of all files with separators
        """
        if not file_paths:
            return ""

        self._logger.info(
            "Processing markdown files",
            context=self._log_context,
            file_count=len(file_paths),
        )
        content_parts = []

        for file_path in file_paths:
            self._logger.debug(
                "Processing file", context=self._log_context, file_path=file_path
            )
            processed_content = self.process_file(file_path)

            if processed_content is not None:
                content_parts.append(processed_content)

        return "\n\n".join(content_parts)

    def get_content_stats(self, content: str) -> dict:
        """
        Get statistics about the processed content.

        Args:
            content: The processed content string

        Returns:
            Dictionary with content statistics
        """
        return {
            "total_length": len(content),
            "line_count": content.count("\n"),
            "word_count": len(content.split()) if content else 0,
            "character_count": len(content.replace("\n", "").replace(" ", "")),
        }
