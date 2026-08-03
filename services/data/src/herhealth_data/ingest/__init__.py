"""Source ingestion: fetch documents, store them immutably, record provenance.

Import from this package rather than its modules:

    from herhealth_data.ingest import RawStore, fetch_all, load_plan

Three modules, each with one reason to change:

============  ==============================================================
``config``    What to fetch and the per-source rules — licence guards and
              user-agent overrides. Read from the tracked YAML.
``store``     Where documents go and what we record: the immutable ``raw/``
              layout, manifests, and the tracked lockfile.
``fetch``     The network, and the policy deciding what to request.
============  ==============================================================

``config`` imports nothing from the others; ``store`` imports ``config``;
``fetch`` imports both. No cycles.

Two protocol rules are structural rather than remembered:

* **Tests never hit the network** — the network lives behind an injected
  ``Transport``, and no test supplies the real one.
* **Raw content is immutable** — ``RawStore.save`` refuses to overwrite.
"""

from herhealth_data.ingest.config import (
    USER_AGENT,
    DuplicateTargetError,
    FetchPlan,
    Target,
    load_plan,
)
from herhealth_data.ingest.fetch import Transport, fetch_all, http_get, utc_today
from herhealth_data.ingest.store import (
    FetchOutcome,
    FetchRecord,
    RawStore,
    StoredDocument,
    content_hash,
    read_lock,
    write_lock,
)

__all__ = [
    "USER_AGENT",
    "DuplicateTargetError",
    "FetchOutcome",
    "FetchPlan",
    "FetchRecord",
    "RawStore",
    "StoredDocument",
    "Target",
    "Transport",
    "content_hash",
    "fetch_all",
    "http_get",
    "load_plan",
    "read_lock",
    "utc_today",
    "write_lock",
]
