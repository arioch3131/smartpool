"""Tests for utility functions."""

from unittest.mock import Mock

from smartpool.core.utils import safe_log


class TestSafeLogUtility:
    """Tests for the safe_log utility function."""

    def test_safe_log_handles_exceptions(self):
        """Test that _safe_log handles exceptions gracefully."""
        mock_logger = Mock()
        mock_logger.isEnabledFor.return_value = True
        mock_logger.log.side_effect = ValueError("Test Error")
        safe_log(mock_logger, 20, "Test message")
        mock_logger.log.assert_called_once_with(20, "Test message")

    def test_safe_log_handles_oserror(self):
        """Test that _safe_log handles OSError gracefully."""
        mock_logger = Mock()
        mock_logger.isEnabledFor.return_value = True
        mock_logger.log.side_effect = OSError("Test OSError")
        safe_log(mock_logger, 20, "Test message")
        mock_logger.log.assert_called_once_with(20, "Test message")

    def test_safe_log_handles_generic_exception(self):
        """Test that _safe_log handles generic Exception gracefully."""
        mock_logger = Mock()
        mock_logger.isEnabledFor.return_value = True
        mock_logger.log.side_effect = Exception("Test Generic Exception")
        safe_log(mock_logger, 20, "Test message")
        mock_logger.log.assert_called_once_with(20, "Test message")

    def test_safe_log_no_logger(self):
        """Test _safe_log when logger is None."""
        safe_log(None, 20, "Test message")
        # No exception should be raised

    def test_safe_log_logger_not_enabled(self):
        """Test _safe_log when logger is not enabled for the level."""
        mock_logger = Mock()
        mock_logger.isEnabledFor.return_value = False
        safe_log(mock_logger, 20, "Test message")
        mock_logger.log.assert_not_called()
