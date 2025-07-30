"""
Tests for built-in connection event handlers.

This module tests the built-in event handlers that provide common functionality
for logging, file output, and other event processing needs.
"""

import json
import os
import tempfile
import time
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest

from pipedoc.connection_events import ConnectionEventType, ConnectionEvent


class TestLoggingEventListener:
    """Test cases for LoggingEventListener."""

    def test_logging_event_handler_basic_functionality(self):
        """Test that LoggingEventListener logs events correctly."""
        # Arrange
        from pipedoc.event_handlers import LoggingEventListener

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            handler = LoggingEventListener()

            event_data = ConnectionEvent(
                event_type=ConnectionEventType.CONNECT_ATTEMPT,
                connection_id="test_conn_1",
                timestamp=time.time(),
            )

            # Act
            handler.on_connection_event(event_data)

            # Assert
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "connect_attempt" in call_args
            assert "test_conn_1" in call_args

    def test_logging_event_handler_custom_logger_name(self):
        """Test LoggingEventListener with custom logger name."""
        # Arrange
        from pipedoc.event_handlers import LoggingEventListener

        with patch("logging.getLogger") as mock_get_logger:
            handler = LoggingEventListener(logger_name="custom.logger")

            # Act - Just creating the handler should use the custom logger name

            # Assert
            mock_get_logger.assert_called_with("custom.logger")

    def test_logging_event_handler_different_event_types(self):
        """Test LoggingEventListener with different event types."""
        # Arrange
        from pipedoc.event_handlers import LoggingEventListener

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            handler = LoggingEventListener()

            events = [
                (ConnectionEventType.CONNECT_ATTEMPT, "info"),
                (ConnectionEventType.CONNECT_SUCCESS, "info"),
                (ConnectionEventType.CONNECT_FAILURE, "warning"),
                (ConnectionEventType.CONNECT_TIMEOUT, "warning"),
                (ConnectionEventType.CONNECT_QUEUED, "debug"),
                (ConnectionEventType.CONNECT_DEQUEUED, "debug"),
            ]

            # Act & Assert
            for event_type, expected_level in events:
                mock_logger.reset_mock()

                event_data = ConnectionEvent(
                    event_type=event_type,
                    connection_id=f"conn_{event_type.value}",
                    timestamp=time.time(),
                )

                handler.on_connection_event(event_data)

                # Verify appropriate log level was called
                log_method = getattr(mock_logger, expected_level)
                log_method.assert_called_once()

    def test_logging_event_handler_with_metadata(self):
        """Test LoggingEventListener includes metadata in log messages."""
        # Arrange
        from pipedoc.event_handlers import LoggingEventListener

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            handler = LoggingEventListener()

            event_data = ConnectionEvent(
                event_type=ConnectionEventType.CONNECT_QUEUED,
                connection_id="test_conn",
                timestamp=time.time(),
                metadata={"queue_depth": 5, "wait_time": 0.5},
            )

            # Act
            handler.on_connection_event(event_data)

            # Assert
            call_args = mock_logger.debug.call_args[0][0]
            assert "queue_depth" in call_args
            assert "5" in call_args


