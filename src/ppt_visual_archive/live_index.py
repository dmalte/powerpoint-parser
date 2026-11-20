"""Bounded, read-only SQLite change feed for an open local browser.

Completed deck transactions are tracked by durable SQLite triggers; a browser
fetches one compact page of updated decks rather than the full static export.
Nothing is written, and all reads use one WAL-consistent SQLite snapshot.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .builder import serialize_deck, serialize_slide
from .index_db import IndexDB

MAX_EVENTS_PER_PAGE = 50


def read_live_index(db_path: str | Path, *, after: int, limit: int = MAX_EVENTS_PER_PAGE) -> dict:
    """Return a bounded change page and current committed counts.

    ``cursor`` is inclusive of the last processed change, not wall-clock time;
    reprocessing a slow PPTX cannot be missed due to its old start timestamp.
    """
    if type(after) is not int or not 0 <= after <= 9223372036854775807:
        raise ValueError("Invalid change cursor")
    if type(limit) is not int or not 1 <= limit <= MAX_EVENTS_PER_PAGE:
        raise ValueError("Invalid change page size")
    source = Path(db_path).resolve()
    if not source.is_file():
        raise FileNotFoundError("Archive index not yet available")

    conn = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=2)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        stats = {
            "deck_count": conn.execute(
                "SELECT COUNT(*) FROM decks WHERE status='active'"
            ).fetchone()[0],
            "slide_count": conn.execute(
                "SELECT COUNT(*) FROM slides s JOIN decks d ON s.deck_id=d.deck_id "
                "WHERE d.status='active'"
            ).fetchone()[0],
        }
        rows = conn.execute(
            "SELECT sequence, deck_id FROM deck_changes WHERE sequence>? "
            "ORDER BY sequence LIMIT ?", (after, limit)
        ).fetchall()
        cursor = int(rows[-1]["sequence"]) if rows else after
        more = conn.execute(
            "SELECT 1 FROM deck_changes WHERE sequence>? LIMIT 1", (cursor,)
        ).fetchone() is not None
        # Retain the last event per deck in the current page; a reprocessed deck
        # or purged deck appears only once, with its final committed state.
        deck_ids = list(dict.fromkeys(row["deck_id"] for row in rows))
        upserts = []
        removed = []
        for deck_id in deck_ids:
            row = conn.execute(
                "SELECT * FROM decks WHERE deck_id=? AND status='active'",
                (deck_id,),
            ).fetchone()
            if row is None:
                removed.append(deck_id)
                continue
            slides = conn.execute(
                "SELECT * FROM slides WHERE deck_id=? ORDER BY slide_number",
                (deck_id,),
            ).fetchall()
            upserts.append({
                "deck": serialize_deck(IndexDB._row_to_deck(row)),
                "slides": [serialize_slide(IndexDB._row_to_slide(slide)) for slide in slides],
            })
        return {
            "cursor": cursor,
            "has_more": more,
            "stats": stats,
            "upserts": upserts,
            "removed": removed,
        }
    finally:
        conn.rollback()
        conn.close()
