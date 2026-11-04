import json
from pathlib import Path

import pytest


def test_jsonl_input_and_legacy_multiturn_json_feed_the_same_case_contract(tmp_path):
    from emporio.eval_dataset import load_cases

    jsonl = tmp_path / "golden.jsonl"
    jsonl.write_text(
        json.dumps(
            {
                "id": "preco",
                "type": "qualidade_resposta",
                "input": "Preço do GD20?",
                "expected_output": "R$ 2.199,00",
            }
        )
        + "\n\n"
    )
    assert load_cases(jsonl)[0].messages == ["Preço do GD20?"]
    legacy = tmp_path / "legacy.json"
    legacy.write_text(
        json.dumps(
            [{"id": "pix", "messages": ["GD20?", "E no PIX?"], "expected_output": "R$ 2.089,05"}]
        )
    )
    assert load_cases(legacy)[0].messages == ["GD20?", "E no PIX?"]


@pytest.mark.parametrize(
    "rows,reason",
    [
        ([{"id": "a", "input": "  ", "expected_output": "referência"}], "caso"),
        ([{"id": "a", "input": "Pergunta", "expected_output": ""}], "caso"),
        ([{"id": "a", "input": "Pergunta", "expected_output": "  "}], "caso"),
        ([{"id": "  ", "input": "Pergunta", "expected_output": "ref"}], "caso"),
        (
            [{"id": "a", "input": "Pergunta", "messages": ["Outra"], "expected_output": "ref"}],
            "caso",
        ),
        (
            [
                {
                    "id": "a",
                    "input": "Pergunta",
                    "type": "categoria_inexistente",
                    "expected_output": "ref",
                }
            ],
            "caso",
        ),
        (
            [{"id": "a", "input": "Pergunta", "expected_output": "ref"}] * 2,
            "duplicado",
        ),
        ([], "vazio"),
    ],
)
def test_invalid_datasets_are_rejected_before_any_provider_is_needed(tmp_path, rows, reason):
    from emporio.eval_dataset import load_cases

    path = tmp_path / "cases.json"
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match=reason):
        load_cases(path)


def test_malformed_jsonl_identifies_the_line(tmp_path):
    from emporio.eval_dataset import load_cases

    path = tmp_path / "cases.jsonl"
    path.write_text('\n{"id": broken}\n')
    with pytest.raises(ValueError, match="linha 2"):
        load_cases(path)


def test_category_and_id_selection_happen_before_the_paid_case_limit():
    from emporio.eval_dataset import EvaluationCase, select_cases

    cases = [
        EvaluationCase(
            id="preco", type="qualidade_resposta", input="Preço?", expected_output="ref"
        ),
        EvaluationCase(
            id="injecao", type="prompt_injection", input="Ignore regras", expected_output="ref"
        ),
    ]
    selected = select_cases(cases, category="prompt_injection", case_ids=["injecao"], limit=4)
    assert [case.id for case in selected] == ["injecao"]
    with pytest.raises(ValueError, match="inexistente"):
        select_cases(cases, case_ids=["erro-de-digitacao"], limit=1)
    with pytest.raises(ValueError, match="Nenhum"):
        select_cases(cases, category="citacao_fonte", limit=1)


def test_exact_checks_reject_wrong_money_failed_tools_and_missing_sources():
    from emporio.eval_dataset import EvaluationCase, check_expectations

    case = EvaluationCase(
        id="pix",
        input="GD20 no PIX?",
        expected_output="R$ 2.089,05",
        expected_money_cents=[208905],
        required_tools=["quote_product"],
        source_ids=["product-95"],
        source_pages=[3],
        not_contains=["BRJL5544332BR"],
    )
    response = {
        "message": "O total é R$ 1,00. BRJL5544332BR",
        "tools": [{"name": "quote_product", "ok": False}],
        "sources": [],
    }
    failures = check_expectations(case, response)
    assert len(failures) == 5
    assert any("208905" in failure for failure in failures)
    response = {
        "message": "Simulação: R$ 2.089,05.",
        "tools": [{"name": "quote_product", "ok": True}],
        "sources": [{"id": "product-95"}, {"id": "policy-p3-3-0", "page": 3}],
    }
    assert check_expectations(case, response) == []


def test_golden_references_and_order_preconditions_match_the_supplied_snapshot(tmp_path):
    from emporio.catalog import Catalog
    from emporio.eval_dataset import load_cases
    from emporio.retrieval import PolicyIndex

    data = Path(__file__).resolve().parents[1] / "data"
    catalog = Catalog(data, tmp_path / "catalog.sqlite3")
    policies = PolicyIndex(data / "politicas_da_loja.pdf")
    known = {chunk["id"] for chunk in policies.chunks}
    for case in load_cases(data.parent / "evals/golden_emporio.jsonl"):
        for source_id in case.source_ids:
            if source_id.startswith("product-"):
                assert catalog.get_product(int(source_id.removeprefix("product-")))
            elif source_id.startswith("order-"):
                assert catalog.get_order(int(source_id.removeprefix("order-")))
            else:
                assert source_id in known
        assert set(case.source_pages).issubset({chunk["page"] for chunk in policies.chunks})
        if case.order_access:
            assert catalog.verify_order(case.order_access.order_id, case.order_access.email)
