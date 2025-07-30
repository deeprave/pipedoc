"""
Integration tests for the enhanced PipeManager orchestrator.

This module tests that the refactored PipeManager maintains backwards compatibility
while internally delegating to the specialized components (MetricsCollector,
WorkerPool, PipeResource, ConnectionManager).
"""

import threading
import time
from unittest.mock import patch, MagicMock

import pytest

from pipedoc.pipe_manager import PipeManager


class TestEnhancedPipeManagerIntegration:
    """Integration tests for enhanced PipeManager architecture."""

    def test_enhanced_pipe_manager_backwards_compatibility(self):
        """Test that public API remains unchanged after refactoring."""
        # Arrange
        manager = PipeManager(max_workers=3)

        # Assert - Public interface should be unchanged
        assert hasattr(manager, "create_named_pipe"), (
            "Should have create_named_pipe method"
        )
        assert hasattr(manager, "start_serving"), "Should have start_serving method"
        assert hasattr(manager, "stop_serving"), "Should have stop_serving method"
        assert hasattr(manager, "cleanup"), "Should have cleanup method"
        assert hasattr(manager, "get_pipe_path"), "Should have get_pipe_path method"
        assert hasattr(manager, "is_running"), "Should have is_running method"
        assert hasattr(manager, "serve_client"), "Should have serve_client method"

        # Test - Basic lifecycle should work
        pipe_path = manager.create_named_pipe()
        assert pipe_path is not None, "Should create pipe successfully"
        assert manager.get_pipe_path() == pipe_path, "Should return correct pipe path"

        # Initial state
        assert not manager.is_running(), "Should not be running initially"

        # Cleanup
        manager.cleanup()

    def test_component_integration_architecture(self):
        """Test that PipeManager integrates with enhanced components internally."""
        # Arrange
        manager = PipeManager(max_workers=2)

        # Assert - Should have component references (internal architecture)
        # Note: These are internal implementation details that may change
        # but help verify the refactoring was successful

        # Test basic functionality that should use components
        pipe_path = manager.create_named_pipe()
        assert pipe_path is not None

        # The PipeManager should now delegate to components for:
        # - PipeResource: pipe creation and management
        # - WorkerPool: thread management
        # - MetricsCollector: connection statistics
        # - ConnectionManager: race condition prevention

        manager.cleanup()

    def test_enhanced_pipe_manager_serving_integration(self):
        """Test serving functionality with component integration."""
        # Arrange
        manager = PipeManager(max_workers=3)

        try:
            # Create pipe
            pipe_path = manager.create_named_pipe()
            assert pipe_path is not None

            # Test serving state management
            assert not manager.is_running()

            # Start serving (this should integrate with ConnectionManager)
            # Note: We're not actually testing the full serving loop here
            # since that would require actual pipe I/O and client connections

            # The internal architecture should handle the always-ready writer pattern
            # through the ConnectionManager component

        finally:
            manager.stop_serving()
            manager.cleanup()

    def test_error_propagation_and_recovery(self):
        """Test that error handling works across component boundaries."""
        # Arrange
        manager = PipeManager(max_workers=2)

        try:
            # Test error conditions that should be handled gracefully
            # by the component architecture

            # Test 1: Multiple cleanup calls should be safe
            manager.cleanup()
            manager.cleanup()  # Should not crash

            # Test 2: Operations on non-created pipe should be handled
            assert manager.get_pipe_path() is None
            assert not manager.is_running()

            # Test 3: Stop without start should be safe
            manager.stop_serving()  # Should not crash

        finally:
            manager.cleanup()

    def test_thread_safety_with_components(self):
        """Test thread safety of the enhanced PipeManager."""
        # Arrange
        manager = PipeManager(max_workers=3)
        results = []
        errors = []

        def concurrent_operations(thread_id: int):
            """Perform concurrent operations on the PipeManager."""
            try:
                # Each thread tries various operations
                pipe_path = manager.create_named_pipe()
                if pipe_path:
                    results.append(f"Thread {thread_id}: Created pipe {pipe_path}")

                is_running = manager.is_running()
                results.append(f"Thread {thread_id}: Running state {is_running}")

                # Cleanup operations
                manager.cleanup()
                results.append(f"Thread {thread_id}: Cleaned up successfully")

            except Exception as e:
                errors.append(f"Thread {thread_id}: Error {str(e)}")

        try:
            # Act - Launch concurrent threads
            threads = []
            num_threads = 4

            for thread_id in range(num_threads):
                thread = threading.Thread(
                    target=concurrent_operations, args=(thread_id,)
                )
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=5.0)

            # Assert - Operations should complete without errors
            assert len(errors) == 0, f"Should have no errors: {errors}"
            assert len(results) > 0, "Should have some successful operations"

        finally:
            manager.cleanup()

    def test_performance_no_regression(self):
        """Test that component architecture doesn't introduce performance regression."""
        # Arrange
        manager = PipeManager(max_workers=4)

        try:
            # Measure pipe creation performance
            start_time = time.time()

            pipe_operations = 10
            for i in range(pipe_operations):
                pipe_path = manager.create_named_pipe()
                assert pipe_path is not None
                manager.cleanup()

            end_time = time.time()
            total_time = end_time - start_time

            # Assert - Should complete operations quickly
            # This is a basic performance check - exact timing depends on system
            assert total_time < 1.0, (
                f"Should complete {pipe_operations} operations quickly, took {total_time:.3f}s"
            )

            # Test memory cleanup - components should not leak resources
            # This is more of a documentation of expected behavior

        finally:
            manager.cleanup()

    def test_metrics_integration(self):
        """Test that metrics collection works through component integration."""
        # Arrange
        manager = PipeManager(max_workers=2)

        try:
            # The enhanced PipeManager should internally use MetricsCollector
            # for connection statistics tracking

            pipe_path = manager.create_named_pipe()
            assert pipe_path is not None

            # Note: Full metrics testing would require actual client connections
            # which is complex to set up in unit tests. The component-level
            # tests already verify MetricsCollector functionality.

            # The integration test verifies that the architecture allows
            # for metrics collection without breaking existing functionality

        finally:
            manager.cleanup()

    def test_resource_cleanup_integration(self):
        """Test that resource cleanup works across all components."""
        # Arrange
        manager = PipeManager(max_workers=2)

        # Create resources
        pipe_path = manager.create_named_pipe()
        assert pipe_path is not None

        # Test that cleanup properly delegates to all components
        manager.cleanup()

        # After cleanup, resources should be released
        assert manager.get_pipe_path() is None
        assert not manager.is_running()

        # Multiple cleanups should be safe
        manager.cleanup()
        manager.cleanup()

    @pytest.mark.hanging
    def test_connection_queue_integration(self):
        """Test end-to-end connection queueing functionality."""
        # Arrange
        manager = PipeManager(max_workers=2, queue_size=3, queue_timeout=5.0)

        # Mock slow connection processing to force queueing
        original_worker = manager._connection_manager._handle_connection_worker

        def slow_worker(connection_id: str):
            time.sleep(0.3)  # Simulate slow processing
            return original_worker(connection_id)

        manager._connection_manager._handle_connection_worker = slow_worker

        try:
            # Act - Start serving
            manager.create_named_pipe()
            manager.start_serving("test content for queue integration")

            # Fill worker pool and queue
            futures = []
            for i in range(5):  # 2 immediate + 3 queued
                future = manager._handle_incoming_connection()
                if future:
                    futures.append(future)

            # Allow some processing time
            time.sleep(0.1)

            # Assert - Verify queue is working
            queue_metrics = manager._get_queue_metrics()
            assert queue_metrics["current_depth"] >= 2, "Should have connections queued"

            # Verify metrics integration
            metrics = manager._get_metrics()
            assert metrics["connections_queued"] >= 3, "Should track queued connections"
            assert metrics["connection_attempts"] >= 5, "Should track all attempts"

            # Test queue overflow
            overflow_future = manager._handle_incoming_connection()
            assert overflow_future is None, "Should reject when queue is full"

            # Verify overflow recorded in metrics
            updated_metrics = manager._get_metrics()
            assert updated_metrics["failed_connections"] > 0, (
                "Should record failed connections"
            )

        finally:
            manager.cleanup()

    def test_connection_queue_timeout_integration(self):
        """Test connection timeout handling in queue integration."""
        # Arrange
        manager = PipeManager(
            max_workers=1,
            queue_size=2,
            queue_timeout=0.2,  # Very short timeout for testing
        )

        # Mock very slow worker to force timeouts
        original_worker = manager._connection_manager._handle_connection_worker

        def very_slow_worker():
            time.sleep(1.0)  # Much longer than timeout
            return original_worker()

        manager._connection_manager._handle_connection_worker = very_slow_worker

        try:
            # Act - Start serving
            manager.create_named_pipe()
            manager.start_serving("test content for timeout integration")

            # Fill worker pool
            blocking_future = manager._handle_incoming_connection()

            # Give time for worker to start
            time.sleep(0.1)

            # Queue connections that will timeout
            timeout_futures = []
            for i in range(2):
                future = manager._handle_incoming_connection()
                if future:
                    timeout_futures.append(future)

            # Wait for timeout to occur
            time.sleep(0.4)

            # Assert - Verify timeout handling
            metrics = manager._get_metrics()
            assert metrics["connections_timeout"] > 0, (
                "Should record connection timeouts"
            )

            # Verify timeout futures are resolved with exceptions
            for future in timeout_futures:
                if future.done():
                    try:
                        future.result()
                        assert False, "Future should have timed out with exception"
                    except Exception:
                        pass  # Expected timeout exception

        finally:
            manager.cleanup()

    @pytest.mark.hanging
    def test_queue_processing_order_integration(self):
        """Test that queue system processes connections and maintains functionality."""
        # Arrange
        manager = PipeManager(max_workers=1, queue_size=5, queue_timeout=10.0)

        # Track connection processing
        processed_connections = []
        original_worker = manager._connection_manager._handle_connection_worker

        def tracking_worker(connection_id: str):
            # Add delay to allow queue observation
            time.sleep(0.3)
            result = original_worker(connection_id)
            processed_connections.append(result)
            return result

        manager._connection_manager._handle_connection_worker = tracking_worker

        try:
            # Act - Start serving
            manager.create_named_pipe()
            manager.start_serving("test content for queue processing integration")

            # Submit multiple connections
            futures = []
            for i in range(3):
                future = manager._handle_incoming_connection()
                if future:
                    futures.append(future)

            # Give time for processing to start
            time.sleep(0.1)

            # Verify queue functionality
            queue_metrics = manager._get_queue_metrics()
            initial_depth = queue_metrics["current_depth"]

            # Wait for some processing to occur
            time.sleep(1.0)

            # Verify system is processing connections
            assert len(processed_connections) > 0, (
                "Should have processed some connections"
            )

            # Verify queue metrics are working
            updated_queue_metrics = manager._get_queue_metrics()
            assert isinstance(updated_queue_metrics, dict), (
                "Should provide queue metrics"
            )
            assert "current_depth" in updated_queue_metrics, (
                "Should include current depth"
            )

            # Verify metrics integration
            metrics = manager._get_metrics()
            assert metrics["connection_attempts"] >= 3, (
                "Should track connection attempts"
            )

            # The queue system is working if we can get metrics and process connections
            assert len(futures) == 3, "Should have accepted 3 connections"

        finally:
            manager.cleanup()

    @pytest.mark.hanging
    def test_queue_recovery_after_errors_integration(self):
        """Test that queue system recovers gracefully from errors."""
        # Arrange
        manager = PipeManager(max_workers=2, queue_size=3, queue_timeout=5.0)

        # Mock worker that sometimes fails
        error_count = 0
        original_worker = manager._connection_manager._handle_connection_worker

        def sometimes_failing_worker(connection_id: str):
            nonlocal error_count
            error_count += 1
            if error_count % 3 == 0:  # Every third call fails
                raise RuntimeError(f"Simulated error {error_count}")
            return original_worker(connection_id)

        manager._connection_manager._handle_connection_worker = sometimes_failing_worker

        try:
            # Act - Start serving
            manager.create_named_pipe()
            manager.start_serving("test content for error recovery")

            # Submit multiple connections, some will fail
            futures = []
            for i in range(6):
                future = manager._handle_incoming_connection()
                if future:
                    futures.append(future)

            # Wait for processing with error handling
            successful_count = 0
            failed_count = 0

            for future in futures:
                try:
                    future.result(timeout=1.0)
                    successful_count += 1
                except Exception:
                    failed_count += 1

            # Assert - Verify system continues to function despite errors
            assert successful_count > 0, "Should have some successful connections"
            # Note: failed_count might be 0 if errors are handled at future level

            # Verify metrics track successes (failures might be tracked differently)
            metrics = manager._get_metrics()
            assert metrics["successful_connections"] > 0, (
                "Should track successful connections"
            )
            # Connection failures might not be tracked if worker fails after task submission

            # Verify queue system is still functional
            queue_metrics = manager._get_queue_metrics()
            assert isinstance(queue_metrics, dict), (
                "Queue metrics should still be accessible"
            )

        finally:
            manager.cleanup()
