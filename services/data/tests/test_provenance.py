"""Tests for quote verification.

The three failures this exists to catch each get a test, because each is
invisible when reading the row: drift, misattribution, and paraphrase.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from herhealth_data.provenance import Verdict, load_corpus, verify_quotes

NICHD_TEXT = [
    "What are the symptoms of uterine fibroids?",
    "Anemia (when you don’t have enough red blood cells)",
    "Feeling “full” in the lower abdomen (belly)—sometimes called pelvic pressure",
]
NHS_TEXT = [
    "Symptoms of pelvic inflammatory disease",
    "pain felt deep inside when you have sex",
    "vaginal discharge that looks, smells or feels unusual for you",
]


@pytest.fixture
def corpus_dir(tmp_path: Path) -> Path:
    def write(source_id: str, slug: str, lines: list[str]) -> None:
        path = tmp_path / source_id / f"{slug}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "source_id": source_id,
                    "slug": slug,
                    "sections": [
                        {
                            "heading": lines[0],
                            "section_type": "symptoms",
                            "paragraphs": lines[1:],
                            "locale_references": [],
                            "escalation_sentences": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    write("nichd", "fibroids", NICHD_TEXT)
    write("nhs", "pid", NHS_TEXT)
    return tmp_path


def check(corpus_dir: Path, source_id: str, quote: str) -> Verdict:
    corpus = load_corpus(corpus_dir)
    return verify_quotes([("row", source_id, quote)], corpus)[0].verdict


# --------------------------------------------------------------------------
# The happy path
# --------------------------------------------------------------------------


def test_an_exact_quote_verifies(corpus_dir: Path) -> None:
    assert check(corpus_dir, "nhs", "pain felt deep inside when you have sex") is Verdict.VERIFIED


def test_a_heading_counts_as_source_text(corpus_dir: Path) -> None:
    assert check(corpus_dir, "nhs", "Symptoms of pelvic inflammatory disease") is Verdict.VERIFIED


def test_surrounding_whitespace_is_forgiven(corpus_dir: Path) -> None:
    """The quote is stored stripped; leading space is not a provenance failure."""
    quote = "   pain felt deep inside when you have sex  "
    assert check(corpus_dir, "nhs", quote) is Verdict.VERIFIED


# --------------------------------------------------------------------------
# Drift — a character out of place
# --------------------------------------------------------------------------


def test_a_straight_apostrophe_does_not_match_a_curly_one(corpus_dir: Path) -> None:
    """REGRESSION. Three real rows failed exactly this way.

    Retyping from a console that renders curly punctuation as a replacement
    glyph produces a quote that reads correctly and cannot be found.
    """
    assert check(corpus_dir, "nichd", "Anemia (when you don't have enough red blood cells)") is (
        Verdict.NOT_FOUND
    )


def test_the_curly_original_does_match(corpus_dir: Path) -> None:
    assert check(corpus_dir, "nichd", NICHD_TEXT[1]) is Verdict.VERIFIED


def test_an_added_character_is_caught(corpus_dir: Path) -> None:
    assert check(corpus_dir, "nhs", "pain felt deep inside when you have sexx") is Verdict.NOT_FOUND


def test_a_truncated_quote_still_verifies_which_is_a_known_limitation(
    corpus_dir: Path,
) -> None:
    """Matching is substring-based, so a quote missing its end still passes.

    Documented rather than fixed. A truncated quote is still verbatim source
    text — incomplete, not invented — which is a far milder fault than a
    paraphrase, and the alternative (requiring whole-sentence equality) would
    reject the many legitimate quotes that are clauses rather than sentences.

    The consequence to be aware of: this check proves a quote EXISTS in its
    source. It does not prove the quote is complete enough to support the row.
    That judgement is the human review step, and this does not replace it.
    """
    assert check(corpus_dir, "nhs", "pain felt deep inside when you have se") is Verdict.VERIFIED


def test_a_near_miss_reports_the_closest_source_text(corpus_dir: Path) -> None:
    """So a reviewer can see the drift instead of hunting for it."""
    corpus = load_corpus(corpus_dir)
    result = verify_quotes(
        [("row", "nichd", "Anemia (when you don't have enough red blood cells)")], corpus
    )[0]
    assert result.closest is not None
    assert "Anemia" in result.closest


# --------------------------------------------------------------------------
# Misattribution — real quote, wrong citation
# --------------------------------------------------------------------------


def test_a_quote_from_another_source_is_not_verified(corpus_dir: Path) -> None:
    """The row looks perfect; only the citation is wrong.

    This is why matching is scoped to the cited source. A corpus-wide search
    would pass precisely the rows that are misattributed.
    """
    result = check(corpus_dir, "nichd", "pain felt deep inside when you have sex")
    assert result is Verdict.WRONG_SOURCE


def test_misattribution_names_where_the_quote_actually_is(corpus_dir: Path) -> None:
    corpus = load_corpus(corpus_dir)
    result = verify_quotes(
        [("row", "nichd", "pain felt deep inside when you have sex")], corpus
    )[0]
    assert result.found_in == "nhs"


# --------------------------------------------------------------------------
# Paraphrase — the most serious
# --------------------------------------------------------------------------


def test_a_paraphrase_is_not_verified(corpus_dir: Path) -> None:
    """A paraphrase of a clinical claim is a new clinical claim."""
    assert check(corpus_dir, "nhs", "deep pain during intercourse") is Verdict.NOT_FOUND


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def test_an_uncited_source_is_reported_separately(corpus_dir: Path) -> None:
    """Not a failure of the row — nothing to check against."""
    assert check(corpus_dir, "cdc", "anything at all") is Verdict.SOURCE_ABSENT


def test_source_absent_is_not_treated_as_a_problem(corpus_dir: Path) -> None:
    corpus = load_corpus(corpus_dir)
    result = verify_quotes([("row", "cdc", "anything")], corpus)[0]
    assert not result.is_problem


@pytest.mark.parametrize(
    ("verdict_source", "quote", "problem"),
    [
        ("nhs", "pain felt deep inside when you have sex", False),
        ("nichd", "pain felt deep inside when you have sex", True),
        ("nhs", "invented text that appears nowhere", True),
    ],
)
def test_only_real_faults_fail_the_build(
    corpus_dir: Path, verdict_source: str, quote: str, problem: bool
) -> None:
    corpus = load_corpus(corpus_dir)
    assert verify_quotes([("row", verdict_source, quote)], corpus)[0].is_problem is problem


def test_an_empty_corpus_directory_loads(tmp_path: Path) -> None:
    assert load_corpus(tmp_path).sources() == []
