"""Portable tests for the opt-in native macOS PowerPoint smoke command."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="macOS PowerPoint native smoke is Darwin-only")


def load_script():
    path = Path(__file__).resolve().parents[1] / "scripts/smoke_macos_powerpoint.py"
    spec = importlib.util.spec_from_file_location("ppt_macos_native_smoke_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def sample_pptx(path: Path) -> Path:
    pres = Presentation()
    slide = pres.slides.add_slide(pres.slide_layouts[0])
    slide.shapes.title.text = "Private fixture"
    pres.save(path)
    return path


def test_fake_mac_success_uses_original_pptx_and_validates_images(tmp_path, monkeypatch):
    import ppt_visual_archive.mac_renderer as renderer

    smoke = load_script()
    monkeypatch.setattr(smoke.sys, "platform", "darwin")
    original = sample_pptx(tmp_path / "private-fixture.pptx")

    class FakeRenderer:
        def __init__(self, config): self.config = config
        def start(self): pass
        def stop(self): pass
        def export_slides(self, source, target):
            assert str(source) == str(original)
            directory = Path(target)
            directory.mkdir(parents=True, exist_ok=True)
            for kind in ("thumb", "preview"):
                Image.new("RGB", (30, 20)).save(directory / f"{kind}_001.jpg")
            return [{"slide_number": 1, "thumb_path": "thumb_001.jpg", "preview_path": "preview_001.jpg"}]

    monkeypatch.setattr(renderer, "MacPowerPointRenderer", FakeRenderer)
    result = smoke.run_smoke(original, tmp_path / "images", "powerpoint", 10)
    assert result["status"] == "pass"
    assert result["rendered_slides"] == 1
    assert result["office_error_code"] is None
    assert str(original) not in json.dumps(result)


def test_native_error_code_is_reported_without_paths(tmp_path, monkeypatch):
    import ppt_visual_archive.mac_renderer as renderer

    smoke = load_script()
    monkeypatch.setattr(smoke.sys, "platform", "darwin")
    original = sample_pptx(tmp_path / "private-fixture.pptx")

    class FakeFailure:
        def __init__(self, config): pass
        def start(self): pass
        def stop(self): pass
        def export_slides(self, source, target):
            try:
                raise subprocess.CalledProcessError(1, ["osascript"], stderr="execution error -9074")
            except subprocess.CalledProcessError as exc:
                raise RuntimeError("PowerPoint export unavailable") from exc

    monkeypatch.setattr(renderer, "MacPowerPointRenderer", FakeFailure)
    result = smoke.run_smoke(original, tmp_path / "images", "powerpoint", 10)
    assert result["status"] == "fail"
    assert result["office_error_code"] == "-9074"
    assert result["rendered_slides"] == 0
    assert str(original) not in json.dumps(result)
