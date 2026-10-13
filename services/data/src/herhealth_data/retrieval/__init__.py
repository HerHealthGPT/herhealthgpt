"""Semantic search over the cleaned corpus.

Two jobs, and they are separate on purpose:

1. **Serving** — build the index the backend retrieves from. Only passages
   whose source licence permits redistribution go into it; a quote-only (NHS)
   passage never does, so the files are safe to copy to a server.
2. **Authoring** — propose candidate evidence rows for a human to approve,
   over a second, local-only index that does include quote-only passages.

:func:`~herhealth_data.retrieval.passages.evidence_statement_passages` is what
makes ``evidence.csv`` part of the corpus: each row is rendered into a passage
tagged ``passage_type="evidence_statement"``, searchable like any sentence.

Nothing here decides urgency. Retrieval finds text.
"""

from herhealth_data.retrieval.embed import HashingEmbedder
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
from herhealth_data.retrieval.source_urls import load_source_urls, resolve_url
from herhealth_data.retrieval.vectorstore import (
    HASHING_MODEL,
    HashingEmbeddings,
    Hit,
    PassageStore,
    endpoint_embeddings,
    read_manifest,
    to_indexed,
)

__all__ = [
    "HASHING_MODEL",
    "Gap",
    "HashingEmbedder",
    "HashingEmbeddings",
    "Hit",
    "Passage",
    "PassageStore",
    "Proposal",
    "endpoint_embeddings",
    "evidence_statement_passages",
    "find_gaps",
    "load_passages",
    "load_source_urls",
    "propose_rows",
    "read_manifest",
    "render_batch",
    "resolve_url",
    "split_sentences",
    "to_indexed",
    "write_batch",
]
