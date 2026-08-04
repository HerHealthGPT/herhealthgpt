"""Tests for loading and validating the knowledge base.

Each cross-file check gets a test that breaks exactly one thing, so a passing
suite means each check catches its own fault rather than some other one.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from herhealth_data import paths
from herhealth_data.knowledge import (
    Problem,
    Severity,
    load_knowledge_base,
    validate_directory,
)

# --------------------------------------------------------------------------
# A minimal valid knowledge directory, one piece per file
# --------------------------------------------------------------------------

FEATURES = """
features:
  - id: cycle_regularity
    label: Cycle regularity
    kind: categorical
    allowed_values: [regular, irregular, absent]
    burden: 1
    probe:
      en: Are your periods usually regular?
  - id: fever
    label: Fever
    kind: boolean
    allowed_values: ["yes", "no"]
    burden: 1
    probe:
      en: Do you have a fever?
"""

CONDITIONS = """
conditions:
  - id: pcos
    label: Polycystic ovary syndrome
    baseline_action: ROUTINE_APPOINTMENT
    source_ids: [medlineplus, nichd]
"""

SOURCES = """
sources:
  - id: medlineplus
    name: MedlinePlus
    url: https://medlineplus.gov/
    precedence: 3
    licence: Public domain
    access: Topic pages
    status: available
  - id: nichd
    name: NICHD
    url: https://www.nichd.nih.gov/
    precedence: 3
    licence: Public domain
    access: Pages
    status: available
  - id: nice_cks
    name: NICE CKS
    url: https://cks.nice.org.uk/
    precedence: 1
    licence: Not reusable
    access: Restricted
    status: restricted
"""

RED_FLAGS = """
red_flags:
  - id: fever_with_irregular_cycles
    label: Fever
    all_of:
      - feature_id: fever
        op: equals
        value: "yes"
    action: URGENT_SAME_DAY
    source_id: medlineplus
    source_quote: Seek care if you have a fever.
"""

WEIGHTS = """
log_odds:
  strong_support: 1.5
  weak_support: 0.6
  neutral: 0.0
  argues_against: -0.5
  rules_out: -4.0
plausibility_floor: 0.05
stop_confidence: 0.65
self_care_stop_confidence: 0.85
stop_margin: 0.15
max_questions: 6
"""

ACTIONS = """
actions:
  - {code: SELF_CARE, severity: 0, description: Manage at home.}
  - {code: ROUTINE_APPOINTMENT, severity: 1, description: Arrange an appointment.}
  - {code: URGENT_SAME_DAY, severity: 2, description: Be seen today.}
  - {code: EMERGENCY, severity: 3, description: Seek emergency care now.}
