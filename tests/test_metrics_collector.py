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