class TestFileEventListener:
    """Test cases for FileEventListener."""

    def test_file_event_handler_basic_functionality(self):
        """Test that FileEventListener writes events to file."""
        # Arrange
        from pipedoc.event_handlers import FileEventListener

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            handler = FileEventListener(temp_path)

            event_data = ConnectionEvent(
                event_type=ConnectionEventType.CONNECT_SUCCESS,
                connection_id="test_conn_1",
                timestamp=time.time(),
                duration=0.05,
            )

            # Act
            handler.on_connection_event(event_data)

            # Assert
            with open(temp_path, "r") as f:
                content = f.read()

            assert "connect_success" in content
            assert "test_conn_1" in content
            assert "0.05" in content

        finally:
            os.unlink(temp_path)

    def test_file_event_handler_json_format(self):
        """Test FileEventListener with JSON format."""
        # Arrange
        from pipedoc.event_handlers import FileEventListener
        import json

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            handler = FileEventListener(temp_path, format="json")

            event_data = ConnectionEvent(
                event_type=ConnectionEventType.CONNECT_ATTEMPT,
                connection_id="json_test_conn",
                timestamp=1234567890.123,
                metadata={"test": "value"},
            )

            # Act
            handler.on_connection_event(event_data)

            # Assert
            with open(temp_path, "r") as f:
                line = f.readline().strip()

            # Should be valid JSON
            parsed = json.loads(line)
            assert parsed["event_type"] == "connect_attempt"
            assert parsed["connection_id"] == "json_test_conn"
            assert parsed["timestamp"] == 1234567890.123
            assert parsed["metadata"]["test"] == "value"

        finally:
            os.unlink(temp_path)

    def test_file_event_handler_append_mode(self):
        """Test FileEventListener appends to existing file."""
        # Arrange
        from pipedoc.event_handlers import FileEventListener

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write("Existing content\n")

        try:
            handler = FileEventListener(temp_path)

            event_data = ConnectionEvent(
                event_type=ConnectionEventType.CONNECT_SUCCESS,
                connection_id="append_test",
                timestamp=time.time(),
            )

            # Act
            handler.on_connection_event(event_data)

            # Assert
            with open(temp_path, "r") as f:
                lines = f.readlines()

            assert len(lines) == 2
            assert "Existing content" in lines[0]
            assert "append_test" in lines[1]

        finally:
            os.unlink(temp_path)

    def test_file_event_handler_cleanup(self):
        """Test FileEventListener cleanup closes file handle."""
        # Arrange
        from pipedoc.event_handlers import FileEventListener

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            handler = FileEventListener(temp_path)

            # Verify file is open
            assert hasattr(handler, "_file")
            assert not handler._file.closed

            # Act
            handler.cleanup()

            # Assert
            assert handler._file.closed

        finally:
            os.unlink(temp_path)


class TestStatisticsEventListener:
    """Test cases for StatisticsEventListener."""

    def test_statistics_event_handler_basic_functionality(self):
        """Test that StatisticsEventListener collects statistics."""
        # Arrange
        from pipedoc.event_handlers import StatisticsEventListener

        handler = StatisticsEventListener()

        events = [
            ConnectionEvent(ConnectionEventType.CONNECT_ATTEMPT, "conn_1", time.time()),
            ConnectionEvent(
                ConnectionEventType.CONNECT_SUCCESS, "conn_1", time.time(), duration=0.1
            ),
            ConnectionEvent(ConnectionEventType.CONNECT_ATTEMPT, "conn_2", time.time()),
            ConnectionEvent(ConnectionEventType.CONNECT_FAILURE, "conn_2", time.time()),
            ConnectionEvent(ConnectionEventType.CONNECT_ATTEMPT, "conn_3", time.time()),
            ConnectionEvent(ConnectionEventType.CONNECT_QUEUED, "conn_3", time.time()),
        ]

        # Act
        for event in events:
            handler.on_connection_event(event)

        # Assert
        stats = handler.get_statistics()
        assert stats["total_attempts"] == 3
        assert stats["total_successes"] == 1
        assert stats["total_failures"] == 1
        assert stats["total_queued"] == 1
        assert stats["success_rate"] == 1.0 / 3.0

    def test_statistics_event_handler_timing_statistics(self):
        """Test StatisticsEventListener tracks timing statistics."""
        # Arrange
        from pipedoc.event_handlers import StatisticsEventListener

        handler = StatisticsEventListener()

        # Generate events with different durations
        durations = [0.1, 0.2, 0.3]
        for i, duration in enumerate(durations):
            handler.on_connection_event(
                ConnectionEvent(
                    event_type=ConnectionEventType.CONNECT_SUCCESS,
                    connection_id=f"conn_{i}",
                    timestamp=time.time(),
                    duration=duration,
                )
            )

        # Act
        stats = handler.get_statistics()

        # Assert
        assert "avg_duration" in stats
        expected_avg = sum(durations) / len(durations)
        assert abs(stats["avg_duration"] - expected_avg) < 0.001
        assert stats["min_duration"] == 0.1
        assert stats["max_duration"] == 0.3

    def test_statistics_event_handler_reset(self):
        """Test StatisticsEventListener reset functionality."""
        # Arrange
        from pipedoc.event_handlers import StatisticsEventListener

        handler = StatisticsEventListener()

        # Add some data
        handler.on_connection_event(
            ConnectionEvent(ConnectionEventType.CONNECT_ATTEMPT, "test", time.time())
        )

        # Verify data exists
        stats_before = handler.get_statistics()
        assert stats_before["total_attempts"] == 1

        # Act
        handler.reset_statistics()

        # Assert
        stats_after = handler.get_statistics()
        assert stats_after["total_attempts"] == 0
        assert stats_after["success_rate"] == 0.0


