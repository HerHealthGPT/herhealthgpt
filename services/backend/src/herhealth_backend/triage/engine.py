"""The stopping controller. Plain Python, no LLM.

The model extracts feature values from what a user writes and phrases the
question or the final answer. It never decides whether to ask again or what
urgency to assign. Those decisions are here, and they are deterministic: the
same state produces the same decision every time, which is what makes the
evaluation harness meaningful and what stops a model from talking the system out
of an escalation.

The engine takes a :class:`KnowledgeBase` rather than loading one, so every test
here constructs its own tiny knowledge base and none of them touch a file. The
strict loader that reads the real files lives in ``herhealth_contracts.loading``
— it is in contracts precisely because both services need it, and nothing
outside contracts may cross a service boundary.

``should_stop`` checks in order, first match wins. The order IS the policy:

1. A red flag fired → escalate. No differential, no model call.
2. Every live condition shares one action → stop; more questions cannot change
   what the user is told.
3. No unasked question could change the action → stop; asking would only cost
   the user time.
4. One condition is clearly ahead → stop.
5. The question budget ran out → stop with the differential.
6. Otherwise → ask.

Under-triage is the dominant failure mode, so wherever this code chooses, it
chooses the more urgent action. Two places matter: an unresolved differential
returns its **most urgent** member's action, and concluding ``SELF_CARE``
requires clearing a strictly higher bar than any other action.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from herhealth_contracts.knowledge import (
    CANONICAL_ACTION_ORDER,
    UNKNOWN_VALUE,
    ActionCode,
    Clause,
    ComparisonOp,
    EvidenceRow,
    KnowledgeBase,
    RedFlagRule,
)

from herhealth_backend.triage.state import Answer, Decision, StopReason, TriageState

__all__ = ["TriageEngine"]


def _severity(action: ActionCode) -> int:
    return CANONICAL_ACTION_ORDER.index(action)


def most_urgent(actions: Iterable[ActionCode]) -> ActionCode | None:
    """The most urgent of several actions.

    Used wherever the differential has not resolved. Choosing the most urgent
    rather than the most likely is the whole design: a differential containing
    both "normal variation" and "pelvic inflammatory disease" must not be
    reported as self-care because the benign one happens to score higher.
    """
    ordered = sorted(actions, key=_severity)
    return ordered[-1] if ordered else None


class TriageEngine:
    """Deterministic triage over a fixed knowledge base."""

    def __init__(self, base: KnowledgeBase) -> None:
        self.base = base
        self.weights = base.weights
        self._conditions = base.conditions_by_id
        self._features = base.features_by_id

        # (feature_id, value) -> rows, so update is a lookup rather than a scan.
        self._evidence: dict[tuple[str, str], list[EvidenceRow]] = {}
        for row in base.evidence:
            self._evidence.setdefault((row.feature_id, row.value), []).append(row)

    # -- state -------------------------------------------------------------

    def initial_state(self) -> TriageState:
        """Every condition at 0.0 log-odds, which is plausibility 0.5.

        Not zero plausibility: before anything is asked, no condition is
        favoured and none is excluded. Baselines deliberately do not seed the
        score — a condition's baseline says what it would MEAN if true, not how
        likely it is.
        """
        return TriageState(scores={condition.id: 0.0 for condition in self.base.conditions})

    def update(self, state: TriageState, feature_id: str, value: str) -> TriageState:
        """Record an answer and add the matching weights.

        An unknown answer is recorded but moves nothing — that is what makes
        ``unknown`` weightless rather than negative.
        """
        answer = Answer(feature_id=feature_id, value=value)
        scores = dict(state.scores)

        if value != UNKNOWN_VALUE:
            for row in self._evidence.get((feature_id, value), ()):
                if row.condition_id in scores:
                    scores[row.condition_id] += self.weights.log_odds[row.strength]

        return TriageState(
            scores=scores,
            answers=(*state.answers, answer),
            fired_red_flag_id=self._first_matching_red_flag(
                (*state.answers, answer)
            ),
        )

    # -- red flags ---------------------------------------------------------

    def _first_matching_red_flag(self, answers: Sequence[Answer]) -> str | None:
        """The first rule every clause of which matches. Order is file order."""
        given = {a.feature_id: a.value for a in answers if a.is_known}
        for rule in self.base.red_flags:
            if all(self._clause_matches(clause, given) for clause in rule.all_of):
                return rule.id
        return None

    @staticmethod
    def _clause_matches(clause: Clause, given: dict[str, str]) -> bool:
        """A clause matches only on a known answer.

        An unasked or unknown feature never satisfies a clause. That is
        deliberate and it is the conservative direction for a conjunction: a
        rule fires only on what the user actually said.
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
                # Numeric comparison on a categorical answer is not meaningful.
                # No feature currently needs it; refusing to match is safer than
                # inventing an ordering over strings.
                return False
        return False

    def red_flag(self, state: TriageState) -> RedFlagRule | None:
        if state.fired_red_flag_id is None:
            return None
        return next(r for r in self.base.red_flags if r.id == state.fired_red_flag_id)

    # -- the decision ------------------------------------------------------

    def should_stop(self, state: TriageState) -> Decision:
        """Six checks, in order, first match wins."""
        floor = self.weights.plausibility_floor
        live = state.live(floor)
        differential = tuple(live.items())

        # 1. A red flag outranks everything, including the differential.
        rule = self.red_flag(state)
        if rule is not None:
            return Decision(
                reason=StopReason.RED_FLAG,
                action=rule.action,
                red_flag_id=rule.id,
                differential=differential,
                explanation=f"red flag {rule.id!r} fired: {rule.label}",
            )

        # Nothing plausible. Ask if we can; otherwise fall through to the
        # budget check, which reports the (empty) differential honestly.
        if not live:
            if state.questions_asked < self.weights.max_questions:
                nxt = self.next_question(state)
                if nxt is not None:
                    return Decision(
                        reason=StopReason.ASK,
                        next_feature_id=nxt,
                        differential=differential,
                        explanation="no condition is above the plausibility floor yet",
                    )
            return self._out_of_questions(state, differential)

        actions = {self._conditions[c].baseline_action for c in live}

        # 2. Everything still plausible means the same thing.
        if len(actions) == 1:
            action = next(iter(actions))
            if self._clears_bar(state, action, live):
                return Decision(
                    reason=StopReason.SHARED_ACTION,
                    action=action,
                    differential=differential,
                    explanation=(
                        f"all {len(live)} plausible condition(s) imply {action.value}"
                    ),
                )

        # 3. Nothing left to ask that could change the answer.
        nxt = self.next_question(state)
        if nxt is None:
            action = most_urgent(actions)
            return Decision(
                reason=StopReason.NO_INFORMATIVE_QUESTION,
                action=action,
                differential=differential,
                explanation="no unasked question could change the action",
            )

        # 4. One condition clearly ahead.
        ranked = state.ranked()
        top_id, top_p = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
        top_action = self._conditions[top_id].baseline_action
        bar = self._bar_for(top_action)
        if top_p >= bar and (top_p - runner_up) >= self.weights.stop_margin:
            return Decision(
                reason=StopReason.CONFIDENT,
                action=top_action,
                differential=differential,
                explanation=(
                    f"{top_id} at {top_p:.2f} clears {bar:.2f} "
                    f"with {top_p - runner_up:.2f} over the next"
                ),
            )

        # 5. Budget.
        if state.questions_asked >= self.weights.max_questions:
            return self._out_of_questions(state, differential)

        # 6. Ask.
        return Decision(
            reason=StopReason.ASK,
            next_feature_id=nxt,
            differential=differential,
            explanation=f"{len(live)} condition(s) live, differing on action",
        )

    def _out_of_questions(
        self, state: TriageState, differential: tuple[tuple[str, float], ...]
    ) -> Decision:
        """Stop with the differential, at its most urgent action.

        Not the most likely one. An unresolved differential that contains
        anything urgent is reported at that urgency — this is the single
        clearest place the design chooses false alarms over missed escalations.
        """
        live = dict(differential)
        actions = {self._conditions[c].baseline_action for c in live}
        action = most_urgent(actions) or ActionCode.ROUTINE_APPOINTMENT
        return Decision(
            reason=StopReason.MAX_QUESTIONS,
            action=action,
            differential=differential,
            explanation=(
                f"asked {state.questions_asked} question(s); returning the "
                f"differential at its most urgent action"
            ),
        )

    def _bar_for(self, action: ActionCode) -> float:
        """Concluding SELF_CARE requires strictly more than anything else."""
        if action is ActionCode.SELF_CARE:
            return self.weights.self_care_stop_confidence
        return self.weights.stop_confidence

    def _clears_bar(
        self, state: TriageState, action: ActionCode, live: dict[str, float]
    ) -> bool:
        """Whether a shared-action stop is allowed to conclude.

        For every action but ``SELF_CARE`` a shared action is enough: if all
        live conditions mean the same thing, more questions cannot change it.

        ``SELF_CARE`` is different. Concluding "nothing to do" on a weakly
        supported differential is the failure this system exists to avoid, so it
        additionally requires the top condition to clear the higher bar.
        """
        if action is not ActionCode.SELF_CARE:
            return True
        top = max(live.values(), default=0.0)
        return top >= self.weights.self_care_stop_confidence

    # -- question selection ------------------------------------------------

    def next_question(self, state: TriageState) -> str | None:
        """The unasked feature that best separates live conditions per burden.

        Returns None when no unasked feature could change the action, which is
        what stopping rule 3 keys on.
        """
        candidates = [
            feature_id
            for feature_id in self._features
            if feature_id not in state.asked_feature_ids
            and self._could_change_action(state, feature_id)
        ]
        if not candidates:
            return None

        def rank(feature_id: str) -> tuple[float, str]:
            burden = self._features[feature_id].burden
            separation = self._separation(state, feature_id)
            # Negated so the highest value sorts first; id breaks ties so the
            # choice is deterministic rather than dict-order dependent.
            return (-separation / burden, feature_id)

        return min(candidates, key=rank)

    def _could_change_action(self, state: TriageState, feature_id: str) -> bool:
        """Whether any answer to this feature could alter the outcome.

        True if the feature appears in a red-flag clause — those can escalate
        regardless of the differential — or if it carries evidence for at least
        one live condition.
        """
        if any(
            clause.feature_id == feature_id
            for rule in self.base.red_flags
            for clause in rule.all_of
        ):
            return True

        live = set(state.live(self.weights.plausibility_floor))
        if not live:
            live = set(state.scores)
        return any(
            row.feature_id == feature_id and row.condition_id in live
            for row in self.base.evidence
        )

    def _separation(self, state: TriageState, feature_id: str) -> float:
        """How much this feature could spread the live conditions apart.

        The sum of absolute weight it could apply across live conditions. Crude
        — it does not model which answer the user will give — but it prefers
        features that discriminate over features that lift everything at once,
        which is the property that matters.
        """
        live = set(state.live(self.weights.plausibility_floor)) or set(state.scores)
        total = 0.0
        for row in self.base.evidence:
            if row.feature_id == feature_id and row.condition_id in live:
                total += abs(self.weights.log_odds[row.strength])
        return total
