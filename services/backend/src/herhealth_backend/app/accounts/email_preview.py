"""Write styled HTML email previews when running with ConsoleEmailSender."""

from __future__ import annotations

from pathlib import Path

_PREVIEW_DIR = Path(__file__).resolve().parents[4] / "var" / "email-previews"


def write_email_preview(*, kind: str, html: str) -> Path:
    """Persist the latest styled email for local inspection."""
    _PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    path = _PREVIEW_DIR / f"latest-{kind}.html"
    path.write_text(html, encoding="utf-8")
    return path
