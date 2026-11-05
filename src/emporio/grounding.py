"""Verificações conservadoras de afirmações comerciais na resposta final.

São defesas complementares ao prompt, não um verificador semântico universal.
Fontes de políticas não autorizam afirmações de estoque/pedido. Valores em R$
precisam aparecer nos dados monetários ou no texto de política consultados neste turno.
"""

import re

from emporio.pricing import cents
from emporio.text import normalize

MONEY = re.compile(r"R\$\s*(\d+(?:\.\d{3})*(?:,\d{2})?)", re.I)
ORDER_STATUS = {
    "pending": "pendente",
    "confirmed": "confirmado",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}
BUDGET_LABEL_WORDS = frozenset(
    "a as o os algumas alguns estes estas esses essas aqui ha tem temos encontrei encontramos "
    "selecionei selecionamos sao seguem opcao opcoes selecao lista catalogo instrumento "
    "instrumentos produto produtos modelo modelos violao guitarra baixo bateria teclado piano "
    "ukulele disponivel disponiveis em estoque com para de do da dos das por seu sua meu minha "
    "um uma ate no maximo limite orcamento e dentro desse nesta nessa nylon aco classico "
    "classicos folk".split()
)
BUDGET_COUNT_SUBJECTS = frozenset(
    "opcao opcoes instrumento instrumentos produto produtos modelo modelos "
    "violao guitarra baixo bateria teclado piano ukulele".split()
)


def money_mentions(text: str) -> set[int]:
    return {cents(m.replace(".", "").replace(",", ".")) for m in MONEY.findall(text)}


