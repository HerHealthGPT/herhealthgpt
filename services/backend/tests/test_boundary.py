"""The Triage context must not import the runtime layer added by the skeleton.

From ``CONTEXT-MAP.md``: Accounts may depend on Triage; Triage must never depend
on Accounts. Concretely, the triage core has to stay runnable with no server, no
database and no user, because that property is what lets the evaluation harness
drive it. This test reads the triage source with the AST and fails if any module
imports ``herhealth_backend.app`` — the FastAPI/SQLAlchemy layer. It needs no
database and no network, so it runs in the plain triage suite.
"""

from __future__ import annotations

import ast
from pathlib import Path

import herhealth_backend.triage as triage

FORBIDDEN_PREFIX = "herhealth_backend.app"


def _imported_names(source: str) -> set[str]:
    """Every dotted name a module imports, from ``import`` and ``from`` alike."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        # Absolute imports only (level 0); a relative import stays within triage
        # and cannot reach a sibling package.
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            names.add(node.module)
    return names


def test_triage_does_not_import_the_app_layer() -> None:
    triage_dir = Path(triage.__path__[0])
    offenders: dict[str, set[str]] = {}
    for module_file in sorted(triage_dir.rglob("*.py")):
        imported = _imported_names(module_file.read_text(encoding="utf-8"))
        reaching = {name for name in imported if name.startswith(FORBIDDEN_PREFIX)}
        if reaching:
            offenders[module_file.name] = reaching
    assert not offenders, f"Triage modules must not import {FORBIDDEN_PREFIX}: {offenders}"
