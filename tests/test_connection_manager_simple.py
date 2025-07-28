"""
Simple tests for ConnectionManager to isolate issues.
"""

import pytest
from pipedoc.connection_manager import ConnectionManager
from pipedoc.worker_pool import WorkerPool
from pipedoc.metrics_collector import MetricsCollector
from pipedoc.pipe_resource import PipeResource


def test_connection_manager_creation():
    """Test that ConnectionManager can be created."""
    # Arrange
    metrics = MetricsCollector()
    worker_pool = WorkerPool(max_workers=2)
    pipe_resource = PipeResource()
    
    # Act
    connection_mgr = ConnectionManager(
        worker_pool=worker_pool,
        metrics_collector=metrics,
        pipe_resource=pipe_resource
    )
    
    # Assert
    assert connection_mgr is not None
    assert not connection_mgr.is_running()
    assert not connection_mgr.is_writer_ready()
    assert connection_mgr.get_active_connections() == 0


def test_connection_manager_lifecycle():
    """Test basic lifecycle operations."""
    # Arrange
    metrics = MetricsCollector()
    worker_pool = WorkerPool(max_workers=2)
    pipe_resource = PipeResource()
    
    connection_mgr = ConnectionManager(
        worker_pool=worker_pool,
        metrics_collector=metrics,
        pipe_resource=pipe_resource
    )
    
    # Test - Start
    connection_mgr.start_connection_management()
    assert connection_mgr.is_running()
    assert connection_mgr.is_writer_ready()
    
    # Test - Shutdown
    connection_mgr.shutdown()
    assert not connection_mgr.is_running()
    assert not connection_mgr.is_writer_ready()