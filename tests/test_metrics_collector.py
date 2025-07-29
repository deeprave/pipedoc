"""
Tests for the MetricsCollector component.

This module tests the thread-safe metrics collection functionality
including connection tracking, timing measurements, and statistics.
"""

import threading
import time

import pytest

from pipedoc.metrics_collector import MetricsCollector


class TestMetricsCollector:
    """Test cases for MetricsCollector component."""

    def test_metrics_collector_basic_functionality(self):
        """Test basic connection tracking and metrics calculation."""
        # Arrange
        collector = MetricsCollector()
        
        # Act - Record various connection events
        collector.record_connection_attempt()
        collector.record_connection_attempt() 
        collector.record_connection_attempt()
        
        # First connection succeeds with timing
        collector.record_connection_success(connection_time=0.05)  # 50ms
        
        # Second connection succeeds with timing  
        collector.record_connection_success(connection_time=0.03)  # 30ms
        
        # Third connection fails
        collector.record_connection_failure()
        
        # Get current metrics
        metrics = collector.get_metrics()
        
        # Assert - Verify basic counters
        assert metrics['connection_attempts'] == 3, "Should track all connection attempts"
        assert metrics['successful_connections'] == 2, "Should track successful connections" 
        assert metrics['failed_connections'] == 1, "Should track failed connections"
        
        # Assert - Verify success rate calculation
        expected_success_rate = 2.0 / 3.0  # 66.67%
        assert abs(metrics['success_rate'] - expected_success_rate) < 0.01, \
            f"Success rate should be {expected_success_rate:.2%}, got {metrics['success_rate']:.2%}"
        
        # Assert - Verify timing calculations
        assert 'avg_connection_time' in metrics, "Should calculate average connection time"
        expected_avg_time = (0.05 + 0.03) / 2  # 40ms average
        assert abs(metrics['avg_connection_time'] - expected_avg_time) < 0.001, \
            f"Average time should be {expected_avg_time:.3f}s, got {metrics['avg_connection_time']:.3f}s"
        
        # Assert - Verify connection times are preserved
        assert len(metrics['connection_times']) == 2, "Should preserve individual connection times"
        assert 0.05 in metrics['connection_times'], "Should contain first connection time"
        assert 0.03 in metrics['connection_times'], "Should contain second connection time"

    def test_metrics_collector_thread_safety(self):
        """Test that MetricsCollector is thread-safe under concurrent access."""
        # Arrange
        collector = MetricsCollector()
        num_threads = 5
        operations_per_thread = 10
        results = []
        
        def worker_thread(thread_id: int):
            """Worker that performs concurrent metrics operations."""
            for i in range(operations_per_thread):
                # Mix of different operations
                collector.record_connection_attempt()
                
                if i % 2 == 0:
                    collector.record_connection_success(connection_time=0.01 * (i + 1))
                else:
                    collector.record_connection_failure()
                
                # Small delay to increase chance of race conditions
                time.sleep(0.001)
            
            results.append(f"Thread {thread_id} completed")
        
        # Act - Launch concurrent worker threads
        threads = []
        for thread_id in range(num_threads):
            thread = threading.Thread(target=worker_thread, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Assert - Verify all operations were recorded correctly
        metrics = collector.get_metrics()
        expected_attempts = num_threads * operations_per_thread
        
        assert metrics['connection_attempts'] == expected_attempts, \
            f"Should have {expected_attempts} attempts, got {metrics['connection_attempts']}"
        
        # Verify that successes + failures = attempts
        total_recorded = metrics['successful_connections'] + metrics['failed_connections']
        assert total_recorded == expected_attempts, \
            f"Successes + failures should equal attempts: {total_recorded} != {expected_attempts}"
        
        # Verify success rate is reasonable (should be around 50% based on our i % 2 logic)
        success_rate = metrics['success_rate']
        assert 0.4 <= success_rate <= 0.6, \
            f"Success rate should be around 50%, got {success_rate:.1%}"
        
        # Verify no data corruption occurred
        assert len(results) == num_threads, "All threads should have completed"
        assert all("completed" in result for result in results), "All threads should report completion"

    def test_metrics_collector_reset_functionality(self):
        """Test metrics reset functionality."""
        # Arrange
        collector = MetricsCollector()
        
        # Add some metrics data
        collector.record_connection_attempt()
        collector.record_connection_success(connection_time=0.1)
        collector.record_connection_failure()
        
        # Verify data exists
        metrics_before = collector.get_metrics()
        assert metrics_before['connection_attempts'] > 0, "Should have data before reset"
        
        # Act - Reset metrics
        collector.reset_metrics()
        
        # Assert - Verify all metrics are reset to initial state
        metrics_after = collector.get_metrics()
        assert metrics_after['connection_attempts'] == 0, "Attempts should be reset to 0"
        assert metrics_after['successful_connections'] == 0, "Successes should be reset to 0"
        assert metrics_after['failed_connections'] == 0, "Failures should be reset to 0"
        assert metrics_after['success_rate'] == 0.0, "Success rate should be reset to 0"
        assert metrics_after['avg_connection_time'] == 0.0, "Average time should be reset to 0"
        assert len(metrics_after['connection_times']) == 0, "Connection times should be empty"

    def test_metrics_collector_edge_cases(self):
        """Test edge cases and error conditions."""
        # Arrange
        collector = MetricsCollector()
        
        # Test - Empty metrics (no operations performed)
        empty_metrics = collector.get_metrics()
        assert empty_metrics['success_rate'] == 0.0, "Success rate should be 0 with no attempts"
        assert empty_metrics['avg_connection_time'] == 0.0, "Average time should be 0 with no connections"
        
        # Test - Only failures (no successes)
        collector.record_connection_attempt()
        collector.record_connection_failure()
        
        failure_only_metrics = collector.get_metrics()
        assert failure_only_metrics['success_rate'] == 0.0, "Success rate should be 0 with only failures"
        assert failure_only_metrics['avg_connection_time'] == 0.0, "Average time should be 0 with no successful connections"
        
        # Test - Negative connection time (should be handled gracefully)
        collector.record_connection_attempt()
        collector.record_connection_success(connection_time=-0.1)  # Invalid negative time
        
        metrics = collector.get_metrics()
        # Implementation should either reject negative times or handle them gracefully
        # This test documents the expected behavior
        assert metrics['successful_connections'] >= 1, "Should still record the success"

    def test_queue_metrics_basic_functionality(self):
        """Test queue-related metrics tracking."""
        # Arrange
        collector = MetricsCollector()
        
        # Act - Record queue events
        collector.record_connection_queued()
        collector.record_connection_queued()
        collector.record_connection_dequeued(wait_time=0.5)  # 500ms wait
        collector.record_connection_queued()
        collector.record_connection_timeout()
        collector.record_connection_dequeued(wait_time=1.2)  # 1200ms wait
        
        # Get current metrics
        metrics = collector.get_metrics()
        
        # Assert - Verify queue counters
        assert metrics['connections_queued'] == 3, "Should track total connections queued"
        assert metrics['connections_timeout'] == 1, "Should track connection timeouts"
        assert metrics['current_queue_depth'] == 0, "Should track current queue depth (3 queued - 2 dequeued - 1 timeout = 0)"
        assert metrics['max_queue_depth'] == 2, "Should track maximum queue depth reached"
        
        # Assert - Verify queue timing calculations
        assert 'avg_queue_wait_time' in metrics, "Should calculate average queue wait time"
        expected_avg_wait = (0.5 + 1.2) / 2  # 850ms average
        assert abs(metrics['avg_queue_wait_time'] - expected_avg_wait) < 0.001, \
            f"Average wait time should be {expected_avg_wait:.3f}s, got {metrics['avg_queue_wait_time']:.3f}s"
        
        # Assert - Verify queue utilisation
        assert 'queue_utilisation' in metrics, "Should calculate queue utilisation"
        expected_utilisation = 1.0  # max_queue_depth reached at some point
        assert metrics['queue_utilisation'] == expected_utilisation, \
            f"Queue utilisation should be {expected_utilisation:.1%}, got {metrics['queue_utilisation']:.1%}"

    def test_queue_metrics_thread_safety(self):
        """Test that queue metrics are thread-safe under concurrent access."""
        # Arrange
        collector = MetricsCollector()
        num_threads = 5
        operations_per_thread = 10
        
        def worker_thread(thread_id: int):
            """Worker that performs mixed queue operations."""
            for i in range(operations_per_thread):
                # Mix of different queue operations
                collector.record_connection_queued()
                
                if i % 3 == 0:
                    wait_time = 0.01 * (i + 1)
                    collector.record_connection_dequeued(wait_time)
                elif i % 3 == 1:
                    collector.record_connection_timeout()
                # else: just queue (no dequeue/timeout)
                
                # Small delay to increase chance of race conditions
                time.sleep(0.001)
        
        # Act - Launch concurrent worker threads
        threads = []
        for thread_id in range(num_threads):
            thread = threading.Thread(target=worker_thread, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Assert - Verify all operations were recorded correctly
        metrics = collector.get_metrics()
        expected_queued = num_threads * operations_per_thread
        
        # Calculate expected dequeued and timeouts based on our logic
        # For each thread: operations 0,3,6,9 → dequeue (4 ops)
        # For each thread: operations 1,4,7 → timeout (3 ops)  
        expected_dequeued = num_threads * 4  # 4 dequeue operations per thread
        expected_timeouts = num_threads * 3   # 3 timeout operations per thread
        
        assert metrics['connections_queued'] == expected_queued, \
            f"Should have {expected_queued} queued, got {metrics['connections_queued']}"
        assert metrics['connections_timeout'] == expected_timeouts, \
            f"Should have {expected_timeouts} timeouts, got {metrics['connections_timeout']}"
        
        # Current queue depth should be non-negative and calculated correctly
        expected_current_depth = expected_queued - expected_dequeued - expected_timeouts
        assert metrics['current_queue_depth'] == expected_current_depth, \
            f"Current queue depth should be {expected_current_depth}, got {metrics['current_queue_depth']}"
        assert metrics['current_queue_depth'] >= 0, "Queue depth should never be negative"

    def test_queue_metrics_reset(self):
        """Test that queue metrics are reset correctly."""
        # Arrange
        collector = MetricsCollector()
        
        # Add some queue metrics data
        collector.record_connection_queued()
        collector.record_connection_dequeued(wait_time=0.5)
        collector.record_connection_timeout()
        
        # Verify data exists
        metrics_before = collector.get_metrics()
        assert metrics_before['connections_queued'] > 0, "Should have queue data before reset"
        
        # Act - Reset metrics
        collector.reset_metrics()
        
        # Assert - Verify all queue metrics are reset
        metrics_after = collector.get_metrics()
        assert metrics_after['connections_queued'] == 0, "Queued connections should be reset to 0"
        assert metrics_after['connections_timeout'] == 0, "Timeout connections should be reset to 0"
        assert metrics_after['current_queue_depth'] == 0, "Current queue depth should be reset to 0"
        assert metrics_after['max_queue_depth'] == 0, "Max queue depth should be reset to 0"
        assert metrics_after['avg_queue_wait_time'] == 0.0, "Average wait time should be reset to 0"
        assert len(metrics_after['queue_wait_times']) == 0, "Queue wait times should be empty"


class TestMetricsCollectorEventIntegration:
    """Test MetricsCollector integration with event system."""
    
    def test_metrics_collector_implements_event_listener(self):
        """Test that MetricsCollector implements ConnectionEventListener protocol."""
        # Arrange
        from pipedoc.connection_events import ConnectionEventListener
        collector = MetricsCollector()
        
        # Assert - Should implement the protocol
        assert isinstance(collector, ConnectionEventListener), "Should implement ConnectionEventListener protocol"
        assert hasattr(collector, 'on_connection_event'), "Should have on_connection_event method"
    
    def test_metrics_collector_event_driven_basic_lifecycle(self):
        """Test event-driven metrics collection for basic connection lifecycle."""
        # Arrange
        from pipedoc.connection_events import ConnectionEventType, ConnectionEvent
        import time
        
        collector = MetricsCollector()
        timestamp = time.time()
        
        # Act - Simulate connection lifecycle through events
        # Connection attempt
        collector.on_connection_event(ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_ATTEMPT,
            connection_id="conn_1",
            timestamp=timestamp
        ))
        
        # Connection success with duration
        collector.on_connection_event(ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_SUCCESS,
            connection_id="conn_1",
            timestamp=timestamp + 0.1,
            duration=0.1
        ))
        
        # Another connection attempt
        collector.on_connection_event(ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_ATTEMPT,
            connection_id="conn_2",
            timestamp=timestamp + 0.2
        ))
        
        # Connection failure
        collector.on_connection_event(ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_FAILURE,
            connection_id="conn_2",
            timestamp=timestamp + 0.3
        ))
        
        # Assert - Should track events correctly
        metrics = collector.get_metrics()
        assert metrics['connection_attempts'] == 2, "Should count attempts from events"
        assert metrics['successful_connections'] == 1, "Should count successes from events"
        assert metrics['failed_connections'] == 1, "Should count failures from events"
        assert metrics['success_rate'] == 0.5, "Should calculate success rate from events"
    
    def test_metrics_collector_event_driven_queue_metrics(self):
        """Test event-driven queue metrics collection."""
        # Arrange
        from pipedoc.connection_events import ConnectionEventType, ConnectionEvent
        import time
        
        collector = MetricsCollector()
        timestamp = time.time()
        
        # Act - Simulate queue lifecycle through events
        # Connection queued
        collector.on_connection_event(ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_QUEUED,
            connection_id="conn_1",
            timestamp=timestamp,
            metadata={'queue_depth': 1}
        ))
        
        # Connection dequeued with wait time
        collector.on_connection_event(ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_DEQUEUED,
            connection_id="conn_1",
            timestamp=timestamp + 0.5,
            metadata={'wait_time': 0.5}
        ))
        
        # Connection timeout
        collector.on_connection_event(ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_TIMEOUT,
            connection_id="conn_2",
            timestamp=timestamp + 1.0
        ))
        
        # Assert - Should track queue events
        metrics = collector.get_metrics()
        assert metrics['connections_queued'] == 1, "Should count queued connections from events"
        assert metrics['connections_timeout'] == 1, "Should count timeouts from events"
        
        # Should track queue statistics
        assert 'max_queue_depth' in metrics, "Should track maximum queue depth"
        assert 'queue_wait_times' in metrics, "Should track queue wait times"
    
    def test_metrics_collector_event_driven_enhanced_statistics(self):
        """Test enhanced statistics from event-driven collection."""
        # Arrange
        from pipedoc.connection_events import ConnectionEventType, ConnectionEvent
        import time
        
        collector = MetricsCollector()
        timestamp = time.time()
        
        # Act - Generate multiple events with various patterns
        events = [
            # Fast successful connection
            (ConnectionEventType.CONNECT_ATTEMPT, "fast_conn", timestamp, {}),
            (ConnectionEventType.CONNECT_SUCCESS, "fast_conn", timestamp + 0.01, {'duration': 0.01}),
            
            # Slow successful connection  
            (ConnectionEventType.CONNECT_ATTEMPT, "slow_conn", timestamp + 0.1, {}),
            (ConnectionEventType.CONNECT_SUCCESS, "slow_conn", timestamp + 0.25, {'duration': 0.15}),
            
            # Queued connection with timeout
            (ConnectionEventType.CONNECT_ATTEMPT, "queued_conn", timestamp + 0.3, {}),
            (ConnectionEventType.CONNECT_QUEUED, "queued_conn", timestamp + 0.3, {'queue_depth': 2}),
            (ConnectionEventType.CONNECT_TIMEOUT, "queued_conn", timestamp + 5.3, {}),
        ]
        
        # Emit all events
        for event_type, conn_id, ts, metadata in events:
            collector.on_connection_event(ConnectionEvent(
                event_type=event_type,
                connection_id=conn_id,
                timestamp=ts,
                metadata=metadata
            ))
        
        # Assert - Should provide enhanced statistics
        metrics = collector.get_metrics()
        
        # Basic counts
        assert metrics['connection_attempts'] == 3, "Should count all attempts"
        assert metrics['successful_connections'] == 2, "Should count successes"
        assert metrics['failed_connections'] == 0, "Should count failures"
        assert metrics['connections_timeout'] == 1, "Should count timeouts"
        
        # Enhanced statistics from events
        assert 'connection_duration_histogram' in metrics, "Should provide duration histogram"
        assert 'events_per_type' in metrics, "Should provide event type breakdown"
    
    def test_metrics_collector_event_backwards_compatibility(self):
        """Test that existing metrics methods still work alongside event system."""
        # Arrange
        from pipedoc.connection_events import ConnectionEventType, ConnectionEvent
        import time
        
        collector = MetricsCollector()
        timestamp = time.time()
        
        # Act - Mix traditional metrics calls with event-driven metrics
        # Traditional method calls
        collector.record_connection_attempt()
        collector.record_connection_success(0.1)
        
        # Event-driven calls
        collector.on_connection_event(ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_ATTEMPT,
            connection_id="event_conn",
            timestamp=timestamp
        ))
        collector.on_connection_event(ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_FAILURE,
            connection_id="event_conn",
            timestamp=timestamp + 0.1
        ))
        
        # Assert - Both methods should contribute to metrics
        metrics = collector.get_metrics()
        assert metrics['connection_attempts'] == 2, "Should count both traditional and event attempts"
        assert metrics['successful_connections'] == 1, "Should count traditional success"
        assert metrics['failed_connections'] == 1, "Should count event failure"
        assert metrics['success_rate'] == 0.5, "Should calculate combined success rate"
    
    def test_metrics_collector_event_thread_safety(self):
        """Test thread safety of event-driven metrics collection."""
        # Arrange
        from pipedoc.connection_events import ConnectionEventType, ConnectionEvent
        import time
        import threading
        
        collector = MetricsCollector()
        event_count = 100
        thread_count = 3
        
        def generate_events(thread_id: int):
            """Generate events from a thread."""
            for i in range(event_count):
                timestamp = time.time()
                collector.on_connection_event(ConnectionEvent(
                    event_type=ConnectionEventType.CONNECT_ATTEMPT,
                    connection_id=f"thread_{thread_id}_conn_{i}",
                    timestamp=timestamp
                ))
                collector.on_connection_event(ConnectionEvent(
                    event_type=ConnectionEventType.CONNECT_SUCCESS,
                    connection_id=f"thread_{thread_id}_conn_{i}",
                    timestamp=timestamp + 0.01,
                    duration=0.01
                ))
        
        # Act - Generate events from multiple threads
        threads = []
        for thread_id in range(thread_count):
            thread = threading.Thread(target=generate_events, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Assert - All events should be recorded correctly
        metrics = collector.get_metrics()
        expected_total = event_count * thread_count
        assert metrics['connection_attempts'] == expected_total, f"Should record all {expected_total} attempts"
        assert metrics['successful_connections'] == expected_total, f"Should record all {expected_total} successes"
        assert metrics['success_rate'] == 1.0, "Should have 100% success rate"