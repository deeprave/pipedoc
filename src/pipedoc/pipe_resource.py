"""
Named pipe resource management component.

This module provides the PipeResource class which handles all named pipe
operations including creation of pipes in temporary locations, connection
monitoring using select(), and proper resource cleanup.
"""

import threading
import os
import select
import tempfile
from typing import Optional


class PipeResource:
    """
    Manages named pipe creation, monitoring, and cleanup.

    This component encapsulates all named pipe operations including creation
    of pipes in temporary locations, connection monitoring using select(),
    and proper resource cleanup.

    Key Features:
    -------------
    - Unique pipe path generation
    - Connection detection with configurable timeouts
    - Robust error handling and cleanup
    - Thread-safe operations
    """

    def __init__(self):
        """Initialise the pipe resource manager."""
        self._pipe_path: Optional[str] = None
        self._is_created = False
        self._lock = threading.Lock()

    def create_pipe(self) -> Optional[str]:
        """
        Create a named pipe in a temporary location.

        Returns:
            Path to the created named pipe, or None if creation failed

        Raises:
            OSError: If pipe creation fails
        """
        with self._lock:
            try:
                # Generate unique pipe path
                temp_dir = tempfile.gettempdir()
                pipe_name = f"pipedoc_{os.getpid()}_{id(self)}"
                self._pipe_path = os.path.join(temp_dir, pipe_name)

                # Remove pipe if it already exists (cleanup from previous runs)
                if os.path.exists(self._pipe_path):
                    os.unlink(self._pipe_path)

                # Create the named pipe
                os.mkfifo(self._pipe_path)
                self._is_created = True

                return self._pipe_path

            except OSError as e:
                # Reset state on failure
                self._pipe_path = None
                self._is_created = False
                raise OSError(f"Failed to create named pipe: {e}")

    def get_pipe_path(self) -> Optional[str]:
        """
        Get the current pipe path.

        Returns:
            Path to the named pipe, or None if not created
        """
        with self._lock:
            return self._pipe_path

    def is_pipe_created(self) -> bool:
        """
        Check if the pipe is currently created.

        Returns:
            True if pipe is created, False otherwise
        """
        with self._lock:
            return self._is_created

    def check_for_connection(self, timeout: float = 1.0) -> bool:
        """
        Check for incoming connections using select().

        Args:
            timeout: Timeout in seconds to wait for connections

        Returns:
            True if a connection is detected, False otherwise
        """
        if not self._is_created or not self._pipe_path:
            return False

        try:
            # Open pipe in non-blocking read/write mode to avoid blocking
            # Using O_RDWR prevents blocking when no writer is connected
            pipe_fd = os.open(self._pipe_path, os.O_RDWR | os.O_NONBLOCK)

            try:
                # Use select to monitor for connection attempts
                ready, _, _ = select.select([pipe_fd], [], [], timeout)
                return len(ready) > 0

            finally:
                # Always close the file descriptor
                try:
                    os.close(pipe_fd)
                except OSError:
                    # File descriptor may already be closed, ignore
                    pass

        except OSError:
            # Error opening pipe for monitoring (e.g., pipe was removed)
            return False

    def cleanup(self) -> None:
        """Clean up the named pipe and reset state."""
        with self._lock:
            if self._pipe_path and os.path.exists(self._pipe_path):
                try:
                    os.unlink(self._pipe_path)
                except OSError:
                    # Pipe may have been removed by another process
                    pass

            # Reset state
            self._pipe_path = None
            self._is_created = False
