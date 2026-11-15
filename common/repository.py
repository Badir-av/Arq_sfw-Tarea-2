"""Persistencia de la 3-tupla <id, hash, long_url> en SQLite.

El id es autoincremental y parte en 597652313, como pide el enunciado. El hash
es la codificación base62 del id, por lo que dos registros distintos nunca
pueden compartir hash.
"""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import base62

FIRST_ID = 597652313


@dataclass(frozen=True)
class ShortUrl:
    id: int
    hash: str
    long_url: str


class UrlRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        # Una conexión por operación: los handlers corren en hilos distintos y
        # las conexiones de sqlite3 no se comparten entre hilos.
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS urls (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash     TEXT UNIQUE,
                    long_url TEXT NOT NULL
                )
                """
            )
            # AUTOINCREMENT guarda el último id entregado en sqlite_sequence.
            # Sembrarlo con FIRST_ID - 1 hace que el primer registro sea FIRST_ID.
            seeded = conn.execute(
                "SELECT 1 FROM sqlite_sequence WHERE name = 'urls'"
            ).fetchone()
            if seeded is None:
                conn.execute(
                    "INSERT INTO sqlite_sequence (name, seq) VALUES ('urls', ?)",
                    (FIRST_ID - 1,),
                )

    def create(self, long_url: str) -> ShortUrl:
        with closing(self._connect()) as conn, conn:
            # El hash depende del id, así que se inserta primero y se completa
            # después, dentro de la misma transacción.
            cursor = conn.execute(
                "INSERT INTO urls (long_url) VALUES (?)", (long_url,)
            )
            new_id = cursor.lastrowid
            url_hash = base62.encode(new_id)
            conn.execute(
                "UPDATE urls SET hash = ? WHERE id = ?", (url_hash, new_id)
            )
        return ShortUrl(id=new_id, hash=url_hash, long_url=long_url)

    def find_by_hash(self, url_hash: str) -> ShortUrl | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT id, hash, long_url FROM urls WHERE hash = ?", (url_hash,)
            ).fetchone()
        return ShortUrl(*row) if row else None
