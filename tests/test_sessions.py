import json
import sqlite3

import pytest


def store(tmp_path):
    from emporio.sessions import SessionStore

    return SessionStore(tmp_path / "sessions.sqlite3")


def test_token_is_required_and_stored_only_as_hash(tmp_path):
    from emporio.sessions import SessionNotFound

    sessions = store(tmp_path)
    a = sessions.create()
    assert sessions.authenticate(a["session_id"], a["token"]) is None
    with pytest.raises(SessionNotFound):
        sessions.authenticate(a["session_id"], "wrong")
    assert a["token"].encode() not in (tmp_path / "sessions.sqlite3").read_bytes()


def test_history_persists_across_instances_and_is_isolated(tmp_path):
    sessions = store(tmp_path)
    a, b = sessions.create(), sessions.create()
    sessions.save_turn(a["session_id"], "Oi", {"message": "Olá", "sources": []}, {"products": [95]})
    restored = store(tmp_path)
    assert [m["content"] for m in restored.history(a["session_id"])] == ["Oi", "Olá"]
    assert restored.context(a["session_id"]) == {"products": [95]}
    assert restored.history(b["session_id"]) == []


def test_reply_latency_persists_across_restart_and_limited_history(tmp_path):
    sessions = store(tmp_path)
    sid = sessions.create()["session_id"]
    sessions.save_turn(sid, "Primeira", {"message": "Resposta", "latency_ms": 2473.6}, {})
    sessions.save_turn(sid, "Segunda", {"message": "Outra resposta", "latency_ms": 0}, {})
    restored = store(tmp_path)
    history = restored.history(sid)
    assert [message.get("latency_ms") for message in history] == [None, 2473.6, None, 0]
    assert restored.history(sid, limit=2) == history[-2:]


def test_legacy_history_migration_preserves_content_and_unknown_latency(tmp_path):
    from emporio.sessions import SessionStore

    path = tmp_path / "sessions.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
        CREATE TABLE sessions (
          session_id TEXT PRIMARY KEY, token_hash TEXT NOT NULL,
          created_at REAL NOT NULL, context TEXT NOT NULL DEFAULT '{}',
          busy_until REAL NOT NULL DEFAULT 0);
        CREATE TABLE messages (
          message_id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id TEXT NOT NULL REFERENCES sessions ON DELETE CASCADE,
          role TEXT NOT NULL CHECK(role IN ('user','assistant')),
          content TEXT NOT NULL, sources TEXT NOT NULL DEFAULT '[]', created_at REAL NOT NULL);
        INSERT INTO sessions(session_id,token_hash,created_at,context)
          VALUES ('legacy','hash',0,'{"products":[95]}');
        INSERT INTO messages(session_id,role,content,sources,created_at)
          VALUES ('legacy','assistant','Resposta anterior','[{"id":"product-95"}]',0);
        """)
    upgraded = SessionStore(path)
    assert upgraded.history("legacy") == [
        {
            "role": "assistant",
            "content": "Resposta anterior",
            "sources": [{"id": "product-95"}],
            "latency_ms": None,
        }
    ]
    assert upgraded.context("legacy") == {"products": [95]}
    upgraded.save_turn("legacy", "Nova pergunta", {"message": "Nova", "latency_ms": 742}, {})
    reopened = SessionStore(path)
    assert reopened.history("legacy")[-1]["latency_ms"] == 742
    assert reopened.history("legacy")[0]["content"] == "Resposta anterior"


def test_order_grants_are_scoped_to_session_and_order(tmp_path):
    sessions = store(tmp_path)
    a, b = sessions.create(), sessions.create()
    sessions.grant_order(a["session_id"], 8)
    assert sessions.can_access_order(a["session_id"], 8) is True
    assert sessions.can_access_order(a["session_id"], 9) is False
    assert sessions.can_access_order(b["session_id"], 8) is False


def test_delete_removes_history_grants_and_tickets(tmp_path):
    from emporio.sessions import SessionNotFound

    sessions = store(tmp_path)
    a = sessions.create()
    sessions.save_turn(a["session_id"], "Olá", {"message": "Oi", "sources": []}, {})
    sessions.grant_order(a["session_id"], 8)
    ticket = sessions.create_ticket(a["session_id"], "Preciso de atendimento")
    assert ticket["status"] == "registered_locally"
    sessions.delete(a["session_id"])
    with pytest.raises(SessionNotFound):
        sessions.authenticate(a["session_id"], a["token"])
    assert sessions.can_access_order(a["session_id"], 8) is False


def test_parallel_turn_is_rejected_without_overwriting_history(tmp_path):
    from emporio.sessions import SessionBusy

    sessions = store(tmp_path)
    a = sessions.create()
    with sessions.turn(a["session_id"]):
        with pytest.raises(SessionBusy), sessions.turn(a["session_id"]):
            pass
    with sessions.turn(a["session_id"]):
        pass


def test_no_raw_token_or_email_appears_in_context(tmp_path):
    sessions = store(tmp_path)
    a = sessions.create()
    sessions.grant_order(a["session_id"], 8)
    assert "token" not in json.dumps(sessions.context(a["session_id"]))
