"""
Tests for connection event system.

This module tests the event data structures and ConnectionEventManager
that provide lifecycle event handling for connections.
"""

import threading
import time
from typing import List
from unittest.mock import Mock

import pytest

from pipedoc.connection_events import (
    ConnectionEventType,
    ConnectionEvent,
    ConnectionEventListener,
    ConnectionEventManager,
)


class TestConnectionEventType:
    """Test ConnectionEventType enum."""

    def test_connection_event_values(self):
        """Test that all expected connection events are defined."""
        # Assert - All lifecycle events should be available
        assert hasattr(ConnectionEventType, "CONNECT_ATTEMPT")
        assert hasattr(ConnectionEventType, "CONNECT_SUCCESS")
        assert hasattr(ConnectionEventType, "CONNECT_FAILURE")
        assert hasattr(ConnectionEventType, "CONNECT_QUEUED")
        assert hasattr(ConnectionEventType, "CONNECT_DEQUEUED")
        assert hasattr(ConnectionEventType, "CONNECT_TIMEOUT")
        assert hasattr(ConnectionEventType, "DISCONNECT")

    def test_connection_event_enum_properties(self):
        """Test that ConnectionEvent behaves as proper enum."""
        # Test enum uniqueness
        events = list(ConnectionEventType)
        assert len(events) == len(set(events)), "All events should be unique"

        # Test string representation
        assert (
            str(ConnectionEventType.CONNECT_ATTEMPT)
            == "ConnectionEventType.CONNECT_ATTEMPT"
        )


class TestConnectionEvent:
    """Test ConnectionEvent dataclass."""

    def test_connection_event_data_creation(self):
        """Test basic ConnectionEvent creation."""
        # Arrange
        event_type = ConnectionEventType.CONNECT_ATTEMPT
        connection_id = "conn_123"
        timestamp = time.time()

        # Act
        event_data = ConnectionEvent(
            event_type=event_type, connection_id=connection_id, timestamp=timestamp
        )

        # Assert
        assert event_data.connection_event_type == event_type
        assert event_data.connection_id == connection_id
        assert event_data.timestamp == timestamp
        assert event_data.duration is None
        assert event_data.metadata == {}

    def test_connection_event_data_with_duration(self):
        """Test ConnectionEvent with duration."""
        # Arrange
        event_type = ConnectionEventType.CONNECT_SUCCESS
        duration = 0.123

        # Act
        event_data = ConnectionEvent(
            event_type=event_type,
            connection_id="conn_123",
            timestamp=time.time(),
            duration=duration,
        )

        # Assert
        assert event_data.duration == duration

    def test_connection_event_data_with_metadata(self):
        """Test ConnectionEvent with metadata."""
        # Arrange
        metadata = {"queue_depth": 5, "worker_id": "worker_1"}

        # Act
        event_data = ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_QUEUED,
            connection_id="conn_123",
            timestamp=time.time(),
            metadata=metadata,
        )

        # Assert
        assert event_data.metadata == metadata

    def test_connection_event_data_immutable(self):
        """Test that ConnectionEvent is immutable (frozen dataclass)."""
        # Arrange
        event_data = ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_ATTEMPT,
            connection_id="conn_123",
            timestamp=time.time(),
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            event_data.connection_event_type = ConnectionEventType.CONNECT_SUCCESS


class MockEventListener:
    """Mock event listener for testing."""

    def __init__(self):
        self.received_events: List[ConnectionEvent] = []
        self.call_count = 0

    def on_connection_event(self, event_data: ConnectionEvent) -> None:
        """Handle connection event."""
        self.received_events.append(event_data)
        self.call_count += 1


