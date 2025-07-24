"""
Pipe manager module for handling named pipe operations.

This module implements the Single Responsibility Principle by focusing solely
on creating, managing, and cleaning up named pipes.
"""

import os
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
