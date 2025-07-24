"""
Main server module that orchestrates the markdown pipe serving functionality.

This module implements the Dependency Inversion Principle by depending on
abstractions rather than concrete implementations, and follows the Open/Closed
Principle by being open for extension but closed for modification.
"""

import signal
from typing import Optional

from .content_processor import ContentProcessor
from .file_finder import MarkdownFileFinder
from .pipe_manager import PipeManager


class MarkdownPipeServer:
    """
    Main server class that orchestrates markdown file serving through named pipes.

    This class follows SOLID principles:
    - Single Responsibility: Orchestrates the overall serving process
    - Open/Closed: Open for extension, closed for modification
    - Liskov Substitution: Components can be substituted with compatible implementations
    - Interface Segregation: Uses focused, specific interfaces
    - Dependency Inversion: Depends on abstractions, not concretions
    """

    def __init__(self, docs_directory: str):
        """
        Initialize the server with a documentation directory.

        Args:
            docs_directory: Path to the directory containing markdown files
        """
        self.docs_directory = docs_directory
        self.file_finder = MarkdownFileFinder(docs_directory)
        self.content_processor = ContentProcessor(docs_directory)
        self.pipe_manager = PipeManager()
        self.content: Optional[str] = None

    def validate_setup(self) -> None:
        """
        Validate the server setup before starting.

        Raises:
            FileNotFoundError: If the directory doesn't exist
            NotADirectoryError: If the path is not a directory
            PermissionError: If the directory is not accessible
        """
        self.file_finder.validate_directory()

    def prepare_content(self) -> str:
        """
        Prepare the content by finding and processing markdown files.

        Returns:
            Concatenated content of all markdown files

        Raises:
            ValueError: If no markdown files are found
        """
        print(f"Scanning directory: {self.docs_directory}")

        # Find all markdown files
        markdown_files = self.file_finder.find_markdown_files()

        if not markdown_files:
            raise ValueError(f"No markdown files found in {self.docs_directory}")

        # Process and concatenate files
        content = self.content_processor.concatenate_files(markdown_files)

        if not content:
            raise ValueError("No content could be processed from the markdown files")

        # Display content statistics
        stats = self.content_processor.get_content_stats(content)
        print(f"Total content length: {stats['total_length']} characters")
        print(f"Lines: {stats['line_count']}, Words: {stats['word_count']}")

        self.content = content
        return content

    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            print(f"\nReceived signal {signum}, shutting down...")
            self.pipe_manager.stop_serving()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def run(self) -> int:
        """
        Main server execution method.

        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            # Validate setup
            self.validate_setup()

            # Prepare content
            content = self.prepare_content()

            # Create named pipe
            self.pipe_manager.create_named_pipe()

            # Set up signal handlers for graceful shutdown
            self.setup_signal_handlers()

            # Start serving content
            self.pipe_manager.start_serving(content)

            return 0

        except (FileNotFoundError, NotADirectoryError, PermissionError) as e:
            print(f"Directory error: {e}")
            return 1
        except ValueError as e:
            print(f"Content error: {e}")
            return 1
        except OSError as e:
            print(f"Pipe error: {e}")
            return 1
        except Exception as e:
            print(f"Server error: {e}")
            return 1
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Clean up server resources."""
        self.pipe_manager.cleanup()

    def get_pipe_path(self) -> Optional[str]:
        """
        Get the path to the named pipe.

        Returns:
            Path to the named pipe, or None if not created
        """
        return self.pipe_manager.get_pipe_path()

    def get_content_stats(self) -> Optional[dict]:
        """
        Get statistics about the current content.

        Returns:
            Dictionary with content statistics, or None if no content
        """
        if self.content is None:
            return None
        return self.content_processor.get_content_stats(self.content)

    def is_running(self) -> bool:
        """
        Check if the server is currently running.

        Returns:
            True if running, False otherwise
        """
        return self.pipe_manager.is_running()
