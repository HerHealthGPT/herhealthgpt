#!/usr/bin/env python3
"""Reject the four things that let the 2026-09-17 contamination into this repo.

See docs/security/0001-injected-postcss-payload-and-leaked-env-backup.md. In
one commit titled "Add ingest_targets.yaml and Dockerfile for retrieval
service", a `git add -A` from a polluted working directory committed: a live
``OPENROUTER_API_KEY`` and session secret in ``infra/envs/backend.env.bak``, a
32,734-byte ``postcss.config.mjs`` whose payload was one 32,566-character line,
17 files of an unrelated "Blockchain Explorer" project under a new root-level
``public/``, and a 32,540-byte text file named ``fa-solid-600.eot`` posing as a
font. None of it was caught, by anything, for three weeks.

**Why a script in this repo rather than gitleaks or a scanning action.** The
incident was foreign code arriving through a path nobody was watching. Adding a
third-party scanner would mean trusting another supply chain to fix a supply
chain problem, and it would need a network fetch on every run. Five rules over
the stdlib are auditable in one sitting, run offline, and are the whole of what
this needs. Reach for a real scanner when these five stop being enough, not
before.

Stdlib only, Python 3.12. Two modes:

    python scripts/check_repo_hygiene.py              # every tracked file (CI)
    python scripts/check_repo_hygiene.py --staged     # what is about to be
                                                      # committed (git hook)

Exits 0 when clean, 1 with a report naming each file and the rule it broke.
Every rule is deliberately narrow: a check that cries wolf is a check somebody
disables, and a disabled check is how this happened in the first place.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass

#: Top-level entries this repo is allowed to have. The root-level ``public/``
#: that carried the blockchain project matched no CI path filter, so no
#: workflow ever looked at it — an allowlist is the only check that notices a
#: directory nobody thought to watch. Adding a real new top-level entry means
#: adding it here, in a reviewed diff, which is the point.
ALLOWED_ROOT_ENTRIES = frozenset(
    {
        ".claude",
        ".dockerignore",
        ".gitattributes",
        ".githooks",
        ".github",
        ".gitignore",
        ".python-version",
        "CLAUDE.md",
        "CONTEXT-MAP.md",
        "CONTEXT.md",
        "CONTRIBUTING.md",
        "HANDOFF.md",
        "Makefile",
        "README.md",
        "branch_structure.json",
        "docs",
        "infra",
        "knowledge",
        "packages",
        "pyproject.toml",
        "scripts",
        "services",
        "uv.lock",
    }
)

#: A file whose name says "environment file" may only be committed as an
#: example. ``*.env`` in .gitignore did not match ``backend.env.bak``, which is
#: exactly how three live credentials reached main; this rule matches on the
#: dot-separated *parts* of the name, so no new suffix can slip past a glob
#: again — ``backend.env.bak``, ``.env.local`` and ``prod.env.old`` all have
#: ``env`` as a part and all fail.
_ENV_FILE_ALLOWED_SUFFIX = (".example", ".sample", ".template")

#: ...but a source file merely *named* env is a module, not a secret store.
#: Alembic's own ``migrations/env.py`` is the case that proved this exclusion
#: necessary rather than hypothetical.
_SOURCE_SUFFIXES = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".go",
    ".rs",
    ".rb",
    ".java",
    ".sh",
    ".ps1",
    ".md",
)

#: Credential shapes specific enough to assert on sight, anywhere in the tree,
#: including documentation. Each requires a realistic length so that a
#: placeholder like ``sk-or-...`` in a runbook does not trip it.
VENDOR_SECRETS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("OpenRouter API key", re.compile(r"sk-or-v1-[A-Za-z0-9]{32,}")),
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_-]{32,}")),
    ("OpenAI API key", re.compile(r"sk-proj-[A-Za-z0-9_-]{32,}")),
    ("AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghs|ghr)_[A-Za-z0-9]{36,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("private key block", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
)

#: ``NAME=<long opaque value>`` for names that announce a secret. Narrower in
#: scope than the vendor patterns because the shape alone is weak evidence:
#: prose and schemas talk about tokens constantly, so this runs only over
#: config-ish files.
_ASSIGNED_SECRET = re.compile(
    r"\b([A-Z0-9_]*(?:SECRET|PASSWORD|API_?KEY|ACCESS_?TOKEN|AUTH_?TOKEN|PRIVATE_?KEY))"
    r"\s*[:=]\s*['\"]?([A-Za-z0-9+/_=-]{24,})['\"]?"
)
_ASSIGNED_SECRET_SCOPE = (
    ".env",
    ".cfg",
    ".conf",
    ".ini",
    ".sh",
    ".ps1",
    ".bat",
    ".mjs",
    ".cjs",
    ".js",
    ".ts",
    ".tsx",
    ".py",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
)
#: Values that look opaque but are not secrets. Keeps the dev-default database
#: password and obvious placeholders from failing every run.
#: ``[\w.-]*`` rather than ``\w*`` on purpose: real placeholders are written as
#: readable phrases, and the one in this repo —
#: ``test-only-session-secret-do-not-use-in-production`` — is hyphenated, so a
#: word-characters-only pattern called it a leaked credential.
_PLACEHOLDER = re.compile(
    r"^(?:x+|y+|0+|1+|changeme[\w.-]*|placeholder[\w.-]*|your[_-]?[\w.-]*|"
    r"example[\w.-]*|dummy[\w.-]*|fake[\w.-]*|sample[\w.-]*|test[\w.-]*|"
    r"redacted|none|null|true|false|herhealth)$",
    re.IGNORECASE,
)

#: The payload was one 32,566-character line. Legitimate long lines in this
#: repo are SVG path data (46 KB at most), one-object-per-line JSONL, lockfiles,
#: and saved source pages — all exempted below, which leaves this threshold
#: comfortably clear of anything real.
MAX_LINE_LENGTH = 5_000

#: Trees that legitimately hold minified or machine-written text.
EXEMPT_PREFIXES = (
    "raw/",
    "build/",
    "docs/research/sources/",
    "docs/submissions/",
)
EXEMPT_SUFFIXES = (
    ".svg",
    ".jsonl",
    ".lock",
    ".map",
    ".ipynb",
    ".csv",
    ".parquet",
)
EXEMPT_NAMES = ("package-lock.json", "uv.lock", "go.sum")

#: Generated by graphify and tracked on purpose: a single-file graph viewer
#: with its data inlined (one line of about 2.3 MB) and its label table (one
#: line of JSON). Named file by file, and exempt from the line-length rule
#: ONLY — unlike EXEMPT_PREFIXES these are still scanned for credentials, and
#: any other file under graphify-out/ is still held to MAX_LINE_LENGTH. A
#: whole-directory exemption would recreate the hiding place the rule exists
#: to remove: the postcss payload returned on 2026-10-11 as one 13,711
#: character line while this check was already failing on these two files,
#: and a check that is always red is a check nobody reads.
GENERATED_LONG_LINE_FILES = frozenset(
    {
        "graphify-out/graph.html",
        "graphify-out/.graphify_labels.json",
    }
)

#: Extensions that must contain binary data. ``fa-solid-600.eot`` was 32,540
#: bytes of text wearing a font's extension, and a lone ``.eot`` with no
#: ``.ttf``/``.woff`` sibling is not something a build tool produces.
BINARY_ONLY_SUFFIXES = (
    ".eot",
    ".ttf",
    ".woff",
    ".woff2",
    ".otf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".parquet",
    ".zip",
    ".gz",
)


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str
    detail: str


def _run(args: list[str]) -> str:
    return subprocess.run(
        args, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace"
    ).stdout


def listed_paths(staged: bool) -> list[str]:
    if staged:
        out = _run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]
        )
    else:
        out = _run(["git", "ls-files", "-z"])
    return [p for p in out.split("\0") if p]


def read_bytes(path: str, staged: bool) -> bytes | None:
    """The content being committed, not whatever is on disk.

    In ``--staged`` mode this reads the index, so staging a clean file and then
    dirtying the working copy cannot smuggle anything past the hook.
    """
    try:
        if staged:
            return subprocess.run(
                ["git", "show", f":{path}"], check=True, capture_output=True
            ).stdout
        with open(path, "rb") as handle:
            return handle.read()
    except (subprocess.CalledProcessError, OSError):
        # Deleted, or unreadable because an antivirus has it locked — which is
        # how this incident surfaced. Nothing to judge either way.
        return None


def is_binary(blob: bytes) -> bool:
    return b"\0" in blob[:8192]


def is_exempt_from_line_length(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (
        path.startswith(EXEMPT_PREFIXES)
        or path in GENERATED_LONG_LINE_FILES
        or path.endswith(EXEMPT_SUFFIXES)
        or name in EXEMPT_NAMES
        or ".min." in name
    )


def check_root_entry(path: str) -> Finding | None:
    entry = path.split("/", 1)[0]
    if entry in ALLOWED_ROOT_ENTRIES:
        return None
    return Finding(
        path,
        "unexpected-root-entry",
        f"{entry!r} is not an allowed top-level entry. A root-level directory "
        "matches no CI path filter, so nothing else would look at it. If this "
        "is genuinely ours, add it to ALLOWED_ROOT_ENTRIES in this script.",
    )


def check_env_filename(path: str) -> Finding | None:
    name = path.rsplit("/", 1)[-1]
    if name.endswith(_SOURCE_SUFFIXES) or name.endswith(_ENV_FILE_ALLOWED_SUFFIX):
        return None
    if "env" not in name.lower().split("."):
        return None
    return Finding(
        path,
        "env-file-committed",
        "an environment file may only be committed as *.env.example. This is "
        "the rule `.gitignore`'s `*.env` glob failed to express, which is how "
        "backend.env.bak reached main with live credentials in it.",
    )


def check_secrets(path: str, text: str) -> list[Finding]:
    # Archived third-party pages are verbatim copies we never authored, and
    # vendor documentation is full of example credentials — the saved Cohere
    # embed page carries an AWS access key id in its AWS setup section.
    # Scanning them reports other people's placeholders, so the one honest
    # option is to say plainly that these trees are out of scope rather than
    # to keep tuning the pattern.
    #
    # The example is described rather than quoted on purpose: a key-shaped
    # literal in this file would trip the rule below on this very file, which
    # it did on first run.
    if path.startswith(EXEMPT_PREFIXES):
        return []

    findings: list[Finding] = []
    for label, pattern in VENDOR_SECRETS:
        match = pattern.search(text)
        if match is not None:
            findings.append(
                Finding(
                    path,
                    "credential",
                    f"looks like a live {label} on line "
                    f"{text[: match.start()].count(chr(10)) + 1}. Rotate it, then "
                    "remove it — a committed key is a rotated key.",
                )
            )
    if path.endswith(_ASSIGNED_SECRET_SCOPE) and not path.endswith(
        _ENV_FILE_ALLOWED_SUFFIX
    ):
        for match in _ASSIGNED_SECRET.finditer(text):
            name, value = match.group(1), match.group(2)
            if _PLACEHOLDER.match(value):
                continue
            findings.append(
                Finding(
                    path,
                    "credential",
                    f"{name} is assigned a {len(value)}-character opaque value on "
                    f"line {text[: match.start()].count(chr(10)) + 1}. Read it from "
                    "the environment instead, or use an obvious placeholder.",
                )
            )
    return findings


def check_line_length(path: str, text: str) -> Finding | None:
    if is_exempt_from_line_length(path):
        return None
    for number, line in enumerate(text.splitlines(), start=1):
        if len(line) > MAX_LINE_LENGTH:
            return Finding(
                path,
                "minified-blob",
                f"line {number} is {len(line):,} characters. Nothing authored in "
                "this repo is one long line; the injected postcss payload was "
                f"32,566. If this is generated, exempt it explicitly.",
            )
    return None


def check_text_posing_as_binary(path: str, blob: bytes) -> Finding | None:
    # The whole blob, not `is_binary`'s first 8 KB: a PDF opens with ~10 KB of
    # ASCII before its first NUL, so the cheap window called two real papers
    # fakes. Every genuine font, image and PDF has a NUL somewhere; 32 KB of
    # injected JavaScript has none.
    if not path.endswith(BINARY_ONLY_SUFFIXES) or b"\x00" in blob:
        return None
    return Finding(
        path,
        "text-posing-as-binary",
        f"{path.rsplit('.', 1)[-1]} files are binary, and this one is text. "
        "fa-solid-600.eot was 32 KB of text wearing a font's extension.",
    )


def inspect(paths: list[str], staged: bool) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        for check in (check_root_entry, check_env_filename):
            finding = check(path)
            if finding is not None:
                findings.append(finding)

        blob = read_bytes(path, staged)
        if blob is None:
            continue

        posing = check_text_posing_as_binary(path, blob)
        if posing is not None:
            findings.append(posing)
        if is_binary(blob):
            continue

        text = blob.decode("utf-8", errors="replace")
        findings.extend(check_secrets(path, text))
        long_line = check_line_length(path, text)
        if long_line is not None:
            findings.append(long_line)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--staged",
        action="store_true",
        help="check the staged tree only (what a commit would contain)",
    )
    args = parser.parse_args()

    paths = listed_paths(args.staged)
    findings = inspect(paths, args.staged)

    if not findings:
        scope = "staged" if args.staged else "tracked"
        print(f"repo hygiene: {len(paths)} {scope} file(s) checked, nothing to report")
        return 0

    print("repo hygiene: FAILED\n", file=sys.stderr)
    for finding in findings:
        print(f"  {finding.path}", file=sys.stderr)
        print(f"    [{finding.rule}] {finding.detail}\n", file=sys.stderr)
    print(
        f"{len(findings)} problem(s). Each rule exists because of a real incident "
        "— see docs/security/0001-injected-postcss-payload-and-leaked-env-backup.md.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
