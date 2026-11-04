from pathlib import Path

import pytest

PDF = Path(__file__).resolve().parents[1] / "data/politicas_da_loja.pdf"


@pytest.mark.parametrize(
    "query,page,term",
    [
        ("Qual o horário de funcionamento aos sábados?", 2, "13:00"),
        ("Como funciona o parcelamento em 12x?", 3, "100,00"),
        ("Me arrependi da compra online e quero devolver", 4, "sete"),
        ("O desconto PIX acumula com promoção?", 6, "cumulativas"),
        ("Qual o endereço da loja?", 2, "3200"),
    ],
)
def test_retrieval_finds_real_policy_with_page(query, page, term):
    from emporio.retrieval import PolicyIndex

    hits = PolicyIndex(PDF).search(query, limit=4)
    assert any(h["page"] == page and term in h["excerpt"].lower() for h in hits)
    assert all(h["kind"] == "policy" and h["id"] for h in hits)


def test_unrelated_query_has_no_fabricated_source():
    from emporio.retrieval import PolicyIndex

    assert PolicyIndex(PDF).search("fotossíntese quasar") == []


def test_whatsapp_citation_distinguishes_the_dedicated_channel():
    from emporio.retrieval import PolicyIndex

    hits = PolicyIndex(PDF).search("Atendimento via WhatsApp", limit=3)
    assert any("3321-4500" in h["excerpt"] for h in hits)
