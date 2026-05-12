from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app.config import settings
from app.utils.files import ensure_data_dirs


def connect() -> sqlite3.Connection:
    ensure_data_dirs()
    connection = sqlite3.connect(settings.db_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
