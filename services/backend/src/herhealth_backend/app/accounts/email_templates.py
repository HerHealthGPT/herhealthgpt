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

_BODY_STYLE = (
    "margin:0;padding:0;"
    f"background-color:{BRAND_BACKGROUND};"
    f"font-family:{_FONT_STACK};"
    f"color:{BRAND_TEXT};"
)
_OUTER_TABLE_STYLE = f"background-color:{BRAND_BACKGROUND};padding:32px 16px;"
_CARD_TABLE_STYLE = (
    f"max-width:520px;background-color:{BRAND_CARD};"
    f"border:1px solid {BRAND_BORDER};"
    "border-radius:12px;overflow:hidden;"
)
_HEADER_GRADIENT = f"linear-gradient(180deg, {BRAND_ACCENT_BG} 0%, {BRAND_CARD} 100%)"
_HEADER_CELL_STYLE = f"padding:28px 28px 20px;background:{_HEADER_GRADIENT};"
_BRAND_TITLE_STYLE = f"margin:0;font-size:22px;font-weight:700;line-height:1.3;color:{BRAND_TEXT};"
_HEADING_STYLE = (
    f"margin:0 0 12px;font-size:20px;font-weight:600;line-height:1.3;color:{BRAND_TEXT};"
)
_CODE_SPAN_STYLE = (
    "display:inline-block;padding:14px 28px;font-size:28px;font-weight:700;"
    "letter-spacing:0.2em;"
    f"color:{BRAND_PRIMARY};background-color:{BRAND_ACCENT_BG};"
    f"border:1px solid {BRAND_BORDER};border-radius:10px;"
    "font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;"
)


# One sentence per line, unwrapped, so a translator reads whole sentences.
# ruff: noqa: E501
#: Every sentence in the two emails, per interface language. ``{brand}``,
#: ``{minutes}`` and ``{code}`` are filled in; the code itself never changes.
_COPY: dict[str, dict[str, str]] = {
    "en": {
        "footer": "{brand} shares health information, not medical advice. If something feels urgent, call emergency services or go to hospital.",
        "received": "You received this because someone used this address on {brand}.",
        "enter_code": "Enter this code in the app:",
        "verify_subject": "Your {brand} verification code",
        "verify_title": "Verify your email",
        "verify_intro": "Thanks for signing up. Use the code below to finish creating your account.",
        "verify_expiry": "This code expires in {minutes} minutes. If you did not request it, you can safely ignore this email.",
        "verify_plain": "Your {brand} verification code is: {code}\n\nIt expires in {minutes} minutes. If you did not sign up, you can ignore this email.",
        "reset_subject": "Reset your {brand} password",
        "reset_title": "Reset your password",
        "reset_intro": "We received a request to reset the password for your account. Enter this code in the app to choose a new password.",
        "reset_expiry": "This code expires in {minutes} minutes. If you did not request a reset, ignore this email. Your password stays the same.",
        "reset_plain": "Your {brand} password reset code is: {code}\n\nIt expires in {minutes} minutes. If you did not ask for this, ignore this email. Your password has not changed.",
    },
    "ar": {
        "footer": "يقدّم {brand} معلومات صحية، وليس نصيحة طبية. إذا شعرتِ أن الأمر عاجل، فاتصلي بخدمات الطوارئ أو توجّهي إلى المستشفى.",
        "received": "وصلتكِ هذه الرسالة لأن أحدًا استخدم هذا العنوان على {brand}.",
        "enter_code": "أدخلي هذا الرمز في التطبيق:",
        "verify_subject": "رمز التأكيد الخاص بكِ في {brand}",
        "verify_title": "تأكيد بريدكِ الإلكتروني",
        "verify_intro": "شكرًا لتسجيلكِ. استخدمي الرمز أدناه لإكمال إنشاء حسابكِ.",
        "verify_expiry": "تنتهي صلاحية هذا الرمز خلال {minutes} دقيقة. إذا لم تطلبيه، يمكنكِ تجاهل هذه الرسالة بأمان.",
        "verify_plain": "رمز التأكيد الخاص بكِ في {brand} هو: {code}\n\nتنتهي صلاحيته خلال {minutes} دقيقة. إذا لم تسجّلي، يمكنكِ تجاهل هذه الرسالة.",
        "reset_subject": "إعادة تعيين كلمة المرور في {brand}",
        "reset_title": "إعادة تعيين كلمة المرور",
        "reset_intro": "تلقّينا طلبًا لإعادة تعيين كلمة مرور حسابكِ. أدخلي هذا الرمز في التطبيق لاختيار كلمة مرور جديدة.",
        "reset_expiry": "تنتهي صلاحية هذا الرمز خلال {minutes} دقيقة. إذا لم تطلبي إعادة التعيين، فتجاهلي هذه الرسالة، وستبقى كلمة مروركِ كما هي.",
        "reset_plain": "رمز إعادة تعيين كلمة المرور في {brand} هو: {code}\n\nتنتهي صلاحيته خلال {minutes} دقيقة. إذا لم تطلبي ذلك، فتجاهلي هذه الرسالة، فكلمة مروركِ لم تتغيّر.",
    },
    "fr": {
        "footer": "{brand} donne des informations de santé, pas un avis médical. Si quelque chose vous semble urgent, appelez les services d'urgence ou rendez-vous à l'hôpital.",
        "received": "Vous recevez ce message car quelqu'un a utilisé cette adresse sur {brand}.",
        "enter_code": "Saisissez ce code dans l'application :",
        "verify_subject": "Votre code de vérification {brand}",
        "verify_title": "Vérifiez votre e-mail",
        "verify_intro": "Merci de votre inscription. Utilisez le code ci-dessous pour terminer la création de votre compte.",
        "verify_expiry": "Ce code expire dans {minutes} minutes. Si vous ne l'avez pas demandé, vous pouvez ignorer cet e-mail.",
        "verify_plain": "Votre code de vérification {brand} est : {code}\n\nIl expire dans {minutes} minutes. Si vous ne vous êtes pas inscrite, ignorez cet e-mail.",
        "reset_subject": "Réinitialiser votre mot de passe {brand}",
        "reset_title": "Réinitialiser votre mot de passe",
        "reset_intro": "Nous avons reçu une demande de réinitialisation du mot de passe de votre compte. Saisissez ce code dans l'application pour choisir un nouveau mot de passe.",
        "reset_expiry": "Ce code expire dans {minutes} minutes. Si vous n'avez pas demandé de réinitialisation, ignorez cet e-mail. Votre mot de passe ne change pas.",
        "reset_plain": "Votre code de réinitialisation {brand} est : {code}\n\nIl expire dans {minutes} minutes. Si vous n'avez rien demandé, ignorez cet e-mail. Votre mot de passe n'a pas changé.",
    },
}


