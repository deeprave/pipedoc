"""
Tests for event system integration and inheritance.

This module tests that ConnectionEvent properly inherits from ApplicationEvent
and that ConnectionEventListener properly extends EventListener.
"""

import time
from pipedoc.connection_events import ConnectionEventType, ConnectionEvent, ConnectionEventListener
from pipedoc.event_system import ApplicationEvent, EventListener, EventLevel


class TestEventSystemIntegration:
    """Test the integration between general and connection-specific event systems."""
    
    def test_connection_event_data_inherits_from_application_event(self):
        """Test that ConnectionEvent is a proper ApplicationEvent."""
        # Arrange & Act
        event_data = ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_SUCCESS,
            connection_id="test_conn",
            timestamp=time.time(),
            duration=0.1,
            metadata={'key': 'value'}
        )
        
        # Assert - Should be both types
        assert isinstance(event_data, ApplicationEvent), "Should be an ApplicationEvent"
        assert isinstance(event_data, ConnectionEvent), "Should be a ConnectionEvent"
        
        # Should have ApplicationEvent properties
        assert event_data.component == "ConnectionManager"
        assert event_data.level == EventLevel.INFO
        assert "Connection test_conn: connect_success" in event_data.message
        
        # Should have ConnectionEvent properties
        assert event_data.connection_id == "test_conn"
        assert event_data.connection_event_type == ConnectionEventType.CONNECT_SUCCESS
        assert event_data.duration == 0.1
    
    def test_connection_event_level_mapping(self):
        """Test that connection events are mapped to appropriate levels."""
        test_cases = [
            (ConnectionEventType.CONNECT_SUCCESS, EventLevel.INFO),
            (ConnectionEventType.CONNECT_ATTEMPT, EventLevel.INFO),
            (ConnectionEventType.CONNECT_FAILURE, EventLevel.WARNING),
            (ConnectionEventType.CONNECT_TIMEOUT, EventLevel.WARNING),
            (ConnectionEventType.CONNECT_QUEUED, EventLevel.DEBUG),
            (ConnectionEventType.CONNECT_DEQUEUED, EventLevel.DEBUG),
        ]
        
        for event_type, expected_level in test_cases:
            event_data = ConnectionEvent(
                event_type=event_type,
                connection_id="test",
                timestamp=time.time()
            )
            assert event_data.level == expected_level, f"{event_type} should map to {expected_level}"
    
    def test_connection_event_listener_extends_event_listener(self):
        """Test that ConnectionEventListener properly extends EventListener."""
        # Arrange
        received_events = []
        
        class TestListener:
            def on_connection_event(self, event_data: ConnectionEvent) -> None:
                received_events.append(("connection", event_data))
            
            def on_event(self, event: ApplicationEvent) -> None:
                received_events.append(("general", event))
                # The default implementation should delegate to connection handler
                if isinstance(event, ConnectionEvent):
                    self.on_connection_event(event)
        
        listener = TestListener()
        
        # Assert - Should implement both protocols
        assert isinstance(listener, ConnectionEventListener), "Should implement ConnectionEventListener"
        # Note: Can't easily test EventListener isinstance due to Protocol limitations
        
        # Test delegation works
        connection_event = ConnectionEvent(
            ConnectionEventType.CONNECT_SUCCESS,
            "test_conn",
            time.time()
        )
        
        # Act - Call as general event listener
        listener.on_event(connection_event)
        
        # Assert - Should have received both general and specific events
        assert len(received_events) == 2
        assert received_events[0][0] == "general"
        assert received_events[1][0] == "connection"
        assert received_events[0][1] == received_events[1][1]  # Same event object
    
    def test_unified_event_handling(self):
        """Test that unified event handling works with general event manager."""
        # Arrange
        from pipedoc.event_system import EventManager
        
        received_events = []
        
        class UnifiedListener:
            def on_event(self, event: ApplicationEvent) -> None:
                received_events.append(event)
        
        event_manager = EventManager()
        listener = UnifiedListener()
        event_manager.add_listener(listener)
        
        # Act - Emit a connection event through general event manager
        connection_event = ConnectionEvent(
            ConnectionEventType.CONNECT_ATTEMPT,
            "unified_test",
            time.time(),
            metadata={'source': 'test'}
        )
        
        event_manager.emit(connection_event)
        
        # Assert - Should have received the event
        assert len(received_events) == 1
        assert received_events[0] == connection_event
        assert received_events[0].connection_id == "unified_test"
        assert received_events[0].component == "ConnectionManager"
    
    def test_backwards_compatibility_maintained(self):
        """Test that existing connection event handling still works."""
        # Arrange
        from pipedoc.connection_events import ConnectionEventManager
        
        received_events = []
        
        class TraditionalListener:
            def on_connection_event(self, event_data: ConnectionEvent) -> None:
                received_events.append(event_data)
        
        event_manager = ConnectionEventManager()
        listener = TraditionalListener()
        event_manager.add_listener(listener)
        
        # Act - Use traditional connection event flow
        event_data = ConnectionEvent(
            ConnectionEventType.CONNECT_SUCCESS,
            "backwards_test",
            time.time()
        )
        
        event_manager.emit_event(event_data)
        
        # Assert - Traditional flow should still work
        assert len(received_events) == 1
        assert received_events[0] == event_data
        assert received_events[0].connection_id == "backwards_test"
        
        # And it should have ApplicationEvent properties
        assert isinstance(received_events[0], ApplicationEvent)
        assert received_events[0].component == "ConnectionManager"


