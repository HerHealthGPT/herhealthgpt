"""The contract for cycle data extracted from a tracking app's export.

One shape for every route in: a code converter for a known format and the
base model reading a format nobody has written a converter for both produce a
:class:`CycleExtraction`, and for the second route the model's JSON reply is
validated against it, the same way a triage decision is. It is also what
the client sends back when she confirms the preview, so the server
re-validates the exact thing she accepted rather than trusting it. See ADR
0019.

**Daily logs, not feature values.** A tracker records days — heavy flow on
the 3rd, cramps on the 2nd. ``features.yaml`` describes a pattern —
``cycle_length: over_35_days``. Storing a day as a feature value would make a
row mean something its feature does not, so this module has a vocabulary of
its own for what a tracker logs, and turning a run of days into feature
values happens in ``herhealth_backend.triage``, where the knowledge base is.

**Nothing here can carry text from the file.** Every field is an enum, a
date, or an ``Identifier``-shaped token. That is the whole
defence against a file written to look like instructions: whatever it
contains, nothing representable here reaches the reasoning model's prompt as
words. Free-text notes, sexual activity, contraception, weight, location,
heart rate and sleep have no field, so an extractor that finds them has nowhere to put
them.

**What this does not check**, because it needs a clock or a knowledge base
this package does not have: that no date is in the future, how far back the
data reaches, and whether a log is recent enough to pre-fill anything. Those
are the backend's, with ``today`` injected, exactly as ``triage.age_bands``
does it.
"""

from __future__ import annotations

import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from herhealth_contracts.knowledge import Identifier

__all__ = [
    "CycleDay",
    "CycleExtraction",
    "ExtractionMethod",
    "FlowLevel",
    "PainIntensity",
    "PregnancyTestResult",
    "TrackerSymptom",
]

#: Roughly three years of daily logs. Enough for any cycle-pattern question the
#: knowledge base can ask, and a bound on what one upload can make the server
#: hold. A longer export is trimmed to its most recent days by the extractor,
#: not refused, because the recent end is the part that matters.
MAX_DAYS = 1100

#: The app the export came from, as a token rather than as text from the
#: file. "Any application" means this cannot be an enum, but it still cannot
#: carry a sentence.
SourceApp = Annotated[Identifier, StringConstraints(max_length=40)]


class ExtractionMethod(StrEnum):
    """How the export was read. Recorded because the two routes are not
    equally trustworthy: a converter is code that was reviewed against a real
    sample, and model extraction is unmeasured until it is run against real
    reports (ADR 0019's risk register)."""

    CONVERTER = "converter"
    MODEL = "model"


class FlowLevel(StrEnum):
    """Bleeding logged on a day, in the levels trackers commonly offer.

    ``none`` is an explicit log of no bleeding, which is information; a day
    with nothing logged is simply absent from the extraction, which is not.
    ``unspecified`` is bleeding the app recorded without a level.
    """

    NONE = "none"
    SPOTTING = "spotting"
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"
    UNSPECIFIED = "unspecified"


class PainIntensity(StrEnum):
    """Only when the app itself records an intensity. Never inferred."""

    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"


class PregnancyTestResult(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class TrackerSymptom(StrEnum):
    """Symptoms a tracker logs that some ``features.yaml`` feature can read.

    Closed to what the knowledge base can use: a symptom no feature reads
    cannot change a decision, so keeping it would cost privacy for nothing.
    Headache and breast tenderness, which most trackers offer, are absent for
    that reason.

    ``unusual_discharge`` is set only when the app's own label says atypical
    or unusual. A tracker's ordinary discharge types describe the normal
    cycle, and reading one as abnormal would be a judgement this project does
    not make.
    """

    CRAMPS = "cramps"
    PELVIC_PAIN = "pelvic_pain"
    PAIN_WITH_SEX = "pain_with_sex"
    LOWER_BACK_PAIN = "lower_back_pain"
    BLOATING = "bloating"
    NAUSEA = "nausea"
    VOMITING = "vomiting"
    DIARRHOEA = "diarrhoea"
    CONSTIPATION = "constipation"
    FATIGUE = "fatigue"
    LOW_MOOD = "low_mood"
    ANXIETY = "anxiety"
    ACNE = "acne"
    UNUSUAL_DISCHARGE = "unusual_discharge"
    BLEEDING_BETWEEN_PERIODS = "bleeding_between_periods"


class CycleDay(BaseModel):
    """Everything logged on one day that this system can use."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    date: datetime.date
    flow: FlowLevel | None = None
    symptoms: frozenset[TrackerSymptom] = frozenset()
    pain_intensity: PainIntensity | None = None
    pregnancy_test: PregnancyTestResult | None = None

    @model_validator(mode="after")
    def _logs_something(self) -> Self:
        # A day with nothing on it is the same as an absent day, and keeping
        # it would let an extractor pad the count of days she logged.
        if (
            self.flow is None
            and not self.symptoms
            and self.pain_intensity is None
            and self.pregnancy_test is None
        ):
            raise ValueError(f"{self.date} logs nothing — omit the day instead")
        return self


class CycleExtraction(BaseModel):
    """What was found in one export, before she confirms it and after."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_app: SourceApp = "unknown"
    method: ExtractionMethod
    days: tuple[CycleDay, ...] = Field(max_length=MAX_DAYS)

    @model_validator(mode="before")
    @classmethod
    def _sort_days(cls, data: object) -> object:
        """Days in date order, whatever order the export used, so every
        consumer can walk cycles front to back without sorting first."""
        if not isinstance(data, dict):
            return data
        days = data.get("days")
        if isinstance(days, list | tuple) and all(isinstance(day, dict) for day in days):
            return {**data, "days": sorted(days, key=lambda day: str(day.get("date", "")))}
        return data

    @model_validator(mode="after")
    def _one_entry_per_day(self) -> Self:
        # Two entries for one day would be two answers to "what did she log
        # that day", and nothing would say which is right. Merging belongs in
        # the extractor, which knows the format.
        dates = [day.date for day in self.days]
        duplicated = sorted({d for d in dates if dates.count(d) > 1})
        if duplicated:
            listed = ", ".join(str(d) for d in duplicated[:5])
            raise ValueError(f"more than one entry for {listed} — merge each day into one")
        if not self.days:
            raise ValueError("no usable days were found in this export")
        return self
