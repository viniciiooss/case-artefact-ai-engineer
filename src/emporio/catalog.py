"""Snapshot validado dos CSVs e consultas SQL parametrizadas de leitura."""

import csv
import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path

from emporio.db import connection
from emporio.pricing import cents, discounted
from emporio.text import normalize, tokens

TABLES = ("categories", "customers", "products", "orders", "order_items", "promotions")
SCHEMA = """
CREATE TABLE IF NOT EXISTS dataset_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS categories (
 category_id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers (
 customer_id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL,
 email TEXT NOT NULL, city TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products (
 product_id INTEGER PRIMARY KEY, price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
 name TEXT NOT NULL, category_id INTEGER NOT NULL REFERENCES categories,
 description TEXT NOT NULL, stock_quantity INTEGER NOT NULL CHECK(stock_quantity >= 0),
 status TEXT NOT NULL CHECK(status IN ('active','discontinued','coming_soon')),
 specs TEXT NOT NULL, created_at TEXT NOT NULL, search_text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS promotions (
 promotion_id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products,
 discount_percent INTEGER NOT NULL CHECK(discount_percent BETWEEN 0 AND 100),
 description TEXT NOT NULL, is_active INTEGER NOT NULL CHECK(is_active IN (0,1)));
CREATE TABLE IF NOT EXISTS orders (
 order_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers,
 order_date TEXT NOT NULL, status TEXT NOT NULL, total_cents INTEGER NOT NULL,
 payment_method TEXT NOT NULL, tracking_code TEXT, estimated_delivery TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS order_items (
 order_id INTEGER NOT NULL REFERENCES orders, quantity INTEGER NOT NULL CHECK(quantity > 0),
 product_id INTEGER NOT NULL REFERENCES products, PRIMARY KEY(order_id, product_id));
CREATE INDEX IF NOT EXISTS ix_products_category ON products(category_id, status);
CREATE INDEX IF NOT EXISTS ix_promotions_product ON promotions(product_id, is_active);
"""
SELECT_PRODUCTS = """
SELECT p.*, c.name AS category, COALESCE(pr.discount_percent, 0) AS discount_percent
FROM products p JOIN categories c ON p.category_id=c.category_id
LEFT JOIN (SELECT product_id, MAX(discount_percent) discount_percent FROM promotions
           WHERE is_active=1 GROUP BY product_id) pr ON pr.product_id=p.product_id
"""


class DataValidationError(ValueError):
    """O snapshot não satisfaz o contrato dos dados."""


