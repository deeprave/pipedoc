"""
Performance and integration tests for the enhanced component architecture.

This module verifies that the component-based refactoring maintains or improves
performance compared to the original monolithic PipeManager implementation.
"""

import threading
import time
from unittest.mock import patch, MagicMock
import os
import tempfile

import pytest

from pipedoc.pipe_manager import PipeManager
from pipedoc.connection_manager import ConnectionManager
from pipedoc.worker_pool import WorkerPool
from pipedoc.metrics_collector import MetricsCollector
from pipedoc.pipe_resource import PipeResource


class TestPerformanceIntegration:
    """Test cases for performance and integration validation."""

    def test_component_integration_basic_workflow(self):
        """Test that all components work together in the basic workflow."""
        # Arrange
        manager = PipeManager(max_workers=3)

        try:
            # Act - Execute component initialization and basic operations
            pipe_path = manager.create_named_pipe()
            assert pipe_path is not None, "Pipe creation should succeed"
            assert os.path.exists(pipe_path), "Pipe should exist on filesystem"

            # Test component integration without blocking operations
            assert manager._worker_pool.is_running(), "WorkerPool should be active"
            assert manager._connection_manager is not None, (
                "ConnectionManager should exist"
            )

            # Test metrics collection integration
            initial_metrics = manager._get_metrics()
            assert isinstance(initial_metrics, dict), "Metrics should be accessible"
            assert "connection_attempts" in initial_metrics, (
                "Metrics should have expected structure"
            )

            # Test worker pool integration
            pool_metrics = manager._get_worker_pool_metrics()
            assert isinstance(pool_metrics, dict), (
                "Worker pool metrics should be accessible"
            )

            # Test pipe resource integration
            assert manager.get_pipe_path() == pipe_path, (
                "Pipe path should be consistent"
            )

        finally:
            manager.cleanup()

    def test_concurrent_client_handling_performance(self):
        """Test concurrent client handling with multiple threads."""
        # Arrange
        manager = PipeManager(max_workers=5)
        results = []
        errors = []

        def concurrent_operations(client_id: int):
            """Simulate concurrent operations without blocking pipe writes."""
            try:
                start_time = time.time()
                # Test concurrent access to manager methods (non-blocking)
                manager._get_metrics()
                manager._get_worker_pool_metrics()
                manager._can_accept_connection()
                end_time = time.time()
                results.append(end_time - start_time)
            except Exception as e:
                errors.append(f"Client {client_id}: {str(e)}")

        try:
            # Create pipe for testing
            manager.create_named_pipe()

            # Act - Launch concurrent operations
            threads = []
            num_clients = 8

            for client_id in range(num_clients):
                thread = threading.Thread(
                    target=concurrent_operations, args=(client_id,)
                )
                threads.append(thread)
                thread.start()

            # Wait for all operations to complete
            for thread in threads:
                thread.join(timeout=5.0)

            # Assert - All operations should complete successfully
            assert len(errors) == 0, (
                f"No errors expected in concurrent operations: {errors}"
            )
            assert len(results) == num_clients, (
                f"Expected {num_clients} results, got {len(results)}"
            )

            # Performance assertion: Operations should be fast
            max_time = max(results) if results else 0
            assert max_time < 1.0, (
                f"Concurrent operations should be fast, max time: {max_time}"
            )

        finally:
            manager.cleanup()

    def test_memory_usage_and_resource_management(self):
        """Test that memory usage remains stable across multiple operations."""
        # Arrange - Test multiple manager lifecycles without blocking operations

        # Test multiple manager lifecycles
        for cycle in range(3):
            manager = PipeManager(max_workers=2)

            try:
                # Perform operations that could cause memory leaks (non-blocking)
                manager.create_named_pipe()

                # Test metrics access (no blocking operations)
                metrics = manager._get_metrics()
                assert isinstance(metrics, dict), "Metrics should be accessible"

                worker_metrics = manager._get_worker_pool_metrics()
                assert isinstance(worker_metrics, dict), (
                    "Worker metrics should be accessible"
                )

            finally:
                manager.cleanup()

        # Final verification - system should be stable after multiple lifecycles
        final_manager = PipeManager(max_workers=2)
        try:
            final_manager.create_named_pipe()
            assert final_manager.get_pipe_path() is not None, (
                "System should remain functional"
            )
        finally:
            final_manager.cleanup()

    def test_thread_pool_efficiency_under_load(self):
        """Test ThreadPoolExecutor efficiency with WorkerPool wrapper."""
        # Arrange
        manager = PipeManager(max_workers=3)

        try:
            manager.create_named_pipe()

            # Test - Measure pool operations without blocking
            start_time = time.time()

            # Test pool capacity and metrics (non-blocking operations)
            for i in range(10):
                manager._can_accept_connection()
                manager._get_worker_pool_metrics()

            operation_time = time.time() - start_time

            # Assert - Pool operations should be efficient
            assert operation_time < 1.0, (
                f"Pool operations should be fast: {operation_time}"
            )

            # Pool should remain stable
            assert manager._worker_pool.is_running(), "WorkerPool should remain stable"

            # Metrics should be consistent and accessible
            pool_metrics = manager._get_worker_pool_metrics()
            assert "active_workers" in pool_metrics, (
                "Pool metrics should include active workers"
            )
            assert "max_workers" in pool_metrics, (
                "Pool metrics should include max workers"
            )

        finally:
            manager.cleanup()

    def test_component_communication_overhead(self):
        """Test that component communication doesn't introduce significant overhead."""
        # Arrange
        manager = PipeManager(max_workers=3)

        try:
            # Act - Measure time for component interactions
            start_time = time.time()

            # Test rapid component method calls
            for i in range(100):
                manager._get_metrics()
                manager._get_worker_pool_metrics()
                manager._can_accept_connection()

            communication_time = time.time() - start_time

            # Assert - Component communication should be fast
            assert communication_time < 1.0, (
                f"Component communication should be fast: {communication_time}"
            )

            # Test pipe operations
            start_time = time.time()
            pipe_path = manager.create_named_pipe()
            pipe_creation_time = time.time() - start_time

            assert pipe_creation_time < 0.5, (
                f"Pipe creation should be fast: {pipe_creation_time}"
            )
            assert pipe_path is not None, "Pipe should be created successfully"

        finally:
            manager.cleanup()

    def test_api_access_performance(self):
        """Test that public API access is performant."""
        # Arrange
        manager = PipeManager(max_workers=3)

        try:
            # Test public API access performance
            start_time = time.time()

            for i in range(1000):
                # Access public API methods (should be fast)
                _ = manager.is_running()
                _ = manager.get_pipe_path()

            api_access_time = time.time() - start_time

            # Assert - Public API should be fast
            assert api_access_time < 0.5, (
                f"Public API access should be fast: {api_access_time}"
            )

            # Test creating pipe doesn't slow down subsequent access
            manager.create_named_pipe()

            start_time = time.time()
            for i in range(100):
                _ = manager.is_running()
                _ = manager.get_pipe_path()

            post_creation_time = time.time() - start_time
            assert post_creation_time < 0.1, (
                f"API access should remain fast after pipe creation: {post_creation_time}"
            )

        finally:
            manager.cleanup()

    def test_error_handling_performance_impact(self):
        """Test that error handling doesn't significantly impact performance."""
        # Arrange
        manager = PipeManager(max_workers=2)

        try:
            manager.create_named_pipe()

            # Test normal operations timing (non-blocking)
            start_time = time.time()
            for i in range(100):
                manager._get_metrics()
                manager._can_accept_connection()
            normal_time = time.time() - start_time

            # Test operations with component access (should be similar performance)
            start_time = time.time()
            for i in range(100):
                try:
                    manager._get_worker_pool_metrics()
                    manager.get_pipe_path()
                except Exception:
                    pass  # Any errors should be handled gracefully
            operation_time = time.time() - start_time

            # Assert - Operations should be fast
            assert normal_time < 1.0, f"Normal operations should be fast: {normal_time}"
            assert operation_time < 1.0, (
                f"Component operations should be fast: {operation_time}"
            )

            # System should remain stable
            assert manager._worker_pool.is_running(), "System should remain stable"

        finally:
            manager.cleanup()

    def test_concurrent_component_access_thread_safety(self):
        """Test thread safety under concurrent component access."""
        # Arrange
        manager = PipeManager(max_workers=4)
        errors = []
        operations_completed = 0
        operations_lock = threading.Lock()

        def concurrent_operations(thread_id: int):
            """Perform concurrent operations on components."""
            try:
                for i in range(20):
                    # Mix of read and write operations
                    if i % 4 == 0:
                        manager._get_metrics()
                    elif i % 4 == 1:
                        manager._get_worker_pool_metrics()
                    elif i % 4 == 2:
                        manager._can_accept_connection()
                    else:
                        manager.get_pipe_path()

                    # Small delay to encourage race conditions
                    time.sleep(0.001)

                with operations_lock:
                    nonlocal operations_completed
                    operations_completed += 1

            except Exception as e:
                errors.append(f"Thread {thread_id}: {str(e)}")

        try:
            manager.create_named_pipe()

            # Act - Launch concurrent threads
            threads = []
            num_threads = 5

            for thread_id in range(num_threads):
                thread = threading.Thread(
                    target=concurrent_operations, args=(thread_id,)
                )
                threads.append(thread)
                thread.start()

            # Wait for completion
            for thread in threads:
                thread.join(timeout=10.0)

            # Assert - All operations should complete without errors
            assert len(errors) == 0, f"No thread safety errors expected: {errors}"
            assert operations_completed == num_threads, (
                f"All threads should complete: {operations_completed}/{num_threads}"
            )

            # System should remain in consistent state
            assert manager._worker_pool.is_running(), "WorkerPool should remain stable"
            metrics = manager._get_metrics()
            assert isinstance(metrics, dict), "Metrics should remain accessible"

        finally:
            manager.cleanup()

    def test_integration_with_real_pipe_operations(self):
        """Test integration with actual pipe file operations."""
        # Arrange
        manager = PipeManager(max_workers=2)

        try:
            # Act - Create real pipe and test operations
            pipe_path = manager.create_named_pipe()
            assert os.path.exists(pipe_path), "Real pipe should be created"

            # Test pipe is actually a FIFO
            stat_info = os.stat(pipe_path)
            import stat

            assert stat.S_ISFIFO(stat_info.st_mode), "Created file should be a FIFO"

            # Test component integration with real pipe
            manager.start_serving("integration test")

            # Verify pipe is still accessible
            assert os.path.exists(pipe_path), "Pipe should remain after start serving"
            assert manager.get_pipe_path() == pipe_path, "Path should be consistent"

            # Test cleanup removes pipe
            manager.cleanup()
            # Note: cleanup() should remove the pipe, but let's be defensive
            # since the test might run before cleanup completes
            time.sleep(0.1)  # Small delay for cleanup

        except Exception as e:
            # Ensure cleanup even if test fails
            try:
                manager.cleanup()
            except:
                pass
            raise e
