"""Files she chose to keep, on the server's own disk, for 30 days (ADR 0020).

Only the kinds of file the cycle-data import reads: CSV, JSON, XML, plain
text, a zip (an Apple Health export) and PDF. A file is kept so she can open
or download it again; nothing reads it, and it never reaches a model. Its
cycle data, if she imports it, is kept separately (ADR 0019).

Three limits, all checked before anything is written:

* one file at most ``MAX_FILE_BYTES``;
* ``MAX_FILES_PER_USER`` files and ``MAX_BYTES_PER_USER`` bytes per account;
* the disk keeps ``MIN_FREE_BYTES`` free, because it is the same disk the
  images, logs and the next release are written to.

On disk a file is ``<root>/<user id>/<file id>``: no name she chose ever
becomes part of a path, and deleting her account removes one directory. The
filename she gave is kept only in the database, for display and download.

The file is not encrypted by this module. The EC2 root volume is encrypted
at rest (``infra/terraform/prod/ec2.tf``), the same protection the cycle data
and health note get in RDS.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import IO

from anyio import to_thread
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.errors import StoredFileRejected
from herhealth_backend.app.accounts.models import StoredFile

__all__ = [
    "ALLOWED_TYPES",
    "MAX_BYTES_PER_USER",
    "MAX_FILES_PER_USER",
    "MAX_FILE_BYTES",
    "MIN_FREE_BYTES",
    "RETENTION",
    "FileStore",
    "add_file",
    "delete_file",
    "file_for",
    "files_for",
    "purge_expired",
    "safe_filename",
]

logger = logging.getLogger(__name__)

#: How long a file is kept before it is deleted automatically.
RETENTION = timedelta(days=30)

MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_FILES_PER_USER = 10
MAX_BYTES_PER_USER = 300 * 1024 * 1024
MIN_FREE_BYTES = 2 * 1024 * 1024 * 1024

#: Extension to the type it is served back as. Matches the import's file
#: picker (``cycle-data-import.tsx``).
ALLOWED_TYPES = {
    ".csv": "text/csv",
    ".json": "application/json",
    ".xml": "application/xml",
    ".txt": "text/plain",
    ".zip": "application/zip",
    ".pdf": "application/pdf",
}

_CHUNK = 1024 * 1024


def safe_filename(name: str | None) -> str:
    """Her filename, made safe to show and to put in a download header.

    The last path component only, control characters removed, at most 120
    characters with the extension kept.
    """
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = "".join(ch for ch in base if unicodedata.category(ch)[0] != "C").strip()
    base = base.lstrip(".") or "file"
    if len(base) > 120:
        stem, dot, ext = base.rpartition(".")
        base = f"{stem[: 119 - len(ext)]}.{ext}" if dot and len(ext) <= 10 else base[:120]
    return base


def _content_type(filename: str, head: bytes) -> str:
    """The type it is stored as, or reject it. The extension says what it
    claims to be; the first bytes have to agree."""
    extension = Path(filename).suffix.lower()
    content_type = ALLOWED_TYPES.get(extension)
    if content_type is None:
        raise StoredFileRejected("unsupported_type")
    if extension == ".pdf" and not head.startswith(b"%PDF"):
        raise StoredFileRejected("unsupported_type")
    if extension == ".zip" and not head.startswith(b"PK\x03\x04"):
        raise StoredFileRejected("unsupported_type")
    if extension not in (".pdf", ".zip"):
        if b"\x00" in head:
            raise StoredFileRejected("unsupported_type")
        try:
            head.decode("utf-8")
        except UnicodeDecodeError as error:
            # A multi-byte character may be cut at the end of the sample.
            if error.start < len(head) - 4:
                raise StoredFileRejected("unsupported_type") from error
    return content_type


class FileStore:
    """The directory files are kept in. One per deployment."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, user_id: uuid.UUID, file_id: uuid.UUID) -> Path:
        return self.root / str(user_id) / str(file_id)

    def free_bytes(self) -> int:
        self.root.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(self.root).free

    def write(
        self, user_id: uuid.UUID, file_id: uuid.UUID, stream: IO[bytes], limit: int
    ) -> tuple[int, str]:
        """Copy ``stream`` in, refusing it past ``limit`` bytes. Returns its
        size and SHA-256. Written under a temporary name and renamed, so a
        failed upload never leaves half a file behind under a real id."""
        target = self.path_for(user_id, file_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f".{file_id}.partial")
        digest = hashlib.sha256()
        size = 0
        try:
            with partial.open("wb") as out:
                while chunk := stream.read(_CHUNK):
                    size += len(chunk)
                    if size > limit:
                        raise StoredFileRejected("too_large")
                    digest.update(chunk)
                    out.write(chunk)
            os.replace(partial, target)
        finally:
            partial.unlink(missing_ok=True)
        return size, digest.hexdigest()

    def remove(self, user_id: uuid.UUID, file_id: uuid.UUID) -> None:
        self.path_for(user_id, file_id).unlink(missing_ok=True)

    def remove_user(self, user_id: uuid.UUID) -> None:
        shutil.rmtree(self.root / str(user_id), ignore_errors=True)


