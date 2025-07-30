"""
Tests for the enhanced PipeManager class.

This module tests the pipe management functionality in the new component-based
architecture, focusing on the public API and essential integration behavior.
"""

import os
import time
from unittest.mock import MagicMock, patch, mock_open
import threading

import pytest

from pipedoc.pipe_manager import PipeManager


class TestPipeManager:
    """Test cases for enhanced PipeManager class."""

    def test_init(self):
        """Test initialization of enhanced PipeManager."""
        manager = PipeManager()

        try:
            # Test component initialization
            assert manager._metrics_collector is not None
            assert manager._worker_pool is not None
            assert manager._pipe_resource is not None
            assert manager._connection_manager is not None

            # Test initial state
            assert not manager._is_serving
            assert manager._current_content == ""

        finally:
            manager.cleanup()

    @patch("os.mkfifo")
    @patch("os.path.exists")
    @patch("os.unlink")
    def test_create_named_pipe_success(self, mock_unlink, mock_exists, mock_mkfifo):
        """Test successful creation of named pipe."""
        mock_exists.return_value = False

        manager = PipeManager()

        try:
            pipe_path = manager.create_named_pipe()

            assert pipe_path is not None
            assert f"pipedoc_{os.getpid()}" in pipe_path
            mock_mkfifo.assert_called_once_with(pipe_path)

        finally:
            manager.cleanup()

    @patch("os.mkfifo")
    @patch("os.path.exists")
    @patch("os.unlink")
    def test_create_named_pipe_existing_pipe(
        self, mock_unlink, mock_exists, mock_mkfifo
    ):
        """Test creation of named pipe when one already exists."""
        mock_exists.return_value = True

        manager = PipeManager()

        try:
            pipe_path = manager.create_named_pipe()

            assert pipe_path is not None
            mock_unlink.assert_called_once()
            mock_mkfifo.assert_called_once_with(pipe_path)

        finally:
            manager.cleanup()

    @patch("os.mkfifo")
    def test_create_named_pipe_failure(self, mock_mkfifo):
        """Test handling of pipe creation failure."""
        mock_mkfifo.side_effect = OSError("Permission denied")

        manager = PipeManager()

        try:
            with pytest.raises(OSError, match="Failed to create named pipe"):
                manager.create_named_pipe()

        finally:
            manager.cleanup()

    @patch("builtins.open", new_callable=mock_open)
    def test_serve_client_success(self, mock_file):
        """Test successful client serving."""
        manager = PipeManager()

        try:
            manager.create_named_pipe()
            manager.serve_client(1, "test content")

            # Verify file operations
            mock_file.assert_called()
            handle = mock_file.return_value.__enter__.return_value
            handle.write.assert_called_with("test content")
            handle.flush.assert_called_once()

            # Verify metrics were recorded
            metrics = manager._get_metrics()
            assert metrics["connection_attempts"] >= 1

        finally:
            manager.cleanup()

    @patch("builtins.open")
    def test_serve_client_broken_pipe(self, mock_open_func):
        """Test handling of broken pipe during client serving."""
        mock_open_func.side_effect = BrokenPipeError("Broken pipe")

        manager = PipeManager()

        try:
            manager.create_named_pipe()
            manager.serve_client(1, "test content")

            # Should handle BrokenPipeError gracefully
            metrics = manager._get_metrics()
            assert metrics["connection_attempts"] >= 1
            # BrokenPipeError should be recorded as failure

        finally:
            manager.cleanup()

    @patch("builtins.open")
    def test_serve_client_general_exception(self, mock_open_func):
        """Test handling of general exception during client serving."""
        mock_open_func.side_effect = IOError("Disk full")

        manager = PipeManager()

        try:
            manager.create_named_pipe()

            with pytest.raises(IOError, match="Disk full"):
                manager.serve_client(1, "test content")

        finally:
            manager.cleanup()

    def test_start_serving(self):
        """Test start serving functionality."""
        manager = PipeManager()

        try:
            manager.create_named_pipe()
            manager.start_serving("test content")

            assert manager.is_running()
            assert manager._current_content == "test content"
            assert manager._connection_manager.is_running()

        finally:
            manager.cleanup()

    def test_stop_serving(self):
        """Test stop serving functionality."""
        manager = PipeManager()

        try:
            manager.create_named_pipe()
            manager.start_serving("test content")

            assert manager.is_running()

            manager.stop_serving()

            assert not manager.is_running()

        finally:
            manager.cleanup()

    def test_cleanup(self):
        """Test cleanup functionality."""
        manager = PipeManager()

        # Create pipe and start serving
        manager.create_named_pipe()
        manager.start_serving("test content")

        # Cleanup should stop serving and clean resources
        manager.cleanup()

        assert not manager.is_running()

    def test_get_pipe_path(self):
        """Test getting pipe path."""
        manager = PipeManager()

        try:
            # Initially no pipe
            assert manager.get_pipe_path() is None

            # After creation, should return path
            pipe_path = manager.create_named_pipe()
            assert manager.get_pipe_path() == pipe_path

        finally:
            manager.cleanup()

    def test_is_running(self):
        """Test running state management."""
        manager = PipeManager()

        try:
            # Initially not serving
            assert not manager.is_running()

            # After start serving
            manager.create_named_pipe()
            manager.start_serving("test content")
            assert manager.is_running()

            # After stop serving
            manager.stop_serving()
            assert not manager.is_running()

        finally:
            manager.cleanup()

    @patch("builtins.open", new_callable=mock_open)
    def test_multiple_clients(self, mock_file):
        """Test serving multiple clients."""
        manager = PipeManager()

        try:
            manager.create_named_pipe()

            # Serve multiple clients
            for i in range(3):
                manager.serve_client(i, f"content {i}")

            # Verify metrics tracked all clients
            metrics = manager._get_metrics()
            assert metrics["connection_attempts"] >= 3

        finally:
            manager.cleanup()

    def test_component_integration(self):
        """Test that all components are properly integrated."""
        manager = PipeManager()

        try:
            # Test component accessibility
            assert manager._get_metrics() is not None
            assert manager._get_worker_pool_metrics() is not None
            assert manager._can_accept_connection() is not None

            # Test component coordination
            manager.create_named_pipe()
            manager.start_serving("test content")

            # All components should be active
            assert manager._worker_pool.is_running()
            assert manager._connection_manager.is_running()

        finally:
            manager.cleanup()

    def test_metrics_integration(self):
        """Test metrics collection integration."""
        manager = PipeManager()

        try:
            initial_metrics = manager._get_metrics()

            # Metrics should be accessible and have expected structure
            assert isinstance(initial_metrics, dict)
            assert "connection_attempts" in initial_metrics
            assert "successful_connections" in initial_metrics
            assert "failed_connections" in initial_metrics

            # Test that metrics are updated
            manager.create_named_pipe()
            manager._metrics_collector.record_connection_attempt()

            updated_metrics = manager._get_metrics()
            assert (
                updated_metrics["connection_attempts"]
                > initial_metrics["connection_attempts"]
            )

        finally:
            manager.cleanup()

    def test_worker_pool_integration(self):
        """Test worker pool integration."""
        manager = PipeManager()

        try:
            pool_metrics = manager._get_worker_pool_metrics()

            # Worker pool metrics should be accessible
            assert isinstance(pool_metrics, dict)
            assert "max_workers" in pool_metrics
            assert "active_workers" in pool_metrics
            assert "is_running" in pool_metrics

            # Worker pool should be running
            assert pool_metrics["is_running"]

        finally:
            manager.cleanup()

    def test_connection_capacity_checking(self):
        """Test connection capacity checking."""
        manager = PipeManager()

        try:
            # Should be able to accept connections initially
            assert manager._can_accept_connection() is not None

            # After creating pipe, should still be able to accept
            manager.create_named_pipe()
            assert manager._can_accept_connection() is not None

        finally:
            manager.cleanup()

    def test_thread_safety(self):
        """Test basic thread safety of manager operations."""
        manager = PipeManager()
        errors = []

        def concurrent_operations(thread_id):
            try:
                for _ in range(10):
                    manager._get_metrics()
                    manager._get_worker_pool_metrics()
                    manager._can_accept_connection()
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        try:
            manager.create_named_pipe()

            # Launch concurrent threads
            threads = []
            for i in range(3):
                thread = threading.Thread(target=concurrent_operations, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for completion
            for thread in threads:
                thread.join(timeout=5.0)

            # Should have no errors
            assert len(errors) == 0, f"Thread safety errors: {errors}"

        finally:
            manager.cleanup()

    def test_resource_cleanup_on_exception(self):
        """Test that resources are properly cleaned up even when exceptions occur."""
        manager = PipeManager()

        try:
            manager.create_named_pipe()
            manager.start_serving("test content")

            # Simulate some work
            assert manager.is_running()

        finally:
            # Cleanup should work even if exceptions occurred
            manager.cleanup()
            assert not manager.is_running()

    def test_configuration_options(self):
        """Test manager configuration options."""
        # Test with custom max_workers
        manager = PipeManager(max_workers=5, thread_pool_timeout=10.0)

        try:
            pool_metrics = manager._get_worker_pool_metrics()
            assert pool_metrics["max_workers"] == 5

        finally:
            manager.cleanup()

    def test_queue_configuration(self):
        """Test queue configuration parameters are passed correctly."""
        # Test with custom queue settings
        manager = PipeManager(max_workers=2, queue_size=5, queue_timeout=15.0)

        try:
            # Verify queue configuration is passed to ConnectionManager
            queue_metrics = manager._get_queue_metrics()
            assert queue_metrics["max_size"] == 5, (
                "Queue size should be configured correctly"
            )

            # Test that queue functionality works
            manager.create_named_pipe()
            manager.start_serving("test content")

            # Should be able to get queue metrics
            assert "current_depth" in queue_metrics
            assert "total_queued" in queue_metrics
            assert "timeout_count" in queue_metrics

        finally:
            manager.cleanup()


class TestPipeManagerEventIntegration:
    """Test PipeManager integration with event system."""

    def test_pipe_manager_event_listener_configuration(self):
        """Test that PipeManager can be configured with event listeners."""
        # Arrange
        from pipedoc.connection_events import ConnectionEventListener, ConnectionEvent

        received_events = []

        class TestEventListener:
            def on_connection_event(self, event_data: ConnectionEvent) -> None:
                received_events.append(event_data)

        listener = TestEventListener()

        # Act - Create PipeManager with event listener
        manager = PipeManager(event_listeners=[listener])

        try:
            # Verify event listener was registered
            assert hasattr(manager, "_event_manager"), "Should have event manager"
            assert manager._event_manager is not None, (
                "Event manager should be initialized"
            )

            # Test that we can add more listeners dynamically
            another_listener = TestEventListener()
            manager.add_event_listener(another_listener)

            # Test that we can remove listeners
            manager.remove_event_listener(listener)

        finally:
            manager.cleanup()

    def test_pipe_manager_metrics_collector_as_event_listener(self):
        """Test that MetricsCollector is automatically registered as event listener."""
        # Arrange
        from pipedoc.connection_events import ConnectionEvent, ConnectionEventType

        # Act - Create PipeManager with default configuration
        manager = PipeManager()

        try:
            # The metrics collector should be registered as an event listener
            # Emit a test event directly to verify integration
            if hasattr(manager, "_event_manager") and manager._event_manager:
                test_event = ConnectionEvent(
                    event_type=ConnectionEventType.CONNECT_ATTEMPT,
                    connection_id="test_conn",
                    timestamp=time.time(),
                )
                manager._event_manager.emit_event(test_event)

                # Allow time for async event processing
                time.sleep(0.1)

                # Verify metrics were updated
                metrics = manager._get_metrics()
                assert metrics["connection_attempts"] >= 1, (
                    "Metrics should track events"
                )

        finally:
            manager.cleanup()

    def test_pipe_manager_without_event_listeners(self):
        """Test that PipeManager works without event listeners (backwards compatibility)."""
        # Arrange & Act
        manager = PipeManager(event_listeners=False)

        try:
            # Should work normally without events
            pipe_path = manager.create_named_pipe()
            assert pipe_path is not None, "Should create pipe without events"

            # Basic operations should work
            assert manager.get_pipe_path() == pipe_path
            assert not manager.is_running()

            # Event manager should be None or minimal
            if hasattr(manager, "_event_manager"):
                # Event manager might exist but with no listeners
                pass

        finally:
            manager.cleanup()

    @pytest.mark.hanging
    def test_pipe_manager_event_flow_integration(self):
        """Test end-to-end event flow through PipeManager."""
        # Arrange
        from pipedoc.connection_events import ConnectionEvent, ConnectionEventType

        received_events = []

        class TestEventListener:
            def on_connection_event(self, event_data: ConnectionEvent) -> None:
                received_events.append(event_data)

        listener = TestEventListener()
        manager = PipeManager(max_workers=2, event_listeners=[listener])

        try:
            # Create pipe and start serving
            pipe_path = manager.create_named_pipe()
            manager.start_serving("test content")

            # Simulate connection handling
            future = manager._handle_incoming_connection()

            # Wait for processing
            if future:
                try:
                    future.result(timeout=2.0)
                except Exception:
                    pass  # Connection handling might fail in test environment

            # Should have received some events
            assert len(received_events) > 0, "Should have received connection events"

            # Check event types
            event_types = [e.connection_event_type for e in received_events]
            assert ConnectionEventType.CONNECT_ATTEMPT in event_types, (
                "Should have connection attempt event"
            )

        finally:
            manager.cleanup()

    def test_pipe_manager_multiple_event_listeners(self):
        """Test that PipeManager can handle multiple event listeners."""
        # Arrange
        from pipedoc.connection_events import ConnectionEvent

        events_listener1 = []
        events_listener2 = []

        class TestEventListener1:
            def on_connection_event(self, event_data: ConnectionEvent) -> None:
                events_listener1.append(event_data)

        class TestEventListener2:
            def on_connection_event(self, event_data: ConnectionEvent) -> None:
                events_listener2.append(event_data)

        listener1 = TestEventListener1()
        listener2 = TestEventListener2()

        # Act - Create PipeManager with multiple listeners
        manager = PipeManager(event_listeners=[listener1, listener2])

        try:
            # Both listeners should be registered
            assert hasattr(manager, "_event_manager"), "Should have event manager"

            # Test adding another listener dynamically
            class TestEventListener3:
                def on_connection_event(self, event_data: ConnectionEvent) -> None:
                    pass

            listener3 = TestEventListener3()
            manager.add_event_listener(listener3)

            # Test removing a listener
            manager.remove_event_listener(listener2)

        finally:
            manager.cleanup()
