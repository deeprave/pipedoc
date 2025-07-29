"""
Tests for the MarkdownPipeServer class.

This module tests the main server functionality, including
orchestration of all components and error handling.
"""

from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from pipedoc.server import MarkdownPipeServer


class TestMarkdownPipeServer:
    """Test cases for MarkdownPipeServer class."""

    def test_init(self, temp_dir: Path):
        """Test initialization of MarkdownPipeServer."""
        server = MarkdownPipeServer(str(temp_dir))

        assert server.docs_directory == str(temp_dir)
        assert server.file_finder is not None
        assert server.content_processor is not None
        assert server.pipe_manager is not None
        assert server.content is None

    def test_validate_setup_valid_directory(self, temp_dir: Path):
        """Test setup validation with valid directory."""
        server = MarkdownPipeServer(str(temp_dir))

        # Should not raise any exception
        server.validate_setup()

    def test_validate_setup_invalid_directory(self, non_existent_dir: Path):
        """Test setup validation with invalid directory."""
        server = MarkdownPipeServer(str(non_existent_dir))

        with pytest.raises(FileNotFoundError):
            server.validate_setup()

    def test_prepare_content_with_files(
        self, temp_dir: Path, sample_markdown_files: List[Path]
    ):
        """Test content preparation with markdown files."""
        server = MarkdownPipeServer(str(temp_dir))
        content = server.prepare_content()

        assert content != ""
        assert server.content == content

        # Check that content from all files is present
        assert "README" in content
        assert "User Guide" in content
        assert "Notes" in content

    def test_prepare_content_no_files(self, empty_dir: Path):
        """Test content preparation with no markdown files."""
        server = MarkdownPipeServer(str(empty_dir))

        with pytest.raises(ValueError, match="No markdown files found"):
            server.prepare_content()

    @patch("signal.signal")
    def test_setup_signal_handlers(self, mock_signal):
        """Test setup of signal handlers."""
        server = MarkdownPipeServer("/tmp")
        server.setup_signal_handlers()

        # Should set up handlers for SIGINT and SIGTERM
        assert mock_signal.call_count == 2

    @patch.object(MarkdownPipeServer, "cleanup")
    @patch.object(MarkdownPipeServer, "setup_signal_handlers")
    def test_run_success(
        self,
        mock_setup_signals,
        mock_cleanup,
        temp_dir: Path,
        sample_markdown_files: List[Path],
        mock_pipe_manager,
    ):
        """Test successful server run."""
        server = MarkdownPipeServer(str(temp_dir))
        server.pipe_manager = mock_pipe_manager

        exit_code = server.run()

        assert exit_code == 0
        mock_setup_signals.assert_called_once()
        mock_cleanup.assert_called_once()
        assert mock_pipe_manager.served_content is not None

    @patch.object(MarkdownPipeServer, "cleanup")
    def test_run_directory_error(self, mock_cleanup, non_existent_dir: Path):
        """Test server run with directory error."""
        server = MarkdownPipeServer(str(non_existent_dir))

        exit_code = server.run()

        assert exit_code == 1
        mock_cleanup.assert_called_once()

    @patch.object(MarkdownPipeServer, "cleanup")
    def test_run_no_content_error(self, mock_cleanup, empty_dir: Path):
        """Test server run with no content error."""
        server = MarkdownPipeServer(str(empty_dir))

        exit_code = server.run()

        assert exit_code == 1
        mock_cleanup.assert_called_once()

    @patch.object(MarkdownPipeServer, "cleanup")
    @patch.object(MarkdownPipeServer, "prepare_content")
    def test_run_pipe_error(self, mock_prepare_content, mock_cleanup, temp_dir: Path):
        """Test server run with pipe creation error."""
        mock_prepare_content.return_value = "test content"

        server = MarkdownPipeServer(str(temp_dir))

        # Mock pipe manager to raise OSError
        server.pipe_manager.create_named_pipe = MagicMock(
            side_effect=OSError("Pipe error")
        )

        exit_code = server.run()

        assert exit_code == 1
        mock_cleanup.assert_called_once()

    @patch.object(MarkdownPipeServer, "cleanup")
    @patch.object(MarkdownPipeServer, "prepare_content")
    def test_run_general_exception(
        self, mock_prepare_content, mock_cleanup, temp_dir: Path
    ):
        """Test server run with general exception."""
        mock_prepare_content.side_effect = Exception("General error")

        server = MarkdownPipeServer(str(temp_dir))

        exit_code = server.run()

        assert exit_code == 1
        mock_cleanup.assert_called_once()

    def test_cleanup(self, temp_dir: Path, mock_pipe_manager):
        """Test server cleanup."""
        server = MarkdownPipeServer(str(temp_dir))
        server.pipe_manager = mock_pipe_manager

        server.cleanup()

        # Cleanup should be called on pipe manager
        assert mock_pipe_manager.running is False

    def test_get_pipe_path(self, temp_dir: Path, mock_pipe_manager):
        """Test getting pipe path."""
        server = MarkdownPipeServer(str(temp_dir))
        server.pipe_manager = mock_pipe_manager

        # Initially None
        assert server.get_pipe_path() is None

        # After setting
        mock_pipe_manager.pipe_path = "/tmp/test_pipe"
        assert server.get_pipe_path() == "/tmp/test_pipe"

    def test_get_content_stats_no_content(self, temp_dir: Path):
        """Test getting content stats when no content is prepared."""
        server = MarkdownPipeServer(str(temp_dir))

        stats = server.get_content_stats()
        assert stats is None

    def test_get_content_stats_with_content(
        self, temp_dir: Path, sample_markdown_files: List[Path]
    ):
        """Test getting content stats with prepared content."""
        server = MarkdownPipeServer(str(temp_dir))
        server.prepare_content()

        stats = server.get_content_stats()

        assert stats is not None
        assert "total_length" in stats
        assert "line_count" in stats
        assert "word_count" in stats
        assert "character_count" in stats

        # All values should be positive
        assert stats["total_length"] > 0
        assert stats["line_count"] > 0
        assert stats["word_count"] > 0
        assert stats["character_count"] > 0

    def test_is_running(self, temp_dir: Path, mock_pipe_manager):
        """Test checking if server is running."""
        server = MarkdownPipeServer(str(temp_dir))
        server.pipe_manager = mock_pipe_manager

        # Initially running (based on mock)
        mock_pipe_manager.running = True
        assert server.is_running() is True

        # After stopping
        mock_pipe_manager.running = False
        assert server.is_running() is False

    def test_integration_with_real_components(
        self, temp_dir: Path, sample_markdown_files: List[Path]
    ):
        """Test integration with real components (not mocked)."""
        server = MarkdownPipeServer(str(temp_dir))

        # Validate setup
        server.validate_setup()

        # Prepare content
        content = server.prepare_content()
        assert content != ""

        # Get stats
        stats = server.get_content_stats()
        assert stats is not None
        assert stats["total_length"] > 0

        # Cleanup
        server.cleanup()

    def test_signal_handler_functionality(self, temp_dir: Path, mock_pipe_manager):
        """Test that signal handler stops the pipe manager."""
        server = MarkdownPipeServer(str(temp_dir))
        server.pipe_manager = mock_pipe_manager

        # Set up signal handlers
        server.setup_signal_handlers()

        # Simulate signal handling by calling stop_serving directly
        server.pipe_manager.stop_serving()

        assert mock_pipe_manager.running is False

    @patch.object(MarkdownPipeServer, "setup_signal_handlers")
    def test_server_stays_running(self, mock_signal_handlers, temp_dir: Path, sample_markdown_files: List[Path]):
        """Test that server doesn't exit immediately after starting."""
        import threading
        import time
        
        server = MarkdownPipeServer(str(temp_dir))
        server_thread = None
        exit_code = None
        
        def run_server():
            nonlocal exit_code
            exit_code = server.run()
        
        # Start server in a thread
        server_thread = threading.Thread(target=run_server)
        server_thread.start()
        
        # Give server time to start
        time.sleep(0.5)
        
        # Server should still be running
        assert server.is_running() is True
        assert server_thread.is_alive() is True
        
        # Stop the server
        server.pipe_manager.stop_serving()
        
        # Wait for thread to complete
        server_thread.join(timeout=2.0)
        
        # Server should have exited cleanly
        assert exit_code == 0
        assert server.is_running() is False