class Catalog:
    def __init__(self, data_dir: Path, db_path: Path):
        self.data_dir, self.db_path = Path(data_dir), Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(b"emporio-catalog-v1")
        for table in TABLES:
            digest.update((self.data_dir / f"{table}.csv").read_bytes())
        self.fingerprint = digest.hexdigest()
        with connection(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            prior = conn.execute(
                "SELECT value FROM dataset_meta WHERE key='fingerprint'"
            ).fetchone()
        if not prior or prior[0] != self.fingerprint:
            self._ingest()

    def _ingest(self):
        prepared = {}
        try:
            for table in TABLES:
                with (self.data_dir / f"{table}.csv").open(encoding="utf-8-sig", newline="") as f:
                    rows = list(csv.DictReader(f))
                if not rows:
                    raise ValueError(f"Tabela vazia: {table}")
                prepared[table] = rows
            for p in prepared["products"]:
                p["price_cents"] = cents(p.pop("price_brl"))
                p["stock_quantity"] = int(p["stock_quantity"])
                if p["stock_quantity"] < 0:
                    raise ValueError("Estoque negativo")
                json.loads(p["specs"])
                date.fromisoformat(p["created_at"])
                p["search_text"] = normalize(p["name"] + " " + p["description"])
            for c in prepared["customers"]:
                c["email"] = c["email"].strip().casefold()
            for o in prepared["orders"]:
                o["total_cents"] = cents(o.pop("total_brl"))
                date.fromisoformat(o["order_date"])
                if o["estimated_delivery"]:
                    date.fromisoformat(o["estimated_delivery"])
            with connection(self.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                for table in reversed(TABLES):
                    conn.execute(f"DELETE FROM {table}")
                for table, rows in prepared.items():
                    columns = tuple(rows[0])
                    # table/columns derive exclusively from the fixed schema/CSV contract.
                    expected = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
                    if set(columns) != expected:
                        raise ValueError(f"Colunas incompatíveis em {table}")
                    names = ",".join(columns)
                    placeholders = ",".join("?" for _ in columns)
                    conn.executemany(
                        f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
                        [tuple(row[c] for c in columns) for row in rows],
                    )
                conn.execute(
                    "INSERT OR REPLACE INTO dataset_meta VALUES ('fingerprint', ?)",
                    (self.fingerprint,),
                )
        except (ValueError, KeyError, sqlite3.IntegrityError) as exc:
            raise DataValidationError(f"Falha de validação do snapshot: {exc}") from exc

    @staticmethod
    def _product(row) -> dict:
        p = dict(row)
        p.pop("search_text", None)
        p["specs"] = json.loads(p["specs"])
        p["available"] = p["status"] == "active" and p["stock_quantity"] > 0
        p["sale_price_cents"] = discounted(p["price_cents"], p["discount_percent"])
        return p

    def counts(self) -> dict:
        with connection(self.db_path) as conn:
            return {
                t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("products", "orders", "customers")
            }

    def search_products(
        self,
        query: str = "",
        *,
        category: str | None = None,
        max_price_brl: float | None = None,
        available_only: bool = True,
        limit: int = 8,
    ) -> list[dict]:
        conditions, params = ["1=1"], []
        if available_only:
            conditions += ["p.status='active'", "p.stock_quantity > 0"]
        if category:
            with connection(self.db_path) as conn:
                categories = conn.execute("SELECT category_id, name FROM categories").fetchall()
            ids = [
                r["category_id"] for r in categories if normalize(category) in normalize(r["name"])
            ]
            if not ids:
                return []
            conditions.append("p.category_id IN (" + ",".join("?" for _ in ids) + ")")
            params.extend(ids)
        for word in tokens(query)[:12]:
            conditions.append("p.search_text LIKE ? ESCAPE '\\'")
            params.append("%" + word + "%")
        if max_price_brl is not None:
            conditions.append(
                "CAST((p.price_cents*(100-COALESCE(pr.discount_percent,0))+50)/100 AS INTEGER)<=?"
            )
            params.append(cents(max_price_brl))
        params.append(max(1, min(int(limit), 30)))
        sql = (
            SELECT_PRODUCTS
            + " WHERE "
            + " AND ".join(conditions)
            + " ORDER BY CAST((p.price_cents*(100-COALESCE(pr.discount_percent,0))+50)/100"
            " AS INTEGER),"
            " p.product_id LIMIT ?"
        )
        with connection(self.db_path) as conn:
            return [self._product(r) for r in conn.execute(sql, params)]

    def get_product(self, product_id: int) -> dict | None:
        with connection(self.db_path) as conn:
            row = conn.execute(SELECT_PRODUCTS + " WHERE p.product_id=?", (product_id,)).fetchone()
        return self._product(row) if row else None

    def verify_order(self, order_id: int, email: str) -> bool:
        with connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM orders o JOIN customers c USING(customer_id) "
                "WHERE o.order_id=? AND c.email=?",
                (order_id, email.strip().casefold()),
            ).fetchone()
        return row is not None

    def get_order(self, order_id: int) -> dict | None:
        """Interno: a ferramenta que o expõe deve validar o grant da sessão."""
        with connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT order_id,order_date,status,total_cents,payment_method,tracking_code,"
                "estimated_delivery,notes FROM orders WHERE order_id=?",
                (order_id,),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["items"] = [
                dict(r)
                for r in conn.execute(
                    "SELECT i.product_id,p.name,i.quantity FROM order_items i "
                    "JOIN products p USING(product_id) WHERE i.order_id=?",
                    (order_id,),
                )
            ]
        return result
