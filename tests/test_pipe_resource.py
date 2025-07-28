"""
Tests for the PipeResource component.

This module tests named pipe operations including creation, monitoring,
error handling, and cleanup functionality.
"""

from unittest.mock import patch

import pytest

from pipedoc.pipe_resource import PipeResource


class TestPipeResource:
    """Test cases for PipeResource component."""

    def test_pipe_resource_creation_and_monitoring(self):
        """Test pipe creation, path management, and cleanup."""
        # Arrange
        pipe_resource = PipeResource()
        
        # Assert - Initial state
        assert pipe_resource.get_pipe_path() is None, "Should have no pipe path initially"
        assert not pipe_resource.is_pipe_created(), "Should not have pipe created initially"
        
        # Act - Create pipe
        pipe_path = pipe_resource.create_pipe()
        
        # Assert - Pipe creation
        assert pipe_path is not None, "Should return valid pipe path"
        assert isinstance(pipe_path, str), "Pipe path should be string"
        assert pipe_resource.get_pipe_path() == pipe_path, "Should store pipe path"
        assert pipe_resource.is_pipe_created(), "Should indicate pipe is created"
        
        # Verify pipe actually exists on filesystem
        import os
        assert os.path.exists(pipe_path), "Pipe should exist on filesystem"
        
        # Test - Cleanup
        pipe_resource.cleanup()
        
        # Assert - Cleanup
        assert not pipe_resource.is_pipe_created(), "Should indicate pipe is not created after cleanup"
        assert not os.path.exists(pipe_path), "Pipe should be removed from filesystem"

    @patch('select.select')
    @patch('os.open')
    @patch('os.close')
    def test_pipe_resource_connection_monitoring(self, mock_close, mock_open, mock_select):
        """Test connection monitoring with select()."""
        # Arrange
        pipe_resource = PipeResource()
        pipe_path = pipe_resource.create_pipe()
        
        # Mock file descriptor
        mock_fd = 5
        mock_open.return_value = mock_fd
        
        try:
            # Test - No connection detected
            mock_select.return_value = ([], [], [])  # No ready file descriptors
            
            connection_detected = pipe_resource.check_for_connection(timeout=0.1)
            assert not connection_detected, "Should not detect connection when select returns empty"
            
            # Verify select was called correctly
            mock_open.assert_called_once()
            mock_select.assert_called_once()
            mock_close.assert_called_once_with(mock_fd)
            
            # Reset mocks
            mock_open.reset_mock()
            mock_select.reset_mock()
            mock_close.reset_mock()
            
            # Test - Connection detected
            mock_select.return_value = ([mock_fd], [], [])  # Ready file descriptor
            
            connection_detected = pipe_resource.check_for_connection(timeout=0.1)
            assert connection_detected, "Should detect connection when select returns ready fd"
            
            # Verify proper cleanup
            mock_close.assert_called_once_with(mock_fd)
            
        finally:
            pipe_resource.cleanup()

    def test_pipe_resource_error_handling(self):
        """Test error handling during pipe operations."""
        # Test - Creation in invalid directory
        pipe_resource = PipeResource()
        
        # Try to create pipe with invalid path (this should be handled gracefully)
        with patch('os.mkfifo') as mock_mkfifo:
            mock_mkfifo.side_effect = OSError("Permission denied")
            
            # Should raise appropriate exception or handle gracefully
            try:
                pipe_path = pipe_resource.create_pipe()
                # If no exception, check that error was logged/handled
                assert pipe_path is None, "Should return None on creation failure"
            except OSError:
                # Acceptable to raise OSError for invalid operations
                pass
        
        # Test - Cleanup of non-existent pipe (should not crash)
        pipe_resource.cleanup()  # Should handle gracefully
        
        # Test - Multiple cleanup calls (should be idempotent)
        pipe_resource.cleanup()
        pipe_resource.cleanup()

    def test_pipe_resource_path_management(self):
        """Test pipe path generation and management."""
        # Test - Multiple instances create different paths
        pipe1 = PipeResource()
        pipe2 = PipeResource()
        
        try:
            path1 = pipe1.create_pipe()
            path2 = pipe2.create_pipe()
            
            # Paths should be different
            assert path1 != path2, "Different instances should create different pipe paths"
            
            # Both should exist
            import os
            assert os.path.exists(path1), "First pipe should exist"
            assert os.path.exists(path2), "Second pipe should exist"
            
        finally:
            pipe1.cleanup()
            pipe2.cleanup()

    def test_pipe_resource_recreation(self):
        """Test pipe recreation after cleanup."""
        pipe_resource = PipeResource()
        
        # Create first pipe
        path1 = pipe_resource.create_pipe()
        assert path1 is not None, "Should create first pipe"
        
        # Cleanup
        pipe_resource.cleanup()
        import os
        assert not os.path.exists(path1), "First pipe should be cleaned up"
        
        # Create second pipe  
        path2 = pipe_resource.create_pipe()
        assert path2 is not None, "Should create second pipe"
        assert os.path.exists(path2), "Second pipe should exist"
        
        # Paths might be the same or different (depends on implementation)
        # Both behaviors are acceptable
        
        # Final cleanup
        pipe_resource.cleanup()