"""SQLite index database."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from .models import Deck, DeckStatus, Slide
from .utils import ensure_dir, logger

SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS decks (
    deck_id        TEXT PRIMARY KEY,
    file_path      TEXT NOT NULL,
    file_name      TEXT NOT NULL,
    folder_path    TEXT NOT NULL,
    file_size      INTEGER NOT NULL,
    modified_time  REAL NOT NULL,
    processed_time REAL NOT NULL DEFAULT 0,
    slide_count    INTEGER NOT NULL DEFAULT 0,
    file_signature TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_decks_signature ON decks(file_signature);
CREATE INDEX IF NOT EXISTS idx_decks_status ON decks(status);
CREATE INDEX IF NOT EXISTS idx_decks_modified ON decks(modified_time);
CREATE INDEX IF NOT EXISTS idx_decks_folder ON decks(folder_path);

CREATE TABLE IF NOT EXISTS slides (
    slide_id       TEXT PRIMARY KEY,
    deck_id        TEXT NOT NULL REFERENCES decks(deck_id) ON DELETE CASCADE,
    slide_number   INTEGER NOT NULL,
    title          TEXT NOT NULL DEFAULT '',
    subtitle_text  TEXT NOT NULL DEFAULT '',
    body_text      TEXT NOT NULL DEFAULT '',
    extra_text     TEXT NOT NULL DEFAULT '',
    extracted_text TEXT NOT NULL DEFAULT '',
    notes_text     TEXT NOT NULL DEFAULT '',
    thumb_path     TEXT NOT NULL DEFAULT '',
    preview_path   TEXT NOT NULL DEFAULT '',
    width          INTEGER NOT NULL DEFAULT 0,
    height         INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_slides_deck ON slides(deck_id);
"""


