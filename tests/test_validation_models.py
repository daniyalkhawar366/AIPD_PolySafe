import pytest
from pydantic import ValidationError
from fastapi import HTTPException

from backend import (
    RegisterAction,
    ResetPasswordAction,
    ShareLinkAction,
    _validate_reset_code,
    _infer_frequency_from_text,
)
from ocr import _normalize_frequency_text


def test_register_action_rejects_short_name():
    with pytest.raises(ValidationError):
        RegisterAction(name="A", email="user@example.com", password="strongpass123", role="patient")


def test_reset_password_action_rejects_short_code():
    with pytest.raises(ValidationError):
        ResetPasswordAction(email="user@example.com", code="123", new_password="newpass123")


def test_share_link_bounds_validation():
    with pytest.raises(ValidationError):
        ShareLinkAction(purpose="consultation", expires_hours=0)


def test_validate_reset_code_accepts_6_digits():
    _validate_reset_code("123456")


def test_validate_reset_code_rejects_non_digits():
    with pytest.raises(HTTPException):
        _validate_reset_code("12ab56")


def test_frequency_normalization_tid_is_thrice_daily():
    assert _normalize_frequency_text("TID") == "thrice daily"


def test_backend_infer_frequency_tid_is_thrice_daily():
    assert _infer_frequency_from_text("", "TID") == "thrice daily"


def test_backend_infer_frequency_qd_is_once_daily():
    assert _infer_frequency_from_text("", "QD") == "once daily"
