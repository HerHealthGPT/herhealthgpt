"""Domain errors raised by the Accounts use cases, translated to HTTP in routes.py."""

from __future__ import annotations

__all__ = [
    "EmailAlreadyRegistered",
    "InvalidCredentials",
    "TooManySignInAttempts",
    "InvalidSession",
    "InvalidAccessToken",
    "IncorrectVerificationCode",
    "VerificationCodeExpired",
    "TooManyVerificationRequests",
    "GoogleTokenInvalid",
    "GoogleEmailNotVerified",
    "GoogleSignInNotConfigured",
    "NoPasswordCredential",
    "IncorrectPasswordResetCode",
    "PasswordResetCodeExpired",
    "TooManyPasswordResetRequests",
    "InvalidDisplayName",
    "CycleImportFailed",
    "CycleImportUnavailable",
    "StoredFileNotFound",
    "StoredFileRejected",
    "StoredFilesUnavailable",
]


class EmailAlreadyRegistered(Exception):
    """Raised when registering an address that already has a user.

    Carries no detail about the existing user — not whether she is verified,
    not when she registered — because the route this feeds must not reveal
    anything about her beyond the fact that this registration attempt failed.
    """


class InvalidCredentials(Exception):
    """Raised for a sign-in attempt against an unknown address, and for a
    wrong password against a real one — the same exception either way, so
    the route this feeds cannot answer "does this address exist?" (#9's
    second acceptance criterion).
    """


class TooManySignInAttempts(Exception):
    """Raised when an address has failed sign-in too often recently.

    See ``app/accounts/sign_in_throttle.py`` for the count and the window.
    """


class InvalidSession(Exception):
    """Raised when a refresh token is missing, unknown, revoked, or expired —
    by its absolute lifetime or by having sat idle too long. Deliberately one
    exception for all four: none of them should be distinguishable to a
    caller, only "sign in again" is.
    """


class InvalidAccessToken(Exception):
    """Raised when an access token is missing, tampered with, or past its
    (short, unrevocable) lifetime. See ``app/accounts/tokens.py``.
    """


class IncorrectVerificationCode(Exception):
    """Raised when a submitted verification code is wrong, but the stored
    code is still alive (not expired, not used, under the attempt limit).
    Distinct from :class:`VerificationCodeExpired` because #10 asks for the
    two to read differently — "wrong code" invites another try; "expired"
    does not.
    """


class VerificationCodeExpired(Exception):
    """Raised whenever there is no code left that submitting the right
    digits could satisfy: none was ever requested, it passed its expiry
    window, it was already used, or too many wrong guesses used it up.
    Deliberately one exception for all four — which of them is true is not
    revealed, only that a fresh code is needed.
    """


class TooManyVerificationRequests(Exception):
    """Raised when an address has requested a verification code too often
    recently. See ``app/accounts/verification_send_throttle.py``.
    """


class GoogleTokenInvalid(Exception):
    """Raised when a Google ID token is missing, malformed, expired, or
    fails signature/audience verification. See
    ``app/accounts/google_identity.py``.
    """


class GoogleEmailNotVerified(Exception):
    """Raised when Google's identity would otherwise be linked to, or take
    over, an existing user, but the token's ``email_verified`` claim is
    false or absent. #11's fourth acceptance criterion: an unverified claim
    is never linked to an existing user, whether that user is herself
    verified (linking) or not (takeover) — in neither case can the address
    on the token be trusted to be the one behind that user's account.
    """


class GoogleSignInNotConfigured(Exception):
    """Raised when Google sign-in is called with no
    ``HERHEALTH_GOOGLE_CLIENT_ID`` configured. Distinct from
    :class:`GoogleTokenInvalid`: this is a deployment that has not set the
    feature up, not a bad token — the process still boots (see
    ``app/config.py::google_client_id``), this is what the route degrades
    to instead.
    """


class NoPasswordCredential(Exception):
    """Raised when a password-reset request or completion names a real
    account that has no password credential to reset — one that signs in
    with Google alone. #12's own framing: this is the one deliberate
    exception to "an unknown address and a real one must look the same",
    because the alternative (silence, or a reset mail that cannot help)
    strands her looping between two screens that each point at the other.
    """


class IncorrectPasswordResetCode(Exception):
    """Raised when a submitted password-reset code is wrong, but the stored
    code is still alive (not expired, not used, under the attempt limit).
    Distinct from :class:`PasswordResetCodeExpired` for the same reason
    :class:`IncorrectVerificationCode` is distinct from its own expired
    counterpart — "wrong code" invites another try; "expired" does not.
    """


class PasswordResetCodeExpired(Exception):
    """Raised whenever there is no reset code left that submitting the right
    digits could satisfy: none was ever requested, it passed its expiry
    window, it was already used, or too many wrong guesses used it up.
    Deliberately one exception for all four, the same reasoning
    :class:`VerificationCodeExpired` is held to.
    """


class TooManyPasswordResetRequests(Exception):
    """Raised when an address has requested a password reset too often
    recently. See ``app/accounts/password_reset_throttle.py``.
    """


class InvalidDisplayName(Exception):
    """Raised when a display name is empty after normalisation or too long."""


class InvalidDateOfBirth(Exception):
    """Raised when a date of birth is in the future or implies an age outside
    ``profile.MIN_AGE_YEARS``..``profile.MAX_AGE_YEARS``.

    Never corrected to the nearest plausible date: age derives the
    ``age_band`` the reasoning model is told about, so a guess here is a
    guess about what the system suspects.
    """


class InvalidHealthNote(Exception):
    """Raised when a health note exceeds ``profile.MAX_HEALTH_NOTE_LENGTH``.

    Blank input is not an error — it clears the note. See
    ``profile.normalize_health_note``.
    """


class CycleImportFailed(Exception):
    """An uploaded cycle-tracking export could not be read into anything
    usable. ``reason`` is a short code the frontend turns into a message in
    her language: ``too_large``, ``unreadable``, ``unsupported_archive``,
    ``bad_template_row`` or ``nothing_usable``."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class CycleImportUnavailable(Exception):
    """The file needs the model to read it, and no model is configured — as
    in production today, where triage reports "not configured" too."""


class StoredFileRejected(Exception):
    """A file she asked to keep was refused before anything was written.
    ``reason`` is a code the frontend words in her language:
    ``unsupported_type``, ``too_large``, ``too_many_files``,
    ``account_full`` or ``storage_full``."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class StoredFilesUnavailable(Exception):
    """This deployment has no directory to keep files in
    (``HERHEALTH_UPLOAD_DIR`` is unset)."""


class StoredFileNotFound(Exception):
    """No such file, someone else's, or past its date — all answered alike."""
