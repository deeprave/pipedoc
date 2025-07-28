"""
Tests for the ConnectionManager component.

This module tests connection lifecycle management including race condition
prevention, always-ready writer pattern, and integration with WorkerPool.
"""

import threading
import time
from unittest.mock import MagicMock, patch, call
from concurrent.futures import Future

import pytest

from pipedoc.connection_manager import ConnectionManager
from pipedoc.worker_pool import WorkerPool
from pipedoc.metrics_collector import MetricsCollector
from pipedoc.pipe_resource import PipeResource


class TestConnectionManager:
    """Test cases for ConnectionManager component."""

    def test_connection_manager_race_prevention(self):
        """Test always-ready writer pattern for race condition prevention."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=3, metrics_collector=metrics)
        pipe_resource = PipeResource()
        
        # Create connection manager with components
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource
        )
        
        try:
            # Assert - Initial state (before starting)
            assert not connection_mgr.is_writer_ready(), "Should not have writer ready initially"
            assert connection_mgr.get_active_connections() == 0, "Should have no active connections initially"
            
            # Test - Start connection management
            connection_mgr.start_connection_management()
            
            # The always-ready writer pattern means there should always be a writer
            # waiting for incoming connections after starting
            assert connection_mgr.is_writer_ready(), "Should have writer ready after starting"
            
            # Test - Simulate connection arrival
            # This should trigger replacement of the current writer with a new one
            connection_future = connection_mgr.handle_incoming_connection()
            
            # Assert - Connection handling
            assert connection_future is not None, "Should return future for connection handling"
            assert isinstance(connection_future, Future), "Should return Future object"
            
            # Wait for connection to complete
            result = connection_future.result(timeout=1.0)
            assert result == "connection_handled", "Connection should be handled successfully"
            
            # After handling connection, a new writer should be immediately available
            assert connection_mgr.is_writer_ready(), "Should have new writer ready after connection"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=False)  # Don't wait to avoid timeout
            pipe_resource.cleanup()

    def test_connection_manager_lifecycle_management(self):
        """Test connection manager lifecycle and state management."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=2)
        pipe_resource = PipeResource()
        pipe_resource.create_pipe()  # Create pipe for testing
        
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource
        )
        
        try:
            # Assert - Initial state
            assert not connection_mgr.is_running(), "Should not be running initially"
            assert connection_mgr.get_active_connections() == 0, "Should have no active connections"
            
            # Act - Start connection management
            connection_mgr.start_connection_management()
            
            # Assert - Running state
            assert connection_mgr.is_running(), "Should be running after start"
            assert connection_mgr.is_writer_ready(), "Should have writer ready"
            
            # Test - Multiple connection handling
            futures = []
            for i in range(3):
                future = connection_mgr.handle_incoming_connection()
                if future:  # May be None if pool is full
                    futures.append(future)
            
            # Should track active connections
            active_count = connection_mgr.get_active_connections()
            assert 0 <= active_count <= 3, f"Active connections should be 0-3, got {active_count}"
            
            # Test - Shutdown
            connection_mgr.shutdown()
            assert not connection_mgr.is_running(), "Should not be running after shutdown"
            
        finally:
            worker_pool.shutdown(wait=False)
            pipe_resource.cleanup()

    def test_connection_manager_proactive_writer_replacement(self):
        """Test that writers are proactively replaced to maintain readiness."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=4)
        pipe_resource = PipeResource()
        pipe_resource.create_pipe()
        
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource
        )
        
        try:
            connection_mgr.start_connection_management()
            
            # Track writer replacement by monitoring internal state
            initial_writer_id = connection_mgr._get_current_writer_id() if hasattr(connection_mgr, '_get_current_writer_id') else None
            
            # Simulate rapid connection arrivals
            connection_count = 0
            for i in range(5):
                future = connection_mgr.handle_incoming_connection()
                if future:
                    connection_count += 1
                    
                # After each connection, verify a writer is still ready
                time.sleep(0.01)  # Allow time for writer replacement
                assert connection_mgr.is_writer_ready(), f"Should maintain ready writer after connection {i+1}"
            
            # Verify that connections were handled
            assert connection_count > 0, "Should have handled at least one connection"
            
            # Verify metrics were updated
            metrics_data = metrics.get_metrics()
            expected_attempts = connection_count
            assert metrics_data['connection_attempts'] >= expected_attempts, \
                f"Should have recorded connection attempts: expected >= {expected_attempts}, got {metrics_data['connection_attempts']}"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=True)
            pipe_resource.cleanup()

    def test_connection_manager_integration_with_components(self):
        """Test ConnectionManager integration with WorkerPool, MetricsCollector, and PipeResource."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=2, metrics_collector=metrics)
        pipe_resource = PipeResource()
        pipe_path = pipe_resource.create_pipe()
        
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource
        )
        
        try:
            # Test - Component integration
            connection_mgr.start_connection_management()
            
            # Verify pipe resource integration
            assert pipe_resource.is_pipe_created(), "Pipe should be created"
            assert pipe_resource.get_pipe_path() == pipe_path, "Should use correct pipe path"
            
            # Test connection handling with metrics integration
            future = connection_mgr.handle_incoming_connection()
            if future:
                # Let the connection attempt be processed
                time.sleep(0.05)
                
                # Verify metrics were updated
                metrics_data = metrics.get_metrics()
                assert metrics_data['connection_attempts'] > 0, "Should record connection attempts"
            
            # Test worker pool integration
            pool_metrics = worker_pool.get_metrics()
            assert isinstance(pool_metrics, dict), "Should get worker pool metrics"
            
            # Verify connection manager can query component states
            assert connection_mgr.can_accept_connections(), "Should be able to check if connections can be accepted"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=True)
            pipe_resource.cleanup()

    def test_connection_manager_error_handling(self):
        """Test error handling during connection management."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=1)  # Small pool to test overload
        pipe_resource = PipeResource()
        
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource
        )
        
        try:
            # Test - Error handling without pipe created
            connection_mgr.start_connection_management()
            
            # Should handle missing pipe gracefully
            future = connection_mgr.handle_incoming_connection()
            # May return None or handle error gracefully
            
            # Test - Create pipe and try overload
            pipe_resource.create_pipe()
            
            # Fill the worker pool to capacity
            futures = []
            for i in range(3):  # More than max_workers to test overload
                future = connection_mgr.handle_incoming_connection()
                if future:
                    futures.append(future)
            
            # Should handle overload gracefully without crashing
            assert connection_mgr.is_running(), "Should still be running after overload"
            
            # Test - Error in connection handling should be recorded in metrics
            # Force an error condition if possible
            with patch.object(worker_pool, 'submit_task', side_effect=RuntimeError("Pool error")):
                error_future = connection_mgr.handle_incoming_connection()
                # Should handle the error gracefully
                
            # Verify system is still functional
            assert connection_mgr.is_running(), "Should recover from errors"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=True)
            pipe_resource.cleanup()

    def test_connection_manager_concurrency_safety(self):
        """Test thread safety of ConnectionManager under concurrent access."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=5)
        pipe_resource = PipeResource()
        pipe_resource.create_pipe()
        
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource
        )
        
        # Track results from concurrent threads
        results = []
        errors = []
        
        def concurrent_connection_handler(thread_id: int):
            """Handler that simulates concurrent connection requests."""
            try:
                for i in range(3):
                    future = connection_mgr.handle_incoming_connection()
                    if future:
                        results.append(f"Thread {thread_id}: Connection {i} handled")
                    time.sleep(0.01)  # Small delay to increase concurrency
            except Exception as e:
                errors.append(f"Thread {thread_id}: {str(e)}")
        
        try:
            connection_mgr.start_connection_management()
            
            # Act - Launch concurrent threads
            threads = []
            num_threads = 4
            for thread_id in range(num_threads):
                thread = threading.Thread(target=concurrent_connection_handler, args=(thread_id,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=5.0)
            
            # Assert - Verify thread safety
            assert len(errors) == 0, f"Should have no errors in concurrent access: {errors}"
            assert len(results) > 0, "Should have processed some connections concurrently"
            
            # Verify connection manager is still in consistent state
            assert connection_mgr.is_running(), "Should still be running after concurrent access"
            assert connection_mgr.is_writer_ready(), "Should maintain writer readiness"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=True)
            pipe_resource.cleanup()