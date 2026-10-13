"""Which language she is writing in, so the reply can be written in it too.

Observed 2026-10-13: a message in Arabic was understood and answered in
English. Nothing in the prompts said what language to answer in, and every
example in them is English.

The language is named to the model outright ("Write in Arabic") instead of
asking it to "reply in her language". Naming it means detecting it, and the
detection here is deliberately small. Arabic is recognised by its script,
which is unambiguous. French is recognised by common function words, because
it shares its script with English. Anything else gets no instruction, and the
model replies as it did before.

This decides the language of the words she reads and nothing else. Feature
ids, action codes and every other identifier stay as they are, and
cross-language comparison is still on the action code, never on the text.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

__all__ = ["ARABIC", "FRENCH", "detect_language", "language_instruction"]

ARABIC = "Arabic"
FRENCH = "French"

_ARABIC_LETTER = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")
_LATIN_LETTER = re.compile(r"[A-Za-zÀ-ÿ]")
_WORD = re.compile(r"[a-zà-ÿœ'-]+")

#: Words that are common in French and are not English words. Short on
#: purpose: a longer list starts catching English ("me", "on", "son").
_FRENCH_WORDS = frozenset(
    [
        "je",
        "j'ai",
        "suis",
        "mes",
        "ma",
        "mon",
        "nous",
        "vous",
        "elle",
        "elles",
        "ils",
        "est",
        "sont",
        "ai",
        "avez",
        "avoir",
        "être",
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "du",
        "au",
        "aux",
        "et",
        "ou",
        "mais",
        "donc",
        "que",
        "qui",
        "quoi",
        "quand",
        "pourquoi",
        "ne",
        "pas",
        "très",
        "depuis",
        "pendant",
        "avec",
        "sans",
        "pour",
        "dans",
        "sur",
        "chez",
        "cette",
        "ces",
        "cela",
        "ça",
        "c'est",
        "qu'est-ce",
        "est-ce",
        "règles",
        "douleur",
        "douleurs",
        "mois",
        "semaine",
        "semaines",
        "jours",
        "saignement",
        "saignements",
        "enceinte",
        "bonjour",
        "merci",
        "oui",
    ]
)


def _language_of(text: str) -> str | None:
    arabic = len(_ARABIC_LETTER.findall(text))
    latin = len(_LATIN_LETTER.findall(text))
    if arabic and arabic >= latin:
        return ARABIC
    words = _WORD.findall(text.lower())
    hits = sum(1 for word in words if word in _FRENCH_WORDS)
    # Two French words, or one in a message of one or two words ("oui",
    # "oui merci"). A single hit in a longer message is not enough: English
    # borrows too much.
    if hits >= 2 or (hits == 1 and len(words) <= 2):
        return FRENCH
    return None


def detect_language(messages: Iterable[str]) -> str | None:
    """The language of her most recent message that shows one.

    ``messages`` are her own messages, oldest first. The newest is tried
    first and older ones after it, because a reply such as "29" or "3" shows
    no language at all and the conversation should not flip to English on it.
    ``None`` means none was recognised, which is how English reads here.
    """
    for text in reversed(list(messages)):
        if not _LATIN_LETTER.search(text) and not _ARABIC_LETTER.search(text):
            continue  # digits or punctuation only: says nothing
        return _language_of(text)
    return None


def language_instruction(language: str | None) -> str:
    """The line added to a prompt, or an empty string when none is needed."""
    if language is None:
        return ""
    return (
        f"LANGUAGE. She is writing in {language}. Write every word she will read "
        f"in {language}: question_text, answer_text and rationale. Use plain, "
        f"everyday {language} a worried person can follow. Keep the JSON keys, "
        "feature ids, action codes and every other identifier exactly as given, "
        "in English."
    )
