from pathlib import Path

import pytest

from emporio.config import Settings
from emporio.grounding import money_mentions
from emporio.service import ChatService

DATA = Path(__file__).resolve().parents[1] / "data"
SELECTION = [83, 85, 89, 88, 81, 84, 87, 86, 107, 82]
FOLK = [89, 88, 87, 86]
FULL_COMPARISON = (
    "Shelby SN-100 Folk Aço Preto: PIX R$ 521,55, cartão em 3x de R$ 183,00, total R$ 549,00. "
    "Giannini GF-1R Aço Folk Sunburst: PIX R$ 550,91, 3x de R$ 193,30, total R$ 579,90. "
    "Yamaha F310 Aço Natural: PIX R$ 664,91, 3x de R$ 233,30, total R$ 699,90. "
    "Tagima Dallas Tuner Aço Natural: PIX R$ 711,55, 2 parcelas de R$ 249,67 e uma de "
    "R$ 249,66, total R$ 749,00. Simulação sem reserva nem compra concluída."
)


class NoModel:
    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        raise AssertionError("Uma comparação explícita da seleção não precisa de geração.")


def seeded_service(tmp_path, model=None):
    svc = ChatService(
        Settings(provider="demo", data_dir=DATA, state_dir=tmp_path, _env_file=None),
        model=model or NoModel(),
    )
    sid = svc.create_session()["session_id"]
    svc.sessions.save_turn(
        sid,
        "Quais violões disponíveis custam até R$ 1.000?",
        {"message": "Nylon: AC-39, RC-104, C40, GN-15, C70. Folk: SN-100, GF-1R, F310, Dallas."},
        {"products": SELECTION},
    )
    return svc, sid


def test_exact_followup_quotes_every_folk_in_both_payment_modes(tmp_path):
    svc, sid = seeded_service(tmp_path)
    result = svc.chat(sid, "faça a simulacao no pix e parcelado dos folk")
    answer = result["message"]
    assert {52155, 55091, 66491, 71155, 18300, 19330, 23330, 24967, 24966} <= money_mentions(answer)
    for product_id in FOLK:
        assert svc.catalog.get_product(product_id)["name"] in answer
    assert {s["id"] for s in result["sources"] if s["kind"] == "catalog"} == {
        f"product-{i}" for i in FOLK
    }
    assert "3x" in answer and "exemplo" in answer
    assert "sem reserva" in answer and "frete" in answer.lower()
    assert "PIX não acumula com promoções" in answer
    assert "não foram simulados" not in answer
    assert result["model_calls"] == 0
    assert result["execution_path"] == "quote_comparison"
    assert svc.sessions.context(sid)["products"] == FOLK
    assert svc.sessions.history(sid)[-1]["content"] == answer


def test_explicit_installments_are_respected_and_invalid_options_are_not_offered(tmp_path):
    svc, sid = seeded_service(tmp_path)
    result = svc.chat(sid, "Simule no PIX e em 12x dos folk")
    answer = result["message"]
    for product_id in FOLK:
        assert svc.catalog.get_product(product_id)["name"] in answer
    assert {52155, 55091, 66491, 71155} <= money_mentions(answer)
    assert "12x" in answer and "não atende" in answer
    assert "exemplo" not in answer
    assert "sem juros: 12x" not in answer


def test_comparison_reconsults_stock_and_does_not_omit_unavailable_products(tmp_path):
    from emporio.db import connection

    svc, sid = seeded_service(tmp_path)
    with connection(svc.catalog.db_path) as conn:
        conn.execute("UPDATE products SET stock_quantity=0 WHERE product_id=87")
    result = svc.chat(sid, "Faça a simulação no PIX e parcelado dos folk")
    assert "Yamaha F310 Aço Natural" in result["message"]
    assert "indisponível" in result["message"]
    assert 66491 not in money_mentions(result["message"])
    assert svc.sessions.context(sid)["products"] == FOLK


def test_model_requested_batch_preserves_the_normal_agent_cycle(tmp_path):
    from langchain_core.messages import AIMessage

    class BatchModel(NoModel):
        calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 2:
                return AIMessage(content=FULL_COMPARISON)
            assert self.calls == 1
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "quote_products",
                        "args": {"product_ids": FOLK, "installments": 3},
                        "id": "all-folk",
                    }
                ],
            )

    model = BatchModel()
    svc, sid = seeded_service(tmp_path, model)
    # Linguagem fora do roteamento determinístico: a LLM escolhe a ferramenta.
    result = svc.chat(sid, "Compare os quatro folk no PIX e no crédito em três vezes.")
    assert result["model_calls"] == 2
    assert {52155, 55091, 66491, 71155, 18300, 19330, 23330, 24967, 24966} <= money_mentions(
        result["message"]
    )
    assert svc.sessions.context(sid)["products"] == FOLK


def test_batch_keeps_promotion_rules_and_does_not_turn_savings_into_a_price(tmp_path):
    from datetime import date

    from emporio.grounding import supported_answer
    from emporio.tools import make_tools

    svc, sid = seeded_service(tmp_path)
    tool = next(
        t
        for t in make_tools(
            svc.catalog, svc.policies, svc.sessions, sid, "Simule em 3x", date.today()
        )
        if t.name == "quote_products"
    )
    result = tool.invoke({"product_ids": [127], "installments": 3})
    pix, credit = result["quotes"]
    assert pix["total_cents"] == credit["total_cents"] == 32310
    assert pix["discount_percent"] == 10 and not pix["pix_applied"]
    outputs = [{"result": result}]
    name = "Kalani KAL-700T Tenor Natural"
    assert supported_answer(
        f"{name} por R$ 323,10; 3x de R$ 107,70; economia de R$ 35,90.", outputs
    )
    assert not supported_answer(
        f"O {name} custa R$ 35,90; PIX R$ 323,10; 3x de R$ 107,70.", outputs
    )


