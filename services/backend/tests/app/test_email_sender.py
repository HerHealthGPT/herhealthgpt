"""``ConsoleEmailSender`` and ``SesEmailSender`` — neither touches a real network here."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from herhealth_backend.app.accounts.email_sender import (
    SES_FROM_ADDRESS,
    SES_REPLY_TO_ADDRESS,
    ConsoleEmailSender,
    SesEmailSender,
)
from herhealth_backend.app.config import EMAIL_SENDER_ENV
from herhealth_backend.app.main import _build_email_sender


async def test_console_email_sender_logs_the_code(caplog: pytest.LogCaptureFixture) -> None:
    sender = ConsoleEmailSender()

    with caplog.at_level("INFO"):
        await sender.send_verification_code(to="woman@example.com", code="123456")

    assert "woman@example.com" in caplog.text
    assert "123456" in caplog.text


async def test_console_email_sender_logs_the_password_reset_code(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sender = ConsoleEmailSender()

    with caplog.at_level("INFO"):
        await sender.send_password_reset_code(to="woman@example.com", code="654321")

    assert "woman@example.com" in caplog.text
    assert "654321" in caplog.text


async def test_ses_email_sender_calls_send_email_with_the_code() -> None:
    with patch("herhealth_backend.app.accounts.email_sender.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        sender = SesEmailSender()
        await sender.send_verification_code(to="woman@example.com", code="123456")

    mock_boto3.client.assert_called_once_with("ses", region_name="us-east-1")
    mock_client.send_email.assert_called_once()
    call_kwargs = mock_client.send_email.call_args.kwargs
    assert call_kwargs["Source"] == SES_FROM_ADDRESS
    assert call_kwargs["Destination"] == {"ToAddresses": ["woman@example.com"]}
    assert call_kwargs["ReplyToAddresses"] == [SES_REPLY_TO_ADDRESS]
    assert "123456" in call_kwargs["Message"]["Body"]["Text"]["Data"]


async def test_ses_email_sender_calls_send_email_with_the_password_reset_code() -> None:
    with patch("herhealth_backend.app.accounts.email_sender.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        sender = SesEmailSender()
        await sender.send_password_reset_code(to="woman@example.com", code="654321")

    mock_boto3.client.assert_called_once_with("ses", region_name="us-east-1")
    mock_client.send_email.assert_called_once()
    call_kwargs = mock_client.send_email.call_args.kwargs
    assert call_kwargs["Source"] == SES_FROM_ADDRESS
    assert call_kwargs["Destination"] == {"ToAddresses": ["woman@example.com"]}
    assert call_kwargs["ReplyToAddresses"] == [SES_REPLY_TO_ADDRESS]
    assert "654321" in call_kwargs["Message"]["Body"]["Text"]["Data"]


def test_build_email_sender_defaults_to_console(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(EMAIL_SENDER_ENV, raising=False)

    assert isinstance(_build_email_sender(), ConsoleEmailSender)


def test_build_email_sender_selects_console_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EMAIL_SENDER_ENV, "console")

    assert isinstance(_build_email_sender(), ConsoleEmailSender)


def test_build_email_sender_selects_ses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EMAIL_SENDER_ENV, "ses")

    with patch("herhealth_backend.app.accounts.email_sender.boto3"):
        assert isinstance(_build_email_sender(), SesEmailSender)


def test_build_email_sender_rejects_an_unrecognised_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EMAIL_SENDER_ENV, "carrier-pigeon")

    with pytest.raises(RuntimeError, match="carrier-pigeon"):
        _build_email_sender()