class TestEventHandlerIntegration:
    """Test integration of event handlers with the event system."""

    def test_multiple_event_handlers_integration(self):
        """Test multiple event handlers working together."""
        # Arrange
        from pipedoc.connection_events import ConnectionEventManager
        from pipedoc.event_handlers import LoggingEventListener, StatisticsEventListener

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            event_manager = ConnectionEventManager()
            logging_handler = LoggingEventListener()
            stats_handler = StatisticsEventListener()

            event_manager.add_listener(logging_handler)
            event_manager.add_listener(stats_handler)

            event_data = ConnectionEvent(
                event_type=ConnectionEventType.CONNECT_SUCCESS,
                connection_id="integration_test",
                timestamp=time.time(),
                duration=0.15,
            )

            # Act
            event_manager.emit_event(event_data)

            # Assert - Both handlers should have processed the event
            mock_logger.info.assert_called_once()

            stats = stats_handler.get_statistics()
            assert stats["total_successes"] == 1
            assert stats["avg_duration"] == 0.15

    def test_logging_event_handler_json_format(self):
        """Test LoggingEventListener with JSON format."""
        # Arrange
        from pipedoc.event_handlers import LoggingEventListener

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            handler = LoggingEventListener(format_type="json")

            event_data = ConnectionEvent(
                event_type=ConnectionEventType.CONNECT_SUCCESS,
                connection_id="json_test",
                timestamp=1234567890.0,
                duration=0.1,
                metadata={"key": "value"},
            )

            # Act
            handler.on_connection_event(event_data)

            # Assert
            mock_logger.info.assert_called_once()
            logged_json = mock_logger.info.call_args[0][0]
            parsed = json.loads(logged_json)
            assert parsed["event_type"] == "connect_success"
            assert parsed["connection_id"] == "json_test"
            assert parsed["duration"] == 0.1
            assert parsed["metadata"]["key"] == "value"


class TestEventHandlerChain:
    """Test cases for EventHandlerChain."""

    def test_event_handler_chain_basic_functionality(self):
        """Test that EventHandlerChain processes events through multiple handlers."""
        # Arrange
        from pipedoc.event_handlers import EventHandlerChain, StatisticsEventListener

        handler1 = StatisticsEventListener()
        handler2 = StatisticsEventListener()

        chain = EventHandlerChain([handler1, handler2])

        event_data = ConnectionEvent(
            event_type=ConnectionEventType.CONNECT_SUCCESS,
            connection_id="chain_test",
            timestamp=time.time(),
            duration=0.1,
        )

        # Act
        chain.on_connection_event(event_data)

        # Assert - Both handlers should have processed the event
        stats1 = handler1.get_statistics()
        stats2 = handler2.get_statistics()

        assert stats1["total_successes"] == 1
        assert stats2["total_successes"] == 1
        assert chain.get_handler_count() == 2
