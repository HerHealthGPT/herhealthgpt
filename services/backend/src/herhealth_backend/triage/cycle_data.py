"""Cycle data she imported, turned into answers and background. See ADR 0019.

Pure: a :class:`~herhealth_contracts.cycle.CycleExtraction` and ``today`` in,
two things out —

* :func:`prefill` — feature values that count as answered, so she is not
  asked them again;
* :func:`render_cycle_background` — everything else the data shows, for the
  system prompt, framed as unverified background.

Every rule that maps days onto ``allowed_values`` is either mechanical (a
bucket's thresholds are in its name) or quoted from a source already in
``knowledge/``. None is a threshold chosen here. The two numbers that are
ours — :data:`FRESHNESS_DAYS`'s margin and :data:`MIN_CYCLES` — are product
parameters and must not be described as clinically derived.
"""

from __future__ import annotations

import datetime
import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from herhealth_contracts.cycle import (
    CycleDay,
    CycleExtraction,
    FlowLevel,
    PregnancyTestResult,
    TrackerSymptom,
)
from herhealth_contracts.knowledge import KnowledgeBase

__all__ = [
    "ALARMING_PREFILLS",
    "FRESHNESS_DAYS",
    "MIN_CYCLES",
    "POSSIBLE_PREFILLS",
    "CycleSummary",
    "prefill",
    "render_cycle_background",
    "summarize",
]

#: The longest cycle ``features.yaml`` treats as within range — the upper edge
#: of ``21_to_35_days`` — plus a 10-day margin. The 35 is the knowledge base's;
#: the 10 is ours.
FRESHNESS_DAYS = 35 + 10

#: One cycle is not a pattern. A product parameter, not a sourced figure.
MIN_CYCLES = 3

#: How many of her most recent cycles a pattern is read from.
RECENT_CYCLES = 6

#: NHS, quoted in evidence.csv (normal_variation / cycle_length): "A woman's
#: periods are irregular if the gap between them is less than 21 days or more
#: than 35 days."
SHORTEST_REGULAR_CYCLE = 21
LONGEST_REGULAR_CYCLE = 35

#: A day with nothing logged inside a period is still that period: people do
#: not log every day. Two unlogged days in a row end it.
_PERIOD_GAP_DAYS = 2

_BLEEDING = {FlowLevel.LIGHT, FlowLevel.MEDIUM, FlowLevel.HEAVY, FlowLevel.UNSPECIFIED}
_PAIN = {TrackerSymptom.CRAMPS, TrackerSymptom.PELVIC_PAIN}

#: The only values a feature some red flag reads may be pre-filled with: the
#: alarming direction, which can only make an escalation more likely. A
#: benign value there would remove the question that escalates. Never
#: ``pregnant`` (a home test supports "possibly") and never any
#: ``pelvic_pain_severity`` — that is how bad it is today, and it is the
#: clause that keeps most red flags in the consultation.
ALARMING_PREFILLS: Mapping[str, str] = {
    "bleeding_heaviness": "heavy",
    "bleeding_between_periods": "yes",
    "pregnancy_status": "possibly_pregnant",
}

#: Symptom features no red flag reads, and the tracker symptoms that answer
#: "yes" to each. Only ever "yes": not logging something is not the same as
#: not having it.
_SYMPTOM_FEATURES: Mapping[str, frozenset[TrackerSymptom]] = {
    "pain_with_sex": frozenset({TrackerSymptom.PAIN_WITH_SEX}),
    "lower_back_pain": frozenset({TrackerSymptom.LOWER_BACK_PAIN}),
    "bloating_or_digestive_symptoms": frozenset(
        {TrackerSymptom.BLOATING, TrackerSymptom.DIARRHOEA, TrackerSymptom.CONSTIPATION}
    ),
    "low_mood_or_anxiety": frozenset({TrackerSymptom.LOW_MOOD, TrackerSymptom.ANXIETY}),
    "acne_or_oily_skin": frozenset({TrackerSymptom.ACNE}),
}

#: Every (feature, value) :func:`prefill` can ever produce. The red-flag test
#: checks this set, so a new value here is a new value that test examines.
POSSIBLE_PREFILLS: Mapping[str, frozenset[str]] = {
    "cycle_length": frozenset({"under_21_days", "21_to_35_days", "over_35_days"}),
    "cycle_regularity": frozenset({"regular", "irregular"}),
    "period_duration": frozenset({"under_3_days", "3_to_7_days", "over_7_days"}),
    "pelvic_pain_timing": frozenset({"with_periods", "none"}),
    **{feature: frozenset({value}) for feature, value in ALARMING_PREFILLS.items()},
    **{feature: frozenset({"yes"}) for feature in _SYMPTOM_FEATURES},
}


