"""Tests for the scanner, index_db, extractor, and builder modules."""

import os
import tempfile
from pathlib import Path
from typing import Any, cast

import pytest
from pptx import Presentation
from pptx.util import Inches

from ppt_visual_archive.config import AppConfig, RenderConfig, ProcessingConfig, ViewerConfig, load_config
from ppt_visual_archive.models import ScanResult, Deck, Slide, DeckStatus
from ppt_visual_archive.index_db import IndexDB
from ppt_visual_archive.scanner import scan_files, detect_changes
from ppt_visual_archive.extractor import extract_metadata
from ppt_visual_archive.builder import build_viewer
from ppt_visual_archive.pipeline import _format_processing_message
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
    title1 = slide1.shapes.title
    assert title1 is not None
    title1.text_frame.text = "First Slide Title"
    subtitle1 = cast(Any, slide1.placeholders[1])
    subtitle1.text_frame.text = "Body text on slide one"

    # Slide 2
    layout2 = prs.slide_layouts[1]
    slide2 = prs.slides.add_slide(layout2)
    title2 = slide2.shapes.title
    assert title2 is not None
    title2.text_frame.text = "Second Slide"
    body2 = cast(Any, slide2.placeholders[1])
    body2.text_frame.text = "More content here"

    # Slide 3 with additional freeform textbox text
    blank_layout = prs.slide_layouts[6]
    slide3 = prs.slides.add_slide(blank_layout)
    title_box = slide3.shapes.add_textbox(Inches(1), Inches(0.5), Inches(6), Inches(0.5))
    title_box.text_frame.text = "Third Slide"
    body_box = slide3.shapes.add_textbox(Inches(1), Inches(1.5), Inches(6), Inches(1))
    body_box.text_frame.text = "Additional freeform textbox text"

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
            Slide(
                slide_id="test_01_s001",
                deck_id="test_01",
                slide_number=1,
                title="Hello",
                subtitle_text="Subtitle",
                body_text="Body text",
                extra_text="Extra text",
                notes_text="Speaker notes",
            ),
            Slide(slide_id="test_01_s002", deck_id="test_01", slide_number=2, title="World"),
        ]
        db.upsert_slides(slides)
        fetched = db.get_slides_for_deck("test_01")
        assert len(fetched) == 2
        assert fetched[0].title == "Hello"
        assert fetched[0].subtitle_text == "Subtitle"
        assert fetched[0].body_text == "Body text"
        assert fetched[0].extra_text == "Extra text"

        # Search
        found = db.search_slides("Hello")
        assert len(found) == 1
        assert len(db.search_slides("Subtitle")) == 1
        assert len(db.search_slides("Speaker notes")) == 1

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

    def test_change_detection_scoped_deletions(self, tmp_output):
        db_path = str(Path(tmp_output) / "data" / "test3.db")
        db = IndexDB(db_path)

        deck_a = Deck(
            deck_id="deck_a",
            file_path="C:/scope/a.pptx",
            file_name="a.pptx",
            folder_path="C:/scope",
            file_size=1000,
            modified_time=100.0,
            file_signature="C:/scope/a.pptx|1000|100.0",
            status=DeckStatus.ACTIVE.value,
        )
        deck_b = Deck(
            deck_id="deck_b",
            file_path="C:/other/b.pptx",
            file_name="b.pptx",
            folder_path="C:/other",
            file_size=2000,
            modified_time=200.0,
            file_signature="C:/other/b.pptx|2000|200.0",
            status=DeckStatus.ACTIVE.value,
        )
        db.upsert_deck(deck_a)
        db.upsert_deck(deck_b)

        changeset = detect_changes([], db, deletion_scope_roots=["C:/scope"])
        assert changeset.deleted == ["deck_a"]

        db.close()

    def test_scan_files_can_override_roots(self, config, sample_pptx, tmp_path):
        _, scan_dir = sample_pptx
        other_root = tmp_path / "other"
        other_root.mkdir()
        extra = other_root / "other_deck.pptx"
        extra.write_bytes(b"not-a-real-pptx")

        results = scan_files(config, roots=[scan_dir])
        assert len(results) == 1
        assert results[0].folder_path == str(Path(scan_dir).resolve())


# ── Extractor tests ──

class TestExtractor:
    def test_extract_titles(self, sample_pptx):
        pptx_path, _ = sample_pptx
        meta = extract_metadata(pptx_path)
        assert meta["slide_count"] == 3
        assert meta["slides"][0]["title"] == "First Slide Title"
        assert meta["slides"][1]["title"] == "Second Slide"
        assert meta["slides"][0]["subtitle_text"] == "Body text on slide one"
        assert "More content here" in meta["slides"][1]["body_text"]
        assert "Additional freeform textbox text" in meta["slides"][2]["extra_text"]
        assert "First Slide Title" in meta["slides"][0]["extracted_text"]


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

    def test_build_viewer_exports_structured_slide_fields(self, config, tmp_output):
        db = IndexDB(config.db_path)
        deck = Deck(
            deck_id="deck_structured",
            file_path="C:/slides/structured.pptx",
            file_name="structured.pptx",
            folder_path="C:/slides",
            file_size=1234,
            modified_time=1700000000.0,
            processed_time=1700000001.0,
            slide_count=1,
            file_signature="C:/slides/structured.pptx|1234|1700000000.0",
            status=DeckStatus.ACTIVE.value,
        )
        slide = Slide(
            slide_id="deck_structured_s001",
            deck_id="deck_structured",
            slide_number=1,
            title="Title",
            subtitle_text="Subtitle",
            body_text="Body",
            extra_text="Extra",
            extracted_text="Title\n\nSubtitle\n\nBody\n\nExtra",
            notes_text="Notes",
        )
        db.upsert_deck(deck)
        db.upsert_slides([slide])
        db.close()

        build_viewer(config)

        json_path = Path(config.output_dir) / "data" / "export.json"
        content = json_path.read_text(encoding="utf-8")
        assert '"subtitle":"Subtitle"' in content
        assert '"body":"Body"' in content
        assert '"extra":"Extra"' in content


# ── Utils test ──

class TestUtils:
    def test_make_deck_id_deterministic(self):
        id1 = make_deck_id("C:/slides/my presentation.pptx")
        id2 = make_deck_id("C:/slides/my presentation.pptx")
        assert id1 == id2
        assert len(id1) > 8


class TestPipeline:
    def test_progress_message_includes_position_and_directory(self):
        scan_result = ScanResult(
            file_path="C:/slides/demo/example.pptx",
            file_name="example.pptx",
            folder_path="C:/slides/demo",
            file_size=123,
            modified_time=100.0,
            file_signature="C:/slides/demo/example.pptx|123|100.0",
        )

        message = _format_processing_message(2, 5, scan_result)

        assert "[2/5]" in message
        assert "example.pptx" in message
        assert "directory: C:/slides/demo" in message

    def test_make_deck_id_different_paths(self):
        id1 = make_deck_id("C:/a/deck.pptx")
        id2 = make_deck_id("C:/b/deck.pptx")
        assert id1 != id2
