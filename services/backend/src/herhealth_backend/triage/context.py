"""The grounding a turn is built from, assembled by code rather than by cosine.

This is the retrieval fix. It sits beside ``agent.py``'s ``render_red_flags``
and ``clients.py``'s ``_render_context``, and replaces what both of them do
with something derived from the knowledge base's own structure.

**Why it exists.** ``evidence.csv`` is a keyed grid: 140 rows, each addressed by
``(condition_id, feature_id, value)``. Until now the only way a row reached the
model was by winning a cosine-similarity contest against 3,600 unstructured
sentences in the same index, which it usually lost — 93 of the 140 rows are
servable at all after the licence filter, and they are 2.5% of the corpus. A
similarity search over rows you hold the keys to is strictly worse than a join,
so this module joins.

``red_flags.yaml`` had the mirror problem in the other direction. Every rule was
injected every turn, but only as ``id``/``action``/``label``/``source_quote`` —
the ``all_of`` clauses, which are the actual trigger, were dropped at render
time. A model shown "Pelvic pain with faintness" cannot know the rule needs only
``pelvic_pain_severity != none``, and reads the label as requiring severe pain.
That is an under-triage vector in the dominant failure mode. This module keeps
the clauses and reports, per rule, exactly which are satisfied and which are
outstanding.

**What this module does not do.** It does not decide. There is no ask-or-
conclude rule here, no threshold, no score, no action code chosen. Every
function is a projection of the knowledge base through what the user has
actually said. ``TurnContext`` is a *description of the position*, and
:class:`Askable` is a ranked menu with reasons attached, not an instruction.
The reasoning model still chooses, which is what
docs/adr/0011-controller-free-triage.md requires — it simply now chooses while
able to see what ``should_stop`` could see.

Clause evaluation mirrors ``engine.TriageEngine._clause_matches`` deliberately
and is duplicated rather than imported: ``engine.py`` is the outgoing
controller (ADR 0011), and this module must outlive it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from herhealth_contracts.knowledge import (
    ActionCode,
    Clause,
    ComparisonOp,
    Condition,
    EvidenceRow,
    EvidenceStrength,
    Feature,
    KnowledgeBase,
    RedFlagRule,
)
from herhealth_contracts.retrieval import RetrievedPassage

__all__ = [
    "Askable",
    "ConditionEvidence",
    "DEFAULT_PROBE_LANGUAGE",
    "RuleStatus",
    "TurnContext",
    "assess_rules",
    "build_turn_context",
    "clause_matches",
    "condition_support",
    "discrimination",
    "join_evidence",
    "live_conditions",
    "rank_askable",
    "render_topic_brief",
    "render_turn_context",
    "separation",
    "topic_conditions",
]

DEFAULT_PROBE_LANGUAGE = "en"

#: Strengths that raise a condition; every other strength lowers it.
_SUPPORTING = {EvidenceStrength.STRONG_SUPPORT, EvidenceStrength.WEAK_SUPPORT}

#: Severity order, used to rank rules and to decide which fired rule wins.
#: Mirrors ``actions.yaml``'s ``severity`` rather than restating a judgement.
_SEVERITY: dict[ActionCode, int] = {
    ActionCode.SELF_CARE: 0,
    ActionCode.ROUTINE_APPOINTMENT: 1,
    ActionCode.URGENT_SAME_DAY: 2,
    ActionCode.EMERGENCY: 3,
}


def clause_matches(clause: Clause, given: Mapping[str, str]) -> bool:
    """Whether one red-flag clause is satisfied by what she has actually said.

    An unasked or unknown feature never satisfies a clause. For a conjunction
    that is the conservative direction — a rule fires only on real answers —
    and it is what makes "outstanding" in :class:`RuleStatus` mean "still
    unknown" rather than "assumed absent".
    """
    actual = given.get(clause.feature_id)
    if actual is None:
        return False

    match clause.op:
        case ComparisonOp.EQUALS:
            return actual == clause.value
        case ComparisonOp.NOT_EQUALS:
            return actual != clause.value
        case ComparisonOp.IN:
            return isinstance(clause.value, tuple) and actual in clause.value
        case ComparisonOp.GTE | ComparisonOp.LTE:
            # Numeric comparison on a categorical answer is not meaningful. No
            # feature needs it today; refusing to match beats inventing an
            # ordering over strings.
            return False
    return False


@dataclass(frozen=True, slots=True)
class RuleStatus:
    """One red-flag rule, measured against what she has said so far."""

    rule: RedFlagRule
    matched: tuple[Clause, ...]
    outstanding: tuple[Clause, ...]

    @property
    def fired(self) -> bool:
        return not self.outstanding

    @property
    def distance(self) -> int:
        """How many more answers would complete this rule. 0 means it fired."""
        return len(self.outstanding)

    @property
    def severity(self) -> int:
        return _SEVERITY[self.rule.action]

    @property
    def engaged(self) -> bool:
        """At least one clause already matches.

        Scopes attention to escalations *of the presentation in front of us*.
        Without it every unrelated single-clause rule would look one answer
        away from the moment the consultation starts, and the ranking below
        would chase all of them.
        """
        return bool(self.matched)


def assess_rules(base: KnowledgeBase, given: Mapping[str, str]) -> tuple[RuleStatus, ...]:
    """Every red-flag rule, with its clauses resolved against ``given``.

    Returned in a stable order — fired first, then nearest, then most severe,
    then file order — so the rendered block does not reshuffle between turns
    for reasons the reader cannot see.
    """
    statuses = [
        RuleStatus(
            rule=rule,
            matched=tuple(c for c in rule.all_of if clause_matches(c, given)),
            outstanding=tuple(c for c in rule.all_of if not clause_matches(c, given)),
        )
        for rule in base.red_flags
    ]
    order = {rule.id: i for i, rule in enumerate(base.red_flags)}
    return tuple(sorted(statuses, key=lambda s: (s.distance, -s.severity, order[s.rule.id])))


def fired_rule(statuses: Sequence[RuleStatus]) -> RuleStatus | None:
    """The MOST SEVERE fired rule, never the first in file order.

    Two rules can match the same answers — ``severe_pelvic_pain`` needs only
    severity, ``sudden_severe_pelvic_pain`` needs severity and sudden onset —
    and taking whichever came first in the YAML would make an escalation depend
    on how the file was arranged.
    """
    fired = [s for s in statuses if s.fired]
    if not fired:
        return None
    return max(fired, key=lambda s: s.severity)


@dataclass(frozen=True, slots=True)
class ConditionEvidence:
    """Every evidence row that her answers actually key into, for one condition.

    This is channel one: a join, not a search. ``rows`` are the cells of the
    sparse grid addressed by ``(feature_id, value)`` pairs she has answered,
    so the set is complete by construction — no row that applies can be missed
    because a different sentence scored higher.
    """

    condition: Condition
    rows: tuple[EvidenceRow, ...]

    @property
    def supporting(self) -> tuple[EvidenceRow, ...]:
        return tuple(
            r
            for r in self.rows
            if r.strength in {EvidenceStrength.STRONG_SUPPORT, EvidenceStrength.WEAK_SUPPORT}
        )

    @property
    def against(self) -> tuple[EvidenceRow, ...]:
        return tuple(
            r
            for r in self.rows
            if r.strength in {EvidenceStrength.ARGUES_AGAINST, EvidenceStrength.RULES_OUT}
        )

    @property
    def strong_count(self) -> int:
        return sum(1 for r in self.rows if r.strength is EvidenceStrength.STRONG_SUPPORT)


def join_evidence(base: KnowledgeBase, given: Mapping[str, str]) -> tuple[ConditionEvidence, ...]:
    """Channel one. Every row keyed by an answer she has given, grouped by condition.

    Ordering is by strong-support count, then total rows, then condition id —
    a presentation order, not a ranking of likelihood. **No score is computed
    here.** Turning counts into a plausibility is what ``weights.yaml`` and the
    retired engine did, and ADR 0011 moved that judgement to the model; this
    function's job is to put the right rows in front of it, completely and in a
    stable order.
    """
    conditions = base.conditions_by_id
    by_condition: dict[str, list[EvidenceRow]] = {}

    for row in base.evidence:
        if given.get(row.feature_id) == row.value:
            by_condition.setdefault(row.condition_id, []).append(row)

    grouped = [
        ConditionEvidence(
            condition=conditions[condition_id],
            # Stable within a condition: strongest first, then by feature id.
            rows=tuple(
                sorted(
                    rows,
                    key=lambda r: (
                        r.strength is not EvidenceStrength.STRONG_SUPPORT,
                        r.feature_id,
                    ),
                )
            ),
        )
        for condition_id, rows in by_condition.items()
        if condition_id in conditions
    ]
    return tuple(sorted(grouped, key=lambda g: (-g.strong_count, -len(g.rows), g.condition.id)))


def live_conditions(evidence: Sequence[ConditionEvidence]) -> set[str]:
    """The conditions her answers actually support, as ids.

    "Live" in the sense the retired engine used: the differential still in
    play. Conditions reached only by an ``argues_against`` row are excluded —
    they were touched by the join but pushed down, not up.
    """
    return {group.condition.id for group in evidence if group.supporting}


def condition_support(
    evidence: Sequence[ConditionEvidence], log_odds: Mapping[str, float]
) -> dict[str, float]:
    """How strongly her answers back each live condition, as a share of the total.

    Membership of the live set is not enough, and treating it as enough is
    what produced visibly silly questions. After "my periods are all over the
    place", seven conditions are live — but ``primary_ovarian_insufficiency``,
    ``pcos`` and ``perimenopause`` rest on ``strong_support`` while
    ``pelvic_inflammatory_disease``, ``ovarian_cyst``, ``infertility`` and
    ``hypothyroidism`` each rest on a single ``weak_support`` row. Counting
    all seven equally made ``fever`` — a question about PID — the top-ranked
    follow-up to a menstrual complaint.

    Shares rather than raw sums so the number means "how much of the current
    differential is this condition", which is what the ranking needs.
    """
    raw: dict[str, float] = {}
    for group in evidence:
        total = sum(
            (1.0 if row.strength in _SUPPORTING else -1.0)
            * abs(log_odds.get(row.strength.value, 0.0))
            for row in group.rows
        )
        if total > 0:
            raw[group.condition.id] = total
    grand = sum(raw.values())
    if grand <= 0:
        return {}
    return {condition: value / grand for condition, value in raw.items()}


def discrimination(
    base: KnowledgeBase,
    feature_id: str,
    *,
    support: Mapping[str, float],
    log_odds: Mapping[str, float],
) -> float:
    """How much one answer to this feature could change which condition leads.

    The counterpart to :func:`separation`, and the two must not be confused.
    ``separation`` is a static property of the grid — an authoring metric, the
    same on turn one and turn six. This is a property of *this consultation*.

    **Measured as spread, not mass, and that distinction is the whole fix.**
    The first version summed the absolute weight of every row touching a live
    condition. That rewards a feature for *touching many conditions* rather
    than for *telling them apart*, which is the same "support, not
    discrimination" flaw the evidence grid itself has. Observed live
    2026-09-11: asked only about irregular periods, the system offered
    "have you been trying to become pregnant without success?" — burden 3, the
    most sensitive tier — as its opening question, because
    ``difficulty_conceiving`` carries rows for nine conditions. Eight of those
    are ``weak_support`` pointing the same way, so answering it lifts the whole
    differential and separates nothing.

    Instead, for each value the feature could take, weight each condition's
    delta by how much of the current differential that condition holds, and
    score the value by how far the resulting leader pulls clear of the runner
    up. The best value wins. A feature that raises everything uniformly moves
    no one clear and scores near zero; a feature that singles one plausible
    condition out scores high, which is what makes the next question follow
    from what she just said.

    **This reads ``weights.yaml`` inside a module documented as computing no
    score, and that is a real softening of the boundary rather than an
    oversight.** What it produces ranks *questions*; it is never attached to a
    condition, never accumulated across turns, and never turned into a
    plausibility or an action code. Those remain the model's, per ADR 0011.
    """
    if not support:
        return 0.0

    by_value: dict[str, dict[str, float]] = {}
    for row in base.evidence:
        if row.feature_id != feature_id or row.condition_id not in support:
            continue
        signed = (1.0 if row.strength in _SUPPORTING else -1.0) * abs(
            log_odds.get(row.strength.value, 0.0)
        )
        by_value.setdefault(row.value, {})[row.condition_id] = signed

    best = 0.0
    for deltas in by_value.values():
        weighted = sorted(
            (deltas.get(condition, 0.0) * share for condition, share in support.items()),
            reverse=True,
        )
        if len(weighted) > 1:
            best = max(best, weighted[0] - weighted[1])
    return best


def separation(base: KnowledgeBase, feature_id: str) -> int:
    """How many distinct ``(condition, value)`` pairs this feature splits.

    The measure of whether a question is worth a turn. ``abnormal_discharge``
    supports bacterial vaginosis, thrush and STI at the same value ``yes``, so
    it separates nothing and costs a turn; ``discharge_smell`` points ``fishy``
    at one condition and ``none`` at another, so it does real work.

    Counted as distinct pairs rather than distinct conditions because a feature
    that distinguishes two conditions *by value* is exactly what the grid is
    short of — see the batch 24 note in ``services/data/evidence_batches/``.
    """
    return len({(r.condition_id, r.value) for r in base.evidence if r.feature_id == feature_id})


@dataclass(frozen=True, slots=True)
class Askable:
    """One feature she could be asked next, with its authored question and why.

    ``reasons`` is the whole point. A menu of 39 ids tells the model nothing;
    "answering this resolves 2 EMERGENCY warning signs" tells it what the
    question is *for*, which is the information ``should_stop`` rule 1 used to
    act on in code and the model has never been shown.
    """

    feature: Feature
    probe: str
    allowed_values: tuple[str, ...]
    resolves: tuple[RuleStatus, ...]
    separation: int

    #: Live-weighted discrimination over the conditions still in play. Falls
    #: as the differential narrows, unlike ``separation``.
    discrimination: float = 0.0

    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def top_severity(self) -> int:
        return max((s.severity for s in self.resolves), default=-1)

    @property
    def value(self) -> float:
        """Discrimination per unit of burden — what one question is worth.

        A ratio, not a lexicographic tier, and that distinction is the whole
        point. Sorting by burden first means every burden-1 question beats
        every burden-2 question no matter how much better the latter is, so a
        near-useless cheap question outranks a decisive slightly costlier one.
        Measured on a real PCOS-shaped case: burden-first surfaced
        ``lower_back_pain`` and ``period_duration``, while the ratio surfaces
        ``difficulty_conceiving`` (burden 3, discrimination 4.4) — which is
        the question that actually separates that differential.

        Burden is only rated 1-3 in practice despite the schema allowing 1-5,
        so it is a gentle divisor rather than a veto. That is the intended
        behaviour: burden is a price, not a prohibition.
        """
        return self.discrimination / self.feature.burden


def rank_askable(
    base: KnowledgeBase,
    given: Mapping[str, str],
    asked: Iterable[str],
    statuses: Sequence[RuleStatus],
    *,
    evidence: Sequence[ConditionEvidence] = (),
    language: str = DEFAULT_PROBE_LANGUAGE,
    limit: int = 8,
) -> tuple[Askable, ...]:
    """The features worth asking about, most useful first.

    **Two tiers, ranked on different things, because they are different jobs.**

    *Screening* — features that would complete a warning sign one answer away.
    Ranked by that sign's severity, then how many signs one answer settles,
    then burden. Severity first is what keeps it safe; coverage next is what
    keeps it short, since one question can close several rules; burden last so
    the cheapest of otherwise-equal probes wins. Discrimination is deliberately
    not consulted here — how well a feature splits the differential says
    nothing about whether she is having an emergency.

    *Differential* — everything else, ranked by :attr:`Askable.value`,
    discrimination per unit of burden, recomputed each turn against the
    conditions still live.

    Two properties of that second tier are the fix for a measured defect. It is
    a **ratio**, so a decisive costlier question can outrank a near-useless
    cheap one; sorting by burden lexicographically meant it never could. And
    the numerator is **live**, so the ranking narrows as the differential
    narrows; the previous version used static ``separation``, which is
    identical on turn one and turn six and made the sequence of questions look
    disconnected from the answers — because it was.

    A feature already asked is excluded even if its answer came back
    ``unknown``: the answer is in, and asking again reads as not having
    listened.
    """
    asked_ids = set(asked) | set(given)
    features = base.features_by_id
    log_odds = {strength.value: value for strength, value in base.weights.log_odds.items()}
    support = condition_support(evidence, log_odds)
    if not support:
        # Nothing raised yet — every condition is equally in play, which is the
        # same fallback ``engine._separation`` used. Without it the opening
        # turn would score every question at zero and rank on id alone.
        conditions = base.conditions_by_id
        support = {condition: 1.0 / len(conditions) for condition in conditions}

    resolves_by_feature: dict[str, list[RuleStatus]] = {}
    for status in statuses:
        # Only rules a SINGLE answer would complete, and only ones already
        # engaged by something she said. Chasing rules two answers away does
        # not terminate tidily — every probe here either fires its rule or
        # kills it.
        if status.distance != 1 or not status.engaged:
            continue
        clause = status.outstanding[0]
        if clause.feature_id in asked_ids:
            continue
        resolves_by_feature.setdefault(clause.feature_id, []).append(status)

    candidates: list[Askable] = []
    for feature_id, feature in features.items():
        if feature_id in asked_ids:
            continue
        resolves = tuple(resolves_by_feature.get(feature_id, ()))
        sep = separation(base, feature_id)
        if not resolves and sep == 0:
            # Neither settles a warning sign nor splits the differential. It is
            # a question whose answer changes nothing — the burden without the
            # benefit. Red-flag-only features reach this branch only when no
            # rule is engaged, which is correct: they exist to fire rules.
            continue

        power = discrimination(base, feature_id, support=support, log_odds=log_odds)

        reasons: list[str] = []
        for status in sorted(resolves, key=lambda s: -s.severity):
            reasons.append(f"one answer completes {status.rule.id} ({status.rule.action.value})")
        if power:
            reasons.append(
                f"separates the {len(support)} conditions still in play "
                f"(discrimination {power:.2f} at burden {feature.burden})"
            )

        candidates.append(
            Askable(
                feature=feature,
                probe=feature.probe.get(language) or feature.probe[DEFAULT_PROBE_LANGUAGE],
                allowed_values=feature.allowed_values,
                resolves=resolves,
                separation=sep,
                discrimination=power,
                reasons=tuple(reasons),
            )
        )

    candidates.sort(
        key=lambda a: (
            # Screening first: top_severity is -1 with no rule to settle, so
            # every screening candidate sorts ahead of every differential one.
            -a.top_severity,
            -len(a.resolves),
            # Burden separates otherwise-equal probes while screening. Zero for
            # the differential tier, where the ratio below already prices it.
            a.feature.burden if a.resolves else 0,
            -a.value,
            a.feature.id,
        )
    )
    return tuple(candidates[:limit])


@dataclass(frozen=True, slots=True)
class TurnContext:
    """Everything this turn is grounded in, and where each part came from.

    **A feature is in one of three states, and conflating any two of them
    breaks something.**

    * *Unasked* — not in ``asked``, not in ``given``. Offerable as a question;
      any rule waiting on it is genuinely one answer away.
    * *Pending* — in ``asked``, not yet in ``given``. The question went out and
      her reply has not been read into the case vector yet. Must NOT be offered
      again (she was just asked), and must STILL count as one answer away,
      because the answer that completes the rule may be in the very message
      being read this turn.
    * *Answered* — in ``given``. A rule whose outstanding clause sits on an
      answered feature is dead, not near.

    Getting this wrong is not cosmetic. Basing ``near_misses`` on ``asked``
    rather than ``given`` hides a rule during exactly the turn it is about to
    fire: the model asks "do you feel faint", and on the turn it reads "yes"
    the block has already stopped telling it that answer completes an
    EMERGENCY rule. That is an under-triage vector introduced by the fix for a
    different under-triage vector, which is why both directions have tests.
    """

    #: The case vector: what she has answered, mapped onto allowed_values.
    given: Mapping[str, str]

    #: Features already put to her. Used only to stop re-offering a question —
    #: never to decide whether a rule is live. See the three states above.
    asked: frozenset[str]

    #: The feature the last question asked about, still awaiting a value: the
    #: one *pending* feature, if there is one. Named separately because the
    #: model has to be told which feature her incoming message answers.
    #:
    #: Observed live 2026-09-10, and the reason this field exists: shown only
    #: "WHAT SHE HAS ANSWERED SO FAR", the model treated `observed` as a place
    #: to echo that list back rather than to report what it had just read. It
    #: returned `{"cycle_regularity": "irregular"}` on a turn whose incoming
    #: message was "large clots, very heavy bleeding", so `bleeding_heaviness`
    #: — a clause of an EMERGENCY rule — was never recorded at all.
    #:
    #: Carries the whole :class:`Feature`, not just its id, because the line
    #: rendered from it has to name the value vocabulary her answer must land
    #: in, and this dataclass holds no knowledge base to look one up in.
    pending: Feature | None

    statuses: tuple[RuleStatus, ...]
    fired: RuleStatus | None
    evidence: tuple[ConditionEvidence, ...]
    askable: tuple[Askable, ...]
    prose: tuple[RetrievedPassage, ...]

    @property
    def near_misses(self) -> tuple[RuleStatus, ...]:
        """Rules a single *unasked* answer would complete. The escalation screen.

        The "unasked" qualifier is what makes the screen terminate, and leaving
        it out is a real error rather than a cosmetic one. Once
        ``bleeding_heaviness`` comes back ``moderate``,
        ``pelvic_pain_with_heavy_bleeding`` still has exactly one outstanding
        clause — but that clause can never be satisfied now, because the answer
        is in. Reporting it as "one answer away" would show the model six live
        emergency rules where five are live and one is dead, and would keep
        showing it for the rest of the consultation.
        """
        return tuple(
            s
            for s in self.statuses
            if s.distance == 1 and s.engaged and s.outstanding[0].feature_id not in self.given
        )

    @property
    def refuted(self) -> tuple[RuleStatus, ...]:
        """Rules killed by an answer: one clause outstanding, on a feature she
        has already answered with a value that does not satisfy it. Every probe
        either fires its rule or lands here, which is why the screen finishes.
        """
        return tuple(
            s
            for s in self.statuses
            if s.distance >= 1 and s.engaged and s.outstanding[0].feature_id in self.given
        )


def build_turn_context(
    base: KnowledgeBase,
    *,
    given: Mapping[str, str],
    asked: Iterable[str] = (),
    prose: Sequence[RetrievedPassage] = (),
    language: str = DEFAULT_PROBE_LANGUAGE,
    askable_limit: int = 8,
) -> TurnContext:
    """Assemble one turn's grounding. Pure: no network, no model, no index.

    ``asked`` is in the order the questions went out, so the pending feature
    is the last one that has not come back with a value.
    """
    statuses = assess_rules(base, given)
    evidence = join_evidence(base, given)
    asked_order = list(asked)
    pending_id = next(
        (feature_id for feature_id in reversed(asked_order) if feature_id not in given),
        None,
    )
    pending = base.features_by_id.get(pending_id) if pending_id is not None else None
    return TurnContext(
        given=dict(given),
        asked=frozenset(asked_order) | frozenset(given),
        pending=pending,
        statuses=statuses,
        fired=fired_rule(statuses),
        evidence=evidence,
        askable=rank_askable(
            base,
            given,
            asked,
            statuses,
            evidence=evidence,
            language=language,
            limit=askable_limit,
        ),
        prose=tuple(prose),
    )


#: Label fragments too generic to identify a topic by. ``normal_variation``'s
#: label is "Normal variation", and matching the bare word "normal" would pull
#: a brief into half the consultations in the corpus.
_UNUSABLE_TOPIC_TERMS = frozenset({"normal", "variation", "normal variation"})

#: An acronym in a condition's label, e.g. "(PCOS)" or "(PID)". These are what
#: a user actually types — "what is PCOS?" never contains the authored label
#: "Polyendocrine metabolic ovarian syndrome" — so they are the highest-value
#: terms to match on, and the only ones short enough to need word boundaries.
_LABEL_ACRONYM = re.compile(r"\(([A-Z][A-Za-z0-9]{1,9})\)")


def _topic_terms(condition: Condition) -> set[str]:
    """Every string that should be taken to name this condition."""
    terms = {condition.id.replace("_", " ")}
    label = condition.label
    # The label up to its first parenthesis: "Pelvic inflammatory disease (PID)"
    # yields "pelvic inflammatory disease", which is what prose uses.
    terms.add(label.split("(")[0].strip())
    terms.update(_LABEL_ACRONYM.findall(label))
    search_term = getattr(condition, "search_term", "") or ""
    if search_term:
        terms.add(search_term)
    return {t.strip() for t in terms if len(t.strip()) >= 3}


def topic_conditions(
    base: KnowledgeBase,
    message: str,
    context: Sequence[RetrievedPassage] = (),
    *,
    limit: int = 2,
) -> tuple[str, ...]:
    """Which authored conditions a message is *asking about*.

    Deliberately not the same question as :func:`join_evidence`'s. That joins
    on what she has **answered**, which is the right key for triage and the
    wrong one for a question: an informational message reports no symptom, so
    ``given`` is empty, the join returns nothing, and the model is left with
    whatever cosine similarity returned. Measured on the first real
    informational turn (2026-10-10, *"what is PCOS?"*): four retrieved
    passages, all four of them restatements of the definition, and a 433-
    character answer naming not one symptom — while ``evidence.csv`` held ten
    authored, quoted PCOS symptom rows that were never shown. This is the key
    that reaches them.

    Two channels, both cheap and neither a model call: the acronyms and labels
    in ``conditions.yaml`` matched against her words, and the ``condition_id``
    that evidence-statement passages already carry. Matching on text is
    reliable here only because the vocabulary is closed and tiny — 19
    conditions — which is the same property that makes the rest of this module
    work.
    """
    lowered = message.lower()
    scored: list[tuple[int, str]] = []
    for condition in base.conditions:
        best = 0
        for term in _topic_terms(condition):
            if term.lower() in _UNUSABLE_TOPIC_TERMS:
                continue
            if len(term) <= 5:
                # An acronym: require word boundaries, or "POI" matches
                # "point" and "PID" matches "rapid".
                if re.search(rf"\b{re.escape(term.lower())}\b", lowered):
                    best = max(best, len(term) + 10)  # an acronym is a strong signal
            elif term.lower() in lowered:
                best = max(best, len(term))
        if best:
            scored.append((best, condition.id))

    # Longest/strongest match first, so "polycystic ovary syndrome" outranks a
    # condition that merely shares a word with it.
    named = [condition_id for _, condition_id in sorted(scored, reverse=True)]

    # Second channel: an evidence statement carries the condition it was
    # authored for, so retrieval can identify a topic the text match missed.
    for passage in context:
        if passage.condition_id and passage.condition_id not in named:
            named.append(passage.condition_id)

    return tuple(named[:limit])


def _warning_signs_touching(base: KnowledgeBase, feature_ids: set[str]) -> tuple[RedFlagRule, ...]:
    """Red-flag rules that trigger on any of these features.

    Scoped by feature overlap rather than by injecting all of
    ``red_flags.yaml``: an informational answer about PCOS carrying the full
    emergency roster reads alarmingly and buries the part that applies. When
    the overlap is empty the honest output is "our sources record none for
    this topic", which the prompt then has to say rather than invent urgency
    for — the verification protocol's rule, applied to generated prose.
    """
    return tuple(
        rule
        for rule in base.red_flags
        if any(clause.feature_id in feature_ids for clause in rule.all_of)
    )


def render_topic_brief(base: KnowledgeBase, condition_ids: Sequence[str]) -> str:
    """The authored material behind a topic, for an informational answer.

    Returns ``""`` when nothing is identified, so the caller can append
    unconditionally.

    Every line is a real ``evidence.csv`` row with its verbatim
    ``source_quote`` and ``source_id`` — the same rows ``build/cards/
    by-condition.md`` renders for human review, reaching the model at runtime
    instead. Nothing here is generated, inferred or summarised, which is what
    lets an informational answer be as complete as an NHS page while still
    restating only what a cited source says.
    """
    sections: list[str] = []
    for condition_id in condition_ids:
        condition = base.conditions_by_id.get(condition_id)
        if condition is None:
            continue
        rows = [row for row in base.evidence if row.condition_id == condition_id]
        if not rows:
            continue

        lines = [f"### {condition.label}  [{condition.id}]"]
        towards = [r for r in rows if r.strength is not EvidenceStrength.ARGUES_AGAINST]
        against = [r for r in rows if r.strength is EvidenceStrength.ARGUES_AGAINST]

        def _row_line(row: EvidenceRow) -> str:
            feature = base.features_by_id.get(row.feature_id)
            name = getattr(feature, "label", None) or row.feature_id
            return (
                f"- {name} = {row.value} ({row.strength.value}, {row.source_id}): "
                f'"{row.source_quote}"'
            )

        if towards:
            lines.append(
                f"What our sources associate with it ({len(towards)} authored row(s) "
                "— cover ALL of these in an informational answer):"
            )
            lines.extend(_row_line(row) for row in towards)
        if against:
            lines.append("What our sources record as arguing against it:")
            lines.extend(_row_line(row) for row in against)

        signs = _warning_signs_touching(base, {row.feature_id for row in rows})
        if signs:
            lines.append(
                "Urgent warning signs our sources record for these same symptoms. "
                "Describe them in plain words as when to seek care — never as a "
                "rule, a label or an action code:"
            )
            lines.extend(
                f"- needs {rule.action.value}: {rule.label} ({rule.source_id}): "
                f'"{rule.source_quote}"'
                for rule in signs
            )
        else:
            lines.append(
                "Our sources record NO urgent warning sign specific to this topic. "
                "Say that seeing a clinician is the route rather than inventing an "
                "urgency we have no source for."
            )
        sections.append("\n".join(lines))

    if not sections:
        return ""

    return (
        "THE TOPIC SHE IS ASKING ABOUT — authored material for an INFORMATIONAL "
        "answer only.\nThis is what our sources say about the subject, NOT "
        "evidence about her own case. She has reported no symptom, so none of it "
        "may be used to conclude, to assign an urgency, or to name a condition as "
        "hers. Use it to answer the question she actually asked, completely.\n\n"
        + "\n\n".join(sections)
    )


def render_turn_context(context: TurnContext, *, max_rules: int = 8) -> str:
    """The block injected into the system prompt, in place of the old two.

    **It is not cheaper, and the measurement should not be dressed up.** On the
    severe-pelvic-pain turn traced in the design notes, the three blocks this
    replaces — ``render_feature_vocabulary`` (218 tok), ``render_red_flags``
    (718 tok) and ``clients._render_context`` at k=8 (335 tok) — come to 1,272
    tokens; this comes to 1,459. It costs **+187 tokens, about 15% more**.

    What that buys, on the same turn: six EMERGENCY rules reported as one
    answer away rather than sixteen rules with their triggers stripped out;
    five condition ids keyed by a join, where the k=8 similarity search
    returned **zero** evidence statements and therefore no condition id at all;
    and eight candidate questions carrying their authored probe, their value
    vocabulary and a stated reason, where the old block listed 39 bare ids.

    The tokens come back elsewhere. Most of ``clients._JSON_SHAPE_INSTRUCTION``
    (1,308 tok) exists to compensate for what was missing here — the "THREE
    DIFFERENT KINDS OF ID" section, the rules about where a condition id may
    come from, and ``_available_ids_hint``'s retry feedback all become
    unnecessary once the ids arrive labelled, scoped and typed.
    """
    lines: list[str] = []

    if context.given:
        answered = "  ".join(f"{k}={v}" for k, v in sorted(context.given.items()))
        lines.append(
            f"ALREADY ANSWERED, do not ask about any of these again: {answered}\n"
            "These values are already recorded. Do NOT repeat them back in "
            "`observed` — `observed` is only for what her NEWEST message adds."
        )
    else:
        lines.append(
            "ALREADY ANSWERED: nothing yet — this is her opening message. Read it "
            "for anything it already answers and put those in `observed`."
        )

    if context.pending is not None:
        pending = context.pending
        values = ", ".join(pending.allowed_values) or "her own words"
        lines.append(
            f"\nHER NEWEST MESSAGE IS THE ANSWER TO: {pending.id} ({pending.label}). "
            "You asked it last turn and it is still unrecorded. Read her newest "
            f'message and set observed["{pending.id}"] to one of: {values} — or '
            '"unknown" if she genuinely could not say. Do not leave it out: an '
            "unrecorded answer cannot be checked against a warning sign, and she "
            "will end up being asked the same thing twice."
        )

    if context.fired is not None:
        rule = context.fired.rule
        lines.append(
            f"\nA WARNING SIGN IS ALREADY MET: red_flag_id={rule.id} ({rule.action.value}) "
            f'— {rule.label}. Source ({rule.source_id}): "{rule.source_quote}"'
        )

    near = context.near_misses[:max_rules]
    if near:
        lines.append(
            "\nWARNING SIGNS ONE ANSWER AWAY — each needs exactly one more answer to "
            "be met. A more severe sign than any already met is a reason to ask, not "
            "to conclude:"
        )
        for status in near:
            clause = status.outstanding[0]
            want = ", ".join(clause.value) if isinstance(clause.value, tuple) else str(clause.value)
            have = "; ".join(
                f"{c.feature_id}={context.given.get(c.feature_id)}" for c in status.matched
            )
            lines.append(
                f"- red_flag_id={status.rule.id} ({status.rule.action.value}) — "
                f"already true: {have}. Outstanding: {clause.feature_id} "
                f"{clause.op.value} {want}"
            )

    if context.evidence:
        lines.append(
            "\nEVIDENCE HER ANSWERS KEY INTO — every authored row matching what she "
            "said, looked up by feature and value, not by similarity. This set is "
            "complete: no other authored row applies to these answers. Use these "
            "condition ids in matching_conditions, and cite these rows:"
        )
        for group in context.evidence:
            lines.append(f"- condition_id={group.condition.id} ({group.condition.label})")
            for row in group.rows:
                lines.append(
                    f"    {row.feature_id}={row.value} [{row.strength.value}] "
                    f'({row.source_id}): "{row.source_quote}"'
                )
    else:
        lines.append(
            "\nEVIDENCE HER ANSWERS KEY INTO: none yet — no authored row matches what "
            "she has answered, so matching_conditions must be empty."
        )

    if context.askable:
        lines.append(
            "\nQUESTIONS YOU MAY ASK NEXT, most useful first. The wording given is "
            "the authored, reviewed probe — use it, adapting only for what she has "
            "already said. Her answer must land in one of the listed values:"
        )
        for askable in context.askable:
            values = ", ".join(askable.allowed_values) or "free text"
            why = "; ".join(askable.reasons)
            lines.append(
                f'- next_feature_id={askable.feature.id} — "{askable.probe}"\n'
                f"    values: {values}\n"
                f"    why: {why}"
            )

    if context.prose:
        lines.append(
            "\nBACKGROUND PASSAGES, retrieved by similarity. These are for wording and "
            "context only — they are NOT authored evidence and carry no strength. "
            "Never take a condition id from these:"
        )
        for passage in context.prose:
            lines.append(f'- passage_id={passage.id} ({passage.citation}): "{passage.text}"')

    return "\n".join(lines)


def care_guidance(
    base: KnowledgeBase,
    question: str,
    context: Sequence[RetrievedPassage] = (),
    mentioned: Iterable[str] = (),
) -> dict[str, object]:
    """When to get help, for an informational answer, assembled by code.

    An ``inform`` carries no urgency level, and the benchmark run of
    2026-10-13 (ADR 0018) found that the model's own prose rarely said when to
    seek care: 121 of 192 questions labelled see-doctor or urgent got an
    informational answer, and a warning sign appeared in two. The topic brief
    already holds the material; this returns it as data so the interface
    shows it every time, whatever the model wrote.

    Everything here is read from the knowledge base, nothing is generated:
    the identified topics with their ``baseline_action`` from
    ``conditions.yaml``, and the ``red_flags.yaml`` rules that touch the
    symptoms those topics are linked to, most severe first. Nothing is said
    about her: the interface frames it as what our sources advise for
    symptoms like these, and always invites her to describe her own.
    ``topics`` is empty when no authored condition is recognised in her words.

    Warning signs come from two places. The topic's evidence rows, and
    ``mentioned``: the features her question itself names, as the extract
    step read them (any language, closed vocabulary). The second matters
    most. Measured on the 121 affected benchmark questions, topic rows alone
    produced no warning sign for any of them, because the urgent ones ("can I
    bleed during pregnancy?", "what if my period pain is severe?") name a
    symptom rather than a condition. The rules themselves are still read
    from ``red_flags.yaml``; the model only says which symptoms she named.
    """
    # Conditions she named, not ones the retrieved passages happen to be
    # about: "can I bleed during pregnancy?" retrieved endometriosis rows,
    # and a topic she never raised is noise under her answer, or worse.
    topics = topic_conditions(base, question, (), limit=2)
    feature_ids = {row.feature_id for row in base.evidence if row.condition_id in topics}
    # Her age band is profile data, not a symptom she raised.
    feature_ids |= {f for f in mentioned if f in base.features_by_id and f != "age_band"}
    signs = _warning_signs_touching(base, feature_ids) if feature_ids else ()
    severity = {action.code: action.severity for action in base.actions.actions}
    named = set(mentioned)
    # Signs about what she asked come first, then by severity: a pregnancy
    # question should lead with bleeding in pregnancy, not with every
    # emergency that pelvic pain can carry.
    ordered = sorted(
        signs,
        key=lambda rule: (
            not any(clause.feature_id in named for clause in rule.all_of),
            -severity.get(rule.action, 0),
        ),
    )
    return {
        "topics": [
            {
                "condition_id": condition_id,
                "baseline_action": base.conditions_by_id[condition_id].baseline_action.value,
            }
            for condition_id in topics
        ],
        "warning_signs": [
            {"rule_id": rule.id, "action": rule.action.value, "source_id": rule.source_id}
            for rule in ordered
        ],
    }
