"""Run real Node tests for recursive folder logic; static viewer shape assertions."""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
import pytest


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js unavailable")
def test_folder_tree_filters_node_tests():
    project=Path(__file__).resolve().parents[1]
    result=subprocess.run(
        ["node","--test",str(project/"tests/folder_tree_node.test.cjs")],
        cwd=project,capture_output=True,text=True,timeout=35,
    )
    assert result.returncode==0,result.stdout+"\n"+result.stderr


def test_folder_tree_ui_controls_are_loaded_and_viewer_only():
    project=Path(__file__).resolve().parents[1]
    template=(project/"web/templates/index.html.j2").read_text(encoding="utf-8")
    app=(project/"web/static/js/app.js").read_text(encoding="utf-8")
    for name in ("folder-search","folder-clear","folder-list","folder-selection-status"):
        assert 'id="'+name+'"' in template
    assert template.index('src="js/folder-tree.js"') < template.index('src="js/app.js"')
    assert "FolderFilterTree.matches" in app
    assert "folderIncludes" in app and "folderExcludes" in app
    assert "folder-tree.js" not in (project/"src/ppt_visual_archive/pipeline.py").read_text(encoding="utf-8")
