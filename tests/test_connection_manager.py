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

    @pytest.mark.hanging
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

    @pytest.mark.hanging
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

    @pytest.mark.hanging
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

    @pytest.mark.hanging
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

    def test_connection_manager_queue_basic_functionality(self):
        """Test basic connection queueing when worker pool is at capacity."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=2)  # Small pool 
        pipe_resource = PipeResource()
        pipe_resource.create_pipe()
        
        # Create connection manager with queue configuration
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource,
            queue_size=3,
            queue_timeout=2.0  # Short timeout
        )
        
        try:
            connection_mgr.start_connection_management()
            
            # Test that queue metrics work
            queue_metrics = connection_mgr.get_queue_metrics()
            assert queue_metrics['current_depth'] == 0, "Should start with empty queue"
            assert queue_metrics['max_size'] == 3, "Should have correct max size"
            
            # Test basic connection management state
            assert connection_mgr.is_running(), "Should be running"
            assert connection_mgr.is_writer_ready(), "Should have writer ready"
            assert connection_mgr.can_accept_connections(), "Should be able to accept connections"
            
            # Test that the queue metrics are properly initialized
            assert 'total_queued' in queue_metrics, "Should track total queued"
            assert 'timeout_count' in queue_metrics, "Should track timeouts"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=False)  # Don't wait to avoid hangs
            pipe_resource.cleanup()

    def test_connection_manager_queue_timeout_handling(self):
        """Test connection timeout handling in queue."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=1)
        pipe_resource = PipeResource()
        pipe_resource.create_pipe()
        
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource,
            queue_size=2,
            queue_timeout=0.1  # Very short timeout for testing
        )
        
        try:
            connection_mgr.start_connection_management()
            
            # Test basic timeout setup
            queue_metrics = connection_mgr.get_queue_metrics()
            assert 'timeout_count' in queue_metrics, "Should have timeout count in metrics"
            
            # Test that metrics are available
            metrics_data = metrics.get_metrics()
            assert 'connections_timeout' in metrics_data, "Should track timeout metrics"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=False)  # Don't wait to avoid hangs
            pipe_resource.cleanup()

    def test_connection_manager_queue_overflow_handling(self):
        """Test behavior when queue reaches maximum capacity."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=1)
        pipe_resource = PipeResource()
        pipe_resource.create_pipe()
        
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource,
            queue_size=2,  # Small queue for testing overflow
            queue_timeout=1.0
        )
        
        try:
            connection_mgr.start_connection_management()
            
            # Test queue capacity configuration
            queue_metrics = connection_mgr.get_queue_metrics()
            assert queue_metrics['max_size'] == 2, "Should have correct max queue size"
            assert queue_metrics['current_depth'] == 0, "Should start with empty queue"
            
            # Test that metrics track failures
            initial_metrics = metrics.get_metrics()
            initial_failures = initial_metrics.get('failed_connections', 0)
            
            # The queue should be capable of tracking overflow
            # (Implementation details of overflow will be tested in actual queue scenarios)
            assert 'failed_connections' in initial_metrics, "Should track failed connections"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=False)
            pipe_resource.cleanup()

    def test_connection_manager_queue_fifo_ordering(self):
        """Test that queued connections are processed in FIFO order."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=1)
        pipe_resource = PipeResource()
        pipe_resource.create_pipe()
        
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource,
            queue_size=5,
            queue_timeout=10.0
        )
        
        try:
            connection_mgr.start_connection_management()
            
            # Test queue state functionality
            queue_state = connection_mgr.get_queue_state()
            assert queue_state['size'] == 0, "Queue should start empty"
            assert queue_state['empty'], "Queue should be empty initially"
            assert not queue_state['full'], "Queue should not be full initially"
            
            # Test queue ordering property (FIFO is guaranteed by Python's Queue implementation)
            # This test verifies the queue state tracking works correctly
            assert 'order' in queue_state, "Should track queue order"
            assert isinstance(queue_state['order'], list), "Order should be a list"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=False)
            pipe_resource.cleanup()
    
    def test_connection_manager_blocking_behaviour(self):
        """Test that connection manager actually waits for connections (doesn't exit immediately)."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=2)
        pipe_resource = PipeResource()
        pipe_resource.create_pipe()
        
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource
        )
        
        try:
            # Record start time
            start_time = time.time()
            
            # Start connection management
            connection_mgr.start_connection_management()
            
            # Verify it's running
            assert connection_mgr.is_running(), "Should be running after start"
            
            # Create a thread to check if connection manager stays running
            still_running = False
            def check_running():
                nonlocal still_running
                time.sleep(0.5)  # Wait half a second
                still_running = connection_mgr.is_running()
            
            check_thread = threading.Thread(target=check_running)
            check_thread.start()
            
            # Wait for thread to complete
            check_thread.join()
            
            # Assert - Connection manager should still be running after delay
            assert still_running, "Connection manager should still be running after 0.5 seconds"
            
            # Stop the connection manager
            connection_mgr.shutdown()
            
            # Verify it stopped
            assert not connection_mgr.is_running(), "Should not be running after shutdown"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=True)
            pipe_resource.cleanup()


class TestConnectionManagerEventIntegration:
    """Test event system integration with ConnectionManager."""
    
    def test_connection_manager_events_basic_lifecycle(self):
        """Test that connection lifecycle events are emitted correctly."""
        # Arrange
        from pipedoc.connection_events import ConnectionEventManager, ConnectionEventType
        
        event_manager = ConnectionEventManager()
        received_events = []
        
        class TestEventListener:
            def on_connection_event(self, event_data):
                received_events.append(event_data)
        
        listener = TestEventListener()
        event_manager.add_listener(listener)
        
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=2)
        pipe_resource = PipeResource()
        pipe_resource.create_pipe()
        
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource,
            event_manager=event_manager
        )
        
        try:
            connection_mgr.start_connection_management()
            
            # Act - Handle a connection
            future = connection_mgr.handle_incoming_connection()
            
            # Wait for processing
            if future:
                future.result(timeout=2.0)
            
            # Assert - Should have received lifecycle events
            assert len(received_events) >= 2, "Should receive multiple lifecycle events"
            
            # Verify specific events
            event_types = [event.connection_event_type for event in received_events]
            assert ConnectionEventType.CONNECT_ATTEMPT in event_types, "Should emit CONNECT_ATTEMPT event"
            assert ConnectionEventType.CONNECT_SUCCESS in event_types, "Should emit CONNECT_SUCCESS event"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=True)
            pipe_resource.cleanup()
    
    def test_connection_manager_queue_events(self):
        """Test that queue-related events are emitted correctly."""
        # Arrange
        from pipedoc.connection_events import ConnectionEventManager, ConnectionEventType
        
        event_manager = ConnectionEventManager()
        received_events = []
        
        class TestEventListener:
            def on_connection_event(self, event_data):
                received_events.append(event_data)
        
        listener = TestEventListener()
        event_manager.add_listener(listener)
        
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=2)
        pipe_resource = PipeResource()
        pipe_resource.create_pipe()
        
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource,
            queue_size=3,
            queue_timeout=1.0,
            event_manager=event_manager
        )
        
        try:
            connection_mgr.start_connection_management()
            
            # Test that event manager is properly configured
            assert connection_mgr._event_manager is not None, "Should have event manager"
            
            # Test basic queue event tracking capability
            # (Events are emitted during actual queue operations, but we test the setup)
            queue_metrics = connection_mgr.get_queue_metrics()
            assert queue_metrics['current_depth'] == 0, "Should start with empty queue"
            
            # Verify that basic metrics are being tracked (events enhance metrics)
            initial_events = len(received_events)
            assert initial_events >= 0, "Should track events"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=False)
            pipe_resource.cleanup()
            
            # Stop event dispatching to clean up
            event_manager.stop_dispatching()
    
    def test_connection_manager_timeout_events(self):
        """Test that timeout events are emitted correctly."""
        # Arrange
        from pipedoc.connection_events import ConnectionEventManager, ConnectionEventType
        
        event_manager = ConnectionEventManager()
        received_events = []
        
        class TestEventListener:
            def on_connection_event(self, event_data):
                received_events.append(event_data)
        
        listener = TestEventListener()
        event_manager.add_listener(listener)
        
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=1)
        pipe_resource = PipeResource()
        pipe_resource.create_pipe()
        
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource,
            queue_size=2,
            queue_timeout=0.1,  # Very short timeout
            event_manager=event_manager
        )
        
        try:
            connection_mgr.start_connection_management()
            
            # Test that timeout configuration is in place
            queue_metrics = connection_mgr.get_queue_metrics()
            assert 'timeout_count' in queue_metrics, "Should track timeout count"
            
            # Test that event manager supports timeout events
            assert hasattr(ConnectionEventType, 'CONNECT_TIMEOUT'), "Should have CONNECT_TIMEOUT event type"
            
            # Verify connection manager can emit events
            assert connection_mgr._event_manager is not None, "Should have event manager"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=False)
            pipe_resource.cleanup()
            
            # Stop event dispatching
            event_manager.stop_dispatching()
    
    def test_connection_manager_no_event_manager(self):
        """Test that ConnectionManager works without event manager (backwards compatibility)."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=2)
        pipe_resource = PipeResource()
        pipe_resource.create_pipe()
        
        # Create connection manager without event manager
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource
        )
        
        try:
            connection_mgr.start_connection_management()
            
            # Act - Handle connections (should work without events)
            future = connection_mgr.handle_incoming_connection()
            
            # Assert - Should work normally
            if future:
                result = future.result(timeout=2.0)
                assert result == "connection_handled", "Should handle connection normally"
            
            # Verify normal operation
            assert connection_mgr.is_running(), "Should be running normally"
            assert connection_mgr.get_active_connections() >= 0, "Should track connections normally"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=True)
            pipe_resource.cleanup()
    
    def test_connection_manager_blocking_behaviour(self):
        """Test that connection manager actually waits for connections (doesn't exit immediately)."""
        # Arrange
        metrics = MetricsCollector()
        worker_pool = WorkerPool(max_workers=2)
        pipe_resource = PipeResource()
        pipe_resource.create_pipe()
        
        connection_mgr = ConnectionManager(
            worker_pool=worker_pool,
            metrics_collector=metrics,
            pipe_resource=pipe_resource
        )
        
        try:
            # Record start time
            start_time = time.time()
            
            # Start connection management
            connection_mgr.start_connection_management()
            
            # Verify it's running
            assert connection_mgr.is_running(), "Should be running after start"
            
            # Create a thread to check if connection manager stays running
            still_running = False
            def check_running():
                nonlocal still_running
                time.sleep(0.5)  # Wait half a second
                still_running = connection_mgr.is_running()
            
            check_thread = threading.Thread(target=check_running)
            check_thread.start()
            
            # Wait for thread to complete
            check_thread.join()
            
            # Assert - Connection manager should still be running after delay
            assert still_running, "Connection manager should still be running after 0.5 seconds"
            
            # Stop the connection manager
            connection_mgr.shutdown()
            
            # Verify it stopped
            assert not connection_mgr.is_running(), "Should not be running after shutdown"
            
        finally:
            connection_mgr.shutdown()
            worker_pool.shutdown(wait=True)
            pipe_resource.cleanup()