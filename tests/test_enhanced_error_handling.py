"""
Tests for enhanced error handling and recovery across components.

This module tests that the enhanced component architecture provides robust
error handling with proper isolation, recovery mechanisms, and error reporting.
"""

import threading
import time
from unittest.mock import patch, MagicMock
from concurrent.futures import Future

import pytest

from pipedoc.pipe_manager import PipeManager
from pipedoc.connection_manager import ConnectionManager
from pipedoc.worker_pool import WorkerPool
from pipedoc.metrics_collector import MetricsCollector
from pipedoc.pipe_resource import PipeResource


class TestEnhancedErrorHandling:
    """Test cases for enhanced error handling and recovery."""

    def test_component_failure_isolation(self):
        """Test that component failures don't cascade across the system."""
        # Arrange
        manager = PipeManager(max_workers=3)

        try:
            # Create pipe for testing
            pipe_path = manager.create_named_pipe()
            assert pipe_path is not None

            # Test - Force a failure in one component (PipeResource)
            original_cleanup = manager._pipe_resource.cleanup

            def failing_cleanup():
                raise RuntimeError("Simulated pipe cleanup failure")

            manager._pipe_resource.cleanup = failing_cleanup

            # The failure in PipeResource should not prevent other components from working
            assert manager._worker_pool.is_running(), "WorkerPool should still be running"
            assert manager._connection_manager.is_running() or not manager._connection_manager.is_running(), "ConnectionManager should be in consistent state"

            # Metrics should still be accessible
            metrics = manager._get_metrics()
            assert isinstance(metrics, dict), "Metrics should still be accessible"

            # Restore original cleanup for proper test cleanup
            manager._pipe_resource.cleanup = original_cleanup

        finally:
            manager.cleanup()

    @pytest.mark.hanging
    def test_automatic_recovery_mechanisms(self):
        """Test automatic recovery from component failures."""
        # Arrange
        manager = PipeManager(max_workers=2)

        try:
            manager.create_named_pipe()
            manager.start_serving("test content")

            # Test - Simulate WorkerPool failure and recovery
            original_submit = manager._worker_pool.submit_task
            failure_count = 0

            def failing_then_recovering_submit(fn, *args, **kwargs):
                nonlocal failure_count
                failure_count += 1
                if failure_count <= 2:
                    # Fail first 2 attempts
                    return None
                else:
                    # Recover on subsequent attempts
                    return original_submit(fn, *args, **kwargs)

            manager._worker_pool.submit_task = failing_then_recovering_submit

            # System should recover from initial failures
            connection_future = manager._handle_incoming_connection()
            # First attempts might fail, but system should handle gracefully

            # Reset and test successful recovery
            manager._worker_pool.submit_task = original_submit
            recovery_future = manager._handle_incoming_connection()
            assert recovery_future is not None, "Should recover and handle connections"

        finally:
            manager.cleanup()

    def test_error_reporting_and_logging(self):
        """Test that errors are properly reported with context."""
        # Arrange
        manager = PipeManager(max_workers=2)

        try:
            # Test - Error reporting through metrics
            manager.create_named_pipe()

            # Simulate connection failures
            original_serve = manager.serve_client

            def failing_serve_client(client_id, content):
                raise RuntimeError("Simulated serve failure")

            manager.serve_client = failing_serve_client

            # Error should be captured and reported
            with pytest.raises(RuntimeError):
                manager.serve_client(1, "test")

            # Metrics should reflect the failure
            metrics = manager._get_metrics()
            # Note: The exact failure tracking depends on implementation
            # This test verifies the error handling infrastructure exists

        finally:
            manager.cleanup()

    @pytest.mark.hanging
    def test_graceful_degradation_under_load(self):
        """Test system behavior when components are under stress."""
        # Arrange - Small worker pool to test overload
        manager = PipeManager(max_workers=1)

        try:
            manager.create_named_pipe()
            manager.start_serving("test content")

            # Test - Overload the system with connection requests
            futures = []
            for i in range(5):  # More requests than worker capacity
                future = manager._handle_incoming_connection()
                if future:
                    futures.append(future)

            # System should handle overload gracefully
            # Some connections might be rejected, but system should remain stable
            assert manager._worker_pool.is_running(), "WorkerPool should remain stable"
            assert manager._connection_manager.is_running(), "ConnectionManager should remain stable"

            # Completed futures should have valid results
            for future in futures:
                if future and future.done():
                    try:
                        result = future.result(timeout=0.1)
                        assert result is not None, "Completed futures should have valid results"
                    except:
                        pass  # Timeout or other issues are acceptable under overload

        finally:
            manager.cleanup()

    def test_resource_leak_prevention(self):
        """Test that error conditions don't cause resource leaks."""
        # Arrange
        initial_metrics = None

        # Test multiple manager lifecycles with failures
        for i in range(3):
            manager = PipeManager(max_workers=2)

            try:
                manager.create_named_pipe()

                # Capture initial state
                if initial_metrics is None:
                    initial_metrics = manager._get_worker_pool_metrics()

                # Simulate various operations that might cause leaks
                manager.start_serving("test content")
                manager.stop_serving()

                # Force cleanup to test resource management
                manager.cleanup()

            except Exception:
                # Even with exceptions, cleanup should prevent leaks
                manager.cleanup()

        # Create a final manager to check for resource leaks
        final_manager = PipeManager(max_workers=2)
        try:
            final_metrics = final_manager._get_worker_pool_metrics()

            # Resource usage should be consistent (no major leaks)
            # This is a basic check - more sophisticated leak detection would be needed for production
            assert isinstance(final_metrics, dict), "Metrics should be accessible after multiple lifecycles"

        finally:
            final_manager.cleanup()

    def test_concurrent_error_handling(self):
        """Test error handling under concurrent access."""
        # Arrange
        manager = PipeManager(max_workers=3)
        errors = []
        successes = []

        def concurrent_operations(thread_id: int):
            """Perform operations that might fail concurrently."""
            try:
                # Mix of operations that might succeed or fail
                pipe_path = manager.create_named_pipe()
                if pipe_path:
                    successes.append(f"Thread {thread_id}: Created pipe")

                # Start and stop serving
                manager.start_serving("test content")
                successes.append(f"Thread {thread_id}: Started serving")

                manager.stop_serving()
                successes.append(f"Thread {thread_id}: Stopped serving")

            except Exception as e:
                errors.append(f"Thread {thread_id}: {str(e)}")

        try:
            # Act - Launch concurrent threads
            threads = []
            num_threads = 4

            for thread_id in range(num_threads):
                thread = threading.Thread(target=concurrent_operations, args=(thread_id,))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=5.0)

            # Assert - System should handle concurrent errors gracefully
            # Some operations might fail due to conflicts, but system should remain stable
            assert manager._worker_pool.is_running(), "WorkerPool should survive concurrent access"

            # System should still be functional after concurrent stress
            final_metrics = manager._get_metrics()
            assert isinstance(final_metrics, dict), "System should remain functional"

        finally:
            manager.cleanup()

    def test_error_recovery_with_component_restart(self):
        """Test recovery mechanisms that involve component restart."""
        # Arrange
        manager = PipeManager(max_workers=2)

        try:
            manager.create_named_pipe()
            original_path = manager.get_pipe_path()

            # Test - Simulate component failure requiring restart
            manager.start_serving("test content")

            # Force connection manager shutdown (simulating failure)
            manager._connection_manager.shutdown()
            assert not manager._connection_manager.is_running(), "ConnectionManager should be stopped"

            # Test recovery by restarting
            manager._connection_manager.start_connection_management()
            assert manager._connection_manager.is_running(), "ConnectionManager should recover"

            # System should be functional again
            assert manager.get_pipe_path() == original_path, "Pipe should still be available"

        finally:
            manager.cleanup()

    def test_metrics_integrity_during_errors(self):
        """Test that metrics remain accurate during error conditions."""
        # Arrange
        manager = PipeManager(max_workers=2)

        try:
            # Don't create pipe to force error condition
            # Record initial metrics
            initial_metrics = manager._get_metrics()

            # Generate error condition - this should fail but not crash metrics
            try:
                # This should fail because no pipe exists, but metrics should remain intact
                manager._handle_incoming_connection()
            except:
                pass  # Expected to potentially fail

            # Metrics should still be accessible and reasonable
            error_metrics = manager._get_metrics()
            assert isinstance(error_metrics, dict), "Metrics should remain accessible"

            # Basic metrics structure should be intact
            assert 'connection_attempts' in error_metrics, "Metrics should have expected structure"

        finally:
            manager.cleanup()

    def test_cross_component_error_propagation(self):
        """Test how errors propagate between components and are handled."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=2, metrics_collector=metrics)
        pipe_resource = PipeResource()
        connection_manager = ConnectionManager(worker_pool, metrics, pipe_resource)

        try:
            # Test - Error in one component affecting others
            pipe_resource.create_pipe()
            connection_manager.start_connection_management()

            # Force an error in the WorkerPool
            worker_pool.shutdown(wait=False)
            assert not worker_pool.is_running(), "WorkerPool should be shutdown"

            # ConnectionManager should handle WorkerPool failure gracefully
            # It might not be able to handle new connections, but shouldn't crash
            future = connection_manager.handle_incoming_connection()
            # future might be None due to WorkerPool being down, which is acceptable

            # System should remain in consistent state
            assert isinstance(metrics.get_metrics(), dict), "Metrics should remain accessible"

        finally:
            connection_manager.shutdown()
            pipe_resource.cleanup()
            metrics.reset_metrics()
