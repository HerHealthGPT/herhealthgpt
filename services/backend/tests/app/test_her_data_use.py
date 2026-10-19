"""When a reply is marked as drawing on her cycle data (``her_data``)."""

from __future__ import annotations

from test_cycle_breakdown import _summary


def test_her_data_is_shown_on_the_breakdown_turn() -> None:
    from herhealth_backend.app.triage.routes import _her_data_use

    use = _her_data_use(
        _summary(),  # type: ignore[arg-type]
        {"cycle_regularity": "irregular"},
        breakdown=True,
        concluded=False,
        first_turn=False,
    )
    assert use is not None
    assert use["source_app"] == "apple_health"
    assert use["breakdown"] is True
    assert use["answered"] == ["cycle_regularity"]


def test_her_data_is_not_repeated_on_every_question() -> None:
    from herhealth_backend.app.triage.routes import _her_data_use

    use = _her_data_use(
        _summary(),  # type: ignore[arg-type]
        {"cycle_regularity": "irregular"},
        breakdown=False,
        concluded=False,
        first_turn=False,
    )
    assert use is None


def test_her_data_is_shown_on_a_conclusion_it_answered_for() -> None:
    from herhealth_backend.app.triage.routes import _her_data_use

    summary = _summary()
    assert _her_data_use(summary, {}, breakdown=False, concluded=True, first_turn=True) is None  # type: ignore[arg-type]
    use = _her_data_use(
        summary,  # type: ignore[arg-type]
        {"cycle_regularity": "irregular"},
        breakdown=False,
        concluded=True,
        first_turn=False,
    )
    assert use is not None and use["breakdown"] is False
