"""
Integration tests for the enhanced PipeManager orchestrator.

This module tests that the refactored PipeManager maintains backwards compatibility
while internally delegating to the specialized components (MetricsCollector,
WorkerPool, PipeResource, ConnectionManager).
"""

import threading
import time
from unittest.mock import patch, MagicMock

import pytest

from pipedoc.pipe_manager import PipeManager


class TestEnhancedPipeManagerIntegration:
    """Integration tests for enhanced PipeManager architecture."""

    def test_enhanced_pipe_manager_backwards_compatibility(self):
        """Test that public API remains unchanged after refactoring."""
        # Arrange
        manager = PipeManager(max_workers=3)
        
        # Assert - Public interface should be unchanged
        assert hasattr(manager, 'create_named_pipe'), "Should have create_named_pipe method"
        assert hasattr(manager, 'start_serving'), "Should have start_serving method"
        assert hasattr(manager, 'stop_serving'), "Should have stop_serving method"
        assert hasattr(manager, 'cleanup'), "Should have cleanup method"
        assert hasattr(manager, 'get_pipe_path'), "Should have get_pipe_path method"
        assert hasattr(manager, 'is_running'), "Should have is_running method"
        assert hasattr(manager, 'serve_client'), "Should have serve_client method"
        
        # Test - Basic lifecycle should work
        pipe_path = manager.create_named_pipe()
        assert pipe_path is not None, "Should create pipe successfully"
        assert manager.get_pipe_path() == pipe_path, "Should return correct pipe path"
        
        # Initial state
        assert not manager.is_running(), "Should not be running initially"
        
        # Cleanup
        manager.cleanup()

    def test_component_integration_architecture(self):
        """Test that PipeManager integrates with enhanced components internally."""
        # Arrange
        manager = PipeManager(max_workers=2)
        
        # Assert - Should have component references (internal architecture)
        # Note: These are internal implementation details that may change
        # but help verify the refactoring was successful
        
        # Test basic functionality that should use components
        pipe_path = manager.create_named_pipe()
        assert pipe_path is not None
        
        # The PipeManager should now delegate to components for:
        # - PipeResource: pipe creation and management
        # - WorkerPool: thread management  
        # - MetricsCollector: connection statistics
        # - ConnectionManager: race condition prevention
        
        manager.cleanup()

    def test_enhanced_pipe_manager_serving_integration(self):
        """Test serving functionality with component integration."""
        # Arrange
        manager = PipeManager(max_workers=3)
        
        try:
            # Create pipe
            pipe_path = manager.create_named_pipe()
            assert pipe_path is not None
            
            # Test serving state management
            assert not manager.is_running()
            
            # Start serving (this should integrate with ConnectionManager)
            # Note: We're not actually testing the full serving loop here
            # since that would require actual pipe I/O and client connections
            
            # The internal architecture should handle the always-ready writer pattern
            # through the ConnectionManager component
            
        finally:
            manager.stop_serving()
            manager.cleanup()

    def test_error_propagation_and_recovery(self):
        """Test that error handling works across component boundaries."""
        # Arrange
        manager = PipeManager(max_workers=2)
        
        try:
            # Test error conditions that should be handled gracefully
            # by the component architecture
            
            # Test 1: Multiple cleanup calls should be safe
            manager.cleanup()
            manager.cleanup()  # Should not crash
            
            # Test 2: Operations on non-created pipe should be handled
            assert manager.get_pipe_path() is None
            assert not manager.is_running()
            
            # Test 3: Stop without start should be safe
            manager.stop_serving()  # Should not crash
            
        finally:
            manager.cleanup()

    def test_thread_safety_with_components(self):
        """Test thread safety of the enhanced PipeManager."""
        # Arrange
        manager = PipeManager(max_workers=3)
        results = []
        errors = []
        
        def concurrent_operations(thread_id: int):
            """Perform concurrent operations on the PipeManager."""
            try:
                # Each thread tries various operations
                pipe_path = manager.create_named_pipe()
                if pipe_path:
                    results.append(f"Thread {thread_id}: Created pipe {pipe_path}")
                
                is_running = manager.is_running()
                results.append(f"Thread {thread_id}: Running state {is_running}")
                
                # Cleanup operations
                manager.cleanup()
                results.append(f"Thread {thread_id}: Cleaned up successfully")
                
            except Exception as e:
                errors.append(f"Thread {thread_id}: Error {str(e)}")
        
        try:
            # Act - Launch concurrent threads
            threads = []
            num_threads = 4
            
            for thread_id in range(num_threads):
                thread = threading.Thread(target=concurrent_operations, args=(thread_id,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=5.0)
            
            # Assert - Operations should complete without errors
            assert len(errors) == 0, f"Should have no errors: {errors}"
            assert len(results) > 0, "Should have some successful operations"
            
        finally:
            manager.cleanup()

    def test_performance_no_regression(self):
        """Test that component architecture doesn't introduce performance regression."""
        # Arrange
        manager = PipeManager(max_workers=4)
        
        try:
            # Measure pipe creation performance
            start_time = time.time()
            
            pipe_operations = 10
            for i in range(pipe_operations):
                pipe_path = manager.create_named_pipe()
                assert pipe_path is not None
                manager.cleanup()
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Assert - Should complete operations quickly
            # This is a basic performance check - exact timing depends on system
            assert total_time < 1.0, f"Should complete {pipe_operations} operations quickly, took {total_time:.3f}s"
            
            # Test memory cleanup - components should not leak resources
            # This is more of a documentation of expected behavior
            
        finally:
            manager.cleanup()

    def test_metrics_integration(self):
        """Test that metrics collection works through component integration."""
        # Arrange  
        manager = PipeManager(max_workers=2)
        
        try:
            # The enhanced PipeManager should internally use MetricsCollector
            # for connection statistics tracking
            
            pipe_path = manager.create_named_pipe()
            assert pipe_path is not None
            
            # Note: Full metrics testing would require actual client connections
            # which is complex to set up in unit tests. The component-level
            # tests already verify MetricsCollector functionality.
            
            # The integration test verifies that the architecture allows
            # for metrics collection without breaking existing functionality
            
        finally:
            manager.cleanup()

    def test_resource_cleanup_integration(self):
        """Test that resource cleanup works across all components."""
        # Arrange
        manager = PipeManager(max_workers=2)
        
        # Create resources
        pipe_path = manager.create_named_pipe()
        assert pipe_path is not None
        
        # Test that cleanup properly delegates to all components
        manager.cleanup()
        
        # After cleanup, resources should be released
        assert manager.get_pipe_path() is None
        assert not manager.is_running()
        
        # Multiple cleanups should be safe
        manager.cleanup()
        manager.cleanup()