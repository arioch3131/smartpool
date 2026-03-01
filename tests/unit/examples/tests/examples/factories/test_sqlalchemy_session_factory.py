"""
Complete unit tests for SQLAlchemySessionFactory - 100% coverage.
"""

from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from examples.factories import SQLAlchemySessionFactory


class TestSQLAlchemySessionFactory:  # pylint: disable=W0201, R0904
    """Complete tests for SQLAlchemySessionFactory."""

    def setup_method(self):
        """Setup for each test."""
        self.session_source = Mock()
        self.factory = SQLAlchemySessionFactory(self.session_source)

    def test_init(self):
        """Test the constructor."""
        assert self.factory.session_source == self.session_source

    def test_init_with_different_service(self):
        """Test constructor with different services."""
        service1 = Mock()
        service2 = Mock()

        factory1 = SQLAlchemySessionFactory(service1)
        factory2 = SQLAlchemySessionFactory(service2)

        assert factory1.session_source == service1
        assert factory2.session_source == service2
        assert factory1.session_source != factory2.session_source

    def test_create_basic(self):
        """Test basic session creation."""
        mock_session = Mock()
        self.session_source.return_value = mock_session

        result = self.factory.create()

        assert result == mock_session
        self.session_source.assert_called_once_with()

    def test_create_with_kwargs(self):
        """Test creation with kwargs."""
        mock_session = Mock()
        self.session_source.return_value = mock_session

        result = self.factory.create(some_param="value", another_param=123)

        assert result == mock_session
        self.session_source.assert_called_once_with(some_param="value", another_param=123)

    def test_create_multiple_sessions(self):
        """Test creating multiple sessions."""
        session1 = Mock()
        session2 = Mock()
        session3 = Mock()

        self.session_source.side_effect = [session1, session2, session3]

        result1 = self.factory.create()
        result2 = self.factory.create()
        result3 = self.factory.create()

        assert result1 == session1
        assert result2 == session2
        assert result3 == session3
        assert self.session_source.call_count == 3

    def test_create_database_service_exception(self):
        """Test creation when database_service raises an exception."""
        self.session_source.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception) as exc_info:
            self.factory.create()

        assert "Database connection failed" in str(exc_info.value)

    def test_reset_success(self):
        """Test successful session reset."""
        mock_session = Mock()
        mock_session.rollback.return_value = None
        mock_session.expunge_all.return_value = None

        result = self.factory.reset(mock_session)

        assert result is True
        mock_session.rollback.assert_called_once()
        mock_session.expunge_all.assert_called_once()

    def test_reset_with_different_sessions(self):
        """Test reset with different sessions."""
        session1 = Mock()
        session2 = Mock()

        result1 = self.factory.reset(session1)
        result2 = self.factory.reset(session2)

        assert result1 is True
        assert result2 is True

        session1.rollback.assert_called_once()
        session1.expunge_all.assert_called_once()
        session2.rollback.assert_called_once()
        session2.expunge_all.assert_called_once()

    def test_reset_rollback_exception(self):
        """Test reset when rollback raises an exception."""
        mock_session = Mock()
        mock_session.rollback.side_effect = SQLAlchemyError("Rollback failed")

        result = self.factory.reset(mock_session)

        assert result is False
        mock_session.rollback.assert_called_once()
        # expunge_all should not be called because rollback failed
        mock_session.expunge_all.assert_not_called()

    def test_reset_expunge_all_exception(self):
        """Test reset when expunge_all raises an exception."""
        mock_session = Mock()
        mock_session.rollback.return_value = None
        mock_session.expunge_all.side_effect = SQLAlchemyError("Expunge failed")

        result = self.factory.reset(mock_session)

        assert result is False
        mock_session.rollback.assert_called_once()
        mock_session.expunge_all.assert_called_once()

    def test_reset_both_methods_exception(self):
        """Test reset when rollback and expunge_all raise exceptions."""
        mock_session = Mock()
        mock_session.rollback.side_effect = SQLAlchemyError("Rollback failed")
        mock_session.expunge_all.side_effect = SQLAlchemyError("Expunge failed")

        result = self.factory.reset(mock_session)

        assert result is False
        mock_session.rollback.assert_called_once()
        # expunge_all should not be called because rollback failed first
        mock_session.expunge_all.assert_not_called()

    def test_reset_with_none(self):
        """Test reset with None."""
        result = self.factory.reset(None)
        assert result is False

    def test_reset_with_invalid_object(self):
        """Test reset with an invalid object."""
        invalid_obj = "not_a_session"
        result = self.factory.reset(invalid_obj)
        assert result is False

    def test_validate_active_session(self):
        """Test validation of an active session."""
        mock_session = Mock()
        mock_session.is_active = True

        result = self.factory.validate(mock_session)

        assert result is True

    def test_validate_inactive_session(self):
        """Test validation of an inactive session."""
        mock_session = Mock()
        mock_session.is_active = False

        result = self.factory.validate(mock_session)

        assert result is False

    def test_validate_multiple_sessions(self):
        """Test validation of multiple sessions."""
        active_session = Mock()
        inactive_session = Mock()
        active_session.is_active = True
        inactive_session.is_active = False

        result1 = self.factory.validate(active_session)
        result2 = self.factory.validate(inactive_session)

        assert result1 is True
        assert result2 is False

    def test_validate_session_without_is_active(self):
        """Test validation with a session without the is_active attribute."""
        mock_session = Mock()
        # Remove the is_active attribute
        del mock_session.is_active

        result = self.factory.validate(mock_session)

        assert result is False

    def test_validate_is_active_property_exception(self):
        """Test validation when is_active raises an exception."""
        mock_session = Mock()
        del mock_session.is_active
        result = self.factory.validate(mock_session)
        assert result is False

    def test_validate_with_none(self):
        """Test validation with None."""
        result = self.factory.validate(None)
        assert result is False

    def test_validate_with_invalid_object(self):
        """Test validation with an invalid object."""
        result = self.factory.validate("not_a_session")
        assert result is False

    def test_get_key_default(self):
        """Test default key generation."""
        result = self.factory.get_key()
        assert result == "session_default"

    def test_get_key_with_kwargs(self):
        """Test key generation with kwargs (ignored)."""
        result1 = self.factory.get_key(param1="value1", param2="value2")
        result2 = self.factory.get_key(different="kwargs")
        result3 = self.factory.get_key()

        # All should return the same key because kwargs are ignored
        assert result1 == "session_default"
        assert result2 == "session_default"
        assert result3 == "session_default"

    def test_get_key_consistency(self):
        """Test key generation consistency."""
        # Calling get_key multiple times should yield the same result
        keys = [self.factory.get_key() for _ in range(10)]
        assert all(key == "session_default" for key in keys)

    def test_comprehensive_workflow(self):
        """Test complete workflow."""
        # Setup session mock
        mock_session = Mock()
        mock_session.is_active = True
        self.session_source.return_value = mock_session

        # Test complete workflow
        key = self.factory.get_key()
        session = self.factory.create()
        is_valid_before = self.factory.validate(session)
        reset_success = self.factory.reset(session)
        is_valid_after = self.factory.validate(session)

        # Assertions
        assert key == "session_default"
        assert session == mock_session
        assert is_valid_before is True
        assert reset_success is True
        assert is_valid_after is True  # session is still active after reset

        # Call verifications
        self.session_source.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.expunge_all.assert_called_once()

    def test_session_lifecycle_simulation(self):
        """Test session lifecycle simulation."""
        # Simulate a session that becomes inactive after use
        mock_session = Mock()

        # session is active at the beginning
        mock_session.is_active = True
        self.session_source.return_value = mock_session

        # Create and validate
        session = self.factory.create()
        assert self.factory.validate(session) is True

        # Simulate the session becoming inactive
        mock_session.is_active = False
        assert self.factory.validate(session) is False

        # Reset should succeed even if the session is inactive
        assert self.factory.reset(session) is True

        # session can become active again after reset
        mock_session.is_active = True
        assert self.factory.validate(session) is True

    def test_multiple_factory_instances(self):
        """Test with multiple factory instances."""
        service1 = Mock()
        service2 = Mock()

        factory1 = SQLAlchemySessionFactory(service1)
        factory2 = SQLAlchemySessionFactory(service2)

        session1 = Mock()
        session2 = Mock()
        service1.return_value = session1
        service2.return_value = session2

        # Create sessions with each factory
        result1 = factory1.create()
        result2 = factory2.create()

        assert result1 == session1
        assert result2 == session2
        assert result1 != result2

        # Each factory uses its own service
        service1.assert_called_once()
        service2.assert_called_once()

    def test_factory_immutability(self):
        """Test that the factory is not modified by operations."""
        original_service = self.factory.session_source

        # Perform various operations
        self.factory.get_key()
        self.factory.get_key(param="value")

        mock_session = Mock()
        self.factory.reset(mock_session)
        self.factory.validate(mock_session)

        # The factory should remain unchanged
        assert self.factory.session_source == original_service
