import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connection(path: Path):
    """Uma conexão por operação, fechada inclusive em caso de exceção."""
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    try:
        with conn:
            yield conn
    finally:
        conn.close()
