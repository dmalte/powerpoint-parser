"""Cumulative release metadata and embedded frontend contracts."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def test_release_version_consistent_across_windows_and_python():
    project=(ROOT/'pyproject.toml').read_text(encoding='utf-8')
    expected=re.search(r'^version\s*=\s*"([^"]+)"',project,re.MULTILINE).group(1)
    assert expected == '0.1.4'
    assert f'__version__ = "{expected}"' in (ROOT/'src/ppt_visual_archive/__init__.py').read_text()
    assert f'[string]$Version = "{expected}"' in (ROOT/'packaging/windows/build.ps1').read_text()
    assert f'#define AppVersion "{expected}"' in (ROOT/'packaging/windows/PowerPointVisualArchive.iss').read_text()


def test_both_platform_bundles_include_latest_viewer_and_backend():
    for platform in ('macos','windows'):
        spec=(ROOT/f'packaging/{platform}/PowerPointVisualArchive.spec').read_text()
        assert 'datas=[(str(web_root), "web")]' in spec
        assert (ROOT/f'packaging/{platform}/README.md').is_file()
    assert (ROOT/'web/static/js/live-index.js').is_file()
    assert '<script src="js/live-index.js"></script>' in (ROOT/'web/templates/index.html.j2').read_text()
    app=(ROOT/'web/static/js/app.js').read_text()
    assert 'setInterval(poll, 10000)' in app
    assert '/api/index/live?' in app
    assert (ROOT/'src/ppt_visual_archive/live_index.py').is_file()
    assert 'CloseApplications=force' in (ROOT/'packaging/windows/PowerPointVisualArchive.iss').read_text()


def test_cumulative_public_docs_include_live_and_https_images():
    public_docs=ROOT/'publishing/templates/public-README.md'
    if not public_docs.exists():
        public_docs=ROOT/'README.md'  # curated source has generated public README, not private template
    text=public_docs.read_text(encoding='utf-8')
    assert 'every 10 seconds' in text
    assert 'Automatically imported HTTPS Markdown images' in text
    assert 'Offline Mode' in text


def test_macos_distribution_contains_user_installer_and_offline_docs():
    release=(ROOT/'packaging/macos/build_release.sh').read_text()
    install=(ROOT/'packaging/macos/Install.command').read_text()
    uninstall=(ROOT/'packaging/macos/Uninstall.command').read_text()
    docs=(ROOT/'packaging/macos/RELEASE_INSTALL.md').read_text()
    assert 'PyInstaller --clean --noconfirm --onefile --console' in release
    assert 'packaging/macos/install_agent.py' in release
    assert 'hdiutil create' in release and 'hdiutil verify' in release
    assert 'codesign --verify' in release and 'source_revision' in release
    assert '--install --artifacts' in install and '--uninstall' in uninstall
    assert 'markdown_offline_mode' in (ROOT/'config/config.example.yaml').read_text()
    assert 'Offline Mode' in docs and 'Not notarized' in docs
    public_readme = ROOT/'publishing/templates/public-README.md'
    if not public_readme.exists():
        public_readme = ROOT/'README.md'
    assert 'self-contained installer' in public_readme.read_text(encoding='utf-8')
