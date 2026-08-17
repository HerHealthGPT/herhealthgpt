"""Extract every Mermaid diagram in docs/ into its own file.

Tracked and reproducible rather than a one-off, because the diagrams go into
mentor decks and the report, and a diagram pasted into a slide has no link back
to the sentence it illustrates. Re-running this after editing a document
regenerates every export, so an exported picture can never quietly drift from
the prose around it.

Writes ``.mmd`` source files, which need no network and no browser. Rendering
them to SVG or PNG needs ``@mermaid-js/mermaid-cli``, which this script does not
install and does not call — see ``--render-command``.

    python scripts/extract_diagrams.py            # write .mmd files
    python scripts/extract_diagrams.py --list      # show what is there
    python scripts/extract_diagrams.py --render-command   # print the render command

Filenames carry the document, the position and the nearest heading, so an
exported diagram can be traced back to the section it came from:

    KNOWLEDGE_BASE-03-the-schema.mmd
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
OUT = REPO / "build" / "diagrams"

FENCE = re.compile(r"^```mermaid\s*$(.*?)^```\s*$", re.M | re.S)
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)

#: Mermaid diagram kinds, for the summary. Anything else is reported as-is so a
#: new kind shows up rather than being silently bucketed as "unknown".
KINDS = (
    "flowchart",
    "graph",
    "sequenceDiagram",
    "erDiagram",
    "gantt",
    "pie",
    "classDiagram",
    "stateDiagram",
    "journey",
    "mindmap",
    "timeline",
)


@dataclass(frozen=True, slots=True)
class Diagram:
    document: str
    index: int
    heading: str
    kind: str
    source: str

    @property
    def filename(self) -> str:
        return f"{self.document}-{self.index:02d}-{slugify(self.heading)}.mmd"


def slugify(text: str) -> str:
    text = re.sub(r"[`*_#]", "", text).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text or "diagram")[:48]


def heading_before(markdown: str, position: int) -> str:
    """The nearest heading above this offset, or the document name."""
    last = ""
    for match in HEADING.finditer(markdown, 0, position):
        last = match.group(1)
    return last or "untitled"


def kind_of(source: str) -> str:
    first = next((ln.strip() for ln in source.splitlines() if ln.strip()), "")
    for kind in KINDS:
        if first.startswith(kind):
            return kind
    return first.split()[0] if first else "empty"


def find_diagrams(docs: Path) -> list[Diagram]:
    found: list[Diagram] = []
    for path in sorted(docs.rglob("*.md")):
        markdown = path.read_text(encoding="utf-8")
        for index, match in enumerate(FENCE.finditer(markdown), start=1):
            source = match.group(1).strip("\n")
            found.append(
                Diagram(
                    document=path.stem,
                    index=index,
                    heading=heading_before(markdown, match.start()),
                    kind=kind_of(source),
                    source=source,
                )
            )
    return found


def write(diagrams: list[Diagram], out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    # Remove stale exports so a deleted diagram does not linger as a file that
    # still looks current.
    for stale in out.glob("*.mmd"):
        stale.unlink()

    written = []
    for diagram in diagrams:
        target = out / diagram.filename
        target.write_text(diagram.source + "\n", encoding="utf-8")
        written.append(target)
    return written


RENDER_COMMAND = """\
# Renders every .mmd to SVG and PNG. Needs one npm install (pulls Chromium).
npm install -g @mermaid-js/mermaid-cli

for f in build/diagrams/*.mmd; do
  mmdc -i "$f" -o "${f%.mmd}.svg" -b transparent
  mmdc -i "$f" -o "${f%.mmd}.png" -b white -s 3
done
"""


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--docs", type=Path, default=DOCS)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--list", action="store_true", help="show diagrams, write nothing")
    parser.add_argument(
        "--render-command", action="store_true", help="print how to rasterise the exports"
    )
    args = parser.parse_args(argv)

    if args.render_command:
        print(RENDER_COMMAND)
        return 0

    if not args.docs.is_dir():
        print(f"no such directory: {args.docs}", file=sys.stderr)
        return 2

    diagrams = find_diagrams(args.docs)
    if not diagrams:
        print(f"no mermaid diagrams found in {args.docs}", file=sys.stderr)
        return 1

    by_document: dict[str, int] = {}
    for diagram in diagrams:
        by_document[diagram.document] = by_document.get(diagram.document, 0) + 1

    if args.list:
        for diagram in diagrams:
            print(f"  {diagram.kind:<16} {diagram.document}  §{diagram.heading}")
    else:
        written = write(diagrams, args.out)
        for path in written:
            print(f"  {path.relative_to(REPO)}")
        print(f"\n{len(written)} diagram(s) written to {args.out.relative_to(REPO)}")

    print("\nby document: " + ", ".join(f"{d} {n}" for d, n in sorted(by_document.items())))
    kinds: dict[str, int] = {}
    for diagram in diagrams:
        kinds[diagram.kind] = kinds.get(diagram.kind, 0) + 1
    print("by kind:     " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())))

    if not args.list:
        print("\nTo rasterise: python scripts/extract_diagrams.py --render-command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
