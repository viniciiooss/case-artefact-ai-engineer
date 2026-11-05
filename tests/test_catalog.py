import shutil
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"


def catalog(tmp_path):
    from emporio.catalog import Catalog

    return Catalog(DATA, tmp_path / "catalog.sqlite3")


def test_ingestion_preserves_all_products_and_is_idempotent(tmp_path):
    from emporio.catalog import Catalog

    repo = catalog(tmp_path)
    assert repo.counts() == {"products": 65, "orders": 20, "customers": 50}
    assert Catalog(DATA, tmp_path / "catalog.sqlite3").fingerprint == repo.fingerprint


def test_catalog_budget_and_availability(tmp_path):
    results = catalog(tmp_path).search_products(category="Violões", max_price_brl=1000, limit=30)
    assert len(results) >= 10
    assert all(p["price_cents"] <= 100000 for p in results)
    assert all(p["stock_quantity"] > 0 and p["status"] == "active" for p in results)
    assert 96 not in {p["product_id"] for p in results}


@pytest.mark.parametrize("query", ["violão", "violões"])
def test_family_query_does_not_include_another_category_mentioned_in_a_description(tmp_path, query):
    results = catalog(tmp_path).search_products(query=query, max_price_brl=1000, limit=30)
    assert {p["product_id"] for p in results} == {81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 107, 112}
    assert all(p["category"] == "Violões" for p in results)


def test_family_inference_preserves_brand_filter_and_explicit_category(tmp_path):
    repo = catalog(tmp_path)
    yamaha = repo.search_products(query="violão Yamaha", max_price_brl=1000, limit=30)
    assert {p["product_id"] for p in yamaha} == {81, 82, 87}
    explicit = repo.search_products(query="violão", category="Ukuleles", max_price_brl=1000)
    assert {p["product_id"] for p in explicit} == {128}


def test_model_search_and_inactive_promotion(tmp_path):
    result = catalog(tmp_path).search_products(query="Takamine GD20", available_only=False)
    assert len(result) == 1
    assert result[0]["price_cents"] == 219900
    assert result[0]["discount_percent"] == 0


def test_discontinued_positive_stock_and_coming_soon_are_unavailable(tmp_path):
    repo = catalog(tmp_path)
    assert repo.get_product(136)["available"] is False
    assert repo.get_product(136)["stock_quantity"] == 13
    assert repo.get_product(130)["available"] is False


def test_search_does_not_execute_sql(tmp_path):
    repo = catalog(tmp_path)
    assert repo.search_products(query="'; DROP TABLE products; --") == []
    assert repo.counts()["products"] == 65


def test_only_active_promotion_is_used(tmp_path):
    result = catalog(tmp_path).get_product(127)
    assert result["discount_percent"] == 10
    assert result["sale_price_cents"] == 32310


def test_order_authentication_is_case_insensitive_and_minimizes_data(tmp_path):
    repo = catalog(tmp_path)
    assert repo.verify_order(8, "ANACAROL.FERREIRA@COLDMAIL.COM") is True
    assert repo.verify_order(8, "wrong@example.com") is False
    result = repo.get_order(8)
    assert result["tracking_code"] == "BRJL5544332BR"
    assert "email" not in result and "phone" not in result and "customer_id" not in result


def test_bad_csv_import_rolls_back_previous_snapshot(tmp_path):
    from emporio.catalog import Catalog, DataValidationError

    data_copy = tmp_path / "input"
    shutil.copytree(DATA, data_copy)
    db_path = tmp_path / "catalog.sqlite3"
    repo = Catalog(data_copy, db_path)
    original = (data_copy / "products.csv").read_text()
    (data_copy / "products.csv").write_text(original.replace("599.9,", "-599.9,", 1))
    with pytest.raises(DataValidationError):
        Catalog(data_copy, db_path)
    assert repo.get_product(81)["price_cents"] == 59990