def test_mixed_request_continues_to_other_tools_after_a_batch_quote(tmp_path):
    from langchain_core.messages import AIMessage

    class MixedModel(NoModel):
        calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "quote_products",
                            "args": {"product_ids": FOLK, "installments": 3},
                            "id": "compare",
                        }
                    ],
                )
            if self.calls == 2:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_policies",
                            "args": {"query": "horário de funcionamento"},
                            "id": "hours",
                        }
                    ],
                )
            return AIMessage(
                content=FULL_COMPARISON
                + " Usei 3x como exemplo. A loja abre de segunda a sexta das 09h às 18h."
            )

    svc, sid = seeded_service(tmp_path, MixedModel())
    result = svc.chat(sid, "Simule no PIX e parcelado dos folk e me diga o horário de atendimento.")
    assert result["model_calls"] == 3
    assert [t["name"] for t in result["tools"]] == ["quote_products", "search_policies"]
    assert "09h às 18h" in result["message"]
    assert "711,55" in result["message"]


def test_partial_model_summary_after_batch_is_rejected_and_repaired(tmp_path):
    from langchain_core.messages import AIMessage

    class PartialModel(NoModel):
        calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "quote_products",
                            "args": {"product_ids": FOLK, "installments": 3},
                            "id": "compare",
                        }
                    ],
                )
            if self.calls == 2:
                return AIMessage(
                    content="Shelby SN-100 Folk Aço Preto: PIX R$ 521,55, 3x de R$ 183,00."
                )
            return AIMessage(content=FULL_COMPARISON)

    svc, sid = seeded_service(tmp_path, PartialModel())
    result = svc.chat(sid, "Compare os quatro folk no PIX e no crédito em três vezes.")
    assert result["model_calls"] == 3
    assert result["message"] == FULL_COMPARISON
    assert len(svc.sessions.history(sid)) == 4


def test_default_installments_cannot_be_chosen_silently_by_the_model(tmp_path):
    from datetime import date

    from emporio.grounding import supported_answer
    from emporio.tools import make_tools

    svc, sid = seeded_service(tmp_path)
    tool = next(
        t
        for t in make_tools(
            svc.catalog,
            svc.policies,
            svc.sessions,
            sid,
            "Simule no PIX e parcelado dos folk e me diga os horários.",
            date.today(),
        )
        if t.name == "quote_products"
    )
    result = tool.invoke({"product_ids": FOLK, "installments": 12})
    assert result["installments"] == 3 and result["installments_example"] is True
    assert not supported_answer(FULL_COMPARISON, [{"result": result}])
    assert supported_answer(FULL_COMPARISON + " Usei 3x como exemplo.", [{"result": result}])


@pytest.mark.parametrize(
    "question,counts",
    [
        ("faça a simulacao no pix e parcelado dos folk", []),
        ("Simule os folk no PIX e 6x", [6]),
        ("Simule os folk em doze vezes e me diga o horário", [12]),
        ("Compare os folk no PIX e parcelado e veja se tem Ibanez Bass 2X", []),
        ("Compare os folk no PIX e em 12x e veja se tem Ibanez Bass 2X", [12]),
    ],
)
def test_installment_counts_do_not_treat_model_names_as_payment_terms(question, counts):
    from emporio.comparisons import installment_counts

    assert installment_counts(question) == counts


def test_individual_quote_calls_keep_all_selected_products_in_context(tmp_path):
    from langchain_core.messages import AIMessage

    class IndividualModel(NoModel):
        calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "quote_product",
                            "args": {"product_id": i, "payment": "pix"},
                            "id": f"quote-{i}",
                        }
                        for i in FOLK
                    ],
                )
            return AIMessage(content="Simulações: R$ 521,55, R$ 550,91, R$ 664,91 e R$ 711,55.")

    svc, sid = seeded_service(tmp_path, IndividualModel())
    svc.chat(sid, "Simule só o PIX dos quatro folk.")
    assert svc.sessions.context(sid)["products"] == FOLK


def test_empty_filtered_selection_asks_for_a_model_instead_of_inventing_a_quote(tmp_path):
    svc, sid = seeded_service(tmp_path)
    svc.sessions.save_turn(
        sid, "Mostre nylon", {"message": "AC-39 e RC-104"}, {"products": [83, 85]}
    )
    result = svc.chat(sid, "Simule no PIX e parcelado dos folk")
    assert "Não encontrei" in result["message"]
    assert not money_mentions(result["message"])


@pytest.mark.parametrize(
    "question",
    [
        "faça a simulacao no pix e parcelado dos folk para Campo Grande",
        "faça a simulacao no pix e parcelado de 2 unidades dos folk",
        "faça a simulacao no pix e parcelado só do primeiro folk",
        "faça a simulacao no pix e parcelado dos folk e veja o pedido 8",
        "não faça a simulacao no pix e parcelado dos folk",
    ],
)
def test_comparison_route_does_not_drop_other_constraints_or_actions(tmp_path, question):
    from langchain_core.messages import AIMessage

    class Clarifier(NoModel):
        def invoke(self, messages):
            return AIMessage(content="Pode confirmar os detalhes da simulação?")

    svc, sid = seeded_service(tmp_path, Clarifier())
    result = svc.chat(sid, question)
    assert result["execution_path"] == "agent"
    assert result["model_calls"] == 1
