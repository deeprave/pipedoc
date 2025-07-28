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
