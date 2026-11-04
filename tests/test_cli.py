from pathlib import Path

import pytest
from typer.testing import CliRunner

from emporio import cli
from emporio.config import Settings
from emporio.service import AgentUnavailable, ChatService


@pytest.fixture
def configured(tmp_path, monkeypatch):
    settings = Settings(provider="demo", state_dir=tmp_path, data_dir=Path("data"), _env_file=None)
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    return settings


def test_ask_answers_and_marks_demo(configured):
    result = CliRunner().invoke(cli.app, ["ask", "Qual o horário de funcionamento?"])
    assert result.exit_code == 0, result.output
    assert "demo" in result.output.lower()
    assert "Fontes" in result.output
    assert "horário" in result.output.lower()


def test_ask_order_options_must_be_paired(configured):
    result = CliRunner().invoke(cli.app, ["ask", "Pedido?", "--order-id", "1"])
    assert result.exit_code != 0
    assert "email" in result.output.lower()


def test_provider_failure_is_friendly(configured, monkeypatch):
    def fail(*args, **kwargs):
        raise AgentUnavailable("SECRET")

    monkeypatch.setattr(ChatService, "chat", fail)
    result = CliRunner().invoke(cli.app, ["ask", "Oi"])
    assert result.exit_code == 1
    assert "indisponível" in result.output.lower()
    assert "SECRET" not in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("provider_auth_error", "autenticar no provedor"),
        ("provider_credit_error", "créditos e limites da chave"),
        ("provider_request_error", "modelo ou os parâmetros"),
        ("provider_rate_limit", "limitou as requisições"),
        ("provider_timeout", "tempo limite"),
        ("unknown_error", "indisponível"),
    ],
)
def test_provider_error_codes_show_only_safe_messages(configured, monkeypatch, code, expected):
    def fail(*args, **kwargs):
        raise AgentUnavailable("SECRET upstream response", code=code)

    monkeypatch.setattr(ChatService, "chat", fail)
    result = CliRunner().invoke(cli.app, ["ask", "Oi"])
    assert result.exit_code == 1
    assert expected in result.output
    assert "SECRET" not in result.output
    assert "Traceback" not in result.output


def test_startup_errors_do_not_expose_configuration(configured, monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("SECRET")

    monkeypatch.setattr(cli, "ChatService", fail)
    result = CliRunner().invoke(cli.app, ["ask", "Oi"])
    assert result.exit_code == 1
    assert "configuração" in result.output
    assert "SECRET" not in result.output


def test_chat_verification_command_does_not_send_email_to_model(configured, monkeypatch):
    verified, questions = [], []
    original = ChatService.chat

    def verify(self, sid, order_id, email):
        verified.append((order_id, email))
        return {"verified": True, "order_id": order_id}

    def chat(self, sid, message):
        questions.append(message)
        return original(self, sid, message)

    monkeypatch.setattr(ChatService, "verify_order", verify)
    monkeypatch.setattr(ChatService, "chat", chat)
    result = CliRunner().invoke(
        cli.app, ["chat"], input="/verificar 1 pessoa@example.com\nOlá\n/novo\n/sair\n"
    )
    assert result.exit_code == 0, result.output
    assert verified == [(1, "pessoa@example.com")]
    assert questions == ["Olá"]
    assert "Nova conversa" in result.output


def test_ingest_reports_counts_and_idempotence(configured):
    runner = CliRunner()
    first = runner.invoke(cli.app, ["ingest"])
    second = runner.invoke(cli.app, ["ingest"])
    assert first.exit_code == second.exit_code == 0
    assert "produtos" in second.output.lower()
    assert "idempotente" in second.output.lower()
    assert first.output == second.output


def test_serve_starts_uvicorn_with_requested_address(monkeypatch):
    import uvicorn

    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    result = CliRunner().invoke(cli.app, ["serve", "--host", "127.0.0.1", "--port", "8123"])
    assert result.exit_code == 0
    assert calls == [(("emporio.api:app",), {"host": "127.0.0.1", "port": 8123})]