def _copy(language: str, key: str, **values: object) -> str:
    table = _COPY.get(language, _COPY["en"])
    return table[key].format(brand=BRAND_NAME, **values)


def email_subject(kind: str, language: str = "en") -> str:
    """The subject line: ``kind`` is ``verify`` or ``reset``."""
    return _copy(language, f"{kind}_subject")


def _wrap_email(*, title: str, body_html: str, language: str = "en") -> str:
    safe_title = escape(title)
    direction = "rtl" if language == "ar" else "ltr"
    return f"""<!DOCTYPE html>
<html lang="{language}" dir="{direction}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
</head>
<body style="{_BODY_STYLE}">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
         style="{_OUTER_TABLE_STYLE}">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
               style="{_CARD_TABLE_STYLE}" dir="{direction}">
          <tr>
            <td style="{_HEADER_CELL_STYLE}">
              <p style="{_BRAND_TITLE_STYLE}" dir="ltr">
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
                {escape(_copy(language, "footer"))}
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:16px 0 0;font-size:11px;color:{BRAND_MUTED};">
          {escape(_copy(language, "received"))}
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _code_block(code: str, language: str = "en") -> str:
    safe_code = escape(code)
    return f"""
      <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:{BRAND_TEXT};">
        {escape(_copy(language, "enter_code"))}
      </p>
      <p style="margin:0 0 20px;text-align:center;" dir="ltr">
        <span style="{_CODE_SPAN_STYLE}">
          {safe_code}
        </span>
      </p>"""


def _email(kind: str, *, code: str, minutes: int, language: str) -> tuple[str, str]:
    plain = _copy(language, f"{kind}_plain", code=code, minutes=minutes)
    body = f"""
      <h1 style="{_HEADING_STYLE}">
        {escape(_copy(language, f"{kind}_title"))}
      </h1>
      <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:{BRAND_MUTED};">
        {escape(_copy(language, f"{kind}_intro"))}
      </p>
      {_code_block(code, language)}
      <p style="margin:0;font-size:14px;line-height:1.6;color:{BRAND_MUTED};">
        {escape(_copy(language, f"{kind}_expiry", minutes=minutes))}
      </p>
    """
    html = _wrap_email(title=_copy(language, f"{kind}_title"), body_html=body, language=language)
    return plain, html


def verification_email(*, code: str, minutes: int, language: str = "en") -> tuple[str, str]:
    return _email("verify", code=code, minutes=minutes, language=language)


def password_reset_email(*, code: str, minutes: int, language: str = "en") -> tuple[str, str]:
    return _email("reset", code=code, minutes=minutes, language=language)
