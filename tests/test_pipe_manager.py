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
    def test_create_named_pipe_existing_pipe(self, mock_unlink, mock_exists, mock_mkfifo):
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
            assert metrics['connection_attempts'] >= 1
            
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
            assert metrics['connection_attempts'] >= 1
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
            assert metrics['connection_attempts'] >= 3
            
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
            assert 'connection_attempts' in initial_metrics
            assert 'successful_connections' in initial_metrics
            assert 'failed_connections' in initial_metrics
            
            # Test that metrics are updated
            manager.create_named_pipe()
            manager._metrics_collector.record_connection_attempt()
            
            updated_metrics = manager._get_metrics()
            assert updated_metrics['connection_attempts'] > initial_metrics['connection_attempts']
            
        finally:
            manager.cleanup()

    def test_worker_pool_integration(self):
        """Test worker pool integration."""
        manager = PipeManager()
        
        try:
            pool_metrics = manager._get_worker_pool_metrics()
            
            # Worker pool metrics should be accessible
            assert isinstance(pool_metrics, dict)
            assert 'max_workers' in pool_metrics
            assert 'active_workers' in pool_metrics
            assert 'is_running' in pool_metrics
            
            # Worker pool should be running
            assert pool_metrics['is_running']
            
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
            assert pool_metrics['max_workers'] == 5
            
        finally:
            manager.cleanup()

    def test_queue_configuration(self):
        """Test queue configuration parameters are passed correctly."""
        # Test with custom queue settings
        manager = PipeManager(
            max_workers=2,
            queue_size=5,
            queue_timeout=15.0
        )
        
        try:
            # Verify queue configuration is passed to ConnectionManager
            queue_metrics = manager._get_queue_metrics()
            assert queue_metrics['max_size'] == 5, "Queue size should be configured correctly"
            
            # Test that queue functionality works
            manager.create_named_pipe()
            manager.start_serving("test content")
            
            # Should be able to get queue metrics
            assert 'current_depth' in queue_metrics
            assert 'total_queued' in queue_metrics
            assert 'timeout_count' in queue_metrics
            
        finally:
            manager.cleanup()