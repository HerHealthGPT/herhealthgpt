# Step 3b: connecting the production backend to the campus models

**Status:** draft for review, 2026-10-13. Nothing here is built. No AWS,
production or network change has been made.

## Goal

The backend and frontend on the EC2 host answer triage turns using the three
model servers on the campus GPU box: chat (`Qwen/Qwen3.5-9B` and the
`herhealth` adapter), embeddings (`herhealth-embed`) and, when switched on,
the reranker (`herhealth-rerank`). No model runs on AWS and no third-party
model API is called.

## What exists today

| Piece | State |
|---|---|
| Model servers | `scripts/serve-models.sh` on the campus pod, bound to `127.0.0.1` on ports 8002, 8003 and 8004, with no API key |
| Backend settings | `HERHEALTH_VLLM_URL`, `HERHEALTH_EMBEDDING_URL`, `HERHEALTH_RERANKER_URL`, `HERHEALTH_MODELS_API_KEY`, `HERHEALTH_INDEX_DIR` are already read from the environment |
| Production | `HERHEALTH_TRIAGE_MODE=vllm` with no endpoints or index, so triage reports "not configured" |
| Retrieval index | `build/index` on the campus box, 40 MB, untracked, built without quote-only (NHS) text |
| Turn time | median 29 s, slowest 108 s over 540 first turns; the route allows 150 s per turn and 50 s per model call |

## The constraint that shapes everything

The campus pod is an unprivileged container. It accepts no inbound
connections, cannot run Docker, and loses every process when it restarts.
Only outbound connections from the pod are possible, so the link has to be
opened from the campus side.

## Decision 1: how the EC2 host reaches the pod

| Option | How | For | Against |
|---|---|---|---|
| **A. Private mesh network (Tailscale)** | The pod runs the client in userspace mode (no root needed); the EC2 host joins the same private network. The backend calls a private address. | Nothing is published on the internet. Stable address across restarts. Encrypted. | A third-party account. A binary to download on the pod. Must be allowed by the university. |
| B. Cloudflare tunnel | The pod opens an outbound tunnel; the endpoints get a public HTTPS name. | Already described in the campus runbook. | The endpoints are public, protected only by the API key. A stable name needs the domain's DNS on Cloudflare; the free "quick" tunnel changes its address on every restart. Cloudflare cuts requests at 100 s, below the 108 s slowest turn. |
| C. Reverse SSH tunnel | The pod connects out to the EC2 host and forwards the three ports. | No third party. `ssh` is already on the pod. | Port 22 must be opened on the EC2 host, which today has no SSH at all (SSM only). No `autossh` on the pod, so a dropped link stays down until someone notices. |

**Recommended: A**, with the vLLM API key switched on as well, so that a
machine on the private network still needs the key. B is the fallback for a
demo day if A is not permitted.

All three send user messages from AWS to the university network. **Whether
the university permits a standing outbound tunnel from this pod has to be
checked by the repo owner before any of them is set up.**

## Decision 2: one address or three

The backend takes three URLs. Recommended: keep three ports and no extra
gateway on the pod. Fewer moving parts, and the settings already exist. A
gateway would only be needed for option B, to publish one hostname.

## Decision 3: how the index reaches the EC2 host

The index must be built on the campus box, because building it calls the
embedding server. It must reach the host without being committed.

| Option | How | Note |
|---|---|---|
| **A. S3 object, pulled at deploy** | Upload `index.faiss`, `passages.jsonl` and `manifest.json` under a key named by the manifest; `deploy.sh` downloads it to a read-only volume. | Recommended. The earlier upload script was deleted with bge-m3 and would be rewritten, keeping its refusal to upload quote-only text. |
| B. Copy over the link from decision 1 | The host pulls the files from the pod. | No AWS credentials needed on campus, but a deploy then fails whenever the pod is down. |
| C. Bake into the backend image | Build step copies the index in. | CI cannot build the index, so it would have to be committed or fetched anyway. |

The backend already refuses an index whose manifest names a different
embedding model (`IndexRefused`), so a mismatched upload fails at start-up
with a clear message and not with wrong search results.

## Behaviour when the campus box is unreachable

This will happen: the pod restarts, and the models take several minutes to
load and are started by hand.

- A triage turn returns the existing "temporarily unavailable" error. The
  tracker, directory and accounts keep working.
- **The deploy health check must not call the model endpoints.** If it did, a
  deploy made while the pod is down would roll itself back.
- `/health` stays as it is; a separate readiness field reports whether the
  model endpoints answered recently, for the operator and for the frontend to
  show a plain notice before she types.
- No retry beyond what the chain already does. A second whole-turn attempt on
  a dead link doubles the wait for nothing.

## Timeouts

- Caddy on the EC2 host sets no response timeout and the browser calls
  `api.herhealthgpt.org` directly, so no proxy on the AWS side cuts a slow
  turn. To be confirmed with one deliberately slow request after set-up.
- The per-call limit of 50 s and the per-turn limit of 150 s stay. Option A
  adds network latency in the order of tens of milliseconds per call, small
  against a 29 s turn.
- Option B's 100 s cut would need the per-turn limit lowered to match.

## Secrets

- One new secret, the model API key. On AWS it goes in the parameter store
  and is written to the host by `refresh-secrets.sh`, like the others. On the
  campus box it goes in an untracked file read by `serve-models.sh`.
- The mesh network's join key (option A) is a second secret, used once per
  machine.
- Neither is committed, printed or pasted into a chat session.

## Privacy

User messages will be processed on university hardware. Request logging on
the three vLLM servers must be confirmed off, and the privacy notice must say
where messages are processed. This is a change from "processed by a
third-party model provider" and needs the same sentence in `DATASHEET.md`.

## Capacity

One chat server, three model calls per turn, about 30 s per turn. This is
enough for a demonstration and a marked capstone, and not for concurrent
public use. Turns queue; they are not dropped. No scaling work is proposed.

## Not in scope

- Running any model on AWS.
- Starting the model servers automatically after a pod restart. The pod
  offers no service manager; a restart needs a person. A runbook step, not
  code.
- French and Arabic. The benchmark run was English only.

## A question to settle before going live

The full-benchmark run (ADR 0018, 2026-10-13) found that 121 of 192 questions
labelled see-doctor or urgent got an informational answer with no urgency
level, and that few of those answers advised seeing anyone. Connecting
production does not change that behaviour; it exposes it to real users. The
repo owner should decide whether that is acceptable for a demonstration, or
whether the informational path is tightened first.

## Decisions needed from the repo owner

1. Connection: A (private mesh), B (Cloudflare tunnel) or C (reverse SSH).
2. Confirmation that the university allows it.
3. Index delivery: A (S3), B (over the link) or C (in the image).
4. Go live now, or tighten informational answers first.

## Done when

- A triage turn typed into `herhealthgpt.org` is answered by the campus
  models, with citations from the delivered index.
- With the model servers stopped, the site stays up, triage shows a plain
  unavailable notice, and a deploy still succeeds.
- A turn that takes more than 60 s completes in the browser.
- No model endpoint answers a request that lacks the API key.
- `docs/runbooks/aws-deploy.md` and `docs/runbooks/uni-server-vllm.md`
  describe the set-up and the restart procedure.