"""

EVIDENCE_HEADER = "condition_id,feature_id,value,strength,source_id,source_quote,note\n"
GOOD_ROW = (
    "pcos,cycle_regularity,irregular,strong_support,medlineplus,"
    "Irregular periods are common.,\n"
)


@pytest.fixture
def knowledge(tmp_path: Path) -> Path:
    """A directory that validates cleanly."""
    for name, body in [
        ("features.yaml", FEATURES),
        ("conditions.yaml", CONDITIONS),
        ("sources.yaml", SOURCES),
        ("red_flags.yaml", RED_FLAGS),
        ("weights.yaml", WEIGHTS),
        ("actions.yaml", ACTIONS),
    ]:
        (tmp_path / name).write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")
    (tmp_path / "evidence.csv").write_text(EVIDENCE_HEADER + GOOD_ROW, encoding="utf-8")
    return tmp_path


def errors(problems: list[Problem]) -> list[Problem]:
    return [p for p in problems if p.severity is Severity.ERROR]


def messages(problems: list[Problem]) -> str:
    return "\n".join(p.message for p in problems)


def set_evidence(directory: Path, *rows: str) -> None:
    (directory / "evidence.csv").write_text(EVIDENCE_HEADER + "".join(rows), encoding="utf-8")


# --------------------------------------------------------------------------
# The happy path
# --------------------------------------------------------------------------


def test_a_valid_directory_has_no_errors(knowledge: Path) -> None:
    assert errors(validate_directory(knowledge)) == []


def test_a_valid_directory_loads(knowledge: Path) -> None:
    base, problems = load_knowledge_base(knowledge)
    assert base is not None
    assert errors(problems) == []
    assert len(base.features) == 2
    assert len(base.evidence) == 1


def test_an_evidence_file_with_only_a_header_is_valid(knowledge: Path) -> None:
    set_evidence(knowledge)
    assert errors(validate_directory(knowledge)) == []


# --------------------------------------------------------------------------
# Foreign keys
# --------------------------------------------------------------------------


def test_unknown_condition_id_is_an_error(knowledge: Path) -> None:
    set_evidence(knowledge, "ghost,cycle_regularity,irregular,weak_support,medlineplus,q,\n")
    found = messages(errors(validate_directory(knowledge)))
    assert "condition_id 'ghost' does not resolve" in found


def test_unknown_feature_id_is_an_error(knowledge: Path) -> None:
    set_evidence(knowledge, "pcos,ghost,irregular,weak_support,medlineplus,q,\n")
    assert "feature_id 'ghost' does not resolve" in messages(errors(validate_directory(knowledge)))


def test_unknown_source_id_is_an_error(knowledge: Path) -> None:
    set_evidence(knowledge, "pcos,cycle_regularity,irregular,weak_support,ghost,q,\n")
    assert "source_id 'ghost' does not resolve" in messages(errors(validate_directory(knowledge)))


def test_unknown_source_on_a_condition_is_an_error(knowledge: Path) -> None:
    (knowledge / "conditions.yaml").write_text(
        CONDITIONS.replace("[medlineplus, nichd]", "[medlineplus, ghost]"), encoding="utf-8"
    )
    assert "source_id 'ghost' does not resolve" in messages(errors(validate_directory(knowledge)))


def test_unknown_feature_in_a_red_flag_clause_is_an_error(knowledge: Path) -> None:
    (knowledge / "red_flags.yaml").write_text(
        RED_FLAGS.replace("feature_id: fever", "feature_id: ghost"), encoding="utf-8"
    )
    assert "feature_id 'ghost' does not resolve" in messages(errors(validate_directory(knowledge)))


# --------------------------------------------------------------------------
# Values must exist
# --------------------------------------------------------------------------


def test_value_outside_allowed_values_is_an_error(knowledge: Path) -> None:
    set_evidence(knowledge, "pcos,cycle_regularity,sporadic,weak_support,medlineplus,q,\n")
    assert "is not in allowed_values" in messages(errors(validate_directory(knowledge)))


def test_unknown_is_rejected_as_a_value(knowledge: Path) -> None:
    """`unknown` is implicit and weightless; a row for it could never act."""
    set_evidence(knowledge, "pcos,cycle_regularity,unknown,weak_support,medlineplus,q,\n")
    assert "implicit on every feature" in messages(errors(validate_directory(knowledge)))


def test_red_flag_clause_value_must_exist(knowledge: Path) -> None:
    (knowledge / "red_flags.yaml").write_text(
        RED_FLAGS.replace('value: "yes"', 'value: "maybe"'), encoding="utf-8"
    )
    assert "is not in allowed_values" in messages(errors(validate_directory(knowledge)))


# --------------------------------------------------------------------------
# Licensing
# --------------------------------------------------------------------------


def test_citing_a_restricted_source_is_an_error(knowledge: Path) -> None:
    """The licensing rule is enforced by CI, not by memory."""
    set_evidence(knowledge, "pcos,cycle_regularity,irregular,weak_support,nice_cks,q,\n")
    assert "does not permit quoting" in messages(errors(validate_directory(knowledge)))


def test_a_red_flag_citing_a_restricted_source_is_an_error(knowledge: Path) -> None:
    (knowledge / "red_flags.yaml").write_text(
        RED_FLAGS.replace("source_id: medlineplus", "source_id: nice_cks"), encoding="utf-8"
    )
    assert "does not permit quoting" in messages(errors(validate_directory(knowledge)))


# --------------------------------------------------------------------------
# Schema faults surface through the loader
# --------------------------------------------------------------------------


def test_a_neutral_row_is_rejected(knowledge: Path) -> None:
    set_evidence(knowledge, "pcos,cycle_regularity,irregular,neutral,medlineplus,q,\n")
    assert "sparse" in messages(errors(validate_directory(knowledge)))


def test_a_missing_source_quote_is_rejected(knowledge: Path) -> None:
    set_evidence(knowledge, "pcos,cycle_regularity,irregular,weak_support,medlineplus,,\n")
    assert errors(validate_directory(knowledge))


def test_duplicate_cells_are_rejected(knowledge: Path) -> None:
    set_evidence(knowledge, GOOD_ROW, GOOD_ROW.replace("strong_support", "weak_support"))
    assert "duplicate" in messages(errors(validate_directory(knowledge)))


def test_a_missing_file_is_an_error(knowledge: Path) -> None:
    (knowledge / "weights.yaml").unlink()
    assert "file is missing" in messages(errors(validate_directory(knowledge)))


def test_an_empty_file_is_an_error(knowledge: Path) -> None:
    (knowledge / "actions.yaml").write_text("", encoding="utf-8")
    assert "file is empty" in messages(errors(validate_directory(knowledge)))


def test_broken_yaml_is_reported_not_raised(knowledge: Path) -> None:
    (knowledge / "sources.yaml").write_text("sources: [{ unclosed", encoding="utf-8")
    assert "not valid YAML" in messages(errors(validate_directory(knowledge)))


def test_every_problem_is_reported_not_just_the_first(knowledge: Path) -> None:
    set_evidence(
        knowledge,
        "ghost,cycle_regularity,irregular,weak_support,medlineplus,q,\n",
        "pcos,phantom,irregular,weak_support,medlineplus,q,\n",
    )
    assert len(errors(validate_directory(knowledge))) >= 2


# --------------------------------------------------------------------------
# Phase policy
# --------------------------------------------------------------------------


def test_non_english_probes_are_rejected_in_this_phase(knowledge: Path) -> None:
    (knowledge / "features.yaml").write_text(
        FEATURES.replace(
            "      en: Are your periods usually regular?",
            "      en: Are your periods usually regular?\n"
            "      fr: Vos regles sont-elles regulieres?",
        ),
        encoding="utf-8",
    )
    assert "not authored in this phase" in messages(errors(validate_directory(knowledge)))


# --------------------------------------------------------------------------
# Warnings — real but not failures
# --------------------------------------------------------------------------


def test_an_unused_feature_warns(knowledge: Path) -> None:
    """With no evidence rows, cycle_regularity is used by nothing at all."""
    set_evidence(knowledge)
    problems = validate_directory(knowledge)
    warnings = [p for p in problems if p.severity is Severity.WARNING]
    assert any(p.location == "cycle_regularity" for p in warnings)
    assert errors(problems) == [], "an unused feature must not fail the build"


def test_a_feature_used_only_by_a_red_flag_does_not_warn(knowledge: Path) -> None:
    """Red-flag-only features are not dead weight — red flags run first."""
    (knowledge / "red_flags.yaml").write_text(
        RED_FLAGS.replace("feature_id: fever", "feature_id: cycle_regularity").replace(
            'value: "yes"', "value: absent"
        ),
        encoding="utf-8",
    )
    warnings = [p for p in validate_directory(knowledge) if p.severity is Severity.WARNING]
    assert not any(p.location == "cycle_regularity" for p in warnings)


def test_a_condition_with_no_evidence_warns(knowledge: Path) -> None:
    set_evidence(knowledge)
    warnings = [p for p in validate_directory(knowledge) if p.severity is Severity.WARNING]
    assert any("nothing can ever raise it" in p.message for p in warnings)


# --------------------------------------------------------------------------
# The real knowledge directory
# --------------------------------------------------------------------------


def test_the_repository_knowledge_base_validates() -> None:
    """The committed knowledge/ must have no errors. Warnings are allowed."""
    problems = validate_directory(paths.KNOWLEDGE_DIR)
    assert errors(problems) == [], "\n".join(str(p) for p in errors(problems))
