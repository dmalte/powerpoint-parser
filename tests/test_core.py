"""Tests for the scanner, index_db, extractor, and builder modules."""

import os
import tempfile
from pathlib import Path

import pytest
from pptx import Presentation

from ppt_visual_archive.config import AppConfig, RenderConfig, ProcessingConfig, ViewerConfig, load_config
from ppt_visual_archive.models import ScanResult, Deck, Slide, DeckStatus
from ppt_visual_archive.index_db import IndexDB
from ppt_visual_archive.scanner import scan_files, detect_changes
from ppt_visual_archive.extractor import extract_metadata
from ppt_visual_archive.builder import build_viewer
from ppt_visual_archive.utils import make_deck_id


@pytest.fixture
def tmp_output(tmp_path):
    """Temp directory for test output."""
    return str(tmp_path / "output")


@pytest.fixture
def sample_pptx(tmp_path):
    """Create a minimal .pptx file for testing."""
    pptx_dir = tmp_path / "slides"
    pptx_dir.mkdir()
    pptx_path = pptx_dir / "test_deck.pptx"

    prs = Presentation()
    # Slide 1
    layout = prs.slide_layouts[0]
    slide1 = prs.slides.add_slide(layout)
    slide1.shapes.title.text = "First Slide Title"
    slide1.placeholders[1].text = "Body text on slide one"

    # Slide 2
    layout2 = prs.slide_layouts[1]
    slide2 = prs.slides.add_slide(layout2)
    slide2.shapes.title.text = "Second Slide"
    slide2.placeholders[1].text = "More content here"

    prs.save(str(pptx_path))
    return str(pptx_path), str(pptx_dir)


@pytest.fixture
def config(sample_pptx, tmp_output):
    _, scan_dir = sample_pptx
    return AppConfig(
        scan_roots=[scan_dir],
        output_dir=tmp_output,
        db_path=str(Path(tmp_output) / "data" / "index.db"),
        render=RenderConfig(thumbnail_width=160, preview_width=640),
        viewer=ViewerConfig(),
        processing=ProcessingConfig(),
    )


# ── Scanner tests ──

class TestScanner:
    def test_finds_pptx(self, config, sample_pptx):
        results = scan_files(config)
        assert len(results) == 1
        assert results[0].file_name == "test_deck.pptx"

    def test_excludes_temp_files(self, config, sample_pptx):
        pptx_path, scan_dir = sample_pptx
        # Create a temp file that should be excluded
        temp = Path(scan_dir) / "~$test_deck.pptx"
        temp.write_bytes(b"fake")
        config.exclude_patterns = ["~$*.pptx"]
        results = scan_files(config)
        assert len(results) == 1  # only the real file

    def test_signature_format(self, sample_pptx):
        sig = ScanResult.compute_signature("/path/file.pptx", 1234, 999.0)
        assert sig == "/path/file.pptx|1234|999.0"


# ── IndexDB tests ──

class TestIndexDB:
    def test_create_and_query(self, tmp_output):
        db_path = str(Path(tmp_output) / "data" / "test.db")
        db = IndexDB(db_path)

        deck = Deck(
            deck_id="test_01",
            file_path="C:/slides/test.pptx",
            file_name="test.pptx",
            folder_path="C:/slides",
            file_size=5000,
            modified_time=1700000000.0,
            processed_time=1700000001.0,
            slide_count=3,
            file_signature="C:/slides/test.pptx|5000|1700000000.0",
            status=DeckStatus.ACTIVE.value,
        )
        db.upsert_deck(deck)

        # Query back
        result = db.get_deck("test_01")
        assert result is not None
        assert result.file_name == "test.pptx"
        assert result.slide_count == 3

        # Slides
        slides = [
            Slide(slide_id="test_01_s001", deck_id="test_01", slide_number=1, title="Hello"),
            Slide(slide_id="test_01_s002", deck_id="test_01", slide_number=2, title="World"),
        ]
        db.upsert_slides(slides)
        fetched = db.get_slides_for_deck("test_01")
        assert len(fetched) == 2
        assert fetched[0].title == "Hello"

        # Search
        found = db.search_slides("Hello")
        assert len(found) == 1

        # Stats
        stats = db.get_stats()
        assert stats["deck_count"] == 1
        assert stats["slide_count"] == 2

        db.close()

    def test_change_detection(self, tmp_output):
        db_path = str(Path(tmp_output) / "data" / "test2.db")
        db = IndexDB(db_path)

        deck = Deck(
            deck_id="deck_a",
            file_path="C:/test/a.pptx",
            file_name="a.pptx",
            folder_path="C:/test",
            file_size=1000,
            modified_time=100.0,
            file_signature="C:/test/a.pptx|1000|100.0",
            status=DeckStatus.ACTIVE.value,
        )
        db.upsert_deck(deck)

        # Unchanged file
        sr_unchanged = ScanResult(
            file_path="C:/test/a.pptx", file_name="a.pptx",
            folder_path="C:/test", file_size=1000,
            modified_time=100.0,
            file_signature="C:/test/a.pptx|1000|100.0",
        )
        # New file
        sr_new = ScanResult(
            file_path="C:/test/b.pptx", file_name="b.pptx",
            folder_path="C:/test", file_size=2000,
            modified_time=200.0,
            file_signature="C:/test/b.pptx|2000|200.0",
        )

        changeset = detect_changes([sr_unchanged, sr_new], db)
        assert len(changeset.unchanged) == 1
        assert len(changeset.new) == 1
        assert len(changeset.deleted) == 0

        db.close()


# ── Extractor tests ──

class TestExtractor:
    def test_extract_titles(self, sample_pptx):
        pptx_path, _ = sample_pptx
        meta = extract_metadata(pptx_path)
        assert meta["slide_count"] == 2
        assert meta["slides"][0]["title"] == "First Slide Title"
        assert meta["slides"][1]["title"] == "Second Slide"
        assert "Body text" in meta["slides"][0]["extracted_text"]


# ── Builder test ──

class TestBuilder:
    def test_build_viewer_without_data(self, config):
        """Build viewer with empty DB — should generate valid HTML."""
        # Make sure DB is created
        db = IndexDB(config.db_path)
        db.close()

        build_viewer(config)
        html_path = Path(config.output_dir) / "index.html"
        assert html_path.exists()
        content = html_path.read_text(encoding="utf-8")
        assert "PowerPoint Visual Archive" in content
        assert "<script" in content

        json_path = Path(config.output_dir) / "data" / "export.json"
        assert json_path.exists()


# ── Utils test ──

class TestUtils:
    def test_make_deck_id_deterministic(self):
        id1 = make_deck_id("C:/slides/my presentation.pptx")
        id2 = make_deck_id("C:/slides/my presentation.pptx")
        assert id1 == id2
        assert len(id1) > 8

    def test_make_deck_id_different_paths(self):
        id1 = make_deck_id("C:/a/deck.pptx")
        id2 = make_deck_id("C:/b/deck.pptx")
        assert id1 != id2
