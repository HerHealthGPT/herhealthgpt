"""The page-style informational answer: sectioned search, layout, attribution."""

from __future__ import annotations

from collections.abc import Sequence

from herhealth_contracts.retrieval import PassageType, RetrievedPassage
from langchain_core.messages import AIMessage

from herhealth_backend.triage.chain import (
    PAGE_SECTIONS,
    LangChainAnswerWriter,
    shape_page,
)

HEADINGS = [title for title, _ in PAGE_SECTIONS]

PAGE = (
    "Overview: PCOS is a hormonal condition.\n"
    "Symptoms:\n- Irregular periods\n- Extra hair growth\n"
    "**Causes:** The cause is not known.\n"
    "Treatment: Medicines and lifestyle changes may help."
)


def _passage(index: int) -> RetrievedPassage:
    return RetrievedPassage(
        id=f"{index:016x}",
        text=f"Sentence number {index} about the condition.",
        citation="womenshealth.gov",
        source_id="womenshealth",
        url="https://www.womenshealth.gov/a-z-topics/pcos",
        score=0.5,
        passage_type=PassageType.SOURCE_PASSAGE,
    )


def _sections(filled: int = 4) -> list[tuple[str, Sequence[RetrievedPassage]]]:
    return [
        (title, [_passage(index)] if index < filled else []) for index, title in enumerate(HEADINGS)
    ]


class _Chat:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    def invoke(self, messages: list[object]) -> AIMessage:
        self.calls += 1
        return AIMessage(content=self.reply)


def test_a_heading_with_text_on_its_line_is_split_so_it_renders() -> None:
    page = shape_page(PAGE, HEADINGS)

    assert page is not None
    lines = page.splitlines()
    assert "Overview:" in lines
    assert "PCOS is a hormonal condition." in lines
    assert "Causes:" in lines
    assert "- Irregular periods" in lines


def test_a_reply_without_the_sections_is_not_a_page() -> None:
    assert shape_page("PCOS is a hormonal condition. See a clinician.", HEADINGS) is None
    assert shape_page("Overview: one.\nSymptoms: two.", HEADINGS) is None


def test_the_first_writer_is_named_when_it_returns_a_page() -> None:
    adapter, base = _Chat(PAGE), _Chat(PAGE)
    writer = LangChainAnswerWriter(
        adapter, name="herhealth", fallback_chat=base, fallback_name="base"
    )

    page = writer.write_page("What is PCOS?", _sections(), "A short answer.")

    assert page is not None
    assert page[1] == "herhealth"
    assert base.calls == 0


def test_the_fallback_writes_and_is_named_when_the_first_reply_is_not_a_page() -> None:
    adapter, base = _Chat("PCOS is a hormonal condition."), _Chat(PAGE)
    writer = LangChainAnswerWriter(
        adapter, name="herhealth", fallback_chat=base, fallback_name="base"
    )

    page = writer.write_page("What is PCOS?", _sections(), "A short answer.")

    assert page is not None
    assert page[1] == "base"


def test_no_page_when_neither_writer_returns_one() -> None:
    writer = LangChainAnswerWriter(
        _Chat("Short."), name="herhealth", fallback_chat=_Chat("Also short."), fallback_name="b"
    )

    assert writer.write_page("What is PCOS?", _sections(), "A short answer.") is None


def test_no_page_is_attempted_when_the_search_found_too_little() -> None:
    adapter = _Chat(PAGE)
    writer = LangChainAnswerWriter(adapter, name="herhealth")

    assert writer.write_page("What is PCOS?", _sections(filled=0), "A short answer.") is None
    assert adapter.calls == 0


def test_warning_lines_from_the_base_answer_are_carried_onto_the_page() -> None:
    writer = LangChainAnswerWriter(_Chat(PAGE), name="herhealth")
    base_answer = "PCOS is common.\nGet emergency care now if you have severe pain."

    page = writer.write_page("What is PCOS?", _sections(), base_answer)

    assert page is not None
    assert "Get emergency care now if you have severe pain." in page[0]


def test_a_page_with_internal_wording_is_refused() -> None:
    leaked = PAGE + "\nThe action_code is ROUTINE_APPOINTMENT."
    writer = LangChainAnswerWriter(_Chat(leaked), name="herhealth")

    assert writer.write_page("What is PCOS?", _sections(), "A short answer.") is None
