"""Regression tests for the shared login password policy."""

import pytest

from core.security import validate_password


@pytest.mark.parametrize("password", ["Clave123", "usuario2026", "A1b2c3d4"])
def test_password_policy_accepts_eight_or_more_alphanumeric_characters(password):
    validate_password(password)


@pytest.mark.parametrize("password", ["Clave12", "abcdefgh", "12345678", "Clave123!"])
def test_password_policy_rejects_invalid_values(password):
    with pytest.raises(ValueError):
        validate_password(password)
