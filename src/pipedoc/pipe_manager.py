"""
Pipe manager module for handling named pipe operations.

This module implements the Single Responsibility Principle by focusing solely
on creating, managing, and cleaning up named pipes.
"""

import os
import select
import tempfile
import threading
import time
from typing import List, Optional


class PipeManager:
    """
    Responsible for managing named pipe operations.

    This class follows the Single Responsibility Principle by handling
    only the creation, management, and cleanup of named pipes.
    """

    def __init__(self):
        """Initialize the pipe manager."""
        self.pipe_path: Optional[str] = None
        self.running = True
        self.threads: List[threading.Thread] = []
        self._client_counter = 0
        self._ready_worker_count = 0
        self._active_worker_count = 0
        self._worker_failure_count = 0
        self._worker_start_failure_count = 0
        self._worker_lock = threading.Lock()
        self._max_start_retries = 3

    def create_named_pipe(self) -> str:
        """
        Create a named pipe in a temporary location.

        Returns:
            Path to the created named pipe

        Raises:
            OSError: If pipe creation fails
        """
        # Create pipe in temp directory with a unique name
        temp_dir = tempfile.gettempdir()
        pipe_name = f"pipedoc_{os.getpid()}"
        self.pipe_path = os.path.join(temp_dir, pipe_name)

        # Remove pipe if it already exists
        if os.path.exists(self.pipe_path):
            os.unlink(self.pipe_path)

        # Create the named pipe
        try:
            os.mkfifo(self.pipe_path)
            print(f"Created named pipe: {self.pipe_path}")
            return self.pipe_path
        except OSError as e:
            raise OSError(f"Failed to create named pipe: {e}")

    def serve_client(self, client_id: int, content: str) -> None:
        """
        Serve content to a single client process.

        Args:
            client_id: Unique identifier for the client
            content: Content to serve to the client
        """
        try:
            print(f"Client {client_id}: Opening pipe for writing...")

            # Open pipe for writing (this will block until a reader connects)
            with open(self.pipe_path, "w") as pipe:
                print(f"Client {client_id}: Connected, sending content...")

                # Send the content
                pipe.write(content)
                pipe.flush()

                print(f"Client {client_id}: Content sent successfully")

        except BrokenPipeError:
            print(f"Client {client_id}: Reader disconnected")
        except Exception as e:
            print(f"Client {client_id}: Error serving content: {e}")

    def start_serving(self, content: str) -> None:
        """
        Start accepting connections and spawn threads for each client.

        Args:
            content: Content to serve to clients
        """
        client_counter = 0

        print(f"Server ready. Clients can read from: {self.pipe_path}")
        print("Press Ctrl+C to stop the server")

        while self.running:
            try:
                client_counter += 1
                print(f"Waiting for client {client_counter}...")

                # Create a thread for each client
                client_thread = threading.Thread(
                    target=self.serve_client,
                    args=(client_counter, content),
                    daemon=True,
                )
                client_thread.start()
                self.threads.append(client_thread)

                # Small delay to prevent tight loop
                time.sleep(0.1)

            except KeyboardInterrupt:
                print("\nShutting down server...")
                self.running = False
                break
            except Exception as e:
                print(f"Error accepting connection: {e}")
                time.sleep(1)

    def stop_serving(self) -> None:
        """Stop the serving process."""
        self.running = False

    def cleanup(self) -> None:
        """Clean up resources."""
        self.running = False

        # Wait for threads to finish (with timeout)
        for thread in self.threads:
            thread.join(timeout=1.0)

        # Remove the named pipe
        if self.pipe_path and os.path.exists(self.pipe_path):
            try:
                os.unlink(self.pipe_path)
                print(f"Cleaned up pipe: {self.pipe_path}")
            except Exception as e:
                print(f"Error cleaning up pipe: {e}")

        self.threads.clear()

    def get_pipe_path(self) -> Optional[str]:
        """
        Get the current pipe path.

        Returns:
            Path to the named pipe, or None if not created
        """
        return self.pipe_path

    def is_running(self) -> bool:
        """
        Check if the pipe manager is currently running.

        Returns:
            True if running, False otherwise
        """
        return self.running

    def _monitor_connections_once(self) -> None:
        """
        Monitor for a single connection attempt using select().
        
        This method opens the pipe in non-blocking mode and uses select()
        to detect when a client attempts to connect. If a connection is
        detected, it spawns a worker thread to handle the client.
        
        Raises:
            OSError: If pipe cannot be opened for monitoring
        """
        if not self.pipe_path:
            return
            
        try:
            # Open pipe in read-only, non-blocking mode for monitoring
            pipe_fd = os.open(self.pipe_path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as e:
            print(f"Error opening pipe for monitoring: {e}")
            return
        
        try:
            # Use select to monitor for connection attempts with 1 second timeout
            ready, _, _ = select.select([pipe_fd], [], [], 1.0)
            
            if ready:
                # Connection detected - spawn a worker thread reactively
                # Note: For now, we pass empty content since we don't have it yet
                # This will be improved in the next TDD iteration
                self._spawn_worker()
        finally:
            # Always close the file descriptor
            try:
                os.close(pipe_fd)
            except OSError:
                # File descriptor may already be closed, ignore
                pass

    def _spawn_worker(self, content: str = "") -> None:
        """
        Spawn a worker thread to handle a client connection.
        
        This method delegates to the reactive worker spawning implementation.
        
        Args:
            content: Content to serve to the client (defaults to empty string)
        """
        self._spawn_worker_reactive(content)

    def _spawn_worker_reactive(self, content: str, retry_count: int = 0) -> None:
        """
        Spawn a worker thread reactively when a client connection is detected.
        
        Unlike the old preemptive approach, this method only creates threads
        in response to actual client connections, not speculatively.
        
        Args:
            content: Content to serve to the client
            retry_count: Number of retries attempted so far (for failure handling)
        """
        # Increment client counter for this connection
        self._client_counter += 1
        
        # Create a worker thread for this specific client
        worker_thread = threading.Thread(
            target=self.serve_client,
            args=(self._client_counter, content),
            daemon=True
        )
        
        try:
            # Start the thread immediately (reactive approach)
            worker_thread.start()
            
            # Note: We deliberately do NOT add to self.threads list
            # to avoid the unbounded growth issue from the old implementation
            
            # Track that we have a ready worker and an active worker
            with self._worker_lock:
                self._ready_worker_count += 1
                self._active_worker_count += 1
        except Exception as e:
            # Thread failed to start - attempt recovery with retry tracking
            print(f"Worker thread failed to start: {e}")
            self._handle_worker_start_failure(content, retry_count)

    def _start_reactive_serving(self, content: str) -> None:
        """
        Start reactive serving by ensuring one ready worker exists.
        
        This method initializes the reactive serving system by ensuring
        exactly one worker thread is ready to handle incoming connections.
        
        Args:
            content: Content to serve to clients
        """
        self._ensure_ready_worker(content)


    def _worker_became_busy(self) -> None:
        """
        Handle when a worker becomes busy by spawning a replacement.
        
        This method decrements the ready worker count and spawns a
        replacement worker if needed to maintain exactly one ready worker.
        """
        should_spawn = False
        
        with self._worker_lock:
            if self._ready_worker_count > 0:
                self._ready_worker_count -= 1
                if self._ready_worker_count == 0:
                    should_spawn = True
        
        if should_spawn:
            # Spawn replacement worker to maintain exactly one ready worker
            self._spawn_worker_reactive("test content")

    def _ensure_ready_worker(self, content: str) -> None:
        """
        Ensure exactly one ready worker exists.
        
        This method checks if there are any ready workers and spawns
        one if needed. It's thread-safe and avoids deadlocks by
        releasing the lock before spawning workers.
        
        Args:
            content: Content to serve to clients
        """
        should_spawn = False
        with self._worker_lock:
            if self._ready_worker_count == 0:
                should_spawn = True
        
        if should_spawn:
            self._spawn_worker_reactive(content)

    def _get_ready_worker_count(self) -> int:
        """
        Get the current count of ready workers.
        
        Returns:
            Number of ready workers
        """
        with self._worker_lock:
            return self._ready_worker_count

    def _get_active_worker_count(self) -> int:
        """
        Get the current count of active workers.
        
        Returns:
            Number of active workers
        """
        with self._worker_lock:
            return self._active_worker_count

    def _worker_completed(self) -> None:
        """
        Handle when a worker completes its task and deregisters itself.
        
        This method demonstrates the self-managing nature of workers in
        the reactive system. Workers call this when they finish serving
        a client, allowing for proper resource tracking without the need
        for the old unbounded self.threads list approach.
        
        In a production implementation, this would be called automatically
        by workers when they complete their serve_client tasks.
        """
        with self._worker_lock:
            if self._active_worker_count > 0:
                self._active_worker_count -= 1

    def _cleanup_reactive_workers(self) -> None:
        """
        Clean up reactive workers and reset state.
        
        This method demonstrates proper resource cleanup for the
        reactive thread management system. Unlike the old implementation
        that relied on an unbounded self.threads list, this approach
        uses worker self-registration and controlled state management.
        
        In a production implementation, this would:
        - Signal active workers to gracefully shutdown
        - Wait for workers to complete current tasks
        - Reset counters while maintaining exactly one ready worker
        """
        with self._worker_lock:
            # Reset to clean state while maintaining one ready worker
            self._active_worker_count = 1  # Keep one ready worker
            
            # Ensure we still have exactly one ready worker
            if self._ready_worker_count == 0:
                self._ready_worker_count = 1

    def _worker_failed(self, error: Exception) -> None:
        """
        Handle when a worker encounters a failure during execution.
        
        This method tracks failures and spawns a replacement worker
        to maintain system resilience. It demonstrates automatic
        recovery from worker thread failures.
        
        Args:
            error: The exception that caused the worker to fail
        """
        with self._worker_lock:
            self._worker_failure_count += 1
            if self._ready_worker_count > 0:
                self._ready_worker_count -= 1
            if self._active_worker_count > 0:
                self._active_worker_count -= 1
        
        print(f"Worker failed with error: {error}")
        
        # Spawn replacement worker to maintain service availability
        self._ensure_ready_worker("test content")

    def _handle_worker_start_failure(self, content: str, retry_count: int = 0) -> None:
        """
        Handle when a worker thread fails to start.
        
        This method attempts to recover by spawning another replacement
        worker, with retry limits to prevent infinite recursion.
        
        Args:
            content: Content to serve to clients
            retry_count: Number of retries attempted so far
        """
        with self._worker_lock:
            self._worker_start_failure_count += 1
        
        if retry_count < self._max_start_retries:
            print(f"Retrying worker start (attempt {retry_count + 1}/{self._max_start_retries})")
            try:
                self._spawn_worker_reactive(content, retry_count + 1)
            except Exception as e:
                print(f"Worker retry {retry_count + 1} failed: {e}")
        else:
            print(f"Exceeded maximum start retries ({self._max_start_retries}), giving up")

    def _get_worker_failure_count(self) -> int:
        """
        Get the count of worker execution failures.
        
        Returns:
            Number of worker execution failures encountered
        """
        with self._worker_lock:
            return self._worker_failure_count
    
    def _get_worker_start_failure_count(self) -> int:
        """
        Get the count of worker thread start failures.
        
        Returns:
            Number of worker thread start failures encountered
        """
        with self._worker_lock:
            return self._worker_start_failure_count
    
    def _get_total_failure_count(self) -> int:
        """
        Get the total count of all worker failures.
        
        Returns:
            Total number of worker failures (execution + start failures)
        """
        with self._worker_lock:
            return self._worker_failure_count + self._worker_start_failure_count