@dataclass(frozen=True)
class Period:
    start: datetime.date
    end: datetime.date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def contains(self, date: datetime.date, *, margin: int = 0) -> bool:
        return (
            self.start - datetime.timedelta(days=margin)
            <= date
            <= self.end + datetime.timedelta(days=margin)
        )


@dataclass(frozen=True)
class CycleSummary:
    """What her days add up to. Plain counts and dates, no scores."""

    source_app: str
    last_entry: datetime.date
    days_since_last_entry: int
    periods: tuple[Period, ...]
    #: Start to start, oldest first, for her most recent cycles only.
    cycle_lengths: tuple[int, ...]
    #: Of periods followed by another — the last one may not have ended.
    period_durations: tuple[int, ...]
    heavy_days_recent: int
    between_period_bleeding_recent: int
    positive_test_recent: datetime.date | None
    negative_test_recent: datetime.date | None
    #: How many days each symptom was logged within the freshness window.
    symptoms_recent: Mapping[TrackerSymptom, int]
    pain_only_during_periods: bool | None
    confirmed_no_period_pain: bool

    @property
    def fresh(self) -> bool:
        return self.days_since_last_entry <= FRESHNESS_DAYS


def _periods(days: Sequence[CycleDay]) -> tuple[Period, ...]:
    bleeding = [day.date for day in days if day.flow in _BLEEDING]
    periods: list[Period] = []
    for date in bleeding:
        if periods and (date - periods[-1].end).days <= _PERIOD_GAP_DAYS:
            periods[-1] = Period(periods[-1].start, date)
        else:
            periods.append(Period(date, date))
    return tuple(periods)


def summarize(
    extraction: CycleExtraction,
    *,
    today: datetime.date,
    confirmed_no_period_pain: bool = False,
) -> CycleSummary:
    days = extraction.days
    periods = _periods(days)
    starts = [period.start for period in periods]
    lengths = tuple((later - earlier).days for earlier, later in itertools.pairwise(starts))
    durations = tuple(period.days for period in periods[:-1])
    window_start = today - datetime.timedelta(days=FRESHNESS_DAYS)
    recent = [day for day in days if day.date >= window_start]

    def inside_a_period(date: datetime.date) -> bool:
        return any(period.contains(date, margin=1) for period in periods)

    between = sum(
        1
        for day in recent
        if TrackerSymptom.BLEEDING_BETWEEN_PERIODS in day.symptoms
        or (day.flow is FlowLevel.SPOTTING and not inside_a_period(day.date))
    )
    tests = [(day.date, day.pregnancy_test) for day in recent if day.pregnancy_test]
    pain_days = [day.date for day in days if day.symptoms & _PAIN]
    symptom_counts: dict[TrackerSymptom, int] = {}
    for day in recent:
        for symptom in day.symptoms:
            symptom_counts[symptom] = symptom_counts.get(symptom, 0) + 1

    return CycleSummary(
        source_app=extraction.source_app,
        last_entry=days[-1].date,
        days_since_last_entry=(today - days[-1].date).days,
        periods=periods,
        cycle_lengths=lengths[-RECENT_CYCLES:],
        period_durations=durations[-RECENT_CYCLES:],
        heavy_days_recent=sum(1 for day in recent if day.flow is FlowLevel.HEAVY),
        between_period_bleeding_recent=between,
        positive_test_recent=max(
            (d for d, r in tests if r is PregnancyTestResult.POSITIVE), default=None
        ),
        negative_test_recent=max(
            (d for d, r in tests if r is PregnancyTestResult.NEGATIVE), default=None
        ),
        symptoms_recent=symptom_counts,
        pain_only_during_periods=(
            all(inside_a_period(date) for date in pain_days) if pain_days else None
        ),
        confirmed_no_period_pain=confirmed_no_period_pain,
    )


def _one_bucket(values: Sequence[int], buckets: Sequence[tuple[str, int, int]]) -> str | None:
    """The bucket every value falls in, or ``None`` if they span more than one."""
    found = {name for value in values for name, low, high in buckets if low <= value <= high}
    return found.pop() if len(found) == 1 else None


_CYCLE_BUCKETS = (
    ("under_21_days", 0, SHORTEST_REGULAR_CYCLE - 1),
    ("21_to_35_days", SHORTEST_REGULAR_CYCLE, LONGEST_REGULAR_CYCLE),
    ("over_35_days", LONGEST_REGULAR_CYCLE + 1, 10_000),
)
_DURATION_BUCKETS = (
    ("under_3_days", 0, 2),
    ("3_to_7_days", 3, 7),
    ("over_7_days", 8, 10_000),
)