class TestConnectionEventManager:
    """Test ConnectionEventManager functionality."""

    def test_event_manager_creation(self):
        """Test basic event manager creation."""
        # Act
        manager = ConnectionEventManager()

        # Assert
        assert not manager.is_running()
        assert manager.get_listener_count() == 0

    def test_add_remove_listener(self):
        """Test adding and removing event listeners."""
        # Arrange
        manager = ConnectionEventManager()
        listener = MockEventListener()

        # Act - Add listener
        manager.add_listener(listener)

        # Assert
        assert manager.get_listener_count() == 1

        # Act - Remove listener
        manager.remove_listener(listener)

        # Assert
        assert manager.get_listener_count() == 0

    def test_add_duplicate_listener(self):
        """Test that adding same listener twice doesn't duplicate."""
        # Arrange
        manager = ConnectionEventManager()
        listener = MockEventListener()

        # Act
        manager.add_listener(listener)
        manager.add_listener(listener)  # Add same listener again

        # Assert
        assert manager.get_listener_count() == 1

    def test_remove_nonexistent_listener(self):
        """Test removing listener that wasn't added."""
        # Arrange
        manager = ConnectionEventManager()
        listener = MockEventListener()

        # Act - Should not raise exception
        manager.remove_listener(listener)

        # Assert
        assert manager.get_listener_count() == 0

    def test_emit_event_no_listeners(self):
        """Test emitting event when no listeners registered."""
        # Arrange
        manager = ConnectionEventManager()
        event_data = ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_ATTEMPT,
            connection_id="conn_123",
            timestamp=time.time(),
        )

        # Act - Should not raise exception
        manager.emit_event(event_data)

        # Assert - No assertions needed, just ensure no exceptions

    def test_emit_event_with_listeners_sync(self):
        """Test emitting event to listeners synchronously (when not running)."""
        # Arrange
        manager = ConnectionEventManager()
        listener1 = MockEventListener()
        listener2 = MockEventListener()

        manager.add_listener(listener1)
        manager.add_listener(listener2)

        event_data = ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_SUCCESS,
            connection_id="conn_123",
            timestamp=time.time(),
            duration=0.1,
        )

        # Act
        manager.emit_event(event_data)

        # Assert
        assert listener1.call_count == 1
        assert listener2.call_count == 1
        assert len(listener1.received_events) == 1
        assert len(listener2.received_events) == 1
        assert listener1.received_events[0] == event_data
        assert listener2.received_events[0] == event_data

    def test_start_stop_async_dispatching(self):
        """Test starting and stopping async event dispatching."""
        # Arrange
        manager = ConnectionEventManager()

        # Act - Start
        manager.start_dispatching()

        # Assert
        assert manager.is_running()

        # Act - Stop
        manager.stop_dispatching()

        # Assert
        assert not manager.is_running()

    def test_emit_event_async_dispatching(self):
        """Test emitting events with async dispatching enabled."""
        # Arrange
        manager = ConnectionEventManager()
        listener = MockEventListener()
        manager.add_listener(listener)

        event_data = ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_QUEUED,
            connection_id="conn_123",
            timestamp=time.time(),
        )

        try:
            # Act
            manager.start_dispatching()
            manager.emit_event(event_data)

            # Wait for async processing
            time.sleep(0.1)

            # Assert
            assert listener.call_count == 1
            assert len(listener.received_events) == 1
            assert listener.received_events[0] == event_data

        finally:
            manager.stop_dispatching()

    def test_listener_error_isolation(self):
        """Test that listener errors don't affect other listeners."""
        # Arrange
        manager = ConnectionEventManager()

        # Create failing listener
        failing_listener = Mock()
        failing_listener.on_connection_event.side_effect = RuntimeError(
            "Listener error"
        )

        # Create working listener
        working_listener = MockEventListener()

        manager.add_listener(failing_listener)
        manager.add_listener(working_listener)

        event_data = ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_FAILURE,
            connection_id="conn_123",
            timestamp=time.time(),
        )

        # Act - Should not raise exception despite failing listener
        manager.emit_event(event_data)

        # Assert
        assert working_listener.call_count == 1
        assert len(working_listener.received_events) == 1

    def test_thread_safety_multiple_listeners(self):
        """Test thread safety with multiple listeners and concurrent events."""
        # Arrange
        manager = ConnectionEventManager()
        listeners = [MockEventListener() for _ in range(3)]

        for listener in listeners:
            manager.add_listener(listener)

        events = []
        for i in range(10):
            events.append(
                ConnectionEvent(
                    event_type=ConnectionEventType.CONNECT_ATTEMPT,
                    connection_id=f"conn_{i}",
                    timestamp=time.time(),
                )
            )

        def emit_events():
            """Emit events from thread."""
            for event in events:
                manager.emit_event(event)

        try:
            # Act - Start async dispatching
            manager.start_dispatching()

            # Emit events from multiple threads
            threads = []
            for _ in range(3):
                thread = threading.Thread(target=emit_events)
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join()

            # Wait for async processing
            time.sleep(0.2)

            # Assert - Each listener should receive all events from all threads
            expected_total = len(events) * 3  # 3 threads
            for listener in listeners:
                assert listener.call_count == expected_total

        finally:
            manager.stop_dispatching()

    def test_cleanup_after_stop(self):
        """Test that resources are cleaned up after stopping."""
        # Arrange
        manager = ConnectionEventManager()
        listener = MockEventListener()
        manager.add_listener(listener)

        # Act
        manager.start_dispatching()
        manager.stop_dispatching()

        # Assert - Should be able to restart
        manager.start_dispatching()
        assert manager.is_running()
        manager.stop_dispatching()
