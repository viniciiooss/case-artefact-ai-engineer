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


def supported_answer(answer: str, outputs: list[dict]) -> bool:
    payloads = [o["result"] for o in outputs if "error" not in o["result"]]
    known_money = _cents_fields(payloads)
    for payload in payloads:
        for source in payload.get("sources", []):
            if source["kind"] == "policy":
                known_money.update(money_mentions(source.get("excerpt", "")))
    if not money_mentions(answer).issubset(known_money):
        return False
    commercial_money, discount_money = set(), set()
    for payload in payloads:
        for key in ("product", "products", "quote"):
            data = payload.get(key, {})
            if key == "quote":
                # Economia é evidência para o desconto, não para o preço do instrumento.
                discount_money.update(
                    _cents_fields({k: v for k, v in data.items() if k.endswith("discount_cents")})
                )
                data = {k: v for k, v in data.items() if not k.endswith("discount_cents")}
            commercial_money.update(_cents_fields(data))
    # R$ 35 de frete não sustenta a afirmação de que um instrumento custa R$ 35.
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", answer):
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
    has_catalog = bool(products) or any("quote" in data for data in payloads)
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
