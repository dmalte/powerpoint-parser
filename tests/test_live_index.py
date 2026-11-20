"""M016 durable per-deck event feed and bounded loopback client protocol."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from ppt_visual_archive import builder
from ppt_visual_archive.config import default_config
from ppt_visual_archive.index_db import IndexDB
from ppt_visual_archive.live_index import MAX_EVENTS_PER_PAGE, read_live_index
from ppt_visual_archive.models import Deck, Slide
from ppt_visual_archive.server import create_server


def make_deck(identifier: str, version: int = 1, slides: int = 1) -> tuple[Deck, list[Slide]]:
    deck = Deck(
        deck_id=identifier, file_path=f"/private/{identifier}.pdf", file_name=f"{identifier}.pdf",
        folder_path="/private", file_size=250, modified_time=1720000000.0 + version,
        processed_time=1720000000.0 + version, slide_count=slides,
        file_signature=f"sig-{identifier}-{version}", status="active",
    )
    items = [Slide(
        slide_id=f"{identifier}-{i}", deck_id=identifier, slide_number=i,
        title=f"Title v{version} p{i}", thumb_path=f"assets/decks/{identifier}/{version}/t{i}.jpg",
        preview_path=f"assets/decks/{identifier}/{version}/p{i}.jpg",
    ) for i in range(1, slides + 1)]
    return deck, items


def make_archive(tmp_path):
    src = tmp_path / "sources"
    src.mkdir()
    config = default_config(str(tmp_path / "viewer"), [str(src)])
    config.file_types = ["pdf"]
    return config


def test_durable_cursor_and_atomic_successful_deck_changes(tmp_path):
    config = make_archive(tmp_path)
    db = IndexDB(config.db_path)
    try:
        assert db.get_change_cursor() == 0
        deck, slides = make_deck("one", 1, 2)
        db.replace_deck_and_slides(deck, slides)
        first = db.get_change_cursor()
        assert first > 0
        page = read_live_index(config.db_path, after=0)
        assert page["cursor"] == first
        assert page["stats"] == {"deck_count": 1, "slide_count": 2}
        assert len(page["upserts"]) == 1
        assert [s["title"] for s in page["upserts"][0]["slides"]] == ["Title v1 p1", "Title v1 p2"]
        assert page["upserts"][0]["deck"]["file_path"] == deck.file_path
        assert page["removed"] == [] and page["has_more"] is False

        # A failed document replacement must not publish an event or lose rows.
        changed, _ = make_deck("one", 2, 2)
        duplicate = Slide(slide_id="duplicate", deck_id="one", slide_number=1)
        with pytest.raises(sqlite3.IntegrityError):
            db.replace_deck_and_slides(changed, [duplicate, duplicate])
        assert db.get_change_cursor() == first
        assert db.get_slides_for_deck("one")[0].title == "Title v1 p1"
        assert read_live_index(config.db_path, after=first)["upserts"] == []

        updated, slides = make_deck("one", 3, 1)
        db.replace_deck_and_slides(updated, slides)
        next_page = read_live_index(config.db_path, after=first)
        assert next_page["cursor"] > first
        assert next_page["stats"] == {"deck_count": 1, "slide_count": 1}
        assert [s["id"] for s in next_page["upserts"][0]["slides"]] == ["one-1"]
        assert next_page["upserts"][0]["deck"]["modified_date"]
    finally:
        db.close()


def test_bounded_cursor_pagination_delete_and_readd(tmp_path):
    config = make_archive(tmp_path)
    with _db_scope(config.db_path) as db:
        for i in range(8):
            db.replace_deck_and_slides(*make_deck(f"deck-{i}"))
        cursor = 0
        seen = []
        while True:
            page = read_live_index(config.db_path, after=cursor, limit=3)
            assert len(page["upserts"]) <= 3
            assert page["cursor"] > cursor
            cursor = page["cursor"]
            seen.extend(e["deck"]["id"] for e in page["upserts"])
            if not page["has_more"]:
                break
        assert len(seen) == 8 and len(set(seen)) == 8
        assert read_live_index(config.db_path, after=cursor)["cursor"] == cursor
        db.mark_deleted("deck-1")
        removed = read_live_index(config.db_path, after=cursor)
        assert removed["removed"] == ["deck-1"]
        assert removed["stats"]["deck_count"] == 7
        cursor = removed["cursor"]
        db.replace_deck_and_slides(*make_deck("deck-1", 3))
        restored = read_live_index(config.db_path, after=cursor)
        assert restored["upserts"][0]["deck"]["id"] == "deck-1"
        cursor = restored["cursor"]
        db.purge_deck("deck-1")
        purged = read_live_index(config.db_path, after=cursor)
        assert purged["removed"] == ["deck-1"]
        assert purged["stats"]["deck_count"] == 7


class _db_scope:
    def __init__(self, path): self.path = path
    def __enter__(self): self.db = IndexDB(self.path); return self.db
    def __exit__(self, *_): self.db.close()


def test_migrates_preexisting_decks_once_without_source_scan(tmp_path):
    config = make_archive(tmp_path)
    path = Path(config.db_path)
    path.parent.mkdir(parents=True)
    connection = sqlite3.connect(path)
    connection.executescript("""
      CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
      CREATE TABLE decks (deck_id TEXT PRIMARY KEY, file_path TEXT NOT NULL,
        file_name TEXT NOT NULL, folder_path TEXT NOT NULL, file_size INTEGER NOT NULL,
        modified_time REAL NOT NULL, processed_time REAL NOT NULL DEFAULT 0,
        slide_count INTEGER NOT NULL DEFAULT 0, file_signature TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active');
      CREATE TABLE slides (slide_id TEXT PRIMARY KEY, deck_id TEXT NOT NULL,
        slide_number INTEGER NOT NULL, title TEXT NOT NULL DEFAULT '',
        subtitle_text TEXT NOT NULL DEFAULT '', body_text TEXT NOT NULL DEFAULT '',
        extra_text TEXT NOT NULL DEFAULT '', extracted_text TEXT NOT NULL DEFAULT '',
        notes_text TEXT NOT NULL DEFAULT '', thumb_path TEXT NOT NULL DEFAULT '',
        preview_path TEXT NOT NULL DEFAULT '', width INTEGER NOT NULL DEFAULT 0,
        height INTEGER NOT NULL DEFAULT 0);
    """)
    connection.execute("INSERT INTO decks VALUES ('legacy', '/private/legacy.pdf', 'legacy.pdf', '/private', 12, 100, 100, 0, 's', 'active')")
    connection.commit()
    connection.close()

    with _db_scope(config.db_path) as db:
        original = db.get_change_cursor()
        assert original == 1
        assert read_live_index(config.db_path, after=0)["upserts"][0]["deck"]["id"] == "legacy"
    with _db_scope(config.db_path) as db:
        assert db.get_change_cursor() == original
        db.replace_deck_and_slides(*make_deck("after-migration"))
        assert db.get_change_cursor() == original + 1


def test_static_export_snapshot_cursor_is_precise(tmp_path):
    config = make_archive(tmp_path)
    with _db_scope(config.db_path) as db:
        db.replace_deck_and_slides(*make_deck("first"))
        committed = db.get_change_cursor()
    builder.build_viewer(config)
    export = json.loads((Path(config.output_dir) / "data/export.json").read_text(encoding="utf-8"))
    assert export["live_cursor"] == committed
    assert len(export["decks"]) == 1
    with _db_scope(config.db_path) as db:
        db.replace_deck_and_slides(*make_deck("second"))
    diff = read_live_index(config.db_path, after=export["live_cursor"])
    assert [item["deck"]["id"] for item in diff["upserts"]] == ["second"]
    assert builder.viewer_is_current(config) is False
    builder.build_viewer(config)
    assert builder.viewer_is_current(config) is True


def test_live_http_api_is_bounded_readonly_and_rejects_bad_cursors(tmp_path):
    config = make_archive(tmp_path)
    with _db_scope(config.db_path) as db:
        db.replace_deck_and_slides(*make_deck("private-doc"))
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)

    class Control:
        def __init__(self, conf): self.config = conf
        def status_snapshot(self): return {"status": "scanning"}
        def bind_shutdown(self, *_): pass

    listener = create_server(config.output_dir, 0, control=Control(config))
    thread = threading.Thread(target=listener.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{listener.server_port}"
    try:
        with urllib.request.urlopen(base + "/api/index/live?after=0&limit=1", timeout=3) as response:
            assert response.status == 200
            assert response.headers["Cache-Control"] == "no-store"
            data = json.load(response)
        assert data["stats"] == {"deck_count": 1, "slide_count": 1}
        assert data["upserts"][0]["deck"]["id"] == "private-doc"
        cursor = data["cursor"]
        for query in ("after=-1", "after=%2B1", "after=abc", "after=99999999999999999999",
                      "after=1&after=2", "after=0&limit=0", "after=0&limit=51", "after=0&unexpected=1"):
            with pytest.raises(urllib.error.HTTPError) as failed:
                urllib.request.urlopen(base + "/api/index/live?" + query, timeout=3)
            assert failed.value.code == 400
            assert b"/private" not in failed.value.read()
        with urllib.request.urlopen(base + f"/api/index/live?after={cursor}", timeout=3) as response:
            current = json.load(response)
        assert current["upserts"] == [] and current["removed"] == []
    finally:
        listener.shutdown()
        listener.server_close()
        thread.join(timeout=4)


def test_readonly_live_index_does_not_require_an_agent_write_lock(tmp_path):
    config = make_archive(tmp_path)
    with _db_scope(config.db_path) as db:
        db.replace_deck_and_slides(*make_deck("first"))
        stop = threading.Event()
        failures = []
        def concurrent_reader():
            while not stop.is_set():
                try:
                    result = read_live_index(config.db_path, after=0, limit=1)
                    assert result["stats"]["deck_count"] >= 1
                except Exception as exc: failures.append(type(exc).__name__)
                time.sleep(0.001)
        thread = threading.Thread(target=concurrent_reader, daemon=True)
        thread.start()
        for i in range(20):
            db.replace_deck_and_slides(*make_deck(f"concurrent-{i}"))
        stop.set()
        thread.join(timeout=3)
        assert not failures
    assert read_live_index(config.db_path, after=0)["stats"]["deck_count"] == 21


def test_live_index_rejects_bool_negative_large_and_missing_db(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_live_index(tmp_path / "missing.db", after=0)
    for cursor in (-1, True, 2**63):
        with pytest.raises(ValueError):
            read_live_index(tmp_path / "missing.db", after=cursor)
    for limit in (-1, True, 0, MAX_EVENTS_PER_PAGE + 1):
        with pytest.raises(ValueError):
            read_live_index(tmp_path / "missing.db", after=0, limit=limit)
