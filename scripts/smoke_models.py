"""Acceptance check for the three vLLM processes.

    uv run python scripts/smoke_models.py
    uv run python scripts/smoke_models.py --skip-structured

Exit code 0 means every check passed. The structured-output probe is reported
separately and never changes the exit code: it exists to find out whether
schema-constrained decoding works on this hardware, where it crashed the
engine on 2026-09-08.

The fixture sentences are deliberately not about health. They test that the
models answer, embed and rank in three languages, and assert nothing clinical.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = REPO_ROOT / "infra" / "model" / "serve.conf"
HOST = "127.0.0.1"

#: Generation on these cards is slow; the first call also compiles LoRA kernels.
TIMEOUT_SECONDS = 300.0

CHAT_PROMPTS = {
    "en": "Answer in one short sentence: what is a calendar used for?",
    "fr": "Réponds en une phrase courte : à quoi sert un calendrier ?",
    "ar": "أجب بجملة قصيرة واحدة: ما فائدة التقويم؟",
}

#: language -> (query, relevant passage, irrelevant passage)
RERANK_CASES = {
    "en": (
        "What time does the library open?",
        "The library opens at nine every morning.",
        "Tomatoes grow best in warm weather.",
    ),
    "fr": (
        "À quelle heure ouvre la bibliothèque ?",
        "La bibliothèque ouvre à neuf heures chaque matin.",
        "Les tomates poussent mieux par temps chaud.",
    ),
    "ar": (
        "متى تفتح المكتبة؟",
        "تفتح المكتبة في الساعة التاسعة كل صباح.",
        "تنمو الطماطم بشكل أفضل في الطقس الدافئ.",
    ),
}

_FAILURES = (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError)


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def load_env(path: Path) -> dict[str, str]:
    """Read a KEY=value file, skipping blank lines and comments."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def looks_corrupted(text: str) -> bool:
    """True for an empty reply or one that is mostly ``!``.

    A run of ``!`` is token 0, which the sampler emits when the logits are
    NaN. See docs/runbooks/uni-server-vllm.md section 0.1.
    """
    compact = "".join(text.split())
    if not compact:
        return True
    return compact.count("!") / len(compact) > 0.5


def _describe(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return f"HTTP {error.response.status_code}"
    if isinstance(error, httpx.HTTPError):
        return str(error) or type(error).__name__
    return f"unexpected response ({type(error).__name__}: {error})"


def _guarded(name: str, body: Callable[[], CheckResult]) -> CheckResult:
    """Run one check and turn any transport or shape error into a failed
    result, so one dead service never hides the state of the others."""
    try:
        return body()
    except _FAILURES as error:
        return CheckResult(name, False, _describe(error))


def check_health(client: httpx.Client, base_url: str) -> CheckResult:
    name = f"health {base_url}"

    def body() -> CheckResult:
        client.get(f"{base_url}/health").raise_for_status()
        return CheckResult(name, True, "answering")

    return _guarded(name, body)


def check_models(
    client: httpx.Client, base_url: str, expected: Sequence[str]
) -> CheckResult:
    name = f"models {base_url}"

    def body() -> CheckResult:
        response = client.get(f"{base_url}/v1/models")
        response.raise_for_status()
        served = {entry["id"] for entry in response.json()["data"]}
        missing = [model for model in expected if model not in served]
        if missing:
            return CheckResult(name, False, f"not served: {', '.join(missing)}")
        return CheckResult(name, True, ", ".join(expected))

    return _guarded(name, body)


def _chat(client: httpx.Client, base_url: str, payload: dict[str, object]) -> str:
    response = client.post(f"{base_url}/v1/chat/completions", json=payload)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise TypeError("message content is not text")
    return content


def check_chat(
    client: httpx.Client, base_url: str, model: str, language: str, prompt: str
) -> CheckResult:
    name = f"chat {language}"

    def body() -> CheckResult:
        reply = _chat(
            client,
            base_url,
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 64,
                "temperature": 0,
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        if looks_corrupted(reply):
            return CheckResult(name, False, f"corrupted or empty reply: {reply[:40]!r}")
        return CheckResult(name, True, reply.strip()[:80])

    return _guarded(name, body)


def check_embeddings(
    client: httpx.Client, base_url: str, model: str, texts: Sequence[str]
) -> CheckResult:
    name = "embeddings"

    def body() -> CheckResult:
        response = client.post(
            f"{base_url}/v1/embeddings", json={"model": model, "input": list(texts)}
        )
        response.raise_for_status()
        vectors = [entry["embedding"] for entry in response.json()["data"]]
        if len(vectors) != len(texts):
            return CheckResult(
                name, False, f"{len(vectors)} vectors for {len(texts)} inputs"
            )
        widths = {len(vector) for vector in vectors}
        if len(widths) != 1 or 0 in widths:
            return CheckResult(
                name, False, f"widths differ or are empty: {sorted(widths)}"
            )
        if not all(math.isfinite(value) for vector in vectors for value in vector):
            return CheckResult(name, False, "non-finite value in an embedding")
        return CheckResult(name, True, f"width={widths.pop()}")

    return _guarded(name, body)


def check_rerank(
    client: httpx.Client,
    base_url: str,
    model: str,
    language: str,
    query: str,
    relevant: str,
    irrelevant: str,
) -> CheckResult:
    name = f"rerank {language}"

    def body() -> CheckResult:
        response = client.post(
            f"{base_url}/v1/rerank",
            json={"model": model, "query": query, "documents": [relevant, irrelevant]},
        )
        response.raise_for_status()
        scores = {
            entry["index"]: float(entry["relevance_score"])
            for entry in response.json()["results"]
        }
        detail = f"relevant={scores[0]:.4g} irrelevant={scores[1]:.4g}"
        return CheckResult(name, scores[0] > scores[1], detail)

    return _guarded(name, body)


def probe_structured(
    client: httpx.Client, base_url: str, model: str, schema: dict[str, object]
) -> CheckResult:
    """One schema-constrained request. PASS, FAIL or CRASH.

    CRASH means the engine stopped answering ``/health`` afterwards, which is
    the 2026-09-08 failure. Restart chat before doing anything else.
    """
    name = "structured-output"
    outcome = "FAIL"
    detail = ""
    try:
        reply = _chat(
            client,
            base_url,
            {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Reply only with JSON that matches the schema.",
                    },
                    {"role": "user", "content": "I would like to ask a question."},
                ],
                "max_tokens": 512,
                "temperature": 0,
                "chat_template_kwargs": {"enable_thinking": False},
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "triage_decision", "schema": schema},
                },
            },
        )
        parsed = json.loads(reply)
        if isinstance(parsed, dict):
            outcome, detail = "PASS", f"keys: {', '.join(sorted(parsed))}"
        else:
            detail = "reply was JSON but not an object"
    except _FAILURES as error:
        detail = _describe(error)
    if not check_health(client, base_url).ok:
        outcome = "CRASH"
        detail = f"engine no longer answers /health ({detail})"
    return CheckResult(name, outcome == "PASS", f"{outcome}: {detail}")