def prefill(summary: CycleSummary, base: KnowledgeBase) -> dict[str, str]:
    """Feature values her data answers, or nothing at all when it is stale.

    Anything she says in the consultation overrides these; the caller merges
    them beneath her own answers, as it already does the profile age band.
    """
    if not summary.fresh:
        return {}
    values: dict[str, str] = {}

    if len(summary.cycle_lengths) >= MIN_CYCLES:
        length = _one_bucket(summary.cycle_lengths, _CYCLE_BUCKETS)
        if length is not None:
            values["cycle_length"] = length
        # NHS: irregular if any gap is under 21 or over 35 days; the
        # complement is regular. ``varies_widely`` has no source and is never
        # produced.
        outside = any(
            not SHORTEST_REGULAR_CYCLE <= n <= LONGEST_REGULAR_CYCLE for n in summary.cycle_lengths
        )
        values["cycle_regularity"] = "irregular" if outside else "regular"

    if len(summary.period_durations) >= MIN_CYCLES:
        duration = _one_bucket(summary.period_durations, _DURATION_BUCKETS)
        if duration is not None:
            values["period_duration"] = duration

    if summary.pain_only_during_periods and summary.symptoms_recent.keys() & _PAIN:
        values["pelvic_pain_timing"] = "with_periods"
    elif summary.confirmed_no_period_pain and summary.pain_only_during_periods is None:
        values["pelvic_pain_timing"] = "none"

    if summary.heavy_days_recent:
        values["bleeding_heaviness"] = ALARMING_PREFILLS["bleeding_heaviness"]
    if summary.between_period_bleeding_recent:
        values["bleeding_between_periods"] = ALARMING_PREFILLS["bleeding_between_periods"]
    if summary.positive_test_recent is not None:
        values["pregnancy_status"] = ALARMING_PREFILLS["pregnancy_status"]

    for feature, symptoms in _SYMPTOM_FEATURES.items():
        if summary.symptoms_recent.keys() & symptoms:
            values[feature] = "yes"

    return _guarded(values, base)


def _guarded(values: Mapping[str, str], base: KnowledgeBase) -> dict[str, str]:
    """The red-flag rule and the closed vocabulary, enforced on the output
    rather than trusted from the code above it.

    Read from ``red_flags.yaml`` at call time, so a rule added later that
    reads one of these features is covered without anyone remembering to list
    it here.
    """
    allowed = {feature.id: {str(v) for v in feature.allowed_values} for feature in base.features}
    read_by_red_flags = {clause.feature_id for rule in base.red_flags for clause in rule.all_of}
    return {
        feature: value
        for feature, value in values.items()
        if value in allowed.get(feature, ())
        and (feature not in read_by_red_flags or ALARMING_PREFILLS.get(feature) == value)
    }


def render_cycle_background(summary: CycleSummary, prefilled: Mapping[str, str]) -> str:
    """The block appended to the profile background in the system prompt.

    Counts and dates only — nothing from her file appears as words, because
    the extraction that feeds this has no field that could hold any.
    """
    lines = [
        f"Cycle data she imported from her tracking app ({summary.source_app}), "
        "not from this conversation:",
        f"- Last entry {summary.last_entry.isoformat()}, {summary.days_since_last_entry} days ago.",
    ]
    if summary.cycle_lengths:
        lengths = ", ".join(str(n) for n in summary.cycle_lengths)
        lines.append(f"- Her most recent cycle lengths, in days: {lengths}.")
    if summary.period_durations:
        durations = ", ".join(str(n) for n in summary.period_durations)
        lines.append(f"- How long her recent periods lasted, in days: {durations}.")
    if summary.heavy_days_recent:
        lines.append(f"- Heavy flow logged on {summary.heavy_days_recent} recent days.")
    if summary.between_period_bleeding_recent:
        lines.append(
            f"- Bleeding between periods logged on {summary.between_period_bleeding_recent} "
            "recent days."
        )
    if summary.positive_test_recent:
        lines.append(f"- A positive pregnancy test logged on {summary.positive_test_recent}.")
    if summary.negative_test_recent:
        lines.append(f"- A negative pregnancy test logged on {summary.negative_test_recent}.")
    for symptom, count in sorted(summary.symptoms_recent.items()):
        lines.append(f"- {symptom.value.replace('_', ' ')} logged on {count} recent days.")

    if not summary.fresh:
        lines.append(
            f"This data is out of date (over {FRESHNESS_DAYS} days old). Nothing in it "
            "is an answer: ask her as you normally would, and do not read the gap "
            "since her last entry as her periods having stopped — she may simply "
            "have stopped logging."
        )
    elif prefilled:
        answered = ", ".join(f"{feature}={value}" for feature, value in sorted(prefilled.items()))
        lines.append(
            f"Already answered from this data, so do not ask them again: {answered}. "
            "If she says anything different today, what she says wins."
        )
    lines.append(
        "Anything else above is unverified background, NOT an answer: never "
        "conclude from it alone and never let it fire a warning sign on its own. "
        "Where it bears on a question you need to ask — especially bleeding, "
        "pregnancy or pain — ask one short question confirming it instead of "
        "asking from scratch. Pain severity is always asked about today."
    )
    return "\n".join(lines)
