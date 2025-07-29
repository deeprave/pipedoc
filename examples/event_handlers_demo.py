#!/usr/bin/env python3
"""
Demonstration of PipeDoc event handlers and structured logging.

This example shows how to use the built-in event handlers for comprehensive
monitoring, logging, and statistics collection in a PipeDoc application.
"""

import logging
import tempfile
import time
from pathlib import Path

from pipedoc.pipe_manager import PipeManager
from pipedoc.event_handlers import (
    LoggingEventHandler, 
    FileEventHandler, 
    StatisticsEventHandler,
    EventHandlerChain,
    FilteringEventHandler
)
from pipedoc.connection_events import ConnectionEventType


def setup_logging():
    """Configure logging for the demo."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def demo_basic_event_handlers():
    """Demonstrate basic event handler usage."""
    print("\n" + "="*60)
    print("DEMO: Basic Event Handlers")
    print("="*60)
    
    # Create temporary log file
    log_file = tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False)
    log_file.close()
    
    try:
        # Create event handlers
        logging_handler = LoggingEventHandler(
            logger_name="pipedoc.demo",
            format_type="json"  # Use JSON format for structured logging
        )
        
        file_handler = FileEventHandler(
            log_file.name,
            format="json"  # JSON format for machine-readable logs
        )
        
        stats_handler = StatisticsEventHandler()
        
        # Create PipeManager with event handlers
        manager = PipeManager(
            max_workers=2,
            queue_size=3,
            event_listeners=[logging_handler, file_handler, stats_handler]
        )
        
        try:
            # Create pipe and simulate some activity
            pipe_path = manager.create_named_pipe()
            manager.start_serving("Demo content for event handler testing")
            
            # Simulate some connections
            print(f"Simulating connections to {pipe_path}")
            for i in range(5):
                future = manager._handle_incoming_connection()
                if future:
                    try:
                        result = future.result(timeout=1.0)
                        print(f"Connection {i}: {result}")
                    except Exception as e:
                        print(f"Connection {i} failed: {e}")
                
                time.sleep(0.1)  # Small delay between connections
            
            # Get and display statistics
            print("\nConnection Statistics:")
            stats = stats_handler.get_statistics()
            for key, value in stats.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.3f}")
                else:
                    print(f"  {key}: {value}")
            
            # Display log file contents
            print(f"\nLog file contents ({log_file.name}):")
            with open(log_file.name, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    print(f"  {line_num}: {line.strip()}")
            
        finally:
            manager.cleanup()
            
    finally:
        # Cleanup log file
        Path(log_file.name).unlink(missing_ok=True)


def demo_event_handler_chaining():
    """Demonstrate event handler chaining and filtering."""
    print("\n" + "="*60)
    print("DEMO: Event Handler Chaining and Filtering")
    print("="*60)
    
    # Create handlers
    stats_handler = StatisticsEventHandler()
    
    # Create a logging handler that only logs warnings and errors
    error_logger = LoggingEventHandler(
        logger_name="pipedoc.errors",
        format_type="text"
    )
    
    # Filter to only pass failure and timeout events to error logger
    def error_filter(event_data):
        return event_data.connection_event_type in [
            ConnectionEventType.CONNECT_FAILURE,
            ConnectionEventType.CONNECT_TIMEOUT
        ]
    
    filtered_error_handler = FilteringEventHandler(error_logger, error_filter)
    
    # Create an event chain with multiple handlers
    event_chain = (EventHandlerChain()
                  .add_handler(stats_handler)
                  .add_handler(filtered_error_handler))
    
    print(f"Event chain has {event_chain.get_handler_count()} handlers")
    
    # Create PipeManager with the event chain
    manager = PipeManager(
        max_workers=1,  # Single worker to force queueing
        queue_size=2,
        event_listeners=[event_chain]
    )
    
    try:
        pipe_path = manager.create_named_pipe()
        manager.start_serving("Chained event handler demo content")
        
        # Simulate multiple connections to trigger queueing and potential failures
        print("Simulating connections with limited worker pool...")
        futures = []
        for i in range(6):  # More connections than queue + workers
            future = manager._handle_incoming_connection()
            if future:
                futures.append(future)
        
        # Wait for some processing
        time.sleep(0.5)
        
        # Check results
        successful = 0
        failed = 0
        for future in futures:
            try:
                future.result(timeout=0.1)
                successful += 1
            except Exception:
                failed += 1
        
        print(f"Results: {successful} successful, {failed} failed/timeout")
        
        # Display final statistics
        print("\nFinal Statistics:")
        stats = stats_handler.get_statistics()
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.3f}")
            else:
                print(f"  {key}: {value}")
        
    finally:
        manager.cleanup()


def demo_custom_level_mapping():
    """Demonstrate custom log level mapping."""
    print("\n" + "="*60)
    print("DEMO: Custom Log Level Mapping")
    print("="*60)
    
    def custom_level_mapper(event_type):
        """Custom mapping: queue events as INFO, others as DEBUG."""
        if event_type in [ConnectionEventType.CONNECT_QUEUED, ConnectionEventType.CONNECT_DEQUEUED]:
            return "info"
        else:
            return "debug"
    
    # Create handler with custom level mapping
    custom_logger = LoggingEventHandler(
        logger_name="pipedoc.custom",
        format_type="text",
        level_mapper=custom_level_mapper
    )
    
    # Create PipeManager with custom logging
    manager = PipeManager(
        max_workers=1,
        queue_size=3,
        event_listeners=[custom_logger]
    )
    
    try:
        pipe_path = manager.create_named_pipe()
        manager.start_serving("Custom level mapping demo")
        
        print("Generating events with custom log levels...")
        
        # Generate some connections to trigger various event types
        futures = []
        for i in range(4):
            future = manager._handle_incoming_connection()
            if future:
                futures.append(future)
        
        # Wait for processing
        time.sleep(0.3)
        
        print("Check the log output above to see custom log levels in action!")
        
    finally:
        manager.cleanup()


def main():
    """Run all demonstrations."""
    setup_logging()
    
    print("PipeDoc Event Handlers Demonstration")
    print("This demo shows the event system capabilities:")
    print("- Basic event handlers (Logging, File, Statistics)")
    print("- Event handler chaining and filtering")
    print("- Custom log level mapping")
    print("- JSON and text format options")
    
    demo_basic_event_handlers()
    demo_event_handler_chaining()
    demo_custom_level_mapping()
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print("The event system provides:")
    print("✓ Structured logging with JSON/text formats")
    print("✓ File-based event logging")
    print("✓ Real-time statistics collection")
    print("✓ Event filtering and chaining")
    print("✓ Custom log level mapping")
    print("✓ Error isolation between handlers")


if __name__ == "__main__":
    main()