class IndexDB:
    """Persistent SQLite index for decks and slides."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        ensure_dir(self.db_path.parent)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._migrate_schema()
        # Store schema version
        self._conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        self._conn.commit()

    def _migrate_schema(self) -> None:
        columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(slides)").fetchall()
        }
        expected_columns = {
            "subtitle_text": "TEXT NOT NULL DEFAULT ''",
            "body_text": "TEXT NOT NULL DEFAULT ''",
            "extra_text": "TEXT NOT NULL DEFAULT ''",
        }
        for column, definition in expected_columns.items():
            if column not in columns:
                self._conn.execute(
                    f"ALTER TABLE slides ADD COLUMN {column} {definition}"
                )

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _tx(self) -> Generator[sqlite3.Cursor, None, None]:
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ── Deck operations ──────────────────────────────────────

    def get_all_active_signatures(self) -> dict[str, str]:
        """Return {file_signature: deck_id} for all active decks."""
        rows = self._conn.execute(
            "SELECT file_signature, deck_id FROM decks WHERE status = ?",
            (DeckStatus.ACTIVE.value,),
        ).fetchall()
        return {r["file_signature"]: r["deck_id"] for r in rows}

    def get_all_active_decks(self) -> list[Deck]:
        rows = self._conn.execute(
            "SELECT * FROM decks WHERE status = ?", (DeckStatus.ACTIVE.value,)
        ).fetchall()
        return [self._row_to_deck(r) for r in rows]

    def get_deck(self, deck_id: str) -> Deck | None:
        row = self._conn.execute(
            "SELECT * FROM decks WHERE deck_id = ?", (deck_id,)
        ).fetchone()
        return self._row_to_deck(row) if row else None

    def get_deck_by_path(self, file_path: str) -> Deck | None:
        row = self._conn.execute(
            "SELECT * FROM decks WHERE file_path = ? AND status = ?",
            (file_path, DeckStatus.ACTIVE.value),
        ).fetchone()
        return self._row_to_deck(row) if row else None

    def upsert_deck(self, deck: Deck) -> None:
        with self._tx() as cur:
            cur.execute(
                """INSERT INTO decks
                    (deck_id, file_path, file_name, folder_path, file_size,
                     modified_time, processed_time, slide_count, file_signature, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(deck_id) DO UPDATE SET
                     file_path=excluded.file_path,
                     file_name=excluded.file_name,
                     folder_path=excluded.folder_path,
                     file_size=excluded.file_size,
                     modified_time=excluded.modified_time,
                     processed_time=excluded.processed_time,
                     slide_count=excluded.slide_count,
                     file_signature=excluded.file_signature,
                     status=excluded.status
                """,
                (
                    deck.deck_id, deck.file_path, deck.file_name,
                    deck.folder_path, deck.file_size, deck.modified_time,
                    deck.processed_time, deck.slide_count,
                    deck.file_signature, deck.status,
                ),
            )

    def replace_deck_and_slides(self, deck: Deck, slides: list[Slide]) -> None:
        """Replace a rendered deck as one transaction, preserving old rows on error.

        This is intentionally separate from the existing incremental upsert
        helpers: old slides must not be deleted until a valid rendered result
        exists, and no partial deck update may commit if insertion fails.
        """
        if any(slide.deck_id != deck.deck_id for slide in slides):
            raise ValueError("All replacement slides must belong to the same deck")
        with self._tx() as cur:
            cur.execute(
                """INSERT INTO decks
                   (deck_id, file_path, file_name, folder_path, file_size,
                    modified_time, processed_time, slide_count, file_signature, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(deck_id) DO UPDATE SET
                    file_path=excluded.file_path, file_name=excluded.file_name,
                    folder_path=excluded.folder_path, file_size=excluded.file_size,
                    modified_time=excluded.modified_time, processed_time=excluded.processed_time,
                    slide_count=excluded.slide_count, file_signature=excluded.file_signature,
                    status=excluded.status
                """,
                (
                    deck.deck_id, deck.file_path, deck.file_name, deck.folder_path,
                    deck.file_size, deck.modified_time, deck.processed_time,
                    deck.slide_count, deck.file_signature, deck.status,
                ),
            )
            cur.execute("DELETE FROM slides WHERE deck_id = ?", (deck.deck_id,))
            cur.executemany(
                """INSERT INTO slides
                   (slide_id, deck_id, slide_number, title, subtitle_text, body_text,
                    extra_text, extracted_text, notes_text, thumb_path,
                    preview_path, width, height)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        slide.slide_id, slide.deck_id, slide.slide_number,
                        slide.title, slide.subtitle_text, slide.body_text,
                        slide.extra_text, slide.extracted_text, slide.notes_text,
                        slide.thumb_path, slide.preview_path, slide.width, slide.height,
                    )
                    for slide in slides
                ],
            )

    def mark_deleted(self, deck_id: str) -> None:
        with self._tx() as cur:
            cur.execute(
                "UPDATE decks SET status = ? WHERE deck_id = ?",
                (DeckStatus.DELETED.value, deck_id),
            )

    def purge_deck(self, deck_id: str) -> None:
        """Permanently remove a deck and its slides."""
        with self._tx() as cur:
            cur.execute("DELETE FROM slides WHERE deck_id = ?", (deck_id,))
            cur.execute("DELETE FROM decks WHERE deck_id = ?", (deck_id,))

    # ── Slide operations ─────────────────────────────────────

    def get_slides_for_deck(self, deck_id: str) -> list[Slide]:
        rows = self._conn.execute(
            "SELECT * FROM slides WHERE deck_id = ? ORDER BY slide_number",
            (deck_id,),
        ).fetchall()
        return [self._row_to_slide(r) for r in rows]

    def upsert_slides(self, slides: list[Slide]) -> None:
        if not slides:
            return
        with self._tx() as cur:
            for s in slides:
                cur.execute(
                    """INSERT INTO slides
                                                (slide_id, deck_id, slide_number, title, subtitle_text,
                                                 body_text, extra_text, extracted_text,
                         notes_text, thumb_path, preview_path, width, height)
                                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(slide_id) DO UPDATE SET
                         slide_number=excluded.slide_number,
                         title=excluded.title,
                                                 subtitle_text=excluded.subtitle_text,
                                                 body_text=excluded.body_text,
                                                 extra_text=excluded.extra_text,
                         extracted_text=excluded.extracted_text,
                         notes_text=excluded.notes_text,
                         thumb_path=excluded.thumb_path,
                         preview_path=excluded.preview_path,
                         width=excluded.width,
                         height=excluded.height
                    """,
                    (
                        s.slide_id, s.deck_id, s.slide_number,
                        s.title, s.subtitle_text, s.body_text,
                        s.extra_text, s.extracted_text, s.notes_text,
                        s.thumb_path, s.preview_path, s.width, s.height,
                    ),
                )

    def delete_slides_for_deck(self, deck_id: str) -> None:
        with self._tx() as cur:
            cur.execute("DELETE FROM slides WHERE deck_id = ?", (deck_id,))

    # ── Query / search ───────────────────────────────────────

    def get_all_slides(self) -> list[Slide]:
        rows = self._conn.execute(
            """SELECT s.* FROM slides s
               JOIN decks d ON s.deck_id = d.deck_id
               WHERE d.status = ?
               ORDER BY d.modified_time DESC, s.slide_number""",
            (DeckStatus.ACTIVE.value,),
        ).fetchall()
        return [self._row_to_slide(r) for r in rows]

    def search_decks(self, query: str) -> list[Deck]:
        pattern = f"%{query}%"
        rows = self._conn.execute(
            """SELECT * FROM decks
               WHERE status = ? AND (file_name LIKE ? OR folder_path LIKE ?)
               ORDER BY modified_time DESC""",
            (DeckStatus.ACTIVE.value, pattern, pattern),
        ).fetchall()
        return [self._row_to_deck(r) for r in rows]

    def search_slides(self, query: str) -> list[Slide]:
        pattern = f"%{query}%"
        rows = self._conn.execute(
            """SELECT s.* FROM slides s
               JOIN decks d ON s.deck_id = d.deck_id
               WHERE d.status = ? AND (
                                 s.title LIKE ? OR s.subtitle_text LIKE ? OR s.body_text LIKE ?
                                 OR s.extra_text LIKE ? OR s.extracted_text LIKE ? OR s.notes_text LIKE ?
                                 OR d.file_name LIKE ? OR d.folder_path LIKE ?
               )
               ORDER BY d.modified_time DESC, s.slide_number""",
                        (
                                DeckStatus.ACTIVE.value,
                                pattern,
                                pattern,
                                pattern,
                                pattern,
                                pattern,
                                pattern,
                                pattern,
                                pattern,
                        ),
        ).fetchall()
        return [self._row_to_slide(r) for r in rows]

    def get_stats(self) -> dict:
        deck_count = self._conn.execute(
            "SELECT COUNT(*) FROM decks WHERE status = ?",
            (DeckStatus.ACTIVE.value,),
        ).fetchone()[0]
        slide_count = self._conn.execute(
            """SELECT COUNT(*) FROM slides s
               JOIN decks d ON s.deck_id = d.deck_id
               WHERE d.status = ?""",
            (DeckStatus.ACTIVE.value,),
        ).fetchone()[0]
        return {"deck_count": deck_count, "slide_count": slide_count}

    def get_daily_activity(self) -> list[dict]:
        """Return [{date: 'YYYY-MM-DD', deck_count: N, slide_count: N}, ...]."""
        rows = self._conn.execute(
            """SELECT date(modified_time, 'unixepoch', 'localtime') as day,
                      COUNT(DISTINCT d.deck_id) as deck_count,
                      SUM(d.slide_count) as slide_count
               FROM decks d
               WHERE d.status = ?
               GROUP BY day
               ORDER BY day""",
            (DeckStatus.ACTIVE.value,),
        ).fetchall()
        return [
            {"date": r["day"], "deck_count": r["deck_count"], "slide_count": r["slide_count"]}
            for r in rows
        ]

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _row_to_deck(row: sqlite3.Row) -> Deck:
        return Deck(
            deck_id=row["deck_id"],
            file_path=row["file_path"],
            file_name=row["file_name"],
            folder_path=row["folder_path"],
            file_size=row["file_size"],
            modified_time=row["modified_time"],
            processed_time=row["processed_time"],
            slide_count=row["slide_count"],
            file_signature=row["file_signature"],
            status=row["status"],
        )

    @staticmethod
    def _row_to_slide(row: sqlite3.Row) -> Slide:
        return Slide(
            slide_id=row["slide_id"],
            deck_id=row["deck_id"],
            slide_number=row["slide_number"],
            title=row["title"],
            subtitle_text=row["subtitle_text"],
            body_text=row["body_text"],
            extra_text=row["extra_text"],
            extracted_text=row["extracted_text"],
            notes_text=row["notes_text"],
            thumb_path=row["thumb_path"],
            preview_path=row["preview_path"],
            width=row["width"],
            height=row["height"],
        )
