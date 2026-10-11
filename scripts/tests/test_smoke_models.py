"""scripts/smoke_models.py against a mocked HTTP layer. No process, GPU or
network is involved."""

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
import smoke_models
from helpers import SERVE_ENV

Handler = Callable[[httpx.Request], httpx.Response]

CHAT = "http://127.0.0.1:8002"
EMBED = "http://127.0.0.1:8003"
RERANK = "http://127.0.0.1:8004"


def _json(payload: object, status: int = 200) -> Handler:
    return lambda request: httpx.Response(status, json=payload)


def _transport(routes: dict[tuple[str, int, str], Handler]) -> httpx.MockTransport:
    """Routes keyed by (method, port, path). Anything else refuses the
    connection, which is what a process that is down looks like."""

    def handler(request: httpx.Request) -> httpx.Response:
        route = routes.get((request.method, request.url.port or 0, request.url.path))
        if route is None:
            raise httpx.ConnectError("connection refused", request=request)
        return route(request)

    return httpx.MockTransport(handler)


def _client(routes: dict[tuple[str, int, str], Handler]) -> httpx.Client:
    return httpx.Client(transport=_transport(routes))


def _chat_reply(text: str) -> Handler:
    return _json({"choices": [{"message": {"content": text}, "finish_reason": "stop"}]})


def _rerank(relevant: float, irrelevant: float) -> Handler:
    return _json(
        {
            "results": [
                {"index": 1, "relevance_score": irrelevant},
                {"index": 0, "relevance_score": relevant},
            ]
        }
    )


def _healthy_routes() -> dict[tuple[str, int, str], Handler]:
    ok = lambda request: httpx.Response(200)
    return {
        ("GET", 8002, "/health"): ok,
        ("GET", 8003, "/health"): ok,
        ("GET", 8004, "/health"): ok,
        ("GET", 8002, "/v1/models"): _json(
            {"data": [{"id": "Qwen/Qwen3.5-9B"}, {"id": "herhealth"}]}
        ),
        ("POST", 8002, "/v1/chat/completions"): _chat_reply(
            "A calendar shows the date."
        ),
        ("POST", 8003, "/v1/embeddings"): _json(
            {
                "data": [
                    {"embedding": [0.6, 0.8]},
                    {"embedding": [1.0, 0.0]},
                    {"embedding": [0.0, 1.0]},
                ]
            }
        ),
        ("POST", 8004, "/v1/rerank"): _rerank(0.93, 0.02),
    }


@pytest.mark.parametrize(
    ("text", "corrupted"),
    [
        ("", True),
        ("   \n", True),
        ("!!!!!!!!!!!", True),
        ("! ! ! ! !", True),
        ("Yes!", False),
        ("A calendar shows the date.", False),
        ("التقويم يعرض التاريخ.", False),
    ],
)
def test_looks_corrupted(text: str, corrupted: bool) -> None:
    assert smoke_models.looks_corrupted(text) is corrupted


def test_load_env_reads_the_real_file() -> None:
    env = smoke_models.load_env(SERVE_ENV)
    assert env["CHAT_PORT"] == "8002"
    assert env["EMBED_SERVED_NAME"] == "herhealth-embed"


def test_health_ok_and_down() -> None:
    client = _client({("GET", 8002, "/health"): lambda r: httpx.Response(200)})
    assert smoke_models.check_health(client, CHAT).ok
    down = smoke_models.check_health(client, EMBED)
    assert not down.ok
    assert "connection refused" in down.detail


def test_models_reports_a_missing_adapter() -> None:
    client = _client(
        {("GET", 8002, "/v1/models"): _json({"data": [{"id": "Qwen/Qwen3.5-9B"}]})}
    )
    result = smoke_models.check_models(client, CHAT, ["Qwen/Qwen3.5-9B", "herhealth"])
    assert not result.ok
    assert "herhealth" in result.detail


def test_chat_ok() -> None:
    client = _client({("POST", 8002, "/v1/chat/completions"): _chat_reply("Bonjour.")})
    assert smoke_models.check_chat(client, CHAT, "herhealth", "fr", "Bonjour ?").ok


def test_chat_flags_the_corruption_signature() -> None:
    client = _client(
        {("POST", 8002, "/v1/chat/completions"): _chat_reply("!!!!!!!!!!!!")}
    )
    result = smoke_models.check_chat(client, CHAT, "herhealth", "en", "Hello?")
    assert not result.ok
    assert "corrupted" in result.detail


