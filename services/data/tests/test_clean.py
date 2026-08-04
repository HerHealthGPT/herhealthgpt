"""Tests for turning fetched HTML into sectioned, quotable text.

The property that matters most is that text comes out VERBATIM. A cleaner that
rewrites source text destroys the guarantee every source_quote depends on, so
the normalisation tests are the important ones here.
"""

from __future__ import annotations

import pytest

from herhealth_data.ingest.clean import (
    CleanDocument,
    SectionType,
    classify_heading,
    clean_html,
    find_escalation_sentences,
    find_locale_references,
    is_link_list,
)

# --------------------------------------------------------------------------
# Verbatim text — the guarantee everything else rests on
# --------------------------------------------------------------------------


def paragraphs(html: str) -> list[str]:
    return [p for section in clean_html(html) for p in section.paragraphs]


def test_inline_markup_does_not_leave_a_space_before_punctuation() -> None:
    """REGRESSION. MedlinePlus marks up `Obesity<a>, weight gain`.

    Extracting with a separator put a space between the elements, producing
    "Obesity , weight gain" — which is not what the page says, so the quote was
    not verbatim and a reviewer could not have confirmed it against the source.
    """
    html = "<p>Obesity <a href='/x'>weight</a> , weight gain, or trouble losing weight.</p>"
    assert " ," not in paragraphs(html)[0]


@pytest.mark.parametrize("punctuation", [",", ".", ";", ":", "!", "?", ")"])
def test_no_space_survives_before_any_punctuation(punctuation: str) -> None:
    html = f"<p>Some clinical sentence that is long enough {punctuation} and more text here.</p>"
    assert f" {punctuation}" not in paragraphs(html)[0]


def test_no_space_survives_after_an_opening_bracket() -> None:
    html = "<p>Feeling full in the lower abdomen ( belly) is sometimes called pressure.</p>"
    assert "( " not in paragraphs(html)[0]


def test_words_are_never_altered() -> None:
    """Whitespace is normalised; nothing else is."""
    sentence = "Pelvic pain, which often happens during your period and lasts a while."
    assert paragraphs(f"<p>{sentence}</p>")[0] == sentence


def test_runs_of_whitespace_collapse_to_one_space() -> None:
    html = "<p>Heavy   bleeding\n\n   or painful periods that affect your daily life.</p>"
    assert paragraphs(html)[0] == "Heavy bleeding or painful periods that affect your daily life."


def test_short_fragments_are_dropped() -> None:
    """Navigation leftovers are short; clinical sentences are not."""
    html = "<p>Next</p><p>A clinical sentence long enough to be worth keeping here.</p>"
    assert len(paragraphs(html)) == 1


def test_duplicate_paragraphs_within_a_section_are_dropped() -> None:
    sentence = "Heavy bleeding or painful periods that affect your daily life."
    assert len(paragraphs(f"<p>{sentence}</p><p>{sentence}</p>")) == 1


# --------------------------------------------------------------------------
# Boilerplate removal
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tag", ["script", "style", "nav", "header", "footer", "form"])
def test_structural_noise_is_removed(tag: str) -> None:
    html = f"<{tag}><p>Navigation text that is long enough to survive otherwise.</p></{tag}>"
    assert paragraphs(html) == []


@pytest.mark.parametrize("marker", ["cookie", "breadcrumb", "related", "feedback", "sidebar"])
def test_chrome_wrappers_are_removed_by_class(marker: str) -> None:
    html = (
        f"<div class='{marker}-banner'>"
        "<p>Chrome text long enough to otherwise survive.</p></div>"
    )
    assert paragraphs(html) == []


def test_decomposing_a_wrapper_does_not_break_the_walk() -> None:
    """REGRESSION. Removing a parent invalidated descendants mid-iteration."""
    html = (
        "<div class='cookie'><div class='related'><p>Nested chrome text here.</p></div></div>"
        "<p>A real clinical sentence that must survive the removal.</p>"
    )
    assert paragraphs(html) == ["A real clinical sentence that must survive the removal."]


# --------------------------------------------------------------------------
# Sectioning
# --------------------------------------------------------------------------


def test_headings_split_sections() -> None:
    html = (
        "<h2>Symptoms of endometriosis</h2><p>Pelvic pain that happens during your period.</p>"
        "<h2>Causes of endometriosis</h2><p>Researchers do not know what causes it.</p>"
    )
    sections = clean_html(html)
    assert [s.section_type for s in sections] == [SectionType.SYMPTOMS, SectionType.CAUSES]


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("When to get medical help", SectionType.WHEN_TO_GET_HELP),
        ("Call 999 if:", SectionType.WHEN_TO_GET_HELP),
        ("Symptoms of fibroids", SectionType.SYMPTOMS),
        ("Causes of fibroids", SectionType.CAUSES),
        ("How fibroids are diagnosed", SectionType.DIAGNOSIS),
        ("Treatments for fibroids", SectionType.TREATMENT),
        ("Living with it", SectionType.OTHER),
    ],
)
def test_headings_are_classified(heading: str, expected: SectionType) -> None:
    assert classify_heading(heading) is expected


