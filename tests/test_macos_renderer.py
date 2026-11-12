"""Portable Mac PowerPoint renderer tests: emulate only the native converter.

The renderer and its PyMuPDF JPEG outputs run for real; osascript and
LibreOffice calls are mocked because those applications are not installed on Pi.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
from pptx import Presentation

from ppt_visual_archive import agent, mac_renderer, pipeline, server
from ppt_visual_archive.config import RenderConfig, default_config, load_config, save_config
from ppt_visual_archive.index_db import IndexDB
from ppt_visual_archive.mac_renderer import LibreOfficeRenderer, MacPowerPointRenderer
from ppt_visual_archive.platform_paths import (
    default_archive_dir, default_config_path, default_log_dir, user_data_dir,
)
from ppt_visual_archive.renderer import PowerPointRenderer
from ppt_visual_archive.renderer_factory import create_pptx_renderer


def pptx_file(path: Path, slides: int = 2) -> Path:
    p = Presentation()
    for i in range(slides):
        slide = p.slides.add_slide(p.slide_layouts[0])
        slide.shapes.title.text = f"Original title {i + 1}"
        if slide.has_notes_slide:
            slide.notes_slide.notes_text_frame.text = f"Original speaker note {i + 1}"
    p.save(path)
    return path


def pdf_file(path: Path, pages: int = 2) -> None:
    pdf = fitz.open()
    for i in range(pages):
        page = pdf.new_page(width=720, height=405)
        page.insert_text((75, 70), f"Rendered PDF page {i + 1}")
    pdf.save(path)
    pdf.close()


def test_factory_keeps_windows_com_and_requires_explicit_fallback():
    config = RenderConfig()
    assert isinstance(create_pptx_renderer(config, platform_name="win32"), PowerPointRenderer)
    assert isinstance(create_pptx_renderer(config, platform_name="darwin"), MacPowerPointRenderer)
    assert isinstance(create_pptx_renderer(RenderConfig(mac_pptx_backend="libreoffice"), platform_name="darwin"),
                      LibreOfficeRenderer)
    assert isinstance(create_pptx_renderer(RenderConfig(mac_pptx_backend="libreoffice"), platform_name="linux"),
                      LibreOfficeRenderer)
    with pytest.raises(RuntimeError, match="PDF only"):
        create_pptx_renderer(config, platform_name="linux")
    with pytest.raises(ValueError, match="Unsupported"):
        create_pptx_renderer(RenderConfig(mac_pptx_backend="unknown"), platform_name="darwin")


def test_mac_powerpoint_exports_images_and_deletes_temporary_pdf(monkeypatch, tmp_path):
    source = pptx_file(tmp_path / "My presentation ' with spaces.pptx")
    output = tmp_path / "viewer" / "assets" / "decks" / "deckid"
    config = RenderConfig(thumbnail_width=160, preview_width=640)
    commands = []
    monkeypatch.setattr(mac_renderer.shutil, "which", lambda cmd: "/usr/bin/osascript" if cmd == "osascript" else None)

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        assert command[0] == "/usr/bin/osascript" and command[1] == "-e"
        assert command[2] == mac_renderer.POWERPOINT_PDF_APPLESCRIPT
        assert Path(command[3]).name == source.name
        assert Path(command[3]) != source.resolve()  # Automate a private copy, not user-owned open file
        assert Path(command[3]).read_bytes() == source.read_bytes()
        assert str(source) not in command[2]  # paths are argv, not script interpolation
        assert kwargs["timeout"] == 300 and kwargs["check"] is True
        pdf_file(Path(command[4]))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(mac_renderer.subprocess, "run", fake_run)
    renderer = MacPowerPointRenderer(config)
    renderer.start()
    results = renderer.export_slides(str(source), str(output))
    renderer.stop()
    assert len(commands) == 1
    assert [slide["slide_number"] for slide in results] == [1, 2]
    for slide in results:
        assert slide["thumb_path"].startswith("thumb_")
        assert slide["preview_path"].startswith("preview_")
        assert slide["width"] == 160
        assert (output / slide["thumb_path"]).is_file()
        assert (output / slide["preview_path"]).is_file()
    assert not list(output.parent.glob(".pptviewer-mac-*"))
    assert not list(tmp_path.rglob("presentation.pdf"))
    assert source.is_file()  # original PPTX never modified


def test_macos_pptx_to_searchable_index_retains_original_titles(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    pptx_file(source / "original.pptx", slides=2)
    cfg = default_config(str(tmp_path / "viewer"), [str(source)])
    cfg.file_types = ["pptx"]
    monkeypatch.setattr(mac_renderer.shutil, "which", lambda cmd: "/usr/bin/osascript")
    monkeypatch.setattr(mac_renderer.subprocess, "run", lambda cmd, **kwargs: (
        pdf_file(Path(cmd[-1]), pages=2),
        subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
    )[-1])
    monkeypatch.setattr(pipeline, "create_pptx_renderer", lambda _cfg: MacPowerPointRenderer(_cfg))

    summary = pipeline.run_scan(cfg)
    assert summary["processed_ok"] == 1
    db = IndexDB(cfg.db_path)
    try:
        slides = db.get_all_slides()
        assert len(slides) == 2
        assert [slide.title for slide in slides] == ["Original title 1", "Original title 2"]
        assert all("Rendered PDF page" not in slide.extracted_text for slide in slides)
        assert all(slide.thumb_path.endswith(".jpg") for slide in slides)
        assert all((Path(cfg.output_dir) / slide.preview_path).is_file() for slide in slides)
    finally:
        db.close()


def test_mac_missing_pdf_and_timeout_preserve_existing_images(monkeypatch, tmp_path):
    source = pptx_file(tmp_path / "test.pptx")
    output = tmp_path / "images"
    output.mkdir()
    original = output / "thumb_001.jpg"
    original.write_bytes(b"PREVIOUS IMAGE")
    monkeypatch.setattr(mac_renderer.shutil, "which", lambda cmd: "/usr/bin/osascript")

    def no_output(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(mac_renderer.subprocess, "run", no_output)
    with pytest.raises(RuntimeError, match="no PDF"):
        MacPowerPointRenderer(RenderConfig()).export_slides(str(source), str(output))
    assert original.read_bytes() == b"PREVIOUS IMAGE"

    def timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(mac_renderer.subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="timed out"):
        MacPowerPointRenderer(RenderConfig(pptx_conversion_timeout_seconds=1)).export_slides(str(source), str(output))
    assert original.read_bytes() == b"PREVIOUS IMAGE"
    assert not list(tmp_path.glob(".pptviewer-mac-*"))


def test_mac_mismatched_page_count_rejected_before_sql_insert(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    pptx_file(source / "three.pptx", slides=3)
    cfg = default_config(str(tmp_path / "viewer"), [str(source)])
    cfg.file_types = ["pptx"]
    monkeypatch.setattr(mac_renderer.shutil, "which", lambda cmd: "/usr/bin/osascript")
    monkeypatch.setattr(mac_renderer.subprocess, "run", lambda cmd, **kwargs: (
        pdf_file(Path(cmd[-1]), pages=2), subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
    )[-1])
    monkeypatch.setattr(pipeline, "create_pptx_renderer", lambda _cfg: MacPowerPointRenderer(_cfg))
    summary = pipeline.run_scan(cfg)
    assert summary["processed_err"] == 1 and summary["processed_ok"] == 0
    db = IndexDB(cfg.db_path)
    try:
        assert db.get_all_slides() == []
    finally:
        db.close()


def test_explicit_libreoffice_uses_private_profile_and_cleans_pdf(monkeypatch, tmp_path):
    source = pptx_file(tmp_path / "Agenda final.pptx")
    output = tmp_path / "images"
    commands = []
    monkeypatch.setattr(mac_renderer.shutil, "which", lambda cmd: "/usr/bin/soffice" if cmd == "soffice" else None)

    def fake_convert(command, **kwargs):
        commands.append(command)
        assert "--headless" in command and "--convert-to" in command
        assert "pdf:impress_pdf_Export" in command
        assert any(arg.startswith("-env:UserInstallation=file://") for arg in command)
        outdir = Path(command[command.index("--outdir") + 1])
        pdf_file(outdir / "Agenda final.pdf")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(mac_renderer.subprocess, "run", fake_convert)
    renderer = LibreOfficeRenderer(RenderConfig())
    results = renderer.export_slides(str(source), str(output))
    assert len(results) == 2
    assert len(commands) == 1
    assert all((output / slide["thumb_path"]).is_file() for slide in results)
    assert not list(tmp_path.rglob("*.pdf"))


def test_mac_paths_settings_and_native_finder_actions(monkeypatch, tmp_path):
    env = {"HOME": str(tmp_path)}
    root = tmp_path / "Library" / "Application Support" / "PowerPointVisualArchive"
    assert user_data_dir(env, platform_name="darwin") == root
    assert default_config_path(env, platform_name="darwin") == root / "config.yaml"
    assert default_archive_dir(env, platform_name="darwin") == root / "archive"
    logs = tmp_path / "Library" / "Logs" / "PowerPointVisualArchive"
    assert default_log_dir(env, platform_name="darwin") == logs

    config = default_config(str(root / "archive"), [str(tmp_path)])
    config.render.mac_pptx_backend = "libreoffice"
    config.render.pptx_conversion_timeout_seconds = 480
    save_config(config, root / "config.yaml")
    loaded = load_config(root / "config.yaml")
    assert loaded.render.mac_pptx_backend == "libreoffice"
    assert loaded.render.pptx_conversion_timeout_seconds == 480

    src = tmp_path / "document.pptx"
    src.write_bytes(b"demo")
    commands = []
    monkeypatch.setattr(server, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(server.subprocess, "Popen", lambda args: commands.append(args))
    server._open_file(str(src))
    server._open_folder(str(src))
    server._open_folder(str(tmp_path))
    assert commands == [
        ["open", str(src)], ["open", "-R", str(src)], ["open", str(tmp_path)],
    ]

    monkeypatch.setattr(agent, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(agent, "default_log_dir", lambda: logs)
    agent.AgentRuntime(config).open_logs()
    assert commands[-1] == ["open", str(logs)]


def test_end_to_end_mac_pptx_to_viewer_json_without_pdf_persistence(monkeypatch, tmp_path):
    from ppt_visual_archive.agent import refresh_archive
    from ppt_visual_archive import perf_metrics

    source = tmp_path / "pptx"
    source.mkdir()
    pptx_file(source / "Customer Update.pptx", slides=2)
    config = default_config(str(tmp_path / "archive"), [str(source)])
    config.file_types = ["pptx"]
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")
    monkeypatch.setattr(mac_renderer.shutil, "which", lambda executable: "/usr/bin/osascript")
    monkeypatch.setattr(mac_renderer.subprocess, "run", lambda args, **kwargs: (
        pdf_file(Path(args[-1]), pages=2), subprocess.CompletedProcess(args, 0),
    )[-1])
    monkeypatch.setattr(pipeline, "create_pptx_renderer", lambda rc: MacPowerPointRenderer(rc))

    summary = refresh_archive(config)
    assert summary["processed_ok"] == 1 and summary["viewer_rebuilt"]
    export = (Path(config.output_dir) / "data/export.json").read_text(encoding="utf-8")
    import json
    data = json.loads(export)
    assert data["stats"]["deck_count"] == 1
    assert data["stats"]["slide_count"] == 2
    assert data["slides"][0]["title"].startswith("Original title")
    assert data["slides"][0]["thumb"].startswith("assets/decks/")
    assert (Path(config.output_dir) / data["slides"][0]["thumb"]).is_file()
    assert "notes" in data["slides"][0]
    assert not list(tmp_path.rglob("*.pdf"))
    assert (Path(config.output_dir) / "index.html").is_file()
    assert refresh_archive(config)["viewer_rebuilt"] is False


def test_mac_automation_error_does_not_expose_source_path_in_status(monkeypatch, tmp_path):
    source = pptx_file(tmp_path / "Private Customer Deck.pptx", slides=1)
    monkeypatch.setattr(mac_renderer.shutil, "which", lambda command: "/usr/bin/osascript")

    def deny_automation(command, **kwargs):
        raise subprocess.CalledProcessError(
            1, command, stderr=f"Automation denied for: {source}",
        )

    monkeypatch.setattr(mac_renderer.subprocess, "run", deny_automation)
    with pytest.raises(RuntimeError, match="Automation permission") as failure:
        MacPowerPointRenderer(RenderConfig()).export_slides(
            str(source), str(tmp_path / "images"),
        )
    assert str(source) not in str(failure.value)
    assert source.is_file()
