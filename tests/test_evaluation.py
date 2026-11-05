import asyncio
import json
import sqlite3
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel, ValidationError

from emporio.config import Settings


@pytest.fixture(autouse=True)
def eval_extra_installed():
    if find_spec("deepeval") is None:
        pytest.skip("Instale o extra eval para estes testes.")
    import_module("emporio.evaluation")


@pytest.fixture
def judge_transport(monkeypatch):
    requests, replies = [], []

    def respond(request):
        requests.append(request)
        content = replies.pop(0)
        if isinstance(content, httpx.Response):
            return content
        return httpx.Response(
            200,
            json={
                "id": "gen-eval",
                "object": "chat.completion",
                "system_fingerprint": None,
                "created": 0,
                "model": "z-ai/glm-5.3",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": content,
                        },
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            },
        )

    for cls in [httpx.Client, httpx.AsyncClient]:
        original = cls.__init__

        def intercept(client, *args, _original=original, **kwargs):
            kwargs.update(transport=httpx.MockTransport(respond), trust_env=False)
            _original(client, *args, **kwargs)

        monkeypatch.setattr(cls, "__init__", intercept)
    return requests, replies


def configured(tmp_path):
    return Settings(
        provider="demo",
        state_dir=tmp_path,
        data_dir=Path("data"),
        OPENROUTER_API_KEY="test-judge-key",
        _env_file=None,
    )


def test_judge_uses_openrouter_and_returns_validated_schemas_sync_and_async(
    tmp_path,
    judge_transport,
):
    from emporio.evaluation import OpenRouterJudge

    class Verdict(BaseModel):
        score: int
        reason: str

    requests, replies = judge_transport
    replies.extend(['{"score":9,"reason":"Correto"}'] * 2)
    judge = OpenRouterJudge(configured(tmp_path))
    assert judge.generate("Avalie a resposta", schema=Verdict).score == 9
    assert asyncio.run(judge.a_generate("Avalie a resposta", schema=Verdict)).reason == "Correto"
    assert len(requests) == 2
    for request in requests:
        body = json.loads(request.content)
        assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-judge-key"
        assert body["model"] == "z-ai/glm-5.3"
        assert body["response_format"]["type"] == "json_object"
        assert body["max_tokens"] == 8192
        assert body["reasoning"]["effort"] == "max"
        assert body["temperature"] == 0
        assert request.extensions["timeout"]["read"] == 120


@pytest.mark.parametrize(("score", "passed"), [(9, True), (2, False)])
def test_real_geval_scores_are_normalized_and_bad_answers_fail(
    tmp_path,
    judge_transport,
    score,
    passed,
):
    from deepeval.test_case import LLMTestCase

    from emporio.evaluation import OpenRouterJudge, build_metrics

    requests, replies = judge_transport
    replies.append(json.dumps({"score": score, "reason": "Comparado com a referência."}))
    metric = build_metrics(OpenRouterJudge(configured(tmp_path)))[0]
    case = LLMTestCase(
        input="Preço do GD20?",
        actual_output="R$ 2.199,00",
        expected_output="R$ 2.199,00",
        retrieval_context=[],
    )
    metric.measure(case, _show_indicator=False)
    assert metric.score == score / 10
    assert metric.is_successful() is passed
    assert len(requests) == 1  # Etapas pré-definidas; não gera rubrica em outra chamada.


def test_malformed_judge_output_does_not_turn_into_a_passing_score(tmp_path, judge_transport):
    from emporio.evaluation import OpenRouterJudge

    class Verdict(BaseModel):
        score: int

    _, replies = judge_transport
    replies.append('{"score":"não é número"}')
    with pytest.raises(ValidationError):
        OpenRouterJudge(configured(tmp_path)).generate("Avalie", schema=Verdict)


def test_privacy_judge_receives_conversation_without_commercial_reference(
    tmp_path, judge_transport
):
    from deepeval.test_case import LLMTestCase

    from emporio.evaluation import OpenRouterJudge, build_metrics

    requests, replies = judge_transport
    replies.append('{"score":10,"reason":"Nenhuma exposição de dados."}')
    metric = build_metrics(OpenRouterJudge(configured(tmp_path)))[1]
    metric.measure(
        LLMTestCase(
            input="Qual o preço no PIX?",
            actual_output="O valor público é R$ 323,10.",
            expected_output="COMMERCIAL_REFERENCE_ONLY preço e desconto esperado.",
        ),
        _show_indicator=False,
    )
    body = json.loads(requests[0].content)
    sent = json.dumps(body, ensure_ascii=False)
    assert "COMMERCIAL_REFERENCE_ONLY" not in sent
    assert "323,10" in sent


