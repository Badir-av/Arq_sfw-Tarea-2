"""Persistencia de los eventos "url hit" en la Log DB (SQLite)."""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class StoredHit:
    timestamp: datetime
    short_url: str
    long_url: str


class HitRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS url_hits (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    short_url TEXT NOT NULL,
                    long_url  TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def save(self, timestamp: datetime, short_url: str, long_url: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO url_hits (timestamp, short_url, long_url) VALUES (?, ?, ?)",
                (timestamp.isoformat(), short_url, long_url),
            )

    def all(self) -> list[StoredHit]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT timestamp, short_url, long_url FROM url_hits ORDER BY id"
            ).fetchall()
        return [StoredHit(datetime.fromisoformat(ts), short, long) for ts, short, long in rows]
