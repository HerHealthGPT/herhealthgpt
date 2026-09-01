"""Tests for branded account email templates."""

from __future__ import annotations

from herhealth_backend.app.accounts.email_templates import (
    BRAND_PRIMARY,
    password_reset_email,
    verification_email,
)


def test_verification_email_includes_code_in_both_formats() -> None:
    plain, html = verification_email(code="123456", minutes=15)

    assert "123456" in plain
    assert "123456" in html
    assert "15" in plain
    assert "HerHealthGPT" in plain
    assert "HerHealth" in html
    assert BRAND_PRIMARY in html


def test_password_reset_email_includes_code_in_both_formats() -> None:
    plain, html = password_reset_email(code="654321", minutes=15)

    assert "654321" in plain
    assert "654321" in html
    assert "password has not changed" in plain
    assert BRAND_PRIMARY in html
