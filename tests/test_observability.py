import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from emporio.config import Settings
from emporio.service import AgentUnavailable, ChatService


def test_tracing_requires_its_own_credentials(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="LANGFUSE"):
        Settings(langfuse_enabled=True, _env_file=None)


@pytest.fixture
def tracing(tmp_path, monkeypatch):
    langfuse = pytest.importorskip("langfuse")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    original = langfuse.Langfuse
    clients = []

    def local_exporter(**kwargs):
        def no_network(request):
            raise AssertionError("O teste não deve consultar a API Langfuse.")

        client = original(
            **kwargs,
            tracer_provider=TracerProvider(),
            span_exporter=exporter,
            httpx_client=httpx.Client(transport=httpx.MockTransport(no_network)),
        )
        clients.append(client)
        return client

    monkeypatch.setattr(langfuse, "Langfuse", local_exporter)
    settings = Settings(
        provider="demo",
        data_dir=Path("data"),
        state_dir=tmp_path,
        langfuse_enabled=True,
        LANGFUSE_PUBLIC_KEY="pk-lf-test-" + uuid4().hex,
        LANGFUSE_SECRET_KEY="sk-lf-PRIVATE-credential",
        _env_file=None,
    )
    yield settings, exporter
    for client in clients:
        client.shutdown()


def test_real_graph_exports_tool_timing_without_conversation_or_session_credentials(tracing):
    settings, exporter = tracing
    svc = ChatService(settings)
    session = svc.create_session()
    answer = svc.chat(
        session["session_id"], "Quanto custa o produto 95? Meu email é PRIVATE@example.com"
    )
    svc.close()
    assert "2.199,00" in answer["message"]
    spans = exporter.get_finished_spans()
    assert any(span.name == "get_product" for span in spans)
    assert any(span.name == "emporio.chat" for span in spans)
    assert all(span.end_time >= span.start_time for span in spans)
    payload = json.dumps([json.loads(span.to_json()) for span in spans])
    for private in [
        "PRIVATE@example.com",
        "Quanto custa",
        session["session_id"],
        session["token"],
        "sk-lf-PRIVATE-credential",
    ]:
        assert private not in payload
    assert "session.id" in payload


def test_raw_upstream_error_is_not_exported_in_otel_status_or_attributes(tracing):
    class FailingModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            raise RuntimeError("PRIVATE upstream response with bearer credentials")

    settings, exporter = tracing
    svc = ChatService(settings, model=FailingModel())
    with pytest.raises(AgentUnavailable):
        svc.chat(svc.create_session()["session_id"], "Oi")
    svc.close()
    spans = exporter.get_finished_spans()
    assert spans
    payload = json.dumps([json.loads(span.to_json()) for span in spans])
    assert "PRIVATE" not in payload
    assert any(span.status.status_code.name == "ERROR" for span in spans)


def test_embedded_media_is_not_queued_for_upload(tracing, monkeypatch):
    from langfuse._task_manager.media_manager import MediaManager

    jobs = []
    monkeypatch.setattr(
        MediaManager, "_process_upload_media_job", lambda self, *, data: jobs.append(data)
    )
    settings, exporter = tracing
    svc = ChatService(settings)
    svc.chat(
        svc.create_session()["session_id"],
        "data:text/plain;base64,UFJJVkFURS1tZWRpYS1jb250ZW50",
    )
    svc.close()
    assert exporter.get_finished_spans()
    assert jobs == []


def test_collector_initialization_failure_does_not_break_chat(tmp_path, monkeypatch, caplog):
    langfuse = pytest.importorskip("langfuse")

    def fail(**kwargs):
        raise RuntimeError("PRIVATE credentials")

    monkeypatch.setattr(langfuse, "Langfuse", fail)
    svc = ChatService(
        Settings(
            provider="demo",
            state_dir=tmp_path,
            data_dir=Path("data"),
            _env_file=None,
            langfuse_enabled=True,
            LANGFUSE_PUBLIC_KEY="pk-test",
            LANGFUSE_SECRET_KEY="sk-test",
        )
    )
    response = svc.chat(svc.create_session()["session_id"], "Quanto custa o GD20?")
    assert "2.199,00" in response["message"]
    assert "PRIVATE" not in caplog.text
    svc.close()