def test_chat_malformed_payload_fails_cleanly() -> None:
    client = _client({("POST", 8002, "/v1/chat/completions"): _json({"error": "boom"})})
    result = smoke_models.check_chat(client, CHAT, "herhealth", "en", "Hello?")
    assert not result.ok
    assert "unexpected response" in result.detail


def test_embeddings_ok_reports_the_width() -> None:
    client = _client(_healthy_routes())
    result = smoke_models.check_embeddings(
        client, EMBED, "herhealth-embed", ["a", "b", "c"]
    )
    assert result.ok
    assert "width=2" in result.detail


def test_embeddings_rejects_ragged_widths() -> None:
    client = _client(
        {
            ("POST", 8003, "/v1/embeddings"): _json(
                {"data": [{"embedding": [1.0]}, {"embedding": [1.0, 2.0]}]}
            )
        }
    )
    result = smoke_models.check_embeddings(client, EMBED, "herhealth-embed", ["a", "b"])
    assert not result.ok
    assert "widths differ" in result.detail


def test_embeddings_rejects_non_finite_values() -> None:
    body = b'{"data": [{"embedding": [NaN, 1.0]}]}'
    client = _client(
        {("POST", 8003, "/v1/embeddings"): lambda r: httpx.Response(200, content=body)}
    )
    result = smoke_models.check_embeddings(client, EMBED, "herhealth-embed", ["a"])
    assert not result.ok
    assert "non-finite" in result.detail


def test_rerank_ok_when_the_relevant_passage_scores_higher() -> None:
    client = _client({("POST", 8004, "/v1/rerank"): _rerank(0.9, 0.1)})
    assert smoke_models.check_rerank(
        client, RERANK, "herhealth-rerank", "en", "q", "rel", "irr"
    ).ok


def test_rerank_fails_when_the_order_is_wrong() -> None:
    client = _client({("POST", 8004, "/v1/rerank"): _rerank(0.1, 0.9)})
    result = smoke_models.check_rerank(
        client, RERANK, "herhealth-rerank", "ar", "q", "rel", "irr"
    )
    assert not result.ok
    assert "0.1" in result.detail and "0.9" in result.detail


def test_structured_probe_pass() -> None:
    routes = {
        ("POST", 8002, "/v1/chat/completions"): _chat_reply(
            '{"type": "ask", "rationale": "x"}'
        ),
        ("GET", 8002, "/health"): lambda r: httpx.Response(200),
    }
    result = smoke_models.probe_structured(
        _client(routes), CHAT, "herhealth", {"type": "object"}
    )
    assert result.ok
    assert result.detail.startswith("PASS")


def test_structured_probe_fail_when_the_reply_is_not_json() -> None:
    routes = {
        ("POST", 8002, "/v1/chat/completions"): _chat_reply("Sure, here you go"),
        ("GET", 8002, "/health"): lambda r: httpx.Response(200),
    }
    result = smoke_models.probe_structured(
        _client(routes), CHAT, "herhealth", {"type": "object"}
    )
    assert not result.ok
    assert result.detail.startswith("FAIL")


def test_structured_probe_crash_when_the_engine_is_gone_afterwards() -> None:
    routes = {
        ("POST", 8002, "/v1/chat/completions"): _json(
            {"error": "engine dead"}, status=500
        )
    }
    result = smoke_models.probe_structured(
        _client(routes), CHAT, "herhealth", {"type": "object"}
    )
    assert not result.ok
    assert result.detail.startswith("CRASH")


def test_main_exits_zero_when_everything_answers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    transport = _transport(_healthy_routes())
    code = smoke_models.main(
        ["--env", str(SERVE_ENV), "--skip-structured"], transport=transport
    )
    assert code == 0
    assert "FAIL" not in capsys.readouterr().out


def test_main_reports_every_check_when_one_service_is_down(
    capsys: pytest.CaptureFixture[str],
) -> None:
    routes = _healthy_routes()
    del routes[("GET", 8004, "/health")]
    del routes[("POST", 8004, "/v1/rerank")]
    transport = _transport(routes)
    code = smoke_models.main(
        ["--env", str(SERVE_ENV), "--skip-structured"], transport=transport
    )
    out = capsys.readouterr().out
    assert code == 1
    assert out.count("rerank") >= 4  # health plus three languages, all reported
    assert "ok    chat en" in out  # the healthy services were still checked


def test_main_fails_on_a_missing_env_file(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        smoke_models.main(["--env", str(tmp_path / "absent.env")])
