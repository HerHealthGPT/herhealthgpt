"""The interface language of the request being handled.

The frontend sends its chosen language as ``Accept-Language`` on every API
call. A middleware in ``app/main.py`` stores it here for the length of the
request, so code that writes words for her (the verification and reset
emails, the reply language when her own message shows none) can ask for it
without the language being threaded through every function signature in
between, and without the email-sender interface changing.

Only the three languages the interface is written in are recognised; anything
else is English.
"""

from __future__ import annotations

from contextvars import ContextVar

__all__ = [
    "LANGUAGES",
    "LANGUAGE_NAMES",
    "current_language",
    "language_from_accept_language",
    "set_current_language",
]

LANGUAGES = ("en", "ar", "fr")

#: How a language is named to the reasoning model ("Write in Arabic").
LANGUAGE_NAMES = {"en": "English", "ar": "Arabic", "fr": "French"}

_current: ContextVar[str] = ContextVar("herhealth_request_language", default="en")


def language_from_accept_language(header: str | None) -> str:
    """The first supported language in an Accept-Language header, by weight."""
    if not header:
        return "en"
    ranked: list[tuple[float, str]] = []
    for part in header.split(","):
        tag, _, params = part.strip().partition(";")
        weight = 1.0
        if params.strip().startswith("q="):
            try:
                weight = float(params.strip()[2:])
            except ValueError:
                weight = 0.0
        ranked.append((weight, tag.strip().lower().split("-")[0]))
    for _, base in sorted(ranked, key=lambda item: -item[0]):
        if base in LANGUAGES:
            return base
    return "en"


def set_current_language(language: str) -> None:
    _current.set(language if language in LANGUAGES else "en")


def current_language() -> str:
    """The request's interface language: ``en``, ``ar`` or ``fr``."""
    return _current.get()
