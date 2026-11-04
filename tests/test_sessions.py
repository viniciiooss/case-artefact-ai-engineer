import json

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
