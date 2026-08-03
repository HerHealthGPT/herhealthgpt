"""Tests for fetch orchestration — the policy, not the mechanism.

The four checks in order: licence guard, immutability, dry run, then fetch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import forbidden, make_plan, make_target, recording, responds
from herhealth_data.ingest import FetchOutcome, RawStore, fetch_all

# --------------------------------------------------------------------------
# 1. Nothing fetches by accident
# --------------------------------------------------------------------------


def test_dry_run_is_the_default(store: RawStore) -> None:
    records = fetch_all(make_plan(), store, forbidden)
    assert [r.outcome for r in records] == [FetchOutcome.PLANNED]


def test_dry_run_writes_nothing(store: RawStore, tmp_path: Path) -> None:
    fetch_all(make_plan(), store, forbidden)
    assert not list(tmp_path.rglob("*.html"))
    assert not list(tmp_path.rglob("manifest.jsonl"))


# --------------------------------------------------------------------------
# 2. The licence guard runs before any request
# --------------------------------------------------------------------------


def test_barred_url_is_never_requested(store: RawStore, tmp_path: Path) -> None:
    adam = make_target(source_id="medlineplus", slug="adam", url="https://medlineplus.gov/ency/x")
    records = fetch_all(
        make_plan(adam, exclusions={"medlineplus": ("/ency/",)}),
        store,
        forbidden,  # raises if a request is attempted
        dry_run=False,
    )
    assert records[0].outcome == FetchOutcome.EXCLUDED
    assert "/ency/" in (records[0].detail or "")
    assert not list(tmp_path.rglob("*.html"))


def test_the_guard_precedes_even_the_immutability_check(store: RawStore) -> None:
    """A barred URL stays barred even if a file happens to exist for it."""
    adam = make_target(source_id="medlineplus", slug="adam", url="https://medlineplus.gov/ency/x")
    store.save(adam, b"<html>should not matter</html>")

    records = fetch_all(
        make_plan(adam, exclusions={"medlineplus": ("/ency/",)}), store, forbidden, dry_run=False
    )
    assert records[0].outcome == FetchOutcome.EXCLUDED


# --------------------------------------------------------------------------
# 3. Immutability
# --------------------------------------------------------------------------


def test_existing_document_is_left_untouched(store: RawStore) -> None:
    target = make_target()
    store.save(target, b"original")

    records = fetch_all(make_plan(target), store, forbidden, dry_run=False)

    assert records[0].outcome == FetchOutcome.ALREADY_PRESENT
    assert store.read(target) == b"original"


def test_already_present_still_reports_a_hash(store: RawStore) -> None:
    """The lock must describe the corpus, not only the documents fetched today."""
    store.save(make_target(), b"original")
    records = fetch_all(make_plan(), store, forbidden, dry_run=False)
    assert records[0].content_hash
    assert records[0].bytes == len(b"original")


# --------------------------------------------------------------------------
# 4. Fetching
# --------------------------------------------------------------------------


def test_successful_fetch_is_written_and_recorded(store: RawStore) -> None:
    records = fetch_all(make_plan(), store, responds(b"<html>ok</html>"), dry_run=False)

    assert records[0].outcome == FetchOutcome.FETCHED
    assert records[0].http_status == 200
    assert records[0].fetched_at
    assert store.read(make_target()) == b"<html>ok</html>"


@pytest.mark.parametrize("status", [301, 403, 404, 500, 503])
def test_non_200_writes_nothing(store: RawStore, tmp_path: Path, status: int) -> None:
    records = fetch_all(
        make_plan(), store, responds(b"<html>error page</html>", status), dry_run=False
    )
    assert records[0].outcome == FetchOutcome.FAILED
    assert records[0].http_status == status
    assert not list(tmp_path.rglob("*.html"))


def test_empty_body_counts_as_failure(store: RawStore) -> None:
    records = fetch_all(make_plan(), store, responds(b""), dry_run=False)
    assert records[0].outcome == FetchOutcome.FAILED


def test_the_configured_agent_reaches_the_transport(store: RawStore) -> None:
    seen: list[tuple[str, str]] = []
    plan = make_plan(
        make_target(source_id="cdc"),
        user_agents={"cdc": "curl/8.0 HerHealthGPT-research/0.1"},
    )
    fetch_all(plan, store, recording(seen), dry_run=False)
    assert seen[0][1] == "curl/8.0 HerHealthGPT-research/0.1"


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def test_every_target_gets_a_record_in_plan_order(store: RawStore) -> None:
    """A report that omits refused or failed targets is a report that hides them."""
    plan = make_plan(
        make_target(slug="first"),
        make_target(source_id="medlineplus", slug="barred", url="https://medlineplus.gov/ency/x"),
        make_target(slug="third"),
        exclusions={"medlineplus": ("/ency/",)},
    )
    records = fetch_all(plan, store, responds(), dry_run=False)

    assert [r.slug for r in records] == ["first", "barred", "third"]
    assert [r.outcome for r in records] == [
        FetchOutcome.FETCHED,
        FetchOutcome.EXCLUDED,
        FetchOutcome.FETCHED,
    ]


def test_manifests_are_written_on_a_real_run(store: RawStore, tmp_path: Path) -> None:
    fetch_all(make_plan(), store, responds(), dry_run=False)
    assert list(tmp_path.rglob("manifest.jsonl"))
