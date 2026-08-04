"""Tests for the immutable raw document store."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from ingest_factories import DATE, make_target

from herhealth_data.ingest import (
    FetchOutcome,
    FetchRecord,
    RawStore,
    content_hash,
    read_lock,
    write_lock,
)

# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------


def test_documents_land_in_a_dated_directory(store: RawStore, tmp_path: Path) -> None:
    assert store.path_for(make_target()) == tmp_path / "nichd" / DATE / "pcos.html"


def test_a_different_date_is_a_different_location(tmp_path: Path) -> None:
    today = RawStore(tmp_path, DATE)
    later = RawStore(tmp_path, "2026-09-01")
    assert today.path_for(make_target()) != later.path_for(make_target())


# --------------------------------------------------------------------------
# Immutability
# --------------------------------------------------------------------------


def test_save_writes_and_creates_parents(store: RawStore) -> None:
    written = store.save(make_target(), b"<html>x</html>")
    assert written.read_bytes() == b"<html>x</html>"


def test_save_refuses_to_overwrite(store: RawStore) -> None:
    target = make_target()
    store.save(target, b"original")
    with pytest.raises(FileExistsError, match="immutable"):
        store.save(target, b"replacement")
    assert store.read(target) == b"original"


def test_snapshots_coexist_rather_than_replacing(tmp_path: Path) -> None:
    RawStore(tmp_path, DATE).save(make_target(), b"old")
    RawStore(tmp_path, "2026-09-01").save(make_target(), b"new")

    assert RawStore(tmp_path, DATE).read(make_target()) == b"old"
    assert RawStore(tmp_path, "2026-09-01").read(make_target()) == b"new"


def test_has_is_false_before_and_true_after(store: RawStore) -> None:
    target = make_target()
    assert not store.has(target)
    store.save(target, b"x")
    assert store.has(target)


# --------------------------------------------------------------------------
# Reading, for the clean stage
# --------------------------------------------------------------------------


def test_documents_is_empty_when_nothing_is_stored(store: RawStore) -> None:
    assert list(store.documents()) == []


def test_documents_yields_every_stored_document_sorted(store: RawStore) -> None:
    store.save(make_target(source_id="nichd", slug="pcos"), b"a")
    store.save(make_target(source_id="nichd", slug="fibroids"), b"b")
    store.save(make_target(source_id="medlineplus", slug="pcos"), b"c")

    found = [(d.source_id, d.slug) for d in store.documents()]
    assert found == [("medlineplus", "pcos"), ("nichd", "fibroids"), ("nichd", "pcos")]


def test_documents_ignores_other_dates(tmp_path: Path) -> None:
    RawStore(tmp_path, "2026-09-01").save(make_target(), b"later")
    assert list(RawStore(tmp_path, DATE).documents()) == []


def test_documents_can_be_read(store: RawStore) -> None:
    store.save(make_target(), b"<html>body</html>")
    document = next(iter(store.documents()))
    assert document.read_bytes() == b"<html>body</html>"


# --------------------------------------------------------------------------
# Hashing
# --------------------------------------------------------------------------


def test_hash_is_a_full_sha256() -> None:
    body = b"<html>known</html>"
    assert content_hash(body) == hashlib.sha256(body).hexdigest()
    assert len(content_hash(body)) == 64


# --------------------------------------------------------------------------
# Manifests
# --------------------------------------------------------------------------


def record(**overrides: object) -> FetchRecord:
    base = FetchRecord(
        source_id="nichd",
        slug="pcos",
        url="https://www.nichd.nih.gov/health/topics/pcos",
        licence="US federal government work, public domain",
        outcome=FetchOutcome.FETCHED,
        fetched_at="2026-08-03T12:00:00Z",
        content_hash="a" * 64,
        bytes=100,
    )
    return base.with_(**overrides)


def test_manifest_carries_the_required_provenance_fields(store: RawStore) -> None:
    store.write_manifests([record()])
    written = (store.directory_for("nichd") / "manifest.jsonl").read_text(encoding="utf-8")
    entry = json.loads(written.strip())
    for required in ("url", "fetched_at", "content_hash", "licence"):
        assert required in entry, f"provenance field missing: {required}"


def test_manifest_omits_unusable_records(store: RawStore) -> None:
    store.write_manifests(
        [record(), record(slug="barred", outcome=FetchOutcome.EXCLUDED, content_hash=None)]
    )
    written = (store.directory_for("nichd") / "manifest.jsonl").read_text(encoding="utf-8")
    assert "barred" not in written


def test_manifest_is_written_per_source(store: RawStore) -> None:
    written = store.write_manifests([record(), record(source_id="medlineplus")])
    assert {p.parent.parent.name for p in written} == {"nichd", "medlineplus"}


# --------------------------------------------------------------------------
# The tracked lockfile
# --------------------------------------------------------------------------


def test_round_trips(tmp_path: Path) -> None:
    path = write_lock([record()], tmp_path / "lock.jsonl", DATE)
    entries = read_lock(path)
    assert len(entries) == 1
    assert entries[0]["url"] == "https://www.nichd.nih.gov/health/topics/pcos"


def test_reading_a_missing_lock_is_not_an_error(tmp_path: Path) -> None:
    assert read_lock(tmp_path / "absent.jsonl") == []


def test_rows_are_sorted_so_diffs_stay_readable(tmp_path: Path) -> None:
    records = [
        record(source_id="nichd", slug="pcos"),
        record(source_id="medlineplus", slug="fibroids"),
        record(source_id="nichd", slug="endometriosis"),
    ]
    entries = read_lock(write_lock(records, tmp_path / "lock.jsonl", DATE))
    assert [(e["source_id"], e["slug"]) for e in entries] == [
        ("medlineplus", "fibroids"),
        ("nichd", "endometriosis"),
        ("nichd", "pcos"),
    ]


def test_unusable_records_are_excluded(tmp_path: Path) -> None:
    """An excluded or failed document has no bytes; listing it would imply it does."""
    records = [
        record(),
        record(slug="barred", outcome=FetchOutcome.EXCLUDED, content_hash=None, bytes=None),
        record(slug="missing", outcome=FetchOutcome.FAILED, content_hash=None, bytes=None),
    ]
    entries = read_lock(write_lock(records, tmp_path / "lock.jsonl", DATE))
    assert [e["slug"] for e in entries] == ["pcos"]


def test_hash_is_carried_so_upstream_drift_shows_in_a_diff(tmp_path: Path) -> None:
    entries = read_lock(write_lock([record()], tmp_path / "lock.jsonl", DATE))
    assert len(str(entries[0]["content_hash"])) == 64
    assert entries[0]["licence"]
    assert entries[0]["fetched_on"] == DATE


def test_header_is_comments_only(tmp_path: Path) -> None:
    path = write_lock([record()], tmp_path / "lock.jsonl", DATE)
    header = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith("#")]
    assert header and all(ln.startswith("#") for ln in header)
