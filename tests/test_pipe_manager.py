"""
Tests for the PipeManager class.

This module tests the pipe management functionality, including
pipe creation, client serving, and cleanup operations.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from pipedoc.pipe_manager import PipeManager


class TestPipeManager:
    """Test cases for PipeManager class."""

    def test_init(self):
        """Test initialization of PipeManager."""
        manager = PipeManager()

        assert manager.pipe_path is None
        assert manager.running is True
        assert manager.threads == []

    @patch("os.mkfifo")
    @patch("os.path.exists")
    @patch("os.unlink")
    def test_create_named_pipe_success(self, mock_unlink, mock_exists, mock_mkfifo):
        """Test successful creation of named pipe."""
        mock_exists.return_value = False

        manager = PipeManager()
        pipe_path = manager.create_named_pipe()

        assert pipe_path is not None
        assert manager.pipe_path == pipe_path
        assert f"pipedoc_{os.getpid()}" in pipe_path
        mock_mkfifo.assert_called_once_with(pipe_path)

    @patch("os.mkfifo")
    @patch("os.path.exists")
    @patch("os.unlink")
    def test_create_named_pipe_existing_pipe(
        self, mock_unlink, mock_exists, mock_mkfifo
    ):
        """Test creation of named pipe when one already exists."""
        mock_exists.return_value = True

        manager = PipeManager()
        pipe_path = manager.create_named_pipe()

        assert pipe_path is not None
        mock_unlink.assert_called_once()
        mock_mkfifo.assert_called_once_with(pipe_path)

    @patch("os.mkfifo")
    @patch("os.path.exists")
    def test_create_named_pipe_failure(self, mock_exists, mock_mkfifo):
        """Test failure in creating named pipe."""
        mock_exists.return_value = False
        mock_mkfifo.side_effect = OSError("Permission denied")

        manager = PipeManager()

        with pytest.raises(OSError, match="Failed to create named pipe"):
            manager.create_named_pipe()

    @patch("builtins.open")
    def test_serve_client_success(self, mock_open):
        """Test successful client serving."""
        mock_pipe = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_pipe

        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"

        test_content = "Test content"
        manager.serve_client(1, test_content)

        mock_open.assert_called_once_with("/tmp/test_pipe", "w")
        mock_pipe.write.assert_called_once_with(test_content)
        mock_pipe.flush.assert_called_once()

    @patch("builtins.open")
    def test_serve_client_broken_pipe(self, mock_open):
        """Test client serving with broken pipe."""
        mock_pipe = MagicMock()
        mock_pipe.write.side_effect = BrokenPipeError()
        mock_open.return_value.__enter__.return_value = mock_pipe

        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"

        # Should not raise exception, just handle gracefully
        manager.serve_client(1, "test content")

        mock_pipe.write.assert_called_once()

    @patch("builtins.open")
    def test_serve_client_general_exception(self, mock_open):
        """Test client serving with general exception."""
        mock_open.side_effect = Exception("General error")

        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"

        # Should not raise exception, just handle gracefully
        manager.serve_client(1, "test content")

    @patch("threading.Thread")
    @patch("time.sleep")
    def test_start_serving_single_client(self, mock_sleep, mock_thread):
        """Test starting to serve with a single client connection."""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"

        # Mock sleep to break the loop after first iteration
        def side_effect(*args):
            manager.running = False

        mock_sleep.side_effect = side_effect

        manager.start_serving("test content")

        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
        assert mock_thread_instance in manager.threads

    @patch("threading.Thread")
    def test_start_serving_keyboard_interrupt(self, mock_thread):
        """Test handling keyboard interrupt during serving."""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        mock_thread_instance.start.side_effect = KeyboardInterrupt()

        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"

        manager.start_serving("test content")

        assert manager.running is False

    def test_stop_serving(self):
        """Test stopping the serving process."""
        manager = PipeManager()
        manager.running = True

        manager.stop_serving()

        assert manager.running is False

    @patch("os.path.exists")
    @patch("os.unlink")
    def test_cleanup_with_pipe(self, mock_unlink, mock_exists):
        """Test cleanup with existing pipe."""
        mock_exists.return_value = True

        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        manager.running = True

        # Add a mock thread
        mock_thread = MagicMock()
        manager.threads.append(mock_thread)

        manager.cleanup()

        assert manager.running is False
        mock_thread.join.assert_called_once_with(timeout=1.0)
        mock_unlink.assert_called_once_with("/tmp/test_pipe")
        assert manager.threads == []

    @patch("os.path.exists")
    @patch("os.unlink")
    def test_cleanup_unlink_error(self, mock_unlink, mock_exists):
        """Test cleanup when unlink fails."""
        mock_exists.return_value = True
        mock_unlink.side_effect = OSError("Permission denied")

        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"

        # Should not raise exception
        manager.cleanup()

        assert manager.running is False

    def test_cleanup_no_pipe(self):
        """Test cleanup when no pipe exists."""
        manager = PipeManager()
        manager.pipe_path = None

        # Should not raise exception
        manager.cleanup()

        assert manager.running is False

    def test_get_pipe_path(self):
        """Test getting pipe path."""
        manager = PipeManager()

        # Initially None
        assert manager.get_pipe_path() is None

        # After setting
        manager.pipe_path = "/tmp/test_pipe"
        assert manager.get_pipe_path() == "/tmp/test_pipe"

    def test_is_running(self):
        """Test checking if manager is running."""
        manager = PipeManager()

        # Initially running
        assert manager.is_running() is True

        # After stopping
        manager.running = False
        assert manager.is_running() is False

    @patch("threading.Thread")
    @patch("time.sleep")
    def test_multiple_clients(self, mock_sleep, mock_thread):
        """Test handling multiple client connections."""
        mock_thread_instances = [MagicMock() for _ in range(3)]
        mock_thread.side_effect = mock_thread_instances

        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"

        # Mock sleep to break the loop after 3 iterations
        call_count = 0

        def side_effect(*args):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                manager.running = False

        mock_sleep.side_effect = side_effect

        manager.start_serving("test content")

        # Should have created 3 threads
        assert mock_thread.call_count == 3
        for thread_instance in mock_thread_instances:
            thread_instance.start.assert_called_once()

        assert len(manager.threads) == 3
