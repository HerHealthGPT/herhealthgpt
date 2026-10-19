---
status: proposed
---

# She may keep an uploaded file on the server for 30 days

> **Proposed, not accepted.** An in-session product decision, 2026-10-19,
> taken with the person building the app, the same gate
> [ADR 0019](0019-cycle-data-is-imported-from-any-tracker-and-may-pre-fill-answers.md)
> named for itself. It reverses one sentence of ADR 0019 — "the file itself
> is never stored" — for files she explicitly chooses to keep. Read the risk
> register first.

## Context

ADR 0019 reads a tracker export, keeps only closed-vocabulary values and
dates, and discards the file. That is still the right default for what
reaches triage. But the file has a use of its own the extraction cannot
replace: a woman going to an appointment may want the export or the PDF
report her app produced, and on a shared or replaced phone she may no longer
have it.

The request was to let her upload such files, keep them on the production
server (one EC2 host; its encrypted root disk is 60 GB by the Terraform
default, `root_volume_gb`), and delete them
automatically after a set time.

## Decision

1. **Kept only when she asks.** Settings has a **Your files** card with its
   own upload button, and the cycle-data preview has an unticked box, "Also
   keep a copy of this file for 30 days". Importing cycle data never keeps
   the file by itself.
2. **Only the kinds of file the import reads**: CSV, JSON, XML, plain text,
   zip, PDF. The extension must match the first bytes (`%PDF`, `PK\x03\x04`,
   or UTF-8 text without NUL bytes). No images and no arbitrary documents:
   this is cycle data, not a general medical-records store.
3. **Kept for 30 days, then deleted automatically.** `expires_at` is set at
   upload. A file past it is never listed or served, whatever the clean-up
   has done; the backend deletes expired rows and their bytes at start-up and
   then hourly. She can delete a file at any time, and deleting her account
   deletes all of them.
4. **Nothing reads a kept file.** It is never parsed, never sent to a model
   and never part of a consultation. It exists only so she can download it.
5. **On the server's own disk**, under `HERHEALTH_UPLOAD_DIR`, as
   `<user id>/<file id>`. The filename she gave is kept in the
   `stored_files` table for display and download only; it never becomes part
   of a path. In production that directory is the named Docker volume
   `herhealth_uploads`, which survives every release because the compose
   project name is fixed and the deploy never removes volumes.
6. **Limits**: 100 MB per file, 10 files and 300 MB per account, and uploads
   are refused while the disk has less than 2 GB free, because the same disk
   holds the images, logs and the next release.
7. **Downloads are always attachments**, with `Cache-Control: no-store` and
   `nosniff`, so a browser saves the file rather than rendering it. Another
   account's file id is answered exactly as one that does not exist.

## What this does not change

- What reaches triage: still only the confirmed `CycleExtraction`
  (ADR 0019), never file content.
- The four pre-fill rules in ADR 0019 and the red-flag test that guards them.
- The rule that nothing is kept until she confirms: a file is kept only when
  she uploads it to **Your files** or ticks the box.

## Risk register

- **Health data now sits on the application host, not only in RDS.** The
  root volume is encrypted at rest (`infra/terraform/prod/ec2.tf`), but files
  are not encrypted per user by the application. Anyone with shell access to
  the host can read them. Same exposure as the health note and cycle data in
  RDS to someone holding the database password, on a different system.
- **No backup.** Nothing snapshots the root volume. If the instance is
  replaced (`monitoring.tf` recovers the same volume on hardware failure, but
  a rebuild from Terraform would not), kept files are lost. Acceptable for a
  30-day convenience copy; not acceptable if this ever becomes her only copy
  of anything, and the UI does not claim otherwise.
- **Deletion is hourly, not instant, on the disk.** An expired file is
  inaccessible from the moment it expires but stays on disk until the next
  pass, at most an hour. If the backend is down, it stays until it is back.
- **The disk is shared.** The free-space floor stops uploads before the disk
  fills, but a disk filled by something else (logs, images) will refuse
  uploads too, with "We can't keep files right now".
- **A file deleted from the database but not the disk** (a crash between
  the two) is orphaned: unreachable, but not removed by the hourly pass,
  which works from the table. Account deletion removes her whole directory,
  orphans included.
