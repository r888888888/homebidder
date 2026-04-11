"""
Tests for startup environment variable validation.
The server must fail fast with a clear message when required config is missing.
"""

import os
import pytest
from unittest.mock import patch


class TestStartupValidation:
    def test_missing_api_key_raises_on_validate(self):
        """_validate_env_vars should raise RuntimeError when ANTHROPIC_API_KEY is absent."""
        from main import _validate_env_vars

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                _validate_env_vars()

    def test_present_api_key_does_not_raise(self):
        """_validate_env_vars should not raise when ANTHROPIC_API_KEY is set."""
        from main import _validate_env_vars

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}):
            _validate_env_vars()  # must not raise

    def test_error_message_names_the_missing_variable(self):
        """The error message should name the specific missing variable."""
        from main import _validate_env_vars

        with patch.dict(os.environ, {}, clear=True):
            try:
                _validate_env_vars()
            except RuntimeError as exc:
                assert "ANTHROPIC_API_KEY" in str(exc)
            else:
                pytest.fail("Expected RuntimeError was not raised")