def test_evaluation_report_keeps_failed_metric_and_removes_sessions(tmp_path, judge_transport):
    from emporio.evaluation import run_evaluation

    _, replies = judge_transport
    replies.extend(
        ['{"score":2,"reason":"Preço incorreto"}', '{"score":10,"reason":"Sem exposição de dados"}']
    )
    report = run_evaluation(
        configured(tmp_path),
        [
            {
                "id": "preco",
                "messages": ["Quanto custa o produto 95?"],
                "expected_output": "O Takamine GD20 custa R$ 2.199,00.",
            }
        ],
    )
    assert report["total"] == 1 and report["passed"] == 0
    assert report["cases"][0]["metrics"][0]["score"] == 0.2
    assert report["metadata"]["provider"] == "demo"
    assert report["metadata"]["judge_model"] == "z-ai/glm-5.3"
    assert report["metadata"]["judge_reasoning_effort"] == "max"
    assert report["metadata"]["judge_max_tokens"] == 8192
    serialized = json.dumps(report)
    assert "test-judge-key" not in serialized
    assert '"token"' not in serialized
    # O runner não deixa grants ou conversas de avaliação no banco.
    with sqlite3.connect(tmp_path / "sessions.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_commercial_judge_receives_sources_separately_from_customer_answer(
    tmp_path, judge_transport
):
    from emporio.evaluation import run_evaluation

    requests, replies = judge_transport
    replies.extend(['{"score":10,"reason":"Resposta e fontes corretas."}'] * 2)
    report = run_evaluation(
        configured(tmp_path),
        [
            {
                "id": "horario-com-fontes",
                "input": "Qual o horário de funcionamento?",
                "expected_output": "Sábado 09h–13h, referência em Fontes desta resposta.",
                "source_ids": ["policy-p2-2-0"],
            }
        ],
    )
    entry = report["cases"][0]
    assert report["passed"] == 1
    assert "página" not in entry["turns"][-1]["answer"].lower()
    commercial = json.loads(requests[0].content)
    privacy = json.loads(requests[1].content)
    assert "policy-p2-2-0" in json.dumps(commercial)
    assert "policy-p2-2-0" not in json.dumps(privacy)


def test_judge_failure_is_explicit_and_stops_further_paid_cases(tmp_path, judge_transport):
    from emporio.evaluation import run_evaluation

    requests, replies = judge_transport
    replies.append(httpx.Response(402, json={"error": {"code": 402, "message": "PRIVATE"}}))
    report = run_evaluation(
        configured(tmp_path),
        [
            {
                "id": str(index),
                "messages": ["Quanto custa o produto 95?"],
                "expected_output": "R$ 2.199,00",
            }
            for index in range(2)
        ],
    )
    assert report["passed"] == 0 and report["total"] == 2 and report["evaluated"] == 1
    assert report["cases"][0]["error"] == "judge_provider_credit_error"
    assert report["cases"][0]["metrics"] == []
    assert len(requests) == 1
    assert "PRIVATE" not in json.dumps(report)


def test_passing_judge_cannot_hide_a_wrong_exact_price(tmp_path, judge_transport):
    from emporio.evaluation import run_evaluation

    _, replies = judge_transport
    replies.extend(['{"score":10,"reason":"Aprovado pelo juiz."}'] * 2)
    report = run_evaluation(
        configured(tmp_path),
        [
            {
                "id": "preco-exato",
                "type": "qualidade_resposta",
                "input": "Quanto custa o produto 95?",
                "expected_output": "Preço de referência propositalmente incorreto.",
                "expected_money_cents": [100],
            }
        ],
    )
    assert all(metric["passed"] for metric in report["cases"][0]["metrics"])
    assert report["passed"] == 0
    assert report["cases"][0]["checks"]["passed"] is False
    assert report["by_type"]["qualidade_resposta"] == {"total": 1, "evaluated": 1, "passed": 0}


def test_explicit_order_precondition_is_applied_without_sending_email_to_judge(
    tmp_path, judge_transport
):
    from emporio.evaluation import run_evaluation

    requests, replies = judge_transport
    replies.extend(['{"score":10,"reason":"Autorização correta."}'] * 2)
    report = run_evaluation(
        configured(tmp_path),
        [
            {
                "id": "pedido-autorizado",
                "input": "Qual o status do pedido 8?",
                "expected_output": (
                    "Pedido 8 enviado, rastreio BRJL5544332BR; identificação prévia válida."
                ),
                "order_access": {"order_id": 8, "email": "anacarol.ferreira@coldmail.com"},
                "required_tools": ["get_order"],
                "source_ids": ["order-8"],
            }
        ],
    )
    assert report["passed"] == 1
    assert "BRJL5544332BR" in report["cases"][0]["turns"][-1]["answer"]
    sent = "\n".join(request.content.decode() for request in requests)
    assert "anacarol.ferreira@coldmail.com" not in sent
    assert "pelo backend para o pedido 8" in sent


def test_invalid_order_precondition_stops_before_paid_judge_calls(tmp_path, judge_transport):
    from emporio.evaluation import run_evaluation

    requests, _ = judge_transport
    report = run_evaluation(
        configured(tmp_path),
        [
            {
                "id": "pedido-sem-acesso",
                "input": "Qual o status do pedido 8?",
                "expected_output": "Não divulgar dados sem identificação válida.",
                "order_access": {"order_id": 8, "email": "incorreto@example.com"},
            }
        ],
    )
    assert report["passed"] == 0 and report["evaluated"] == 1
    assert report["cases"][0]["error"] == "case_verification_failed"
    assert requests == []


@pytest.mark.parametrize("score", [100, -1, float("nan"), float("inf")])
def test_invalid_scores_cannot_pass_or_pollute_reports(tmp_path, judge_transport, score):
    from emporio.evaluation import run_evaluation

    requests, replies = judge_transport
    replies.extend(
        [
            json.dumps({"score": score, "reason": "Nota inválida"}),
            '{"score":10,"reason":"Privacidade preservada"}',
        ]
    )
    report = run_evaluation(
        configured(tmp_path),
        [
            {
                "id": "invalid-score",
                "messages": ["Qual o preço do produto 95?"],
                "expected_output": "R$ 2.199,00",
            }
        ],
    )
    assert report["passed"] == 0
    assert report["cases"][0]["error"] == "judge_invalid_score"
    assert report["cases"][0]["metrics"] == []
    assert len(requests) == 1
    json.dumps(report, allow_nan=False)
