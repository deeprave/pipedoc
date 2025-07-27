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

    @patch("select.select")
    @patch("os.close")
    @patch("os.open")
    def test_connection_monitor_detects_pipe_connection_attempts(self, mock_os_open, mock_os_close, mock_select):
        """Test that connection monitor detects pipe connection attempts using select()."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        mock_pipe_fd = 42
        mock_os_open.return_value = mock_pipe_fd
        
        # Simulate select() detecting a connection attempt
        # First call: connection detected, second call: timeout (no more connections)
        mock_select.side_effect = [
            ([mock_pipe_fd], [], []),  # Connection detected
            ([], [], [])  # Timeout - no more connections
        ]
        
        # Track if connection was detected
        connection_detected = []
        
        def mock_spawn_worker():
            connection_detected.append(True)
        
        # Mock the worker spawning method that doesn't exist yet
        manager._spawn_worker = mock_spawn_worker
        
        # Act
        # This method doesn't exist yet - we'll implement it next
        manager._monitor_connections_once()
        
        # Assert
        # Should have opened pipe in non-blocking mode for monitoring
        mock_os_open.assert_called_once_with("/tmp/test_pipe", os.O_RDONLY | os.O_NONBLOCK)
        
        # Should have called select to monitor the pipe
        mock_select.assert_called_once_with([mock_pipe_fd], [], [], 1.0)
        
        # Should have detected the connection and spawned a worker
        assert len(connection_detected) == 1
        
        # Should have properly closed the file descriptor
        mock_os_close.assert_called_once_with(mock_pipe_fd)

    @patch("threading.Thread")
    def test_worker_thread_only_created_when_client_connects(self, mock_thread):
        """Test that worker threads are only created reactively when clients connect."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        
        # Act - call spawn worker (this should create exactly one thread)
        manager._spawn_worker_reactive("test content")
        
        # Assert
        # Should have created exactly one thread
        mock_thread.assert_called_once_with(
            target=manager.serve_client,
            args=(1, "test content"),
            daemon=True
        )
        
        # Should have started the thread
        mock_thread_instance.start.assert_called_once()
        
        # Should NOT have added thread to the unbounded threads list
        # (this verifies we're not using the old preemptive approach)
        assert len(manager.threads) == 0

    @patch("threading.Thread")
    def test_new_worker_spawned_only_after_current_worker_busy(self, mock_thread):
        """Test that exactly one replacement worker is spawned when current worker becomes busy."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        mock_thread_instances = [MagicMock(), MagicMock()]
        mock_thread.side_effect = mock_thread_instances
        
        # Act - start reactive serving which should create initial worker
        manager._start_reactive_serving("test content")
        
        # Simulate the worker becoming busy (this should spawn replacement)
        manager._worker_became_busy()
        
        # Assert
        # Should have created exactly 2 threads: initial + replacement
        assert mock_thread.call_count == 2
        
        # Both threads should have been started
        mock_thread_instances[0].start.assert_called_once()
        mock_thread_instances[1].start.assert_called_once()
        
        # Should maintain exactly one ready worker at all times
        assert manager._get_ready_worker_count() == 1

    @patch("threading.Thread")
    def test_thread_cleanup_prevents_resource_leaks(self, mock_thread):
        """Test that thread cleanup prevents resource leaks through proper worker management."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        # Create multiple mock threads to simulate multiple worker lifecycles
        mock_thread_instances = [MagicMock() for _ in range(5)]
        mock_thread.side_effect = mock_thread_instances
        
        # Act - simulate multiple worker creation and completion cycles
        # Start initial worker
        manager._start_reactive_serving("test content")
        
        # Simulate multiple workers becoming busy and being replaced
        for i in range(4):
            manager._worker_became_busy()
        
        # Simulate workers completing and deregistering themselves
        for i in range(3):
            manager._worker_completed()
        
        # Perform cleanup
        manager._cleanup_reactive_workers()
        
        # Assert
        # Should have created 5 threads total (1 initial + 4 replacements)
        assert mock_thread.call_count == 5
        
        # All threads should have been started
        for thread_instance in mock_thread_instances:
            thread_instance.start.assert_called_once()
        
        # Should NOT be using the old unbounded threads list for tracking
        # (The old implementation would have 5 threads in self.threads)
        assert len(manager.threads) == 0
        
        # Should maintain proper active worker count after cleanup
        # (1 worker remains as the ready worker)
        assert manager._get_active_worker_count() == 1
        
        # Should have exactly one ready worker remaining
        assert manager._get_ready_worker_count() == 1

    @patch("threading.Thread")
    def test_system_recovers_from_worker_thread_failures(self, mock_thread):
        """Test that system recovers from worker thread failures automatically."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        # Create mock threads - some will fail
        # We need extra threads because failed starts trigger retries
        mock_thread_instances = [MagicMock() for _ in range(6)]
        mock_thread.side_effect = mock_thread_instances
        
        # Simulate the second and third threads failing on start
        mock_thread_instances[1].start.side_effect = RuntimeError("Thread failed to start")
        mock_thread_instances[2].start.side_effect = OSError("Resource unavailable")
        
        # Act - start reactive serving
        manager._start_reactive_serving("test content")
        
        # Simulate first worker encountering an error and failing
        manager._worker_failed(RuntimeError("Worker encountered error"))
        
        # Simulate another worker failure
        manager._worker_failed(OSError("Pipe error"))
        
        # System should have attempted recovery by spawning replacements
        
        # Assert
        # Should have created 6 threads total due to recovery attempts:
        # 1 initial (success) -> 1st failure triggers thread 2 (fails) -> 
        # retry with thread 3 (fails) -> retry with thread 4 (success) ->
        # 2nd failure triggers thread 5 (success)
        assert mock_thread.call_count >= 5
        
        # First thread should have started successfully
        mock_thread_instances[0].start.assert_called_once()
        
        # Later threads should have been attempted as recovery
        assert mock_thread_instances[3].start.called or mock_thread_instances[4].start.called
        
        # Should have recovered and maintained exactly one ready worker
        assert manager._get_ready_worker_count() == 1
        
        # Should have proper error tracking
        assert manager._get_worker_failure_count() == 2  # 2 execution failures
        assert manager._get_worker_start_failure_count() == 2  # 2 start failures during recovery
        assert manager._get_total_failure_count() == 4  # Total: 2 + 2 = 4
        
        # System should still be running despite failures
        assert manager.is_running() is True
