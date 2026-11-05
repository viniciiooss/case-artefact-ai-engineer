"""Regras comerciais explícitas. A LLM nunca faz os cálculos monetários."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from emporio.text import normalize


def cents(value: str | int | float | Decimal) -> int:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError("Valor monetário deve ser finito e não negativo.")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def discounted(price_cents: int, percent: int) -> int:
    return (price_cents * (100 - percent) + 50) // 100


def brl(value: int) -> str:
    integer, fraction = divmod(value, 100)
    return "R$ " + f"{integer:,}".replace(",", ".") + f",{fraction:02d}"


def quote(
    product: dict,
    *,
    quantity: int = 1,
    payment: str = "debit",
    installments: int = 1,
    city: str | None = None,
) -> dict:
    if not 1 <= quantity <= 100 or not 1 <= installments <= 12:
        raise ValueError("Quantidade deve ser de 1 a 100 e parcelas de 1 a 12.")
    if payment not in {"pix", "credit", "debit", "boleto"}:
        raise ValueError("Forma de pagamento inválida.")
    if payment != "credit" and installments != 1:
        raise ValueError("Somente cartão de crédito permite parcelamento.")
    if product["status"] != "active" or product["stock_quantity"] < quantity:
        return {
            "status": "unavailable",
            "product_id": product["product_id"],
            "notes": ["Produto ou quantidade indisponível para compra no catálogo atual."],
        }

    promotion = product.get("discount_percent", 0)
    percent = promotion if promotion else (5 if payment == "pix" else 0)
    unit = discounted(product["price_cents"], percent)
    total = unit * quantity
    base, remainder = divmod(total, installments)
    parts = [base + (i < remainder) for i in range(installments)]
    status, notes = "ok", []
    if payment == "credit" and installments > 1:
        minimum = 10000 if installments >= 7 else (8000 if installments >= 4 else 5000)
        if min(parts) < minimum:
            if installments <= 3:
                status = "needs_review"
                notes.append(
                    "A exceção para parcelas abaixo de R$ 50,00 depende de análise; "
                    "a equipe precisa confirmar a condição."
                )
            else:
                status = "invalid"
                notes.append(
                    f"Em {installments}x, cada parcela deve ser de pelo menos {brl(minimum)}."
                )

    shipping = None
    if city:
        if normalize(city) in {"campo grande", "campo grande ms"}:
            if total == 50000:
                if status == "ok":
                    status = "needs_review"
                notes.append(
                    "O frete para exatamente R$ 500,00 precisa de confirmação com a equipe."
                )
            else:
                shipping = 0 if total > 50000 else 3500
        else:
            notes.append(
                "Para essa cidade, o frete precisa de cotação com CEP, peso e dimensões; "
                "não há tabela suficiente para confirmar o valor."
            )
    if promotion:
        notes.append("Promoção ativa aplicada. O desconto PIX não acumula com a promoção.")
    if payment == "boleto":
        notes.append("Compensação do boleto em até 3 dias úteis.")
    return {
        "status": status,
        "product_id": product["product_id"],
        "name": product["name"],
        "quantity": quantity,
        "payment": payment,
        "original_unit_cents": product["price_cents"],
        "unit_cents": unit,
        "unit_discount_cents": product["price_cents"] - unit,
        "discount_cents": (product["price_cents"] - unit) * quantity,
        "discount_percent": percent,
        "pix_applied": payment == "pix" and not promotion,
        "total_cents": total,
        "installment_cents": parts,
        "shipping_cents": shipping,
        "grand_total_cents": total + shipping if shipping is not None else None,
        "notes": notes,
    }


def assess_return(
    *,
    channel: str = "unknown",
    reason: str = "regret",
    received_at: date | None = None,
    purchased_at: date | None = None,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    if channel not in {"online", "store", "unknown"} or reason not in {
        "regret",
        "defect",
        "preference",
    }:
        raise ValueError("Canal ou motivo inválido.")
    if any(d and d > today for d in (received_at, purchased_at)):
        raise ValueError("A data informada não pode estar no futuro.")
    missing = []
    if channel == "unknown":
        missing.append("channel")
    base_date = purchased_at if reason == "defect" else received_at
    if base_date is None:
        missing.append("purchased_at" if reason == "defect" else "received_at")
    if missing:
        return {
            "status": "needs_information",
            "missing": missing,
            "message": "Preciso do canal da compra e da data efetiva correspondente. "
            "Previsão de entrega não comprova recebimento.",
        }
    if reason == "regret" and channel == "store":
        return {
            "status": "needs_review",
            "missing": [],
            "message": "O prazo de arrependimento se aplica a compras online. "
            "Para compra presencial, consulte a equipe.",
        }
    elapsed = (today - base_date).days
    limit = 30 if reason == "defect" else 7
    conditions = (
        "Confirmar defeito de fabricação; após 30 dias, a orientação é acionar a garantia "
        "do fabricante, com possível intermediação da loja. Também há garantia "
        "de 90 dias; a equipe deve avaliar a aplicação."
        if reason == "defect"
        else "Confirmar embalagem original, ausência de sinais de uso, acessórios e manuais. "
        "Personalização, venda final ou dúvidas de elegibilidade precisam de análise da equipe."
    )
    return {
        "status": "conditional" if elapsed <= limit else "needs_review",
        "missing": [],
        "elapsed_days": elapsed,
        "policy_limit_days": limit,
        "remaining_days": max(0, limit - elapsed),
        "conditions": conditions,
        "message": "Está dentro do prazo, sujeito às condições."
        if elapsed <= limit
        else "O prazo desta regra foi ultrapassado; a equipe precisa avaliar o caso.",
    }
