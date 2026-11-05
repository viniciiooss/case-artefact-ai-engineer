"""Comparações completas: seleção explícita, cálculos das ferramentas e texto determinístico."""

import re
from collections import Counter

from emporio.pricing import brl
from emporio.text import normalize

REQUEST_WORDS = set(
    "faca fazer simule simular simulacao simulacoes quero gostaria pode poderia me por favor "
    "a o as os de do da dos das desses dessas destes destas todos todas modelos "
    "produtos violao preco no na em e com tanto quanto pix cartao credito parcelado parcelada "
    "parcelados parceladas parcelamento parcela parcelas vezes folk nylon aco".split()
)
GROUPS = {"folk", "nylon", "aco"}
COUNTS = {
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
    "onze": 11,
    "doze": 12,
}
INSTALLMENTS = re.compile(
    r"\b(\d{1,2})x\b|\b(\d{1,2}|" + "|".join(COUNTS) + r") (?:vezes|parcela)\b"
)
ALL_FOLLOWUPS = {"faca de todos", "faca todos", "simule todos", "de todos", "todos"}


def comparison_question(question: str, history: list[dict]) -> str:
    """Recupera só a intenção de pagamento de uma continuação explícita; nunca preços."""
    if normalize(question) not in ALL_FOLLOWUPS:
        return question
    for entry in reversed(history):
        if entry["role"] != "user" or normalize(entry["content"]) in ALL_FOLLOWUPS:
            continue
        previous = entry["content"]
        text = normalize(previous)
        if "pix" in text.split() and ("parcel" in text or installment_counts(previous)):
            return previous
        break
    return question


def installment_counts(question: str) -> list[int]:
    text = normalize(question)
    simple = set(INSTALLMENTS.sub("", text).split()) <= REQUEST_WORDS
    counts = []
    for match in INSTALLMENTS.finditer(text):
        a, b = match.groups()
        if a and not simple:
            # Em pedidos mistos, "2X" também pode ser parte de um modelo (Ibanez Bass 2X).
            before, after = text[: match.start()].strip(), text[match.end() :].strip()
            payment_context = re.search(
                r"\b(?:em|cartao|credito|parcelado|parcelar|parcelamento)$", before
            ) or re.match(r"(?:(?:no|em) (?:cartao|credito)|sem juros)\b", after)
            if not payment_context:
                continue
        counts.append(int(a or b) if (a or b).isdigit() else COUNTS[b])
    return list(dict.fromkeys(counts))


def comparison_request(question: str, context: dict) -> dict | None:
    """Só referências simples à seleção anterior; cidade/quantidade/outros pedidos ficam na LLM."""
    text = normalize(question)
    installments = installment_counts(question)
    if len(installments) > 1 or any(not 2 <= n <= 12 for n in installments):
        return None
    without_counts = INSTALLMENTS.sub("", text)
    words = set(without_counts.split())
    if not words <= REQUEST_WORDS or "pix" not in words:
        return None
    if not installments and not words & {
        "parcelado",
        "parcelada",
        "parcelados",
        "parceladas",
        "parcelamento",
    }:
        return None
    groups = words & GROUPS
    if len(groups) > 1 or not (groups or words & {"todos", "todas", "desses", "dessas"}):
        return None
    ids = context.get("products", [])
    if not 2 <= len(ids) <= 10 or any(type(i) is not int or i < 1 for i in ids):
        return None
    return {
        "product_ids": list(dict.fromkeys(ids)),
        "query": next(iter(groups), ""),
        "installments": installments[0] if installments else None,
    }


def comparison_reply(payload: dict) -> str:
    quotes = payload["quotes"]
    if not quotes:
        return (
            "Não encontrei modelos desse tipo na seleção anterior. Qual modelo você quer simular?"
        )
    blocks = ["Estas são as simulações individuais dos modelos selecionados, no PIX e no cartão."]
    if payload["installments_example"]:
        blocks.append("Como você não definiu o número de parcelas, usei **3x como exemplo**.")
    for product_id in dict.fromkeys(q["product_id"] for q in quotes):
        pix, credit = [q for q in quotes if q["product_id"] == product_id]
        lines = [f"**{pix['name']}**"]
        if pix["status"] == "unavailable":
            lines.append("- PIX e cartão: **indisponível para compra** no catálogo atual.")
            blocks.append("\n".join(lines))
            continue
        lines.append(f"- Preço de tabela: **{brl(pix['original_unit_cents'])}**.")
        discount = ""
        if pix["discount_percent"]:
            label = "desconto PIX" if pix["pix_applied"] else "desconto em promoção ativa"
            discount = f" ({pix['discount_percent']}% de {label})"
        lines.append(f"- PIX: **{brl(pix['total_cents'])}**{discount}.")
        n = payload["installments"]
        if credit["status"] != "ok":
            condition = (
                "não atende às condições de parcelamento"
                if credit["status"] == "invalid"
                else "depende de confirmação da equipe"
            )
            lines.append(f"- Cartão em **{n}x**: {condition}. " + " ".join(credit["notes"]))
        else:
            parts = Counter(credit["installment_cents"])
            amounts = " + ".join(f"{count} de **{brl(value)}**" for value, count in parts.items())
            lines.append(
                f"- Cartão em **{n}x sem juros**: {amounts}; "
                f"total **{brl(credit['total_cents'])}**."
            )
        blocks.append("\n".join(lines))
    blocks.append("O desconto PIX não acumula com promoções.")
    blocks.append(
        "Valores sem frete; a entrega depende da cidade. "
        "É uma simulação, sem reserva de estoque nem compra concluída."
    )
    return "\n\n".join(blocks)
