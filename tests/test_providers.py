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
