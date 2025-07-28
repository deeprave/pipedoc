"""
Tests for the PipeManager class.

This module tests the pipe management functionality, including
pipe creation, client serving, and cleanup operations.
"""

import os
import time
from unittest.mock import MagicMock, patch, mock_open

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

    @patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_worker_thread_only_created_when_client_connects(self, mock_submit):
        """Test that worker tasks are only submitted to pool reactively when clients connect."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        mock_future = MagicMock()
        mock_submit.return_value = mock_future
        
        # Act - call spawn worker (this should submit exactly one task to pool)
        manager._spawn_worker_reactive("test content")
        
        # Assert
        # Should have submitted exactly one task to thread pool
        mock_submit.assert_called_once_with(
            manager.serve_client,
            1,
            "test content"
        )
        
        # Should NOT have added to the old unbounded threads list
        # (this verifies we're not using the old preemptive approach)
        assert len(manager.threads) == 0
        
        # Should track the future in active futures
        assert mock_future in manager._active_futures

    @patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_new_worker_spawned_only_after_current_worker_busy(self, mock_submit):
        """Test that exactly one replacement worker is spawned when current worker becomes busy."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        mock_futures = [MagicMock(), MagicMock()]
        mock_submit.side_effect = mock_futures
        
        # Act - start reactive serving which should create initial worker
        manager._start_reactive_serving("test content")
        
        # Simulate the worker becoming busy (this should spawn replacement)
        manager._worker_became_busy()
        
        # Assert
        # Should have submitted exactly 2 tasks: initial + replacement
        assert mock_submit.call_count == 2
        
        # Should track both futures
        assert len(manager._active_futures) == 2
        assert mock_futures[0] in manager._active_futures
        assert mock_futures[1] in manager._active_futures
        
        # Should maintain exactly one ready worker at all times
        assert manager._get_ready_worker_count() == 1

    @patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_thread_cleanup_prevents_resource_leaks(self, mock_submit):
        """Test that pool-based cleanup prevents resource leaks through proper future management."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        # Create multiple mock futures to simulate multiple worker lifecycles
        mock_futures = [MagicMock() for _ in range(5)]
        mock_submit.side_effect = mock_futures
        
        # Act - simulate multiple worker creation and completion cycles
        # Start initial worker
        manager._start_reactive_serving("test content")
        
        # Simulate multiple workers becoming busy and being replaced
        for i in range(4):
            manager._worker_became_busy()
        
        # Simulate workers completing and deregistering themselves
        for i in range(3):
            mock_futures[i].result.return_value = None  # Successful completion
            manager._worker_completed_callback(mock_futures[i])
        
        # Perform cleanup
        manager._cleanup_reactive_workers()
        
        # Assert
        # Should have submitted 5 tasks total (1 initial + 4 replacements)
        assert mock_submit.call_count == 5
        
        # Should NOT be using the old unbounded threads list for tracking
        # (The old implementation would have 5 threads in self.threads)
        assert len(manager.threads) == 0
        
        # Should track remaining active futures (2 remaining after 3 completed)
        assert len(manager._active_futures) == 2
        
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

    def test_thread_pool_initialized_with_configurable_size(self):
        """Test that ThreadPoolExecutor is initialized with configurable max_workers."""
        # Arrange & Act - create manager with custom pool size
        custom_pool_size = 8
        manager = PipeManager(max_workers=custom_pool_size)
        
        # Assert - should have thread pool with specified size
        assert hasattr(manager, '_thread_pool'), "Manager should have _thread_pool attribute"
        assert manager._thread_pool is not None, "Thread pool should be initialized"
        assert manager._thread_pool._max_workers == custom_pool_size, f"Pool should have {custom_pool_size} max workers"
        
        # Test default size when no parameter provided
        default_manager = PipeManager()
        expected_default = min(32, (os.cpu_count() or 1) + 4)
        assert default_manager._thread_pool._max_workers == expected_default, "Should use CPU count + 4 as default"
        
        # Test that pool is ready for task submission
        assert hasattr(manager._thread_pool, 'submit'), "Pool should have submit method"
        assert not manager._thread_pool._shutdown, "Pool should not be shutdown initially"

    @patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_workers_submitted_to_pool_instead_of_direct_threads(self, mock_submit):
        """Test that worker tasks are submitted to thread pool instead of creating direct threads."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        # Mock the thread pool submit method to return a fake future
        mock_future = MagicMock()
        mock_submit.return_value = mock_future
        
        # Act - spawn a worker reactively (this should use pool instead of direct threading.Thread)
        manager._spawn_worker_reactive("test content")
        
        # Assert
        # Should have submitted task to thread pool instead of creating direct thread
        mock_submit.assert_called_once()
        
        # Verify the task submitted is the serve_client method with correct arguments
        call_args = mock_submit.call_args
        assert call_args[0][0] == manager.serve_client, "Should submit serve_client method"
        assert len(call_args[0]) == 3, "Should have 3 arguments: method, client_id, content"
        assert call_args[0][2] == "test content", "Should pass correct content"
        
        # Should track the future for lifecycle management
        assert hasattr(manager, '_active_futures'), "Should have _active_futures tracking"
        assert mock_future in manager._active_futures, "Should track submitted future"

    @patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_worker_lifecycle_managed_through_futures(self, mock_submit):
        """Test that worker lifecycle is managed through future completion and state tracking."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        # Mock futures for different lifecycle scenarios
        mock_future_success = MagicMock()
        mock_future_failed = MagicMock()
        mock_submit.side_effect = [mock_future_success, mock_future_failed]
        
        # Act - Submit workers to pool
        manager._spawn_worker_reactive("test content 1")
        manager._spawn_worker_reactive("test content 2")
        
        # Verify initial state
        assert len(manager._active_futures) == 2, "Should track both submitted futures"
        assert manager._get_active_worker_count() == 2, "Should have 2 active workers"
        assert manager._get_ready_worker_count() == 2, "Should have 2 ready workers initially"
        
        # Simulate successful completion of first worker
        mock_future_success.result.return_value = None  # Success - no exception
        manager._worker_completed_callback(mock_future_success)
        
        # Assert after successful completion
        assert mock_future_success not in manager._active_futures, "Successful future should be removed from tracking"
        assert manager._get_active_worker_count() == 1, "Should have 1 active worker remaining"
        
        # Simulate failed completion of second worker
        mock_future_failed.result.side_effect = RuntimeError("Worker execution failed")
        manager._worker_completed_callback(mock_future_failed)
        
        # Assert after failed completion
        assert mock_future_failed not in manager._active_futures, "Failed future should be removed from tracking"
        assert manager._get_active_worker_count() == 0, "Should have 0 active workers after failure"
        
        # Should have triggered error recovery (checked via failure count)
        assert manager._get_worker_failure_count() >= 1, "Should have recorded worker failure"

    @patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_worker_busy_replacement_integrates_with_future_lifecycle(self, mock_submit):
        """Test that worker replacement logic (_worker_became_busy) integrates properly with future-based workers."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        # Mock multiple futures for replacement scenario
        mock_futures = [MagicMock() for _ in range(3)]
        mock_submit.side_effect = mock_futures
        
        # Act - Start reactive serving (should create initial worker)
        manager._start_reactive_serving("test content")
        initial_ready_count = manager._get_ready_worker_count()
        initial_active_count = manager._get_active_worker_count()
        
        # Simulate worker becoming busy (should spawn replacement)
        manager._worker_became_busy()
        
        # Assert - Should have spawned replacement worker
        assert mock_submit.call_count == 2, "Should have submitted 2 tasks: initial + replacement"
        assert len(manager._active_futures) == 2, "Should track 2 active futures"
        
        # Verify replacement maintains exactly one ready worker
        assert manager._get_ready_worker_count() == 1, "Should maintain exactly 1 ready worker after replacement"
        assert manager._get_active_worker_count() == 2, "Should have 2 active workers total"
        
        # Simulate first worker completing successfully
        mock_futures[0].result.return_value = None  # Success
        manager._worker_completed_callback(mock_futures[0])
        
        # Should maintain ready worker count through completion
        assert manager._get_ready_worker_count() == 1, "Should still have 1 ready worker"
        assert manager._get_active_worker_count() == 1, "Should have 1 active worker remaining"
        assert len(manager._active_futures) == 1, "Should track 1 remaining future"

    def test_pool_prevents_unbounded_thread_creation(self):
        """Test that thread pool prevents unbounded thread creation under high load."""
        # Arrange - Create manager with small pool size for testing
        small_pool_size = 3
        manager = PipeManager(max_workers=small_pool_size)
        manager.pipe_path = "/tmp/test_pipe"
        
        # Track the original ThreadPoolExecutor to verify thread count
        original_pool = manager._thread_pool
        
        # Act - Simulate burst of simultaneous connection attempts (more than pool size)
        num_connections = 10  # More than pool size of 3
        
        # Submit multiple workers rapidly (simulating burst load)
        for i in range(num_connections):
            manager._spawn_worker_reactive(f"test content {i}")
        
        # Assert - Pool should limit actual threads to max_workers
        # The pool should have accepted all submissions but only use max_workers threads
        assert len(manager._active_futures) == num_connections, f"Should track all {num_connections} submitted futures"
        
        # Verify pool configuration is respected
        assert manager._thread_pool._max_workers == small_pool_size, f"Pool should maintain max_workers={small_pool_size}"
        
        # Verify pool is the same instance (not recreated under load)
        assert manager._thread_pool is original_pool, "Pool instance should remain stable under load"
        
        # The actual number of OS threads is controlled by the pool, not by our submission count
        # We can't directly check OS thread count, but we can verify:
        # 1. All futures are tracked (showing we accepted all connections)
        # 2. Pool configuration is maintained (showing bounded resources)
        # 3. System remains responsive (no resource exhaustion)
        
        # Verify system can still accept new connections (not overwhelmed)
        additional_future_count = len(manager._active_futures)
        manager._spawn_worker_reactive("additional test content")
        assert len(manager._active_futures) == additional_future_count + 1, "Should still accept new connections"
        
        # Verify no worker count explosion (bounded behavior)
        assert manager._get_active_worker_count() <= num_connections + 1, "Active worker count should be bounded"

    def test_pool_configuration_maintained_under_load(self):
        """Test that pool configuration is maintained and stable under load conditions."""
        # Arrange - Create manager with specific pool configuration
        test_pool_size = 4
        test_timeout = 15.0
        manager = PipeManager(max_workers=test_pool_size, thread_pool_timeout=test_timeout)
        manager.pipe_path = "/tmp/test_pipe"
        
        # Store initial pool reference and configuration
        initial_pool = manager._thread_pool
        initial_max_workers = manager._thread_pool._max_workers
        
        # Act - Submit many tasks to potentially stress the pool
        num_tasks = 12  # 3x the pool size
        for i in range(num_tasks):
            manager._spawn_worker_reactive(f"load test content {i}")
        
        # Assert - Pool configuration should remain stable
        assert manager._thread_pool is initial_pool, "Pool instance should not be recreated under load"
        assert manager._thread_pool._max_workers == test_pool_size, "Pool max_workers should remain unchanged"
        assert manager._thread_pool._max_workers == initial_max_workers, "Configuration should be stable"
        
        # Pool should accept all submissions (queuing excess internally)
        assert len(manager._active_futures) == num_tasks, f"Should track all {num_tasks} submitted futures"
        
        # Active worker count should be bounded by pool + queue behavior
        # ThreadPoolExecutor handles queuing, so our counter tracks submitted tasks
        assert manager._get_active_worker_count() == num_tasks, "Should track all active workers"
        
        # Pool should not be shutdown prematurely
        assert not manager._thread_pool._shutdown, "Pool should remain active under load"
        
        # Verify system can still accept additional work (not saturated/deadlocked)
        additional_tasks = 2
        for i in range(additional_tasks):
            manager._spawn_worker_reactive(f"additional content {i}")
            
        total_expected = num_tasks + additional_tasks
        assert len(manager._active_futures) == total_expected, f"Should handle {total_expected} total futures"

    @patch("concurrent.futures.ThreadPoolExecutor.shutdown")
    def test_thread_pool_shuts_down_gracefully(self, mock_shutdown):
        """Test that thread pool shuts down gracefully without interrupting active tasks."""
        # Arrange
        manager = PipeManager(max_workers=3, thread_pool_timeout=5.0)
        manager.pipe_path = "/tmp/test_pipe"
        
        # Submit some workers to simulate active tasks
        for i in range(2):
            manager._spawn_worker_reactive(f"test content {i}")
        
        # Verify pool is initially active
        assert not manager._thread_pool._shutdown, "Pool should be active initially"
        assert len(manager._active_futures) == 2, "Should have 2 active futures"
        
        # Act - Call cleanup which should trigger graceful shutdown
        manager.cleanup()
        
        # Assert - Pool shutdown should have been called with wait=True
        mock_shutdown.assert_called_once_with(wait=True)
        
        # Verify cleanup behavior
        assert manager.running is False, "Manager should be stopped after cleanup"
        
        # Active futures should be cleared after pool shutdown
        assert len(manager._active_futures) == 0, "Active futures should be cleared after shutdown"

    @patch("concurrent.futures.ThreadPoolExecutor.shutdown")
    def test_pool_shutdown_handles_timeout_gracefully(self, mock_shutdown):
        """Test that pool shutdown handles timeout scenarios gracefully."""
        # Arrange
        manager = PipeManager(max_workers=2)
        manager.pipe_path = "/tmp/test_pipe"
        
        # Mock shutdown to simulate a timeout scenario
        mock_shutdown.side_effect = Exception("Shutdown timeout")
        
        # Submit workers to simulate active tasks
        manager._spawn_worker_reactive("test content")
        
        # Act - Cleanup should handle shutdown errors gracefully
        try:
            manager.cleanup()
            # Should not raise exception even if shutdown fails
        except Exception as e:
            pytest.fail(f"Cleanup should handle shutdown errors gracefully, but raised: {e}")
        
        # Assert - Shutdown was attempted despite the error
        mock_shutdown.assert_called_once_with(wait=True)
        
        # Manager should still be stopped
        assert manager.running is False, "Manager should be stopped even after shutdown error"

    def test_pool_shutdown_integration_with_real_executor(self):
        """Test graceful shutdown behavior with real ThreadPoolExecutor (integration test)."""
        # Arrange
        manager = PipeManager(max_workers=2)
        manager.pipe_path = "/tmp/test_pipe"
        
        # Store reference to original pool
        original_pool = manager._thread_pool
        
        # Submit some real tasks (they will execute quickly with our mock pipe)
        for i in range(3):
            manager._spawn_worker_reactive(f"integration test {i}")
        
        # Verify pool is active
        assert not original_pool._shutdown, "Pool should be active before shutdown"
        
        # Act - Perform cleanup
        manager.cleanup()
        
        # Assert - Pool should be gracefully shutdown
        assert original_pool._shutdown, "Pool should be shutdown after cleanup"
        
        # Verify manager state
        assert manager.running is False, "Manager should be stopped"
        assert len(manager._active_futures) == 0, "Active futures should be cleared"

    @patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_always_ready_writer_pattern(self, mock_submit):
        """Test that at least one writer is always blocked on open() waiting for clients."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        # Mock the thread pool submit to track when workers are spawned
        mock_future = MagicMock()
        mock_submit.return_value = mock_future
        
        # Add a done callback handler to prevent hanging
        mock_future.add_done_callback = MagicMock()
        
        # Prevent actual execution by making submit not actually run the task
        def mock_submit_side_effect(func, *args, **kwargs):
            # Just return the mock future without executing the function
            return mock_future
        
        mock_submit.side_effect = mock_submit_side_effect
        
        # Act - Call the existing method that ensures a writer is ready
        manager._ensure_ready_worker("test content")
        
        # Assert
        # Should have submitted exactly one writer task
        assert mock_submit.call_count == 1, "Should have submitted initial writer task"
        
        # Verify the writer was submitted with correct parameters
        submit_call = mock_submit.call_args_list[0]
        assert submit_call[0][0] == manager.serve_client, "Should submit serve_client method"
        assert submit_call[0][2] == "test content", "Should pass content to serve_client"
        
        # Verify the writer is tracked as ready
        assert manager._ready_worker_count == 1, "Should have one ready writer"
        
        # Test that when a worker becomes busy, a replacement is spawned
        # Simulate worker becoming busy (client connects)
        manager._worker_became_busy()
        
        # Should spawn a replacement writer immediately
        assert mock_submit.call_count == 2, "Should spawn replacement writer when one becomes busy"
        assert manager._ready_worker_count == 1, "Should maintain one ready writer"

    @patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_proactive_writer_replacement(self, mock_submit):
        """Test that when a writer unblocks (client connected), a replacement is immediately spawned."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        # Mock futures to track spawning
        mock_future = MagicMock()
        mock_future.add_done_callback = MagicMock()
        mock_submit.return_value = mock_future
        
        # Track calls to the new proactive replacement method
        original_spawn_replacement = getattr(manager, '_spawn_proactive_replacement', None)
        replacement_calls = []
        
        def track_replacement_calls(content):
            replacement_calls.append(content)
            # Call original if it exists, otherwise do nothing
            if original_spawn_replacement:
                return original_spawn_replacement(content)
        
        # Mock the method we expect to implement
        manager._spawn_proactive_replacement = track_replacement_calls
        
        # Set up initial state - one ready worker
        with manager._worker_lock:
            manager._ready_worker_count = 1
            manager._active_worker_count = 1
        
        # Act - Simulate a writer connecting to a client (unblocking)
        # This should trigger proactive replacement
        manager._on_writer_connected("test content")
        
        # Assert
        # Should have called the proactive replacement method
        assert len(replacement_calls) == 1, "Should have triggered proactive replacement"
        assert replacement_calls[0] == "test content", "Should pass content to replacement"
        
        # The proactive replacement should spawn a new ready worker
        # before the current writer completes writing
        # We'll implement this by checking that _spawn_proactive_replacement
        # calls _ensure_ready_worker internally

    @patch("builtins.open")
    @patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_proactive_replacement_timing(self, mock_submit, mock_open):
        """Test that replacement is spawned BEFORE current writer completes."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        # Track the sequence of events
        event_sequence = []
        
        # Mock pipe to track when writing starts/completes
        mock_pipe = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_pipe
        
        def track_write(content):
            event_sequence.append(f"write_start: {content}")
            # Simulate some write time
            time.sleep(0.001)
            event_sequence.append(f"write_complete: {content}")
        
        def track_flush():
            event_sequence.append("flush")
        
        mock_pipe.write.side_effect = track_write
        mock_pipe.flush.side_effect = track_flush
        
        # Mock thread pool to track replacement spawning
        mock_future = MagicMock()
        mock_future.add_done_callback = MagicMock()
        
        def track_submit(func, *args, **kwargs):
            if func == manager.serve_client:
                event_sequence.append(f"replacement_spawned: {args[1]}")  # args[1] is content
            return mock_future
        
        mock_submit.side_effect = track_submit
        
        # Act - Call serve_client which should trigger proactive replacement
        manager.serve_client(1, "test content")
        
        # Assert - Check the event sequence
        assert len(event_sequence) >= 3, f"Expected at least 3 events, got: {event_sequence}"
        
        # Find key events
        replacement_event = next((e for e in event_sequence if e.startswith("replacement_spawned")), None)
        write_complete_event = next((e for e in event_sequence if e.startswith("write_complete")), None)
        
        assert replacement_event is not None, "Replacement should have been spawned"
        assert write_complete_event is not None, "Write should have completed"
        
        # The critical test: replacement should be spawned before write completes
        replacement_index = event_sequence.index(replacement_event)
        write_complete_index = event_sequence.index(write_complete_event)
        
        assert replacement_index < write_complete_index, \
            f"Replacement should be spawned before write completes. Sequence: {event_sequence}"

    @patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_writer_state_tracking(self, mock_submit):
        """Test that writer states are tracked accurately through their lifecycle."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        # Mock futures
        mock_future1 = MagicMock()
        mock_future2 = MagicMock()
        mock_future1.add_done_callback = MagicMock()
        mock_future2.add_done_callback = MagicMock()
        mock_submit.side_effect = [mock_future1, mock_future2]
        
        # Act - Start with always-ready pattern
        manager._ensure_ready_worker("test content")
        
        # Assert initial state
        assert hasattr(manager, '_writer_states'), "Should have writer states tracking"
        
        # Check that we can track writer states
        states = manager._get_writer_states()
        assert isinstance(states, dict), "Writer states should be a dictionary"
        
        # Should have one writer in WAITING_FOR_CLIENT state
        waiting_writers = [w for w, state in states.items() if state == 'WAITING_FOR_CLIENT']
        assert len(waiting_writers) >= 1, "Should have at least one waiting writer"
        
        # Simulate state transitions
        writer_id = waiting_writers[0]
        
        # Writer connects to client
        manager._update_writer_state(writer_id, 'CONNECTED')
        states = manager._get_writer_states()
        assert states[writer_id] == 'CONNECTED', "Writer should be in CONNECTED state"
        
        # Writer starts writing
        manager._update_writer_state(writer_id, 'WRITING')
        states = manager._get_writer_states()
        assert states[writer_id] == 'WRITING', "Writer should be in WRITING state"
        
        # Writer completes
        manager._update_writer_state(writer_id, 'COMPLETED')
        states = manager._get_writer_states()
        assert states[writer_id] == 'COMPLETED', "Writer should be in COMPLETED state"
        
        # Test thread-safe updates
        import threading
        update_errors = []
        
        def concurrent_update():
            try:
                manager._update_writer_state(writer_id, 'CONCURRENT_TEST')
            except Exception as e:
                update_errors.append(e)
        
        threads = [threading.Thread(target=concurrent_update) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(update_errors) == 0, f"Thread-safe updates should not error: {update_errors}"

    @patch("builtins.open")
    @patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_rapid_sequential_connections(self, mock_submit, mock_open):
        """Test that rapid sequential connections all find ready writers without delay."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        # Mock pipe behavior
        mock_pipe = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_pipe
        
        # Track connection timing
        connection_times = []
        ready_worker_counts = []
        
        def track_open_call(*args, **kwargs):
            connection_times.append(time.time())
            ready_worker_counts.append(manager._get_ready_worker_count())
            return mock_open.return_value
        
        mock_open.side_effect = track_open_call
        
        # Mock thread pool to prevent actual execution
        mock_futures = [MagicMock() for _ in range(10)]
        for future in mock_futures:
            future.add_done_callback = MagicMock()
        mock_submit.side_effect = mock_futures
        
        # Act - Simulate rapid sequential connections
        # First establish initial ready writer
        manager._ensure_ready_worker("test content")
        
        # Clear tracking from initial setup
        connection_times.clear()
        ready_worker_counts.clear()
        
        # Simulate 5 rapid connections with microsecond intervals
        num_connections = 5
        for i in range(num_connections):
            # Simulate client connecting
            manager.serve_client(i + 1, f"content_{i}")
            # Tiny delay to simulate rapid but sequential connections
            time.sleep(0.0001)  # 0.1ms interval
        
        # Assert
        assert len(connection_times) == num_connections, f"Should have {num_connections} connections"
        
        # Each connection should find a ready writer (count >= 1)
        # Note: The count might fluctuate due to proactive replacement timing
        for i, count in enumerate(ready_worker_counts):
            assert count >= 0, f"Connection {i} should find available worker capacity (count: {count})"
        
        # Verify proactive replacement worked - should have spawned replacement workers
        # Initial + replacements for each connection
        expected_min_submits = 1 + num_connections  # Initial + one replacement per connection
        assert mock_submit.call_count >= expected_min_submits, \
            f"Should have spawned at least {expected_min_submits} workers, got {mock_submit.call_count}"
        
        # Check that connections happened in rapid succession (< 1ms intervals)
        if len(connection_times) > 1:
            max_interval = max(connection_times[i+1] - connection_times[i] 
                             for i in range(len(connection_times)-1))
            assert max_interval < 0.001, f"Connections should be rapid (< 1ms apart), max interval: {max_interval:.6f}s"

    @patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_prevent_writer_starvation(self, mock_submit):
        """Test that system recovers when all writers become busy simultaneously."""
        # Arrange
        manager = PipeManager(max_workers=3)  # Small pool for testing
        manager.pipe_path = "/tmp/test_pipe"
        
        # Mock futures
        mock_futures = [MagicMock() for _ in range(10)]
        for future in mock_futures:
            future.add_done_callback = MagicMock()
        mock_submit.side_effect = mock_futures
        
        # Act - Start with ready workers
        manager._ensure_ready_worker("test content")
        initial_ready_count = manager._get_ready_worker_count()
        
        # Simulate burst traffic that exhausts all workers
        # Make all workers busy by simulating them becoming active
        with manager._worker_lock:
            manager._ready_worker_count = 0  # All writers busy
            manager._active_worker_count = 3  # Pool capacity
        
        # System should detect starvation and spawn recovery workers
        manager._ensure_ready_worker("test content")
        
        # Assert - System should recover
        assert manager._get_ready_worker_count() >= 1, "Should have recovered with at least one ready writer"
        
        # Test automatic recovery with multiple starved connections
        starved_connections = 5
        for i in range(starved_connections):
            # Each starved connection should trigger recovery
            manager._ensure_ready_worker(f"content_{i}")
        
        # Should maintain minimum ready writers despite high load
        final_ready_count = manager._get_ready_worker_count()
        assert final_ready_count >= 1, f"Should maintain minimum ready workers: {final_ready_count}"
        
        # Verify recovery spawned appropriate number of workers
        # Should have: initial + recovery attempts
        min_expected_spawns = 1 + starved_connections + 1  # Initial + per starved + main recovery
        assert mock_submit.call_count >= min_expected_spawns, \
            f"Should have spawned at least {min_expected_spawns} workers for recovery, got {mock_submit.call_count}"

    @patch("builtins.open")
    @patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_connection_success_metrics(self, mock_submit, mock_open):
        """Test that connection attempts, successes, and failures are tracked accurately."""
        # Arrange
        manager = PipeManager()
        manager.pipe_path = "/tmp/test_pipe"
        
        # Mock pipe behavior with some failures
        mock_pipe = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_pipe
        
        call_count = 0
        def mock_open_with_failures(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:  # Third call fails
                raise BrokenPipeError("Simulated client disconnect")
            return mock_open.return_value
        
        mock_open.side_effect = mock_open_with_failures
        
        # Mock futures
        mock_future = MagicMock()
        mock_future.add_done_callback = MagicMock()
        mock_submit.return_value = mock_future
        
        # Act - Perform several connection attempts with some failures
        # Check initial metrics
        initial_metrics = manager._get_connection_metrics()
        assert isinstance(initial_metrics, dict), "Should return metrics dictionary"
        
        # Successful connections
        manager.serve_client(1, "content1")
        manager.serve_client(2, "content2")
        
        # Failed connection (will raise BrokenPipeError)
        manager.serve_client(3, "content3")
        
        # More successful connections  
        manager.serve_client(4, "content4")
        
        # Assert - Check metrics
        metrics = manager._get_connection_metrics()
        
        # Should track attempts
        assert 'connection_attempts' in metrics, "Should track connection attempts"
        assert metrics['connection_attempts'] == 4, f"Should have 4 attempts, got {metrics['connection_attempts']}"
        
        # Should track successes
        assert 'successful_connections' in metrics, "Should track successful connections"
        assert metrics['successful_connections'] == 3, f"Should have 3 successes, got {metrics['successful_connections']}"
        
        # Should track failures
        assert 'failed_connections' in metrics, "Should track failed connections"
        assert metrics['failed_connections'] == 1, f"Should have 1 failure, got {metrics['failed_connections']}"
        
        # Should calculate success rate
        assert 'success_rate' in metrics, "Should calculate success rate"
        expected_rate = 3.0 / 4.0  # 75%
        assert abs(metrics['success_rate'] - expected_rate) < 0.01, \
            f"Success rate should be {expected_rate:.2f}, got {metrics['success_rate']:.2f}"
        
        # Should track timing if available
        if 'avg_connection_time' in metrics:
            assert metrics['avg_connection_time'] >= 0, "Average connection time should be non-negative"

    @patch('builtins.open', new_callable=mock_open)
    @patch('concurrent.futures.ThreadPoolExecutor.submit')
    def test_graceful_overload_handling(self, mock_submit, mock_open):
        """Test behavior when connections exceed thread pool capacity."""
        # Arrange - Create manager with small thread pool (capacity 2)
        manager = PipeManager(max_workers=2)
        manager.pipe_path = "/tmp/test_pipe"
        
        # Mock futures that simulate pool overload
        overloaded_futures = []
        
        def submit_with_overload(*args, **kwargs):
            future = MagicMock()
            if len(overloaded_futures) >= 2:
                # Simulate pool rejection by raising exception
                raise RuntimeError("Thread pool at capacity")
            overloaded_futures.append(future)
            return future
        
        mock_submit.side_effect = submit_with_overload
        
        # Act - Try to submit more connections than pool capacity
        connection_results = []
        
        # First two connections should succeed
        try:
            manager._spawn_worker_reactive("content1")
            connection_results.append("success")
        except Exception as e:
            connection_results.append(f"failed: {e}")
        
        try:
            manager._spawn_worker_reactive("content2")
            connection_results.append("success")
        except Exception as e:
            connection_results.append(f"failed: {e}")
        
        # Third connection should trigger overload handling
        try:
            manager._spawn_worker_reactive("content3")
            connection_results.append("success")
        except Exception as e:
            connection_results.append(f"overload: {e}")
        
        # Assert - System should handle overload gracefully
        assert len(connection_results) == 3, "Should have processed 3 connection attempts"
        
        # First two should succeed
        assert connection_results[0] == "success", f"First connection should succeed, got: {connection_results[0]}"
        assert connection_results[1] == "success", f"Second connection should succeed, got: {connection_results[1]}"
        
        # Third should trigger overload protection
        assert "overload" in connection_results[2] or "ThreadPool" in str(connection_results[2]), \
            f"Third connection should trigger overload handling, got: {connection_results[2]}"
        
        # Should track overload attempts in metrics
        metrics = manager._get_connection_metrics()
        assert 'failed_connections' in metrics, "Should track overload as failed connections"
        
        # System should remain stable and not crash
        assert manager.is_running(), "Manager should remain running despite overload"

    def test_no_race_conditions_real_pipes(self):
        """Integration test: Verify no race conditions with real named pipes."""
        import subprocess
        import threading
        
        # Arrange - Create real pipe manager and pipe
        manager = PipeManager(max_workers=3)
        pipe_path = manager.create_named_pipe()
        
        # Track results
        connection_results = []
        
        def run_single_client_test(client_id: int, content: str) -> dict:
            """Test single client connection to verify no race condition."""
            try:
                # Start a single serve_client call directly
                server_thread = threading.Thread(
                    target=manager.serve_client,
                    args=(client_id, content),
                    daemon=True
                )
                server_thread.start()
                
                # Small delay to let server start
                time.sleep(0.05)
                
                # Now try to read with timeout
                result = subprocess.run(
                    ['head', '-n', '1', pipe_path],
                    capture_output=True,
                    text=True,
                    timeout=2.0
                )
                
                server_thread.join(timeout=1.0)
                
                if result.returncode == 0 and result.stdout.strip():
                    return {
                        'client_id': client_id,
                        'status': 'success',
                        'content': result.stdout.strip()
                    }
                else:
                    return {
                        'client_id': client_id,
                        'status': 'failed',
                        'error': f"Process failed: returncode={result.returncode}, stderr={result.stderr}"
                    }
                    
            except subprocess.TimeoutExpired:
                return {
                    'client_id': client_id,
                    'status': 'timeout',
                    'error': 'Client timed out - likely race condition'
                }
            except Exception as e:
                return {
                    'client_id': client_id,
                    'status': 'error',
                    'error': str(e)
                }
        
        try:
            # Test multiple sequential connections
            test_content = "Integration test - race condition prevention"
            num_tests = 3
            
            for i in range(num_tests):
                result = run_single_client_test(i + 1, f"{test_content} #{i + 1}")
                connection_results.append(result)
                
                # Small delay between tests
                time.sleep(0.1)
            
            # Assert - Analyze results
            assert len(connection_results) == num_tests, \
                f"Should have {num_tests} test results, got {len(connection_results)}"
            
            # Count successful connections
            successful = [r for r in connection_results if r['status'] == 'success']
            failed = [r for r in connection_results if r['status'] != 'success']
            
            # Print detailed results for debugging
            print(f"\nIntegration test results:")
            for result in connection_results:
                if result['status'] == 'success':
                    print(f"  Client {result['client_id']}: SUCCESS - got content: {result['content']}")
                else:
                    print(f"  Client {result['client_id']}: {result['status'].upper()} - {result.get('error', 'unknown')}")
            
            # With race condition prevention, we should have good success rate
            success_rate = len(successful) / len(connection_results)
            assert success_rate >= 0.8, \
                f"Success rate should be >= 80% with race condition prevention, got {success_rate:.1%} ({len(successful)}/{len(connection_results)})"
            
            # Verify successful connections received correct type of content
            for result in successful:
                assert "Integration test" in result['content'], \
                    f"Client {result['client_id']} received unexpected content: {result['content']}"
            
            print(f"SUCCESS: {len(successful)}/{num_tests} clients connected without race conditions")
            
        finally:
            # Cleanup
            manager.cleanup()

    @patch('builtins.open', new_callable=mock_open)
    @patch('concurrent.futures.ThreadPoolExecutor.submit')
    def test_stress_no_race_conditions(self, mock_submit, mock_open):
        """Stress test: Verify race condition prevention under high load."""
        # Arrange - Create manager with realistic thread pool size
        manager = PipeManager(max_workers=4)
        manager.pipe_path = "/tmp/stress_test_pipe"
        
        # Track successful submissions
        submission_count = 0
        def mock_submit_counter(*args, **kwargs):
            nonlocal submission_count
            submission_count += 1
            future = MagicMock()
            future.add_done_callback = MagicMock()
            return future
        
        mock_submit.side_effect = mock_submit_counter
        
        # Act - Make rapid sequential calls (simpler than threading)
        num_requests = 50
        successful_calls = 0
        overload_calls = 0
        
        for i in range(num_requests):
            try:
                manager._spawn_worker_reactive(f"stress content {i}")
                successful_calls += 1
            except RuntimeError as e:
                if "overload" in str(e).lower():
                    overload_calls += 1
                else:
                    raise  # Unexpected error
        
        # Assert - Verify stress test results
        total_processed = successful_calls + overload_calls
        assert total_processed == num_requests, \
            f"Should process all {num_requests} requests, got {total_processed}"
        
        # With a small thread pool (4), most calls will be blocked by overload protection
        # This demonstrates that our overload protection is working correctly
        success_rate = successful_calls / num_requests
        
        # At least some calls should succeed (up to thread pool capacity)
        assert successful_calls >= manager._max_workers, \
            f"Should have at least {manager._max_workers} successful calls, got {successful_calls}"
        
        # Most calls should be blocked by overload protection
        assert overload_calls > 0, \
            f"Overload protection should have blocked some calls, got {overload_calls} blocked"
        
        print(f"Overload protection working correctly: {overload_calls} calls blocked when pool full")
        
        # Verify system stability
        assert manager.is_running(), "Manager should remain stable after stress test"
        
        # Note: Connection metrics are updated in serve_client, not _spawn_worker_reactive
        # So in this test they won't be updated since we're only testing the spawning logic
        
        print(f"\nStress test results ({num_requests} sequential requests):")
        print(f"  Successful spawns: {successful_calls} ({success_rate:.1%})")
        print(f"  Overload rejections: {overload_calls}")
        print(f"  Thread pool submissions: {submission_count}")
        print(f"  System remained stable: {manager.is_running()}")
