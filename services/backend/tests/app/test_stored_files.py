"""Kept files, without a database: names, types and the disk (ADR 0020)."""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest

from herhealth_backend.app.accounts.errors import StoredFileRejected
from herhealth_backend.app.accounts.stored_files import (
    FileStore,
    _content_type,
    safe_filename,
)


@pytest.mark.parametrize(
    ("given", "kept"),
    [
        ("export.csv", "export.csv"),
        ("../../etc/passwd.csv", "passwd.csv"),
        ("C:\\Users\\her\\cycle.pdf", "cycle.pdf"),
        (".hidden.csv", "hidden.csv"),
        ("bad\x00name\n.csv", "badname.csv"),
        ("دورتي.csv", "دورتي.csv"),
        (None, "file"),
    ],
)
def test_a_filename_keeps_only_its_last_part_and_printable_characters(
    given: str | None, kept: str
) -> None:
    assert safe_filename(given) == kept


def test_a_long_filename_keeps_its_extension() -> None:
    name = safe_filename("a" * 300 + ".csv")
    assert len(name) == 120
    assert name.endswith(".csv")


@pytest.mark.parametrize(
    ("name", "head", "content_type"),
    [
        ("cycle.csv", b"date,flow\n2026-10-01,heavy\n", "text/csv"),
        ("report.pdf", b"%PDF-1.7\n", "application/pdf"),
        ("export.zip", b"PK\x03\x04rest", "application/zip"),
        ("notes.txt", "الدورة".encode(), "text/plain"),
    ],
)
def test_the_accepted_kinds_are_stored_with_their_type(
    name: str, head: bytes, content_type: str
) -> None:
    assert _content_type(name, head) == content_type


@pytest.mark.parametrize(
    ("name", "head"),
    [
        ("photo.jpg", b"\xff\xd8\xff"),
        ("page.html", b"<html>"),
        ("fake.pdf", b"<html><script>"),
        ("fake.zip", b"%PDF-1.7"),
        ("binary.csv", b"MZ\x90\x00\x03"),
    ],
)
def test_anything_else_is_refused(name: str, head: bytes) -> None:
    with pytest.raises(StoredFileRejected, match="unsupported_type"):
        _content_type(name, head)


def test_a_file_is_written_under_its_ids_and_hashed(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    user_id, file_id = uuid.uuid4(), uuid.uuid4()
    size, sha256 = store.write(user_id, file_id, io.BytesIO(b"date,flow\n"), limit=100)
    assert size == 10
    assert len(sha256) == 64
    assert store.path_for(user_id, file_id).read_bytes() == b"date,flow\n"


def test_a_file_over_the_limit_leaves_nothing_behind(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    user_id, file_id = uuid.uuid4(), uuid.uuid4()
    with pytest.raises(StoredFileRejected, match="too_large"):
        store.write(user_id, file_id, io.BytesIO(b"x" * 101), limit=100)
    assert list((tmp_path / str(user_id)).iterdir()) == []


def test_removing_her_account_removes_her_directory_only(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    her, other = uuid.uuid4(), uuid.uuid4()
    store.write(her, uuid.uuid4(), io.BytesIO(b"a"), limit=10)
    store.write(other, uuid.uuid4(), io.BytesIO(b"b"), limit=10)
    store.remove_user(her)
    assert not (tmp_path / str(her)).exists()
    assert (tmp_path / str(other)).exists()
