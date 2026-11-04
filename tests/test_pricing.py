from datetime import date

import pytest


def product(price=219900, discount=0, stock=5, status="active"):
    return {
        "product_id": 95,
        "name": "Takamine GD20",
        "price_cents": price,
        "discount_percent": discount,
        "stock_quantity": stock,
        "status": status,
    }


@pytest.mark.parametrize(
    "value,expected", [(95, "R$ 0,95"), (219900, "R$ 2.199,00"), (123456789, "R$ 1.234.567,89")]
)
def test_brazilian_currency_format(value, expected):
    from emporio.pricing import brl

    assert brl(value) == expected


def test_pix_uses_table_price_and_rounds_half_up():
    from emporio.pricing import quote

    result = quote(product(59990), payment="pix")
    assert result["total_cents"] == 56991
    assert result["discount_percent"] == 5


def test_quote_returns_unit_and_total_savings_without_model_arithmetic():
    from emporio.pricing import quote

    result = quote(product(), payment="pix", quantity=2)
    assert result["unit_discount_cents"] == 10995
    assert result["discount_cents"] == 21990
    assert result["total_cents"] == 417810


def test_active_promotion_cannot_be_stacked_with_pix():
    from emporio.pricing import quote

    result = quote(product(35900, 10), payment="pix")
    assert result["total_cents"] == 32310
    assert result["discount_percent"] == 10
    assert result["pix_applied"] is False


def test_installments_preserve_every_cent():
    from emporio.pricing import quote

    result = quote(product(59990), payment="credit", installments=3)
    assert result["installment_cents"] == [19997, 19997, 19996]
    assert sum(result["installment_cents"]) == 59990


@pytest.mark.parametrize(
    "price,n,expected",
    [
        (47999, 6, "invalid"),
        (48000, 6, "ok"),
        (119999, 12, "invalid"),
        (120000, 12, "ok"),
        (10000, 3, "needs_review"),
    ],
)
def test_installment_boundaries(price, n, expected):
    from emporio.pricing import quote

    assert quote(product(price), payment="credit", installments=n)["status"] == expected


@pytest.mark.parametrize(
    "price,fee,status", [(49999, 3500, "ok"), (50000, None, "needs_review"), (50001, 0, "ok")]
)
def test_local_freight_boundary_is_not_invented(price, fee, status):
    from emporio.pricing import quote

    result = quote(product(price), payment="debit", city="Campo Grande")
    assert result["shipping_cents"] == fee
    assert result["status"] == status


def test_unknown_city_has_no_fabricated_freight():
    from emporio.pricing import quote

    result = quote(product(), city="Dourados")
    assert result["shipping_cents"] is None
    assert "CEP" in result["notes"][0]


@pytest.mark.parametrize("status,stock", [("coming_soon", 2), ("discontinued", 13), ("active", 0)])
def test_unavailable_products_are_not_quoted_as_purchasable(status, stock):
    from emporio.pricing import quote

    assert quote(product(status=status, stock=stock))["status"] == "unavailable"


def test_return_requires_actual_received_date_and_channel():
    from emporio.pricing import assess_return

    result = assess_return(channel="unknown", reason="regret", today=date(2026, 11, 4))
    assert result["status"] == "needs_information"
    assert "channel" in result["missing"]
    assert "received_at" in result["missing"]


@pytest.mark.parametrize(
    "days,status", [(0, "conditional"), (7, "conditional"), (8, "needs_review")]
)
def test_online_return_seven_days_inclusive(days, status):
    from datetime import timedelta

    from emporio.pricing import assess_return

    today = date(2026, 11, 4)
    result = assess_return(
        channel="online", reason="regret", received_at=today - timedelta(days=days), today=today
    )
    assert result["status"] == status


def test_future_received_date_is_rejected():
    from emporio.pricing import assess_return

    with pytest.raises(ValueError):
        assess_return(
            channel="online",
            reason="regret",
            received_at=date(2026, 11, 5),
            today=date(2026, 11, 4),
        )
