"""Semantic search over the cleaned corpus.

Two jobs, and they are separate on purpose:

1. **Authoring** — propose candidate evidence rows for a human to approve,
   widening the knowledge base without weakening the review gate.
2. **Serving** — retrieve passages to ground a user-facing answer. Reuses
   :class:`PassageIndex` with one extra filter: only passages whose source
   licence permits redistribution, which is why ``may_be_ingested`` is carried
   on every passage rather than looked up at the end.
   :func:`~herhealth_data.retrieval.passages.evidence_statement_passages` is
   what makes ``evidence.csv`` part of this corpus rather than authoring-only
   input: each row is rendered into a passage tagged
   ``passage_type="evidence_statement"``, searchable the same way as a source
   sentence.

Nothing here decides urgency. Retrieval finds text; the controller decides, and
the split is the whole safety argument.
"""

from herhealth_data.retrieval.embed import (
    DEFAULT_MODEL,
    Embedder,
    HashingEmbedder,
    SentenceTransformerEmbedder,
)
from herhealth_data.retrieval.index import Hit, PassageIndex, build_index
from herhealth_data.retrieval.passages import (
    Passage,
    evidence_statement_passages,
    load_passages,
    split_sentences,
)
from herhealth_data.retrieval.propose import (
    Gap,
    Proposal,
    find_gaps,
    propose_rows,
    render_batch,
    write_batch,
)

__all__ = [
    "DEFAULT_MODEL",
    "Embedder",
    "Gap",
    "HashingEmbedder",
    "Hit",
    "Passage",
    "PassageIndex",
    "Proposal",
    "SentenceTransformerEmbedder",
    "build_index",
    "evidence_statement_passages",
    "find_gaps",
    "load_passages",
    "propose_rows",
    "render_batch",
    "split_sentences",
    "write_batch",
]