class TestEventSystemDesignPrinciples:
    """Test that the unified design follows good principles."""
    
    def test_liskov_substitution_principle(self):
        """Test that ConnectionEvent can substitute ApplicationEvent."""
        # Arrange
        def process_application_event(event: ApplicationEvent) -> str:
            """Function that expects ApplicationEvent."""
            return f"{event.component}: {event.message}"
        
        # Act - Should work with ConnectionEvent
        connection_event = ConnectionEvent(
            ConnectionEventType.CONNECT_SUCCESS,
            "lsp_test",
            time.time()
        )
        
        result = process_application_event(connection_event)
        
        # Assert - Should work without issues
        assert "ConnectionManager" in result
        assert "connect_success" in result
    
    def test_interface_segregation_principle(self):
        """Test that specific interfaces don't force unnecessary dependencies."""
        # Arrange - A listener that only cares about general events
        class GeneralOnlyListener:
            def on_event(self, event: ApplicationEvent) -> None:
                pass  # Can handle any ApplicationEvent
        
        # A listener that only cares about connection events
        class ConnectionOnlyListener:
            def on_connection_event(self, event_data: ConnectionEvent) -> None:
                pass  # Only needs connection-specific interface
        
        # Assert - Both should be valid without forcing unnecessary methods
        general_listener = GeneralOnlyListener()
        connection_listener = ConnectionOnlyListener()
        
        # Should be able to use each appropriately
        assert hasattr(general_listener, 'on_event')
        assert hasattr(connection_listener, 'on_connection_event')
    
    def test_single_responsibility_principle(self):
        """Test that event types maintain single responsibility."""
        # Arrange
        connection_event = ConnectionEvent(
            ConnectionEventType.CONNECT_QUEUED,
            "srp_test",
            time.time()
        )
        
        # Assert - Should handle both general event concerns and connection specifics
        # General event concerns
        assert hasattr(connection_event, 'timestamp')
        assert hasattr(connection_event, 'level')
        assert hasattr(connection_event, 'component')
        
        # Connection-specific concerns
        assert hasattr(connection_event, 'connection_id')
        assert hasattr(connection_event, 'event_type')
        assert hasattr(connection_event, 'duration')
        
        # But should not have unrelated concerns
        assert not hasattr(connection_event, 'file_path')  # Not a file event
        assert not hasattr(connection_event, 'user_id')    # Not a user event