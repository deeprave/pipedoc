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