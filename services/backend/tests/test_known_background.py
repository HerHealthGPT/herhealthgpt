"""``render_known_background`` — the safety wording, pinned.

This block is the only route by which stored profile data reaches the
reasoning model, so its framing is the whole control: it has to stop the
model re-asking her age, without letting a note she wrote months ago act as
a symptom she is reporting now. ADR 0015's risk register names both.
"""

from __future__ import annotations

from herhealth_backend.triage.agent import render_known_background


def test_nothing_stored_renders_nothing() -> None:
    """No block at all, rather than a block saying "unknown" — an empty
    section is prompt weight spent telling the model nothing."""
    assert render_known_background(age_band=None, health_note=None) is None
    assert render_known_background(age_band=None, health_note="") is None


def test_an_age_band_tells_the_model_not_to_ask_again() -> None:
    rendered = render_known_background(age_band="30_to_39", health_note=None)

    assert rendered is not None
    assert "30_to_39" in rendered
    assert "do not ask her age again" in rendered


def test_a_note_is_framed_as_background_and_not_as_a_symptom() -> None:
    rendered = render_known_background(age_band=None, health_note="PCOS since 2019")

    assert rendered is not None
    assert "PCOS since 2019" in rendered
    # The three claims the framing has to make, or stored text starts
    # behaving like a live report.
    assert "unverified" in rendered
    assert "NOT a symptom she is reporting now" in rendered
    assert "fire a warning sign" in rendered


def test_the_block_says_the_source_is_her_profile_not_the_conversation() -> None:
    """Otherwise the model can cite it back to her as something she just
    said, in a transcript where she did not say it."""
    rendered = render_known_background(age_band="45_to_54", health_note="low iron")

    assert rendered is not None
    assert "not from this conversation" in rendered


def test_both_fields_render_together() -> None:
    rendered = render_known_background(age_band="under_20", health_note="asthma")

    assert rendered is not None
    assert "under_20" in rendered
    assert "asthma" in rendered
    assert "Still ask about what is happening today." in rendered