def _now() -> datetime:
    return datetime.now(UTC)


async def files_for(session: AsyncSession, user_id: uuid.UUID) -> list[StoredFile]:
    """Her files, newest first. An expired file is not listed even before
    the clean-up has removed it."""
    rows = await session.scalars(
        select(StoredFile)
        .where(StoredFile.user_id == user_id, StoredFile.expires_at > _now())
        .order_by(StoredFile.created_at.desc())
    )
    return list(rows)


async def file_for(
    session: AsyncSession, user_id: uuid.UUID, file_id: uuid.UUID
) -> StoredFile | None:
    """One of HER files, unexpired, or ``None``: another account's file id
    is answered exactly like one that does not exist."""
    row = await session.get(StoredFile, file_id)
    if row is None or row.user_id != user_id or row.expires_at <= _now():
        return None
    return row


async def add_file(
    session: AsyncSession,
    store: FileStore,
    user_id: uuid.UUID,
    *,
    filename: str | None,
    stream: IO[bytes],
    declared_size: int | None,
) -> StoredFile:
    """Check, write and record one file. Caller commits."""
    name = safe_filename(filename)
    if declared_size is not None and declared_size > MAX_FILE_BYTES:
        raise StoredFileRejected("too_large")
    head = stream.read(4096)
    stream.seek(0)
    content_type = _content_type(name, head)

    count, used = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(StoredFile.size_bytes), 0)).where(
                StoredFile.user_id == user_id, StoredFile.expires_at > _now()
            )
        )
    ).one()
    if count >= MAX_FILES_PER_USER:
        raise StoredFileRejected("too_many_files")
    room = MAX_BYTES_PER_USER - int(used)
    if room <= 0:
        raise StoredFileRejected("account_full")
    if store.free_bytes() < MIN_FREE_BYTES + min(room, MAX_FILE_BYTES):
        logger.warning("stored files: disk below its free-space floor; refusing uploads")
        raise StoredFileRejected("storage_full")

    file_id = uuid.uuid4()
    try:
        size, sha256 = await to_thread.run_sync(
            store.write, user_id, file_id, stream, min(MAX_FILE_BYTES, room)
        )
    except StoredFileRejected as error:
        if error.reason == "too_large" and room < MAX_FILE_BYTES:
            raise StoredFileRejected("account_full") from error
        raise
    now = _now()
    row = StoredFile(
        id=file_id,
        user_id=user_id,
        filename=name,
        content_type=content_type,
        size_bytes=size,
        sha256=sha256,
        created_at=now,
        expires_at=now + RETENTION,
    )
    session.add(row)
    try:
        await session.flush()
    except Exception:
        store.remove(user_id, file_id)
        raise
    return row


async def delete_file(session: AsyncSession, store: FileStore, row: StoredFile) -> None:
    """Delete one file, the row first. Caller commits."""
    await session.delete(row)
    await session.flush()
    store.remove(row.user_id, row.id)


async def purge_expired(session: AsyncSession, store: FileStore) -> int:
    """Delete every file past its date. Returns how many. Commits."""
    removed = (
        await session.execute(
            delete(StoredFile)
            .where(StoredFile.expires_at <= _now())
            .returning(StoredFile.user_id, StoredFile.id)
        )
    ).all()
    await session.commit()
    for user_id, file_id in removed:
        store.remove(user_id, file_id)
    return len(removed)
