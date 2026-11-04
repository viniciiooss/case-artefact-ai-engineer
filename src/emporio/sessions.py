"""Histórico local, capabilities de sessão e autorização de pedidos no servidor."""

import hashlib
import json
import secrets
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from emporio.db import connection


class SessionNotFound(LookupError):
    pass


class SessionBusy(RuntimeError):
    pass


class SessionStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with connection(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
             session_id TEXT PRIMARY KEY, token_hash TEXT NOT NULL,
             created_at REAL NOT NULL, context TEXT NOT NULL DEFAULT '{}',
             busy_until REAL NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS messages (
             message_id INTEGER PRIMARY KEY AUTOINCREMENT,
             session_id TEXT NOT NULL REFERENCES sessions ON DELETE CASCADE,
             role TEXT NOT NULL CHECK(role IN ('user','assistant')),
             content TEXT NOT NULL, sources TEXT NOT NULL DEFAULT '[]',
             created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS order_grants (
             session_id TEXT NOT NULL REFERENCES sessions ON DELETE CASCADE,
             order_id INTEGER NOT NULL, PRIMARY KEY(session_id, order_id));
            CREATE TABLE IF NOT EXISTS tickets (
             ticket_id TEXT PRIMARY KEY,
             session_id TEXT NOT NULL REFERENCES sessions ON DELETE CASCADE,
             reason TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS verification_attempts (
             session_id TEXT NOT NULL REFERENCES sessions ON DELETE CASCADE,
             created_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS ix_messages_session ON messages(session_id, message_id);
            """)

    def create(self) -> dict:
        session_id, token = str(uuid4()), secrets.token_urlsafe(32)
        with connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO sessions(session_id,token_hash,created_at) VALUES (?,?,?)",
                (session_id, hashlib.sha256(token.encode()).hexdigest(), time.time()),
            )
        return {"session_id": session_id, "token": token}

    def authenticate(self, session_id: str, token: str):
        with connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT token_hash FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        if not row or not secrets.compare_digest(
            row[0], hashlib.sha256(token.encode()).hexdigest()
        ):
            raise SessionNotFound("Sessão não encontrada ou credencial inválida.")

    def history(self, session_id: str, limit: int | None = None) -> list[dict]:
        sql = "SELECT role,content,sources FROM messages WHERE session_id=? ORDER BY message_id"
        params = [session_id]
        if limit:
            sql = (
                "SELECT role,content,sources FROM (SELECT message_id,role,content,sources "
                "FROM messages WHERE session_id=? ORDER BY message_id DESC LIMIT ?) "
                "ORDER BY message_id"
            )
            params.append(limit)
        with connection(self.db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [{**dict(r), "sources": json.loads(r["sources"])} for r in rows]

    def context(self, session_id: str) -> dict:
        with connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT context FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        if not row:
            raise SessionNotFound("Sessão não encontrada.")
        return json.loads(row[0])

    def save_turn(self, session_id: str, question: str, response: dict, context: dict):
        with connection(self.db_path) as conn:
            if not conn.execute(
                "SELECT 1 FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone():
                raise SessionNotFound("A sessão foi excluída durante a consulta.")
            conn.executemany(
                "INSERT INTO messages(session_id,role,content,sources,created_at)"
                " VALUES (?,?,?,?,?)",
                [
                    (session_id, "user", question, "[]", time.time()),
                    (
                        session_id,
                        "assistant",
                        response["message"],
                        json.dumps(response.get("sources", []), ensure_ascii=False),
                        time.time(),
                    ),
                ],
            )
            conn.execute(
                "UPDATE sessions SET context=? WHERE session_id=?",
                (json.dumps(context, ensure_ascii=False), session_id),
            )

    @contextmanager
    def turn(self, session_id: str, lease_seconds: float = 600):
        with connection(self.db_path) as conn:
            changed = conn.execute(
                "UPDATE sessions SET busy_until=? WHERE session_id=? AND busy_until<?",
                (time.time() + lease_seconds, session_id, time.time()),
            ).rowcount
            if not changed:
                exists = conn.execute(
                    "SELECT 1 FROM sessions WHERE session_id=?", (session_id,)
                ).fetchone()
                if not exists:
                    raise SessionNotFound("Sessão não encontrada.")
                raise SessionBusy("Uma resposta já está sendo preparada nesta conversa.")
        try:
            yield
        finally:
            with connection(self.db_path) as conn:
                conn.execute("UPDATE sessions SET busy_until=0 WHERE session_id=?", (session_id,))

    def grant_order(self, session_id: str, order_id: int):
        with connection(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO order_grants VALUES (?,?)", (session_id, order_id))

    def can_access_order(self, session_id: str, order_id: int) -> bool:
        return order_id in self.verified_orders(session_id)

    def verified_orders(self, session_id: str) -> list[int]:
        with connection(self.db_path) as conn:
            return [
                r[0]
                for r in conn.execute(
                    "SELECT order_id FROM order_grants WHERE session_id=? ORDER BY order_id",
                    (session_id,),
                )
            ]

    def allow_verification(self, session_id: str) -> bool:
        with connection(self.db_path) as conn:
            now = time.time()
            conn.execute("DELETE FROM verification_attempts WHERE created_at<?", (now - 60,))
            count = conn.execute(
                "SELECT COUNT(*) FROM verification_attempts WHERE session_id=?", (session_id,)
            ).fetchone()[0]
            if count >= 5:
                return False
            conn.execute("INSERT INTO verification_attempts VALUES (?,?)", (session_id, now))
        return True

    def create_ticket(self, session_id: str, reason: str) -> dict:
        ticket_id = "EM-" + uuid4().hex[:10].upper()
        with connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO tickets VALUES (?,?,?,?)",
                (ticket_id, session_id, reason[:2000], time.time()),
            )
        return {
            "ticket_id": ticket_id,
            "status": "registered_locally",
            "message": "Solicitação registrada nesta conversa. Não houve notificação externa. "
            "Fale com a equipe pelo WhatsApp (67) 3321-4500.",
        }

    def delete(self, session_id: str):
        with connection(self.db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