def _cents_fields(value) -> set[int]:
    result = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith("_cents"):
                if type(item) is int:
                    result.add(item)
                elif isinstance(item, list):
                    result.update(n for n in item if type(n) is int)
            elif isinstance(item, (dict, list)):
                result.update(_cents_fields(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_cents_fields(item))
    return result


def _without_search_budget_limits(answer: str, outputs: list[dict]) -> str:
    """Um teto executado na busca não é uma afirmação de preço do instrumento."""
    budgets: dict[int, set[int]] = {}
    for output in outputs:
        if (
            output.get("name") == "search_products"
            and "error" not in output["result"]
            and output.get("args", {}).get("max_price_brl") is not None
        ):
            budget = cents(output["args"]["max_price_brl"])
            budgets.setdefault(budget, set()).add(len(output["result"].get("products", [])))

    def check(match: re.Match) -> str:
        value = cents(match[1].replace(".", "").replace(",", "."))
        if value not in budgets:
            return match[0]
        clause = re.split(r"\n|(?<=[.!?])\s+", answer[: match.start()])[-1]
        before = normalize(clause)
        after = normalize(answer[match.end() :])
        limit = re.search(
            r"\b(?:ate|no maximo|orcamento(?: de| e| ate)?|limite(?: de preco)? de)$", before
        )
        catalogue_scope = re.search(
            r"\b(?:opcao|opcoes|selecao|catalogo|instrumentos?|produtos?|modelos?|orcamento|"
            r"violao|guitarra|baixo|bateria|teclado|piano|ukulele)\b",
            before,
        )
        # Só rótulos de filtro com vocabulário restrito; não ampliar a exceção a
        # afirmações comerciais sobre preços, frete, descontos ou reembolso.
        words = before.split()
        plain_label = all(
            word in BUDGET_LABEL_WORDS
            or (
                word.isdigit()
                and int(word) in budgets[value]
                and i + 1 < len(words)
                and words[i + 1] in BUDGET_COUNT_SUBJECTS
                and (i == 0 or words[i - 1] not in BUDGET_COUNT_SUBJECTS)
            )
            for i, word in enumerate(words)
        )
        other_subject_after = re.match(
            r"^(?:(?:de|em|para|no)\s+)?"
            r"(?:fretes?|taxas?|descontos?|reembols\w*|pix|parcelas?|pagamento)\b",
            after,
        )
        return (
            ""
            if limit and catalogue_scope and plain_label and not other_subject_after
            else match[0]
        )

    return MONEY.sub(check, answer)


def supported_answer(answer: str, outputs: list[dict]) -> bool:
    checked_answer = _without_search_budget_limits(answer, outputs)
    payloads = [o["result"] for o in outputs if "error" not in o["result"]]
    # Uma comparação em lote exige cobertura de cada modelo e dos valores calculados,
    # mesmo quando a pergunta contém outros assuntos e continua no ciclo generativo.
    stated_money = money_mentions(answer)
    for payload in payloads:
        if (
            payload.get("quotes")
            and payload.get("installments_example")
            and "exemplo" not in normalize(answer).split()
        ):
            return False
        for item in payload.get("quotes", []):
            if normalize(item["name"]) not in normalize(answer):
                return False
            if item["status"] == "ok":
                expected = {item["total_cents"], *item["installment_cents"]}
                if not expected <= stated_money:
                    return False
    known_money = _cents_fields(payloads)
    for payload in payloads:
        for source in payload.get("sources", []):
            if source["kind"] == "policy":
                known_money.update(money_mentions(source.get("excerpt", "")))
    if not money_mentions(checked_answer).issubset(known_money):
        return False
    commercial_money, discount_money = set(), set()
    for payload in payloads:
        for key in ("product", "products", "quote", "quotes"):
            data = payload.get(key, {})
            if key in {"quote", "quotes"}:
                quotes = data if isinstance(data, list) else [data]
                # Economia é evidência para o desconto, não para o preço do instrumento.
                for item in quotes:
                    discount_money.update(
                        _cents_fields(
                            {k: v for k, v in item.items() if k.endswith("discount_cents")}
                        )
                    )
                data = [
                    {k: v for k, v in item.items() if not k.endswith("discount_cents")}
                    for item in quotes
                ]
            commercial_money.update(_cents_fields(data))
    # R$ 35 de frete não sustenta a afirmação de que um instrumento custa R$ 35.
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", checked_answer):
        amounts = set()
        for match in MONEY.finditer(sentence):
            value = cents(match.group(1).replace(".", "").replace(",", "."))
            if value in discount_money - commercial_money:
                before = normalize(sentence[: match.start()])
                after = normalize(sentence[match.end() :])
                labelled_discount = re.search(
                    r"\b(?:desconto|economia|abatimento|economiza)"
                    r"(?:\s+(?:de|no|pix|a|vista|aplicado|promocional|ativo|ativa|total|\d+))*$",
                    before,
                ) or re.match(r"^(?:de\s+)?(?:desconto|economia|abatimento)\b", after)
                if not labelled_discount:
                    return False
                continue
            amounts.add(value)
        wording = normalize(sentence)
        price_claim = re.search(
            r"\b(?:custa|custam|preco|total dos produtos|por unidade)\b", wording
        )
        policy_subject = re.search(r"\b(?:frete|taxa|parcela|parcelamento|boleto)\b", wording)
        instrument_subject = re.search(
            r"\b(?:violao|guitarra|baixo|bateria|teclado|piano|ukulele|produto|modelo)\b"
            r"|\b[a-z]{1,5}\d{2,4}[a-z]?\b",
            wording,
        )
        if amounts and price_claim and (not policy_subject or instrument_subject):
            if not amounts.issubset(commercial_money):
                return False

    products = [p for data in payloads for p in data.get("products", [])]
    products.extend(data["product"] for data in payloads if "product" in data)
    has_catalog = bool(products) or any("quote" in data or data.get("quotes") for data in payloads)
    text = normalize(answer)
    stock_claim = re.search(
        r"\b(?:esta|estao|tem|temos|ha)\s+(?:\d+\s+)?(?:em\s+)?"
        r"(?:estoque|disponivel|disponiveis|esgotado|indisponivel)\b",
        text,
    )
    if stock_claim and not has_catalog:
        return False

    orders = [data["order"] for data in payloads if "order" in data]
    claims = re.findall(
        r"\bpedido(?:\s+(\d+))?\s+(?:(?:esta|foi)\s+)?"
        r"(entregue|enviado|cancelado|confirmado|pendente|despachado)\b",
        text,
    )
    for order_id, status in claims:
        status = {"despachado": "enviado"}.get(status, status)
        if not any(
            (not order_id or order["order_id"] == int(order_id))
            and ORDER_STATUS.get(order["status"]) == status
            for order in orders
        ):
            return False
    tracking = set(re.findall(r"\bBR[A-Z0-9]{7,14}BR\b", answer))
    known_tracking = {o["tracking_code"] for o in orders if o["tracking_code"]}
    for data in payloads:
        for source in data.get("sources", []):
            if source["kind"] == "policy":
                known_tracking.update(
                    re.findall(r"\bBR[A-Z0-9]{7,14}BR\b", source.get("excerpt", ""))
                )
    if not tracking.issubset(known_tracking):
        return False
    return True