def test_escalation_beats_other_matches() -> None:
    """"When to get urgent help" contains "help" and "urgent" — escalation wins."""
    assert classify_heading("When to get urgent help") is SectionType.WHEN_TO_GET_HELP


# --------------------------------------------------------------------------
# Escalation sentences — the source of red_flags.yaml
# --------------------------------------------------------------------------


def test_escalation_language_is_found_mid_paragraph() -> None:
    """US federal sources bury it in prose rather than under a heading."""
    found = find_escalation_sentences(
        ["Fibroids are common. See your doctor if the bleeding is heavy. They are benign."]
    )
    assert found == ("See your doctor if the bleeding is heavy.",)


def test_ordinary_prose_is_not_treated_as_escalation() -> None:
    assert find_escalation_sentences(["Fibroids are non-cancerous growths in the womb."]) == ()


def test_escalation_sentences_are_verbatim() -> None:
    """Each is used directly as a source_quote, so it must not be reworded."""
    sentence = "Call 999 if you have heavy bleeding from your vagina."
    assert find_escalation_sentences([sentence]) == (sentence,)


# --------------------------------------------------------------------------
# Locale references — recorded, never replaced
# --------------------------------------------------------------------------


def test_locale_references_are_recorded() -> None:
    assert "999" in find_locale_references("Call 999 or go to A&E if it is severe.")
    assert "A&E" in find_locale_references("Call 999 or go to A&E if it is severe.")


def test_locale_references_are_not_removed_from_the_text() -> None:
    """Substitution happens at build time; doing it here would corrupt quotes."""
    html = "<p>Call 999 or go to A and E if the pain is severe and getting worse.</p>"
    assert "999" in paragraphs(html)[0]


# --------------------------------------------------------------------------
# The text hash — drift detection
# --------------------------------------------------------------------------


def document(html: str) -> CleanDocument:
    return CleanDocument("nichd", "pcos", clean_html(html))


def test_text_hash_ignores_markup_churn() -> None:
    """REGRESSION. Raw-byte hashes changed on 14 of 19 documents with no words moved."""
    a = document("<link href='/a.css?1785557565749'><p>Irregular or missed menstrual periods.</p>")
    b = document("<link href='/a.css?1785816820556'><p>Irregular or missed menstrual periods.</p>")
    assert a.text_hash == b.text_hash


def test_text_hash_changes_when_words_change() -> None:
    a = document("<p>Irregular or missed menstrual periods happen often.</p>")
    b = document("<p>Irregular or absent menstrual periods happen often.</p>")
    assert a.text_hash != b.text_hash


def test_text_hash_ignores_rotating_link_lists() -> None:
    """MedlinePlus rotates its PubMed article listing on every fetch."""
    a = document("<h2>Journal Articles</h2><p>Article: Safety of continuous force feedback.</p>")
    b = document("<h2>Journal Articles</h2><p>Article: The impact of psychoemotional state.</p>")
    assert a.text_hash == b.text_hash


@pytest.mark.parametrize(
    "heading", ["Journal Articles", "Clinical Trials", "Start Here", "Related Issues"]
)
def test_link_list_headings_are_recognised(heading: str) -> None:
    assert is_link_list(heading)


def test_a_clinical_heading_is_not_a_link_list() -> None:
    assert not is_link_list("Symptoms of endometriosis")


# --------------------------------------------------------------------------
# Encoding defences — quotes must be findable in the source
# --------------------------------------------------------------------------


def test_non_breaking_space_becomes_a_real_space() -> None:
    """The worst corruption: looks identical, breaks matching silently."""
    html = "<p>Heavy\u00a0bleeding or painful periods that affect your daily life.</p>"
    assert "\u00a0" not in paragraphs(html)[0]
    assert paragraphs(html)[0].startswith("Heavy bleeding")


@pytest.mark.parametrize("invisible", ["\u200b", "\u200c", "\u200d", "\u00ad"])
def test_zero_width_characters_are_removed(invisible: str) -> None:
    html = f"<p>Heavy{invisible} bleeding or painful periods affecting daily life.</p>"
    assert invisible not in paragraphs(html)[0]


def test_text_is_normalised_to_nfc() -> None:
    """Decomposed and composed forms must not produce two different quotes."""
    decomposed = "<p>Pain in the abdome\u0301n region that lasts several days here.</p>"
    composed = "<p>Pain in the abdom\u00e9n region that lasts several days here.</p>"
    assert paragraphs(decomposed) == paragraphs(composed)


def test_real_source_characters_are_preserved() -> None:
    """Em-dashes and curly quotes are real text, not corruption to be tidied."""
    sentence = "No menstrual periods\u2014called amenorrhea, which is a real finding."
    assert "\u2014" in paragraphs(f"<p>{sentence}</p>")[0]


def test_replacement_characters_are_refused_not_kept() -> None:
    """U+FFFD means a decode already failed, so the text is lossy."""
    from herhealth_data.ingest.clean import DecodingError

    with pytest.raises(DecodingError, match=r"U\+FFFD"):
        clean_html("<p>Heavy bleeding\ufffd or painful periods affecting daily life.</p>")
