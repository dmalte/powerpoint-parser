"""M016 browser-only incremental polling and merge safety."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js unavailable")
def test_live_index_node_tests():
    result = subprocess.run(
        ["node", "--test", str(ROOT / "tests/live_index_node.test.cjs")],
        cwd=ROOT, capture_output=True, text=True, timeout=25,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_browser_polls_10s_and_keeps_standalone_fallback():
    app = (ROOT / "web/static/js/app.js").read_text(encoding="utf-8")
    helper = (ROOT / "web/static/js/live-index.js").read_text(encoding="utf-8")
    template = (ROOT / "web/templates/index.html.j2").read_text(encoding="utf-8")
    assert 'setInterval(poll, 10000)' in app
    assert 'location.protocol === "file:"' in app
    assert '/api/index/live?after=' in app
    assert 'window.LiveIndex.merge(DATA, page)' in app
    assert 'applyFilters(false)' in app
    assert 'if (resetPage) gridPage = 0;' in app
    assert 'const ids = new Set(page.removed)' in helper
    assert template.index('src="js/live-index.js"') < template.index('src="js/app.js"')
    assert 'fetch("data/export.json", { cache: "no-store" })' in app