def _decision_schema() -> dict[str, object]:
    from herhealth_contracts.decision import TriageDecision

    return TriageDecision.model_json_schema()


def _print(result: CheckResult) -> None:
    print(f"{'ok  ' if result.ok else 'FAIL'}  {result.name}  {result.detail}")


def main(
    argv: Sequence[str] | None = None, *, transport: httpx.BaseTransport | None = None
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--skip-structured", action="store_true")
    args = parser.parse_args(argv)
    if not args.env.is_file():
        parser.error(f"no env file at {args.env}")
    env = load_env(args.env)

    chat = f"http://{HOST}:{env['CHAT_PORT']}"
    embed = f"http://{HOST}:{env['EMBED_PORT']}"
    rerank = f"http://{HOST}:{env['RERANK_PORT']}"
    adapter = env["CHAT_ADAPTER_NAME"]

    results: list[CheckResult] = []
    # The servers require a bearer key once they are reachable from outside.
    key = os.environ.get("HERHEALTH_MODELS_API_KEY", "")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    with httpx.Client(timeout=TIMEOUT_SECONDS, transport=transport, headers=headers) as client:
        for label, url in (("chat", chat), ("embed", embed), ("rerank", rerank)):
            health = check_health(client, url)
            results.append(CheckResult(f"health {label}", health.ok, health.detail))
        results.append(check_models(client, chat, [env["CHAT_MODEL"], adapter]))
        for language, prompt in CHAT_PROMPTS.items():
            results.append(check_chat(client, chat, adapter, language, prompt))
        results.append(
            check_embeddings(
                client,
                embed,
                env["EMBED_SERVED_NAME"],
                [case[1] for case in RERANK_CASES.values()],
            )
        )
        for language, (query, relevant, irrelevant) in RERANK_CASES.items():
            results.append(
                check_rerank(
                    client,
                    rerank,
                    env["RERANK_SERVED_NAME"],
                    language,
                    query,
                    relevant,
                    irrelevant,
                )
            )
        for result in results:
            _print(result)
        if not args.skip_structured:
            print("--- structured-output probe (does not affect the exit code)")
            _print(probe_structured(client, chat, adapter, _decision_schema()))

    failed = [result for result in results if not result.ok]
    print(f"{len(results) - len(failed)} of {len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
