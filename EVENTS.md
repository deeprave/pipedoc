# Event System Architecture

## Overview

PipeDoc implements a comprehensive event-driven architecture for monitoring, logging, and responding to system events. The event system provides both general-purpose and connection-specific event handling capabilities following SOLID design principles.

## Core Components

### Event System Foundation (`src/pipedoc/event_system.py`)

The general-purpose event system provides:

- **ApplicationEvent**: Base class for all application events
- **EventListener**: Protocol for general event listeners  
- **EventManager**: Manages listeners and event dispatching
- **StructuredLogger**: Structured logging replacement for print statements
- **EventLevel**: Standard event levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)

```python
class ApplicationEvent:
    event_type: str
    timestamp: float
    component: str
    message: str
    level: EventLevel = EventLevel.INFO
    metadata: Optional[Dict[str, Any]] = None
```

### Connection Events (`src/pipedoc/connection_events.py`)

Connection-specific event system built on the general foundation:

- **ConnectionEventType**: Enum of connection lifecycle event types
- **ConnectionEvent**: Inherits from ApplicationEvent with connection-specific attributes
- **ConnectionEventListener**: Protocol extending EventListener for connection events
- **ConnectionEventManager**: Manages connection event dispatching with async support

### Event Handlers (`src/pipedoc/event_handlers.py`)

Built-in event handlers providing common functionality:

- **LoggingEventHandler**: Logs events with text/JSON format support
- **FileEventHandler**: Writes events to files
- **StatisticsEventHandler**: Collects connection statistics
- **EventHandlerChain**: Middleware pattern for chaining handlers
- **FilteringEventHandler**: Conditional event processing

## Connection Event Types

| Event Type | Description | Default Level |
|------------|-------------|---------------|
| CONNECT_ATTEMPT | Connection attempt initiated | INFO |
| CONNECT_SUCCESS | Connection established successfully | INFO |
| CONNECT_FAILURE | Connection failed | WARNING |
| CONNECT_QUEUED | Connection queued for processing | DEBUG |
| CONNECT_DEQUEUED | Connection removed from queue | DEBUG |
| CONNECT_TIMEOUT | Connection timed out | WARNING |
| DISCONNECT | Connection closed | INFO |

## Usage Examples

### Basic Event Listening

```python
from pipedoc.connection_events import ConnectionEventManager, ConnectionEvent, ConnectionEventType
from pipedoc.event_handlers import LoggingEventHandler

# Create event manager
event_manager = ConnectionEventManager()

# Add logging handler
logger_handler = LoggingEventHandler(format_type="json")
event_manager.add_listener(logger_handler)

# Start async dispatching
event_manager.start_dispatching()

# Emit events
event_data = ConnectionEvent(
    event_type=ConnectionEventType.CONNECT_SUCCESS,
    connection_id="conn_123",
    timestamp=time.time(),
    duration=0.15
)
event_manager.emit_event(event_data)
```

### Event Handler Chaining

```python
from pipedoc.event_handlers import EventHandlerChain, LoggingEventHandler, StatisticsEventHandler

# Create handler chain
chain = EventHandlerChain()
chain.add_handler(LoggingEventHandler()).add_handler(StatisticsEventHandler())

event_manager.add_listener(chain)
```

### Custom Event Filtering

```python
from pipedoc.event_handlers import FilteringEventHandler, LoggingEventHandler

# Only log failures and timeouts
error_filter = lambda event: event.connection_event_type in [
    ConnectionEventType.CONNECT_FAILURE, 
    ConnectionEventType.CONNECT_TIMEOUT
]

filtered_handler = FilteringEventHandler(
    LoggingEventHandler(format_type="json"),
    error_filter
)
event_manager.add_listener(filtered_handler)
```

### General Event System Usage

```python
from pipedoc.event_system import StructuredLogger, EventManager, ApplicationEvent

# Structured logging
logger = StructuredLogger("MyComponent")
logger.info("Operation completed", operation_id="op_123", duration=0.5)

# General event handling
event_manager = EventManager()
event = ApplicationEvent(
    event_type="custom_operation",
    timestamp=time.time(),
    component="MyComponent",
    message="Custom operation completed",
    metadata={"result": "success"}
)
event_manager.emit(event)
```

## Integration Points

### PipeManager Integration

The PipeManager initialises connection event management with default handlers:

```python
def __init__(self, max_workers: int = 4, queue_size: int = 100):
    self._event_manager = ConnectionEventManager()
    self._event_manager.start_dispatching()
    
    # Add built-in handlers
    self._event_manager.add_listener(LoggingEventHandler())
    self._event_manager.add_listener(StatisticsEventHandler())
```

### ConnectionManager Integration

Connection events are emitted at key lifecycle points:

