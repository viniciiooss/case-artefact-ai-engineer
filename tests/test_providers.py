import json
from pathlib import Path

import httpx
import pytest


def test_openai_sdk_tool_call_roundtrip_uses_real_graph_and_local_tools(tmp_path):
    from langchain_openai import ChatOpenAI

    from emporio.config import Settings
    from emporio.service import ChatService

    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        message = {"role": "assistant", "content": "O GD20 custa R$ 2.199,00."}
        if len(requests) == 1:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-gd20",
                        "type": "function",
                        "function": {"name": "get_product", "arguments": '{"product_id":95}'},
                    }
                ],
            }
        return httpx.Response(
            200,
            json={
                "id": "fake-completion",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4.1-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": message,
                        "finish_reason": "tool_calls" if len(requests) == 1 else "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        llm = ChatOpenAI(
            model="gpt-4.1-mini",
            api_key="fake-key-for-transport-test",
            http_client=client,
            max_retries=0,
        )
        settings = Settings(
            provider="demo",
            state_dir=tmp_path,
            _env_file=None,
            data_dir=Path(__file__).resolve().parents[1] / "data",
        )
        svc = ChatService(settings, model=llm)
        response = svc.chat(svc.create_session()["session_id"], "Preço do GD20?")
    assert len(requests) == 2
    schemas = {t["function"]["name"]: t["function"] for t in requests[0]["tools"]}
    assert "get_product" in schemas and "search_policies" in schemas
    assert set(schemas["get_order"]["parameters"]["properties"]) == {"order_id"}
    tool_message = next(m for m in requests[1]["messages"] if m["role"] == "tool")
    assert json.loads(tool_message["content"])["product"]["price_cents"] == 219900
    assert "2.199,00" in response["message"]
    assert response["sources"][0]["id"] == "product-95"


def test_openai_configuration_rejects_missing_key_instead_of_switching_to_demo(monkeypatch):
    from emporio.config import Settings

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings(provider="openai", _env_file=None)


def test_openrouter_uses_a_separate_secret_and_the_requested_mimo_model():
    from emporio.config import Settings

    settings = Settings(
        provider="openrouter", OPENROUTER_API_KEY="test-openrouter-key", _env_file=None
    )
    assert settings.model == "xiaomi/mimo-v2.6-pro"
    assert settings.openrouter_api_key.get_secret_value() == "test-openrouter-key"
    assert "test-openrouter-key" not in repr(settings)


def test_openrouter_does_not_borrow_an_openai_key(monkeypatch):
    from emporio.config import Settings

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        Settings(provider="openrouter", OPENAI_API_KEY="only-openai", _env_file=None)


def test_openrouter_requires_provider_model_format():
    from emporio.config import Settings

    with pytest.raises(ValueError, match="provedor/modelo"):
        Settings(
            provider="openrouter", OPENROUTER_API_KEY="test", model="mimo-v2.6-pro", _env_file=None
        )


@pytest.mark.parametrize(
    "http_status,expected",
    [
        (401, "provider_auth_error"),
        (402, "provider_credit_error"),
        (404, "provider_request_error"),
        (429, "provider_rate_limit"),
    ],
)
def test_provider_errors_are_useful_and_never_include_upstream_secrets(
    tmp_path, http_status, expected
):
    from openai import APIStatusError

    from emporio.config import Settings
    from emporio.service import AgentUnavailable, ChatService

    class FailingModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            response = httpx.Response(
                http_status, request=httpx.Request("POST", "https://provider.test")
            )
            raise APIStatusError("raw secret-should-not-leak", response=response, body={})

    svc = ChatService(
        Settings(
            provider="demo",
            state_dir=tmp_path,
            _env_file=None,
            data_dir=Path(__file__).resolve().parents[1] / "data",
        ),
        model=FailingModel(),
    )
    session = svc.create_session()["session_id"]
    with pytest.raises(AgentUnavailable) as exc:
        svc.chat(session, "Quanto custa o GD20?")
    assert exc.value.code == expected
    assert "secret-should-not-leak" not in str(exc.value)
    assert svc.sessions.history(session) == []


def _intercept_httpx(monkeypatch, handler):
    original = httpx.Client.__init__

    def configure_transport(client, *args, **kwargs):
        kwargs.update(transport=httpx.MockTransport(handler), trust_env=False)
        original(client, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", configure_transport)


@pytest.mark.parametrize("provider_order", [[], ["Xiaomi"]])
def test_openrouter_sdk_executes_the_same_tools_with_attribution_and_a_bounded_timeout(
    tmp_path, monkeypatch, provider_order
):
    from langchain_openrouter import ChatOpenRouter

    from emporio.config import Settings
    from emporio.service import ChatService

    requests = []

    def respond(request):
        requests.append(request)
        message = {"role": "assistant", "content": "O GD20 custa R$ 2.199,00."}
        if len(requests) == 1:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-router",
                        "type": "function",
                        "function": {"name": "get_product", "arguments": '{"product_id":95}'},
                    }
                ],
            }
        return httpx.Response(
            200,
            json={
                "id": "gen-test",
                "object": "chat.completion",
                "system_fingerprint": None,
                "created": 0,
                "model": "xiaomi/mimo-v2.6-pro",
                "choices": [
                    {
                        "index": 0,
                        "message": message,
                        "finish_reason": "tool_calls" if len(requests) == 1 else "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            },
        )

    _intercept_httpx(monkeypatch, respond)
    settings = Settings(
        provider="openrouter",
        OPENROUTER_API_KEY="test-router-key",
        openrouter_provider_order=provider_order,
        data_dir=Path(__file__).resolve().parents[1] / "data",
        state_dir=tmp_path,
        _env_file=None,
    )
    svc = ChatService(settings)
    assert isinstance(svc.model, ChatOpenRouter)
    result = svc.chat(svc.create_session()["session_id"], "Quanto custa o GD20?")
    assert len(requests) == 2
    first = json.loads(requests[0].content)
    second = json.loads(requests[1].content)
    assert str(requests[0].url) == "https://openrouter.ai/api/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer test-router-key"
    assert requests[0].headers["http-referer"] == settings.openrouter_site_url
    assert requests[0].headers["x-title"] == "Emporio da Musica - Artefact"
    assert requests[0].extensions["timeout"]["read"] == settings.llm_timeout
    assert first["provider"]["require_parameters"] is True
    assert first["provider"]["allow_fallbacks"] is False
    if provider_order:
        assert first["provider"]["order"] == provider_order
    else:
        assert not first["provider"].get("order")
    assert first["max_tokens"] == 1600
    assert first["model"] == "xiaomi/mimo-v2.6-pro"
    assert "response_format" not in first
    assert any(t["function"]["name"] == "get_order" for t in first["tools"])
    tool_message = next(m for m in second["messages"] if m["role"] == "tool")
    assert json.loads(tool_message["content"])["product"]["price_cents"] == 219900
    assert result["provider"] == "openrouter"
    assert "2.199,00" in result["message"]


@pytest.mark.parametrize(
    "http_status,code", [(401, "provider_auth_error"), (503, "provider_error")]
)
def test_openrouter_sdk_failure_is_sanitized_without_automatic_retries(
    tmp_path, monkeypatch, http_status, code
):
    from emporio.config import Settings
    from emporio.service import AgentUnavailable, ChatService

    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            http_status, json={"error": {"code": http_status, "message": "upstream-private-secret"}}
        )

    _intercept_httpx(monkeypatch, respond)
    svc = ChatService(
        Settings(
            provider="openrouter",
            OPENROUTER_API_KEY="test-router-key",
            data_dir=Path(__file__).resolve().parents[1] / "data",
            state_dir=tmp_path,
            _env_file=None,
        )
    )
    session = svc.create_session()["session_id"]
    with pytest.raises(AgentUnavailable) as exc:
        svc.chat(session, "Quanto custa o GD20?")
    assert len(requests) == 1
    assert exc.value.code == code
    assert "upstream-private-secret" not in str(exc.value)
    assert svc.sessions.history(session) == []
