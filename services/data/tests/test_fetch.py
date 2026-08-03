"""Tests for the source fetcher.

Not one of these opens a socket. Every test injects a fake transport, and the
one that asserts a licence guard works proves it by making the transport raise
if it is ever called.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from herhealth_data.ingest.fetch import (
    FetchOutcome,
    FetchPlan,
    Target,
    fetch_all,
    load_plan,
    write_lock,
)

DATE = "2026-08-03"


def target(**overrides: str) -> Target:
    values = {
        "source_id": "nichd",
        "slug": "pcos",
        "url": "https://www.nichd.nih.gov/health/topics/pcos",
        "licence": "US federal government work, public domain",
    }
    values.update(overrides)
    return Target(**values)  # type: ignore[arg-type]


def plan(*targets: Target, exclusions: dict[str, tuple[str, ...]] | None = None) -> FetchPlan:
    return FetchPlan(
        targets=targets or (target(),),
        excluded_path_fragments=exclusions or {},
    )


def ok(body: bytes = b"<html>content</html>"):  # noqa: ANN201 - test helper
    def transport(url: str, user_agent: str) -> tuple[int, bytes]:
        return 200, body

    return transport


def exploding(url: str, user_agent: str = "") -> tuple[int, bytes]:
    raise AssertionError(f"the network must not be touched, but {url} was requested")


# --------------------------------------------------------------------------
# Nothing fetches by accident
# --------------------------------------------------------------------------


def test_dry_run_is_the_default_and_makes_no_request(tmp_path: Path) -> None:
    records = fetch_all(plan(), tmp_path, DATE, exploding)
    assert [r.outcome for r in records] == [FetchOutcome.PLANNED]
    assert not list(tmp_path.rglob("*.html"))


def test_dry_run_writes_no_manifest(tmp_path: Path) -> None:
    fetch_all(plan(), tmp_path, DATE, exploding)
    assert not list(tmp_path.rglob("manifest.jsonl"))


# --------------------------------------------------------------------------
# The licence guard
# --------------------------------------------------------------------------


def test_excluded_url_is_refused_before_any_request(tmp_path: Path) -> None:
    adam = target(source_id="medlineplus", slug="adam", url="https://medlineplus.gov/ency/x.htm")
    records = fetch_all(
        plan(adam, exclusions={"medlineplus": ("/ency/",)}),
        tmp_path,
        DATE,
        exploding,  # would raise if a request were attempted
        dry_run=False,
    )
    assert records[0].outcome == FetchOutcome.EXCLUDED
    assert "/ency/" in (records[0].detail or "")
    assert not list(tmp_path.rglob("*.html"))


def test_guard_is_scoped_to_its_source(tmp_path: Path) -> None:
    """An /ency/ rule for medlineplus must not silently block another source."""
    other = target(source_id="nichd", url="https://www.nichd.nih.gov/ency/thing")
    records = fetch_all(
        plan(other, exclusions={"medlineplus": ("/ency/",)}),
        tmp_path,
        DATE,
        ok(),
        dry_run=False,
    )
    assert records[0].outcome == FetchOutcome.FETCHED


def test_excluded_document_never_reaches_the_lock(tmp_path: Path) -> None:
    adam = target(source_id="medlineplus", slug="adam", url="https://medlineplus.gov/ency/x.htm")
    records = fetch_all(
        plan(adam, exclusions={"medlineplus": ("/ency/",)}),
        tmp_path,
        DATE,
        exploding,
        dry_run=False,
    )
    lock = tmp_path / "ingest.lock.jsonl"
    write_lock(records, lock, DATE)
    assert "/ency/" not in lock.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Per-source user agent
# --------------------------------------------------------------------------


def test_default_user_agent_identifies_the_project() -> None:
    from herhealth_data.ingest.fetch import USER_AGENT

    assert plan().user_agent_for(target()) == USER_AGENT
    assert "HerHealthGPT" in USER_AGENT


def test_override_applies_only_to_its_own_source() -> None:
    from herhealth_data.ingest.fetch import USER_AGENT

    configured = FetchPlan(
        targets=(target(), target(source_id="cdc")),
        excluded_path_fragments={},
        user_agents={"cdc": "curl/8.0 HerHealthGPT-research/0.1"},
    )
    assert configured.user_agent_for(target(source_id="cdc")).startswith("curl/8.0")
    assert configured.user_agent_for(target()) == USER_AGENT


def test_the_agent_reaches_the_transport(tmp_path: Path) -> None:
    seen: list[str] = []

    def recording(url: str, user_agent: str) -> tuple[int, bytes]:
        seen.append(user_agent)
        return 200, b"<html>x</html>"

    configured = FetchPlan(
        targets=(target(source_id="cdc"),),
        excluded_path_fragments={},
        user_agents={"cdc": "curl/8.0 HerHealthGPT-research/0.1"},
    )
    fetch_all(configured, tmp_path, DATE, recording, dry_run=False)
    assert seen == ["curl/8.0 HerHealthGPT-research/0.1"]


def test_no_configured_agent_impersonates_a_browser() -> None:
    """We work around a WAF by leading with a client token, not by pretending."""
    repo_root = Path(__file__).resolve().parents[3]
    loaded = load_plan(repo_root / "services" / "data" / "ingest_targets.yaml")
    for source_id, agent in loaded.user_agents.items():
        assert "HerHealthGPT" in agent, f"{source_id} agent must stay attributable"
        for browser in ("Mozilla", "Chrome", "Safari", "Firefox", "AppleWebKit"):
            assert browser not in agent, f"{source_id} agent impersonates {browser}"


# --------------------------------------------------------------------------
# Immutability
# --------------------------------------------------------------------------


def test_fetch_writes_to_a_dated_directory(tmp_path: Path) -> None:
    records = fetch_all(plan(), tmp_path, DATE, ok(), dry_run=False)
    written = tmp_path / "nichd" / DATE / "pcos.html"
    assert written.exists()
    assert records[0].outcome == FetchOutcome.FETCHED
    assert records[0].bytes == len(b"<html>content</html>")


def test_existing_file_is_never_overwritten(tmp_path: Path) -> None:
    destination = tmp_path / "nichd" / DATE / "pcos.html"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"original")

    records = fetch_all(plan(), tmp_path, DATE, exploding, dry_run=False)

    assert records[0].outcome == FetchOutcome.ALREADY_PRESENT
    assert destination.read_bytes() == b"original"


def test_a_later_date_makes_a_new_directory_rather_than_replacing(tmp_path: Path) -> None:
    fetch_all(plan(), tmp_path, DATE, ok(b"<html>old</html>"), dry_run=False)
    fetch_all(plan(), tmp_path, "2026-09-01", ok(b"<html>new</html>"), dry_run=False)

    assert (tmp_path / "nichd" / DATE / "pcos.html").read_bytes() == b"<html>old</html>"
    assert (tmp_path / "nichd" / "2026-09-01" / "pcos.html").read_bytes() == b"<html>new</html>"


# --------------------------------------------------------------------------
# Failures write nothing
# --------------------------------------------------------------------------


@pytest.mark.parametrize("status", [404, 403, 500, 503])
def test_non_200_writes_no_file(tmp_path: Path, status: int) -> None:
    def failing(url: str, user_agent: str) -> tuple[int, bytes]:
        return status, b"<html>error page</html>"

    records = fetch_all(plan(), tmp_path, DATE, failing, dry_run=False)

    assert records[0].outcome == FetchOutcome.FAILED
    assert records[0].http_status == status
    assert not list(tmp_path.rglob("*.html"))


def test_empty_body_counts_as_failure(tmp_path: Path) -> None:
    records = fetch_all(plan(), tmp_path, DATE, lambda url, ua: (200, b""), dry_run=False)
    assert records[0].outcome == FetchOutcome.FAILED


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------


def test_manifest_records_the_required_provenance_fields(tmp_path: Path) -> None:
    fetch_all(plan(), tmp_path, DATE, ok(), dry_run=False)
    manifest = (tmp_path / "nichd" / DATE / "manifest.jsonl").read_text(encoding="utf-8")
    record = json.loads(manifest.strip())
    for field in ("url", "fetched_at", "content_hash", "licence"):
        assert field in record, f"provenance field missing: {field}"


def test_hash_is_a_full_sha256_of_the_body(tmp_path: Path) -> None:
    import hashlib

    body = b"<html>known</html>"
    records = fetch_all(plan(), tmp_path, DATE, ok(body), dry_run=False)
    assert records[0].content_hash == hashlib.sha256(body).hexdigest()


def test_lock_is_sorted_so_diffs_are_readable(tmp_path: Path) -> None:
    targets = (
        target(source_id="medlineplus", slug="pcos", url="https://medlineplus.gov/a.html"),
        target(source_id="nichd", slug="fibroids"),
        target(source_id="nichd", slug="endometriosis"),
    )
    records = fetch_all(plan(*targets), tmp_path, DATE, ok(), dry_run=False)
    lock = tmp_path / "lock.jsonl"
    write_lock(records, lock, DATE)

    rows = [json.loads(x) for x in lock.read_text(encoding="utf-8").splitlines() if x[:1] == "{"]
    assert [(r["source_id"], r["slug"]) for r in rows] == [
        ("medlineplus", "pcos"),
        ("nichd", "endometriosis"),
        ("nichd", "fibroids"),
    ]


def test_lock_carries_the_hash_so_upstream_drift_shows_in_a_diff(tmp_path: Path) -> None:
    records = fetch_all(plan(), tmp_path, DATE, ok(), dry_run=False)
    lock = tmp_path / "lock.jsonl"
    write_lock(records, lock, DATE)
    row = json.loads([x for x in lock.read_text(encoding="utf-8").splitlines() if x[:1] == "{"][0])
    assert len(row["content_hash"]) == 64
    assert row["licence"]


# --------------------------------------------------------------------------
# The tracked target list
# --------------------------------------------------------------------------


def test_duplicate_targets_are_rejected(tmp_path: Path) -> None:
    targets_file = tmp_path / "targets.yaml"
    targets_file.write_text(
        "documents:\n"
        "  - {source_id: nichd, slug: pcos, url: 'https://a', licence: x}\n"
        "  - {source_id: nichd, slug: pcos, url: 'https://b', licence: x}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="overwrite each other"):
        load_plan(targets_file)


def test_the_real_targets_file_loads_and_guards_ency() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    loaded = load_plan(repo_root / "services" / "data" / "ingest_targets.yaml")

    assert loaded.targets, "no documents configured"
    assert loaded.excluded_path_fragments.get("medlineplus") == ("/ency/",)

    adam = Target("medlineplus", "x", "https://medlineplus.gov/ency/article/000369.htm", "n/a")
    assert loaded.excluded_reason(adam) == "/ency/"

    for configured in loaded.targets:
        assert loaded.excluded_reason(configured) is None, f"{configured.url} is self-excluded"
