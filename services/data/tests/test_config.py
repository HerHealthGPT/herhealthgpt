"""Tests for the target list and its per-source rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_plan, make_target
from herhealth_data import paths
from herhealth_data.ingest import USER_AGENT, DuplicateTargetError, Target, load_plan

# --------------------------------------------------------------------------
# Licence guards
# --------------------------------------------------------------------------


def test_guard_matches_a_barred_path() -> None:
    adam = make_target(source_id="medlineplus", url="https://medlineplus.gov/ency/x.htm")
    plan = make_plan(adam, exclusions={"medlineplus": ("/ency/",)})
    assert plan.excluded_reason(adam) == "/ency/"


def test_guard_permits_everything_else_from_the_same_source() -> None:
    topic = make_target(source_id="medlineplus", url="https://medlineplus.gov/endometriosis.html")
    plan = make_plan(topic, exclusions={"medlineplus": ("/ency/",)})
    assert plan.excluded_reason(topic) is None


def test_guard_is_scoped_to_its_own_source() -> None:
    """A medlineplus rule must not silently bar the same path on another host."""
    elsewhere = make_target(source_id="nichd", url="https://www.nichd.nih.gov/ency/thing")
    plan = make_plan(elsewhere, exclusions={"medlineplus": ("/ency/",)})
    assert plan.excluded_reason(elsewhere) is None


# --------------------------------------------------------------------------
# User agents
# --------------------------------------------------------------------------


def test_default_agent_identifies_the_project() -> None:
    assert make_plan().user_agent_for(make_target()) == USER_AGENT
    assert "HerHealthGPT" in USER_AGENT


def test_override_applies_only_to_its_own_source() -> None:
    plan = make_plan(
        make_target(),
        make_target(source_id="cdc"),
        user_agents={"cdc": "curl/8.0 HerHealthGPT-research/0.1"},
    )
    assert plan.user_agent_for(make_target(source_id="cdc")).startswith("curl/8.0")
    assert plan.user_agent_for(make_target()) == USER_AGENT


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def test_duplicate_targets_are_rejected(tmp_path: Path) -> None:
    targets_file = tmp_path / "targets.yaml"
    targets_file.write_text(
        "documents:\n"
        "  - {source_id: nichd, slug: pcos, url: 'https://a', licence: x}\n"
        "  - {source_id: nichd, slug: pcos, url: 'https://b', licence: x}\n",
        encoding="utf-8",
    )
    with pytest.raises(DuplicateTargetError, match="overwrite each other"):
        load_plan(targets_file)


def test_an_empty_file_loads_to_an_empty_plan(tmp_path: Path) -> None:
    empty = tmp_path / "targets.yaml"
    empty.write_text("", encoding="utf-8")
    assert load_plan(empty).targets == ()


def test_source_ids_are_deduplicated_in_order() -> None:
    plan = make_plan(
        make_target(source_id="nichd", slug="a"),
        make_target(source_id="medlineplus", slug="b"),
        make_target(source_id="nichd", slug="c"),
    )
    assert plan.source_ids() == ("nichd", "medlineplus")


# --------------------------------------------------------------------------
# The real, tracked target list
# --------------------------------------------------------------------------


def test_the_real_target_list_loads() -> None:
    plan = load_plan(paths.INGEST_TARGETS_FILE)
    assert plan.targets, "no documents configured"
    assert plan.excluded_path_fragments.get("medlineplus") == ("/ency/",)


def test_no_configured_target_is_self_excluded() -> None:
    """A target barred by its own guard would be a silent no-op forever."""
    plan = load_plan(paths.INGEST_TARGETS_FILE)
    for target in plan.targets:
        assert plan.excluded_reason(target) is None, f"{target.url} is self-excluded"


def test_the_adam_encyclopedia_is_barred_by_the_real_config() -> None:
    plan = load_plan(paths.INGEST_TARGETS_FILE)
    adam = Target("medlineplus", "x", "https://medlineplus.gov/ency/article/000369.htm", "n/a")
    assert plan.excluded_reason(adam) == "/ency/"


def test_no_configured_agent_impersonates_a_browser() -> None:
    """We work around a WAF by leading with a client token, not by pretending."""
    plan = load_plan(paths.INGEST_TARGETS_FILE)
    for source_id, agent in plan.user_agents.items():
        assert "HerHealthGPT" in agent, f"{source_id} agent must stay attributable"
        for browser in ("Mozilla", "Chrome", "Safari", "Firefox", "AppleWebKit", "Edg/"):
            assert browser not in agent, f"{source_id} agent impersonates {browser}"
