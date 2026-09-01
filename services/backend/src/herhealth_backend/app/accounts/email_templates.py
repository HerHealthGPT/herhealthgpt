"""Branded account emails — HTML + plain text, matched to the web UI.

Colours mirror the frontend tokens: berry primary #9F1239, warm off-white
background, Inter/system sans stack. Layout is table-based for email clients.
"""

from __future__ import annotations

from html import escape

BRAND_NAME = "HerHealthGPT"
BRAND_PRIMARY = "#9F1239"
BRAND_BACKGROUND = "#fdf9f8"
BRAND_CARD = "#ffffff"
BRAND_TEXT = "#3d3640"
BRAND_MUTED = "#6b6570"
BRAND_BORDER = "#ead9de"
BRAND_ACCENT_BG = "#f8eff2"

_FONT_STACK = (
    "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
)


def _wrap_email(*, title: str, body_html: str) -> str:
    safe_title = escape(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
</head>
<body style="margin:0;padding:0;background-color:{BRAND_BACKGROUND};font-family:{_FONT_STACK};color:{BRAND_TEXT};">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:{BRAND_BACKGROUND};padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:520px;background-color:{BRAND_CARD};border:1px solid {BRAND_BORDER};border-radius:12px;overflow:hidden;">
          <tr>
            <td style="padding:28px 28px 20px;background:linear-gradient(180deg, {BRAND_ACCENT_BG} 0%, {BRAND_CARD} 100%);">
              <p style="margin:0;font-size:22px;font-weight:700;line-height:1.3;color:{BRAND_TEXT};">
                HerHealth<span style="color:{BRAND_PRIMARY};">GPT</span>
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 28px 28px;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="padding:0 28px 24px;">
              <p style="margin:0;font-size:12px;line-height:1.5;color:{BRAND_MUTED};">
                {BRAND_NAME} shares health information, not medical advice. If something
                feels urgent, call emergency services or go to hospital.
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:16px 0 0;font-size:11px;color:{BRAND_MUTED};">
          You received this because someone used this address on {BRAND_NAME}.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _code_block(code: str) -> str:
    safe_code = escape(code)
    return f"""
      <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:{BRAND_TEXT};">
        Enter this code in the app:
      </p>
      <p style="margin:0 0 20px;text-align:center;">
        <span style="display:inline-block;padding:14px 28px;font-size:28px;font-weight:700;letter-spacing:0.2em;color:{BRAND_PRIMARY};background-color:{BRAND_ACCENT_BG};border:1px solid {BRAND_BORDER};border-radius:10px;font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;">
          {safe_code}
        </span>
      </p>"""


def verification_email(*, code: str, minutes: int) -> tuple[str, str]:
    plain = (
        f"Your {BRAND_NAME} verification code is: {code}\n\n"
        f"It expires in {minutes} minutes. If you did not sign up, you can ignore this email."
    )
    body = f"""
      <h1 style="margin:0 0 12px;font-size:20px;font-weight:600;line-height:1.3;color:{BRAND_TEXT};">
        Verify your email
      </h1>
      <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:{BRAND_MUTED};">
        Thanks for signing up. Use the code below to finish creating your account.
      </p>
      {_code_block(code)}
      <p style="margin:0;font-size:14px;line-height:1.6;color:{BRAND_MUTED};">
        This code expires in {minutes} minutes. If you did not request it, you can
        safely ignore this email.
      </p>
    """
    html = _wrap_email(title="Verify your email", body_html=body)
    return plain, html


def password_reset_email(*, code: str, minutes: int) -> tuple[str, str]:
    plain = (
        f"Your {BRAND_NAME} password reset code is: {code}\n\n"
        f"It expires in {minutes} minutes. If you did not ask for this, ignore this email. "
        "Your password has not changed."
    )
    body = f"""
      <h1 style="margin:0 0 12px;font-size:20px;font-weight:600;line-height:1.3;color:{BRAND_TEXT};">
        Reset your password
      </h1>
      <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:{BRAND_MUTED};">
        We received a request to reset the password for your account. Enter this code
        in the app to choose a new password.
      </p>
      {_code_block(code)}
      <p style="margin:0;font-size:14px;line-height:1.6;color:{BRAND_MUTED};">
        This code expires in {minutes} minutes. If you did not request a reset, ignore
        this email. Your password stays the same.
      </p>
    """
    html = _wrap_email(title="Reset your password", body_html=body)
    return plain, html
