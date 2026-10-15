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


def test_the_emails_are_written_in_the_requested_language() -> None:
    from herhealth_backend.app.accounts.email_templates import email_subject

    plain, html = verification_email(code="123456", minutes=15, language="ar")
    assert "123456" in plain and "123456" in html
    assert 'lang="ar" dir="rtl"' in html
    assert "تأكيد" in html
    assert email_subject("reset", "fr").startswith("Réinitialiser")


def test_an_unknown_language_falls_back_to_english() -> None:
    plain, _ = password_reset_email(code="654321", minutes=15, language="de")
    assert plain.startswith("Your HerHealthGPT password reset code is: 654321")


def test_the_request_language_comes_from_accept_language() -> None:
    from herhealth_backend.app.locale import language_from_accept_language

    assert language_from_accept_language("ar") == "ar"
    assert language_from_accept_language("fr-FR,fr;q=0.9,en;q=0.8") == "fr"
    assert language_from_accept_language("de-DE,ar;q=0.4") == "ar"
    assert language_from_accept_language("de, es") == "en"
    assert language_from_accept_language(None) == "en"
