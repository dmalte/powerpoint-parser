"""Bounded deck sidebar unit and frontend integration contracts (M007h)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_sidebar_pager_node_contract():
    if not shutil.which("node"):
        pytest.skip("Node.js not installed")
    result = subprocess.run(
        ["node", "--test", str(ROOT / "tests/deck_pager_node.test.cjs")],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_sidebar_controls_loaded_before_viewer_app_and_keep_selection():
    template = (ROOT / "web/templates/index.html.j2").read_text()
    app = (ROOT / "web/static/js/app.js").read_text()
    for control in (
        "deck-page-prev", "deck-page-next", "deck-page-indicator",
        "deck-result-range", "deck-search", "deck-list",
    ):
        assert f'id="{control}"' in template
    assert template.index('src="js/deck-pager.js"') < template.index('src="js/app.js"')
    assert "DeckPager.paginate(DATA.decks, deckSearchQuery, deckPage)" in app
    assert "ul.replaceChildren(fragment);" in app
    assert "deckPage = 0;" in app
    assert 'li.dataset.deckId = deck.id;' in app
    assert 'deckList.addEventListener("click"' in app
    assert 'deckList.addEventListener("keydown"' in app
    assert 'filters.deckId = filters.deckId === deckId ? null : deckId;' in app