```python
def _emit_event(self, event_type: ConnectionEventType, connection_id: str, 
               duration: Optional[float] = None, **metadata):
    if self._event_manager:
        event_data = ConnectionEvent(
            event_type=event_type,
            connection_id=connection_id,
            timestamp=time.time(),
            duration=duration,
            metadata=metadata
        )
        self._event_manager.emit_event(event_data)
```

### Structured Logging

All components use structured logging via the event system:

```python
self._logger = StructuredLogger("ComponentName")
self._logger.info("Operation started", param1=value1, param2=value2)
self._logger.error("Operation failed", error=str(e), context=context)
```

## Design Principles

### Inheritance Hierarchy

- `ConnectionEvent` inherits from `ApplicationEvent`
- `ConnectionEventListener` extends `EventListener` protocol
- Clean extension mechanism using kwargs for additional attributes

### Protocol-Based Design

Uses Python's `Protocol` and `runtime_checkable` for flexible, duck-typed interfaces:

```python
@runtime_checkable
class ConnectionEventListener(EventListener, Protocol):
    def on_connection_event(self, event_data: ConnectionEvent) -> None: ...
    def on_event(self, event: ApplicationEvent) -> None: ...
```

### Thread Safety

Connection event manager provides thread-safe async event dispatching:
- Events queued and processed in background thread
- Thread-safe listener management with locks
- Error isolation prevents listener failures from affecting others

### SOLID Principles

- **Single Responsibility**: Each handler has one clear purpose
- **Open/Closed**: New handlers can be added without modifying existing code
- **Liskov Substitution**: ConnectionEvent can substitute ApplicationEvent
- **Interface Segregation**: Separate protocols for general vs connection-specific events
- **Dependency Inversion**: Components depend on abstractions (protocols)

## Performance Considerations

### Async Event Processing

Events are processed asynchronously to avoid blocking connection operations:

```python
def emit_event(self, event_data: ConnectionEvent) -> None:
    if self._running:
        # Async - queue for background processing
        self._event_queue.put(event_data)
    else:
        # Sync - immediate processing
        self._dispatch_to_listeners(event_data)
```

### Error Isolation

Individual listener failures don't affect other listeners or the main application:

```python
for listener in current_listeners:
    try:
        listener.on_connection_event(event_data)
    except Exception:
        # Isolate errors - continue with other listeners
        continue
```

### Memory Management

- Events use frozen behaviour for immutability
- Statistics handler maintains bounded duration history
- Background thread properly shuts down with resource cleanup

## Configuration Options

### Event Handler Configuration

```python
# Logging with custom levels
logger_handler = LoggingEventHandler(
    logger_name="custom.events",
    format_type="json",
    level_mapper=lambda event: "error" if "failure" in event.value else "info"
)

# File output with JSON format
file_handler = FileEventHandler(
    file_path="/var/log/pipedoc/events.json",
    format="json"
)

# Statistics with custom tracking
stats_handler = StatisticsEventHandler()
```

### Event Manager Options

```python
# Enable/disable async processing
event_manager.start_dispatching()  # Async mode
event_manager.stop_dispatching()   # Sync mode

# Listener management
event_manager.add_listener(handler)
event_manager.remove_listener(handler)
event_manager.get_listener_count()
```

## Extending the Event System

### Creating Custom Events

To create custom event types, extend `ApplicationEvent`:

```python
class CustomEvent(ApplicationEvent):
    def __init__(self, operation: str, user_id: str, timestamp: float, 
                 result: str, metadata: Optional[Dict[str, Any]] = None):
        super().__init__(
            event_type=f"custom_{operation}",
            timestamp=timestamp,
            component="CustomComponent",
            message=f"Operation {operation} completed with result: {result}",
            level=EventLevel.INFO,
            metadata=metadata or {},
            # Additional attributes
            operation=operation,
            user_id=user_id,
            result=result
        )
```

### Creating Custom Handlers

Implement the appropriate listener protocol:

```python
class CustomEventHandler:
    def on_event(self, event: ApplicationEvent) -> None:
        if isinstance(event, CustomEvent):
            # Process custom event
            self.process_custom_event(event)
    
    def process_custom_event(self, event: CustomEvent) -> None:
        # Custom processing logic
        pass
```

## Best Practices

1. **Use Structured Logging**: Replace all print statements with StructuredLogger
2. **Emit Events at Key Points**: Identify critical lifecycle points for event emission
3. **Include Relevant Metadata**: Add context-specific information in event metadata
4. **Handle Errors Gracefully**: Event listeners should not crash the application
5. **Choose Appropriate Levels**: Use DEBUG for detailed tracing, INFO for normal operations
6. **Test Event Handlers**: Include unit tests for custom event handlers
7. **Monitor Performance**: Be mindful of event volume in high-throughput scenarios

## Future Considerations

The event system is designed to be extensible for future enhancements:

- Metrics integration (Prometheus/StatsD export)
- Event persistence for historical analysis
- Event replay capabilities for debugging
- Advanced filtering and routing rules
- Event transformation and enrichment middleware
- Performance monitoring and alerting