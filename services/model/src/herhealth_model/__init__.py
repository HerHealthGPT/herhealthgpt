"""CPU-only retrieval service — see docs/adr/0012-openrouter-reasoning-and-guarded-web-fallback.md.

No reasoning model is served here. That half of ADR 0011's original
``services/model`` plan is served by OpenRouter instead (see
``herhealth_backend.triage.clients.OpenRouterReasoningClient``); this service
only owns embeddings and search, which is CPU-feasible at this corpus size.
"""

from __future__ import annotations
