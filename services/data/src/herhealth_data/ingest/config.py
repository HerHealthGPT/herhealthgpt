"""What to fetch, and the per-source rules that govern how.

Loaded from the tracked ``services/data/ingest_targets.yaml``. Together with
``ingest.lock.jsonl`` this is what makes a fetch reproducible: the targets say
what to get, the lock records what was got.

Two kinds of per-source rule, both here because a rule that lives only in
someone's memory eventually gets broken:

* **Licence guards** — path fragments never requested from a source.
* **User agents** — overrides for sources whose edge rejects our default.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import yaml

__all__ = ["USER_AGENT", "DuplicateTargetError", "FetchPlan", "Target", "load_plan"]

#: Identifies us honestly. An academic project should not pretend to be a
#: browser. Sources whose edge rejects this get a per-source override in the
#: targets file, with the reason recorded there.
USER_AGENT: Final[str] = "HerHealthGPT-research/0.1 (academic capstone; contact via repository)"


class DuplicateTargetError(ValueError):
    """Two targets would write to the same file, so one would be lost."""


@dataclass(frozen=True, slots=True)
class Target:
    """One document we intend to fetch."""

    source_id: str
    slug: str
    url: str
    licence: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.source_id, self.slug)


@dataclass(frozen=True, slots=True)
class FetchPlan:
    """Every target, plus the per-source rules that apply to them."""

    targets: tuple[Target, ...]
    excluded_path_fragments: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    user_agents: Mapping[str, str] = field(default_factory=dict)

    def excluded_reason(self, target: Target) -> str | None:
        """The fragment that bars this target, or None if it is permitted."""
        for fragment in self.excluded_path_fragments.get(target.source_id, ()):
            if fragment in target.url:
                return fragment
        return None

    def user_agent_for(self, target: Target) -> str:
        return self.user_agents.get(target.source_id, USER_AGENT)

    def source_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(t.source_id for t in self.targets))


def load_plan(path: Path) -> FetchPlan:
    """Read and validate the tracked target list."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    targets = tuple(
        Target(
            source_id=str(d["source_id"]),
            slug=str(d["slug"]),
            url=str(d["url"]),
            licence=str(d["licence"]).strip(),
        )
        for d in raw.get("documents", [])
    )
    _reject_duplicates(targets)

    return FetchPlan(
        targets=targets,
        excluded_path_fragments={
            str(source): tuple(str(f) for f in fragments)
            for source, fragments in (raw.get("excluded_path_fragments") or {}).items()
        },
        user_agents={
            str(source): str(agent).strip()
            for source, agent in (raw.get("user_agents") or {}).items()
        },
    )


def _reject_duplicates(targets: Sequence[Target]) -> None:
    keys = [t.key for t in targets]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        shown = ", ".join(f"{source}/{slug}" for source, slug in duplicates)
        raise DuplicateTargetError(f"targets would overwrite each other: {shown}")
