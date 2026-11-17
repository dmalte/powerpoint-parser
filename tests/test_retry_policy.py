"""M008i: persistent encrypted-file holds and bounded PowerPoint retry windows."""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path

import fitz
import pytest
from click.testing import CliRunner

from ppt_visual_archive import pipeline, retry_policy
from ppt_visual_archive.agent import AgentRuntime, refresh_archive
from ppt_visual_archive.cli import main as cli
from ppt_visual_archive.config import default_config, save_config
from ppt_visual_archive.index_db import IndexDB
from ppt_visual_archive.models import ScanResult
from ppt_visual_archive.retry_policy import BACKOFF_SECONDS, RetryState, retry_state_path
from ppt_visual_archive.server import create_server


def _config(tmp_path, extensions=None):
    root = tmp_path / "sources"
    root.mkdir()
    cfg = default_config(str(tmp_path / "viewer"), [str(root)])
    cfg.file_types = extensions or ["pdf"]
    cfg.processing.scan_interval_seconds = 0
    return cfg, root


def _scan_item(path, signature="test-signature"):
    return ScanResult(file_path=str(path), file_name=path.name,
                      folder_path=str(path.parent), file_size=4,
                      modified_time=1, file_signature=signature)


def _pdf(path, *, encrypted=False, text="Normal PDF page"):
    document = fitz.open()
    document.new_page().insert_text((20, 70), text)
    kwargs = {}
    if encrypted:
        kwargs = dict(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner-secret", user_pw="reader-secret")
    document.save(path, **kwargs)
    document.close()


def _post(base, path, body):
    payload = json.dumps(body).encode()
    request = urllib.request.Request(base + path, data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=4) as response:
        return response.status, json.load(response)


def test_retry_state_is_private_and_survives_restart_without_paths(tmp_path):
    cfg, root = _config(tmp_path)
    source = root / "private tax return.pdf"
    source.write_bytes(b"test")
    record = _scan_item(source)
    state = RetryState(cfg)
    state.failed(record, "encrypted PDF, password required", now=100)
    filename = retry_state_path(cfg)
    assert filename.is_file() and filename.parent != Path(cfg.output_dir)
    assert filename.stat().st_mode & 0o777 == 0o600
    blob = filename.read_text()
    for sensitive in ("private tax", str(root), "password required", "owner-secret", "reader-secret"):
        assert sensitive not in blob
    restarted = RetryState(cfg)
    assert restarted.decision(record, now=10_000) == "encrypted_hold"
    assert restarted.decision(record, force=True, now=10_000) is None
    assert restarted.status(now=10_000)["encrypted_held"] == 1


def test_changed_signature_and_manual_reset_make_document_eligible(tmp_path):
    cfg, root = _config(tmp_path)
    item = _scan_item(root / "file.pdf")
    state = RetryState(cfg)
    state.failed(item, "password required", now=0)
    changed = _scan_item(root / "file.pdf", signature="different-size-or-mtime")
    assert RetryState(cfg).decision(changed) is None
    assert RetryState(cfg).status()["encrypted_held"] == 0
    state = RetryState(cfg)
    state.failed(item, "encrypted", now=50)
    assert RetryState(cfg).clear(file_path=item.file_path) == 1
    assert RetryState(cfg).decision(item) is None
    assert RetryState(cfg).clear(all_entries=True) == 0


def test_powerpoint_backoff_increases_caps_and_recovers_when_due(tmp_path):
    cfg, root = _config(tmp_path, ["pptx"])
    item = _scan_item(root / "bad.pptx")
    state = RetryState(cfg)
    for idx, delay in enumerate((*BACKOFF_SECONDS, BACKOFF_SECONDS[-1]), 1):
        timestamp = idx * 30_000
        state.failed(item, "PowerPoint PDF export failed -9074", now=timestamp)
        saved = RetryState(cfg)
        assert saved.decision(item, now=timestamp + delay - 1) == "backoff"
        assert saved.decision(item, now=timestamp + delay) is None
        assert saved.status(now=timestamp + delay - 1)["backoff_waiting"] == 1
        assert saved.status(now=timestamp + delay)["transient_due"] == 1
    state.succeeded(item)
    assert RetryState(cfg).status()["backoff_waiting"] == 0
    assert RetryState(cfg).status()["transient_due"] == 0


def test_permission_is_retryable_and_unknown_pdf_does_not_get_held(tmp_path):
    cfg, root = _config(tmp_path, ["pdf", "pptx"])
    permission = _scan_item(root / "presentation.pptx")
    state = RetryState(cfg)
    state.failed(permission, "Permission denied while using PowerPoint", now=100)
    assert RetryState(cfg).decision(permission, now=399) == "backoff"
    assert RetryState(cfg).decision(permission, now=400) is None
    invalid = _scan_item(root / "invalid.pdf")
    state.failed(invalid, "Document format invalid; unreadable", now=100)
    assert RetryState(cfg).decision(invalid, now=110) is None
    assert RetryState(cfg).status(now=110)["encrypted_held"] == 0


def test_encrypted_pdf_is_held_and_does_not_rebuild_or_modify_source(tmp_path):
    cfg, root = _config(tmp_path)
    protected = root / "protected.pdf"
    _pdf(protected, encrypted=True)
    original = protected.read_bytes()
    first = refresh_archive(cfg)
    assert first["processed_err"] == 1 and first["processed_ok"] == 0
    assert first["viewer_rebuilt"] is True
    assert RetryState(cfg).status()["encrypted_held"] == 1
    second = refresh_archive(cfg)
    assert second["processed_err"] == second["processed_ok"] == 0
    assert second["retry_held"] == 1 and second["retry_backoff"] == 0
    assert second["viewer_rebuilt"] is False
    assert protected.read_bytes() == original
    forced = pipeline.run_scan(cfg, force=True)
    assert forced["processed_err"] == 1 and forced["retry_held"] == 0
    assert RetryState(cfg).status()["encrypted_held"] == 1
    _pdf(protected, text="Repaired and unencrypted source with two lines")
    repaired = refresh_archive(cfg)
    assert repaired["processed_ok"] == 1 and repaired["retry_held"] == 0
    assert RetryState(cfg).status()["encrypted_held"] == 0
    db = IndexDB(cfg.db_path)
    try:
        assert len(db.get_all_slides()) == 1
    finally:
        db.close()


def test_changed_indexed_pdf_can_fail_and_recover_without_losing_prior_generation(tmp_path):
    cfg, root = _config(tmp_path)
    path = root / "indexed.pdf"
    _pdf(path)
    assert refresh_archive(cfg)["processed_ok"] == 1
    db = IndexDB(cfg.db_path)
    try:
        original = db.get_all_slides()[0]
        original_generation = (Path(cfg.output_dir) / original.preview_path).read_bytes()
    finally:
        db.close()
    _pdf(path, encrypted=True)
    first_fail = refresh_archive(cfg)
    assert first_fail["processed_err"] == 1 and first_fail["changed"] == 1
    second_fail = refresh_archive(cfg)
    assert second_fail["retry_held"] == 1 and second_fail["processed_err"] == 0
    db = IndexDB(cfg.db_path)
    try:
        assert db.get_all_slides()[0].preview_path == original.preview_path
    finally:
        db.close()
    assert (Path(cfg.output_dir) / original.preview_path).read_bytes() == original_generation
    _pdf(path, text="Decrypted replacement")
    assert refresh_archive(cfg)["processed_ok"] == 1
    assert RetryState(cfg).status()["encrypted_held"] == 0
    assert (Path(cfg.output_dir) / original.preview_path).read_bytes() == original_generation


def test_pipeline_transient_pptx_backoff_retries_after_due(tmp_path, monkeypatch):
    cfg, root = _config(tmp_path, ["pptx"])
    pptx = root / "unavailable.pptx"
    pptx.write_bytes(b"not a real deck, simulated renderer is injected")
    clock = [1000.0]
    factory = RetryState

    class FakeClockLedger(factory):
        def decision(self, item, *, force=False, now=None):
            return super().decision(item, force=force, now=clock[0])

        def failed(self, item, reason, *, now=None):
            return super().failed(item, reason, now=clock[0])

    class Renderer:
        attempts = 0

        def start(self):
            pass

        def stop(self):
            pass

        def export_slides(self, *_args):
            self.attempts += 1
            raise RuntimeError("PowerPoint PDF export -9074")

    renderer = Renderer()
    monkeypatch.setattr(pipeline, "RetryState", FakeClockLedger)
    monkeypatch.setattr(pipeline, "create_pptx_renderer", lambda _render: renderer)
    first = pipeline.run_scan(cfg)
    assert first["processed_err"] == 1 and renderer.attempts == 1
    second = pipeline.run_scan(cfg)
    assert second["retry_backoff"] == 1 and second["processed_err"] == 0
    assert renderer.attempts == 1
    clock[0] += BACKOFF_SECONDS[0]
    third = pipeline.run_scan(cfg)
    assert third["processed_err"] == 1 and third["retry_backoff"] == 0
    assert renderer.attempts == 2
    fourth = pipeline.run_scan(cfg, force=True)
    assert fourth["processed_err"] == 1 and renderer.attempts == 3


def test_corrupt_state_disables_suppression_and_explicit_reset_recovers(tmp_path):
    cfg, root = _config(tmp_path)
    source = root / "secret.pdf"
    item = _scan_item(source)
    state_path = retry_state_path(cfg)
    state_path.write_bytes(b'{"source_path":"sensitive","schema_version":2')
    before = state_path.read_bytes()
    state = RetryState(cfg)
    assert state.available is False
    assert state.decision(item) is None
    state.failed(item, "encrypted password")
    assert state_path.read_bytes() == before
    assert state.status()["storage_ok"] is False
    assert state.clear(all_entries=True) == 0
    assert RetryState(cfg).available is True
    assert "source_path" not in state_path.read_text()


def test_unwritable_state_fails_open_without_corrupting_persisted_file(tmp_path, monkeypatch):
    cfg, root = _config(tmp_path)
    item = _scan_item(root / "unwritable.pdf")
    state = RetryState(cfg)
    def broken_replace(*_args, **_kwargs):
        raise OSError("simulated disk unavailable")
    monkeypatch.setattr(retry_policy.os, "replace", broken_replace)
    state.failed(item, "password required")
    assert state.available is False
    assert state.decision(item) is None
    assert not retry_state_path(cfg).exists()
    assert not list(tmp_path.glob(".pptviewer-retry-write-*"))


def test_cli_shows_only_counts_and_validates_reset_scope(tmp_path):
    cfg, root = _config(tmp_path)
    config_path = tmp_path / "config.yaml"
    save_config(cfg, config_path)
    secret = root / "private.pdf"
    item = _scan_item(secret)
    RetryState(cfg).failed(item, "encrypted password")
    runner = CliRunner()
    reported = runner.invoke(cli, ["retry-status", "--config", str(config_path)])
    assert reported.exit_code == 0, reported.output
    assert json.loads(reported.output)["encrypted_held"] == 1
    assert "private.pdf" not in reported.output and str(tmp_path) not in reported.output
    denied = runner.invoke(cli, ["retry-reset", "--config", str(config_path), "--path", str(tmp_path / "outside.pdf")])
    assert denied.exit_code != 0
    assert RetryState(cfg).status()["encrypted_held"] == 1
    cleared = runner.invoke(cli, ["retry-reset", "--config", str(config_path), "--path", str(secret)])
    assert cleared.exit_code == 0, cleared.output
    assert json.loads(cleared.output)["reset"] == 1
    assert RetryState(cfg).status()["encrypted_held"] == 0
    all_again = runner.invoke(cli, ["retry-reset", "--config", str(config_path), "--all"])
    assert all_again.exit_code == 0 and json.loads(all_again.output)["reset"] == 0


def test_http_reset_blocks_busy_and_does_not_unpause(tmp_path):
    cfg, root = _config(tmp_path)
    source = root / "private.pdf"
    source.write_bytes(b"hello")
    RetryState(cfg).failed(_scan_item(source), "password encrypted", now=100)
    Path(cfg.output_dir).mkdir(parents=True, exist_ok=True)
    cfg.processing.scan_paused = True
    config_path = tmp_path / "settings.yaml"
    save_config(cfg, config_path)
    calls = []
    runtime = AgentRuntime(cfg, config_path=config_path, refresh_fn=lambda conf: calls.append(conf) or {"processed_ok": 0})
    server = create_server(cfg.output_dir, 0, control=runtime)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(base + "/api/status") as response:
            data = json.load(response)
        assert data["retry_policy"]["encrypted_held"] == 1
        assert "private.pdf" not in json.dumps(data["retry_policy"])
        assert runtime._refresh_lock.acquire(False)
        try:
            with pytest.raises(urllib.error.HTTPError) as failure:
                _post(base, "/api/retry/reset", {"all": True})
            assert failure.value.code == 409
            assert RetryState(cfg).status()["encrypted_held"] == 1
        finally:
            runtime._refresh_lock.release()
        code, reset = _post(base, "/api/retry/reset", {"all": True})
        assert code == 202 and reset["reset"] == 1 and reset["started"] is False
        assert reset["reason"] == "paused"
        assert runtime.scan_paused is True and calls == []
        assert RetryState(cfg).status()["encrypted_held"] == 0
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def test_http_reset_starts_scan_if_not_paused(tmp_path):
    cfg, root = _config(tmp_path)
    item = _scan_item(root / "presentation.pdf")
    RetryState(cfg).failed(item, "encrypted")
    Path(cfg.output_dir).mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "settings.yaml"
    save_config(cfg, config_path)
    reached = threading.Event()
    runtime = AgentRuntime(cfg, config_path=config_path, refresh_fn=lambda _cfg: reached.set() or {"processed_ok": 0})
    server = create_server(cfg.output_dir, 0, control=runtime)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        code, reset = _post(base, "/api/retry/reset", {"all": True})
        assert code == 202 and reset["reset"] == 1 and reset["started"] is True
        assert reached.wait(3)
        assert RetryState(cfg).status()["encrypted_held"] == 0
        assert runtime.scan_paused is False
        assert runtime.status_snapshot()["status"] == "idle"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def test_http_reset_one_path_rejects_outside_roots_and_preserves_other_hold(tmp_path):
    cfg, root = _config(tmp_path)
    first, second = root / "first.pdf", root / "second.pdf"
    ledger = RetryState(cfg)
    ledger.failed(_scan_item(first), "encrypted")
    ledger.failed(_scan_item(second), "encrypted")
    cfg.processing.scan_paused = True
    Path(cfg.output_dir).mkdir(parents=True, exist_ok=True)
    settings = tmp_path / "config.yaml"
    save_config(cfg, settings)
    runtime = AgentRuntime(cfg, config_path=settings, refresh_fn=lambda _cfg: {"processed_ok": 0})
    server = create_server(cfg.output_dir, 0, control=runtime)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(urllib.error.HTTPError) as rejection:
            _post(base, "/api/retry/reset", {"path": str(tmp_path / "outside.pdf")})
        assert rejection.value.code == 400
        assert RetryState(cfg).status()["encrypted_held"] == 2
        code, result = _post(base, "/api/retry/reset", {"path": str(first)})
        assert code == 202 and result["reset"] == 1
        assert result["started"] is False and result["reason"] == "paused"
        assert RetryState(cfg).status()["encrypted_held"] == 1
        assert RetryState(cfg).decision(_scan_item(second)) == "encrypted_hold"
        assert runtime.scan_paused is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_settings_buttons_and_path_free_deferred_status_are_present():
    root = Path(__file__).resolve().parents[1]
    template = (root / "web/templates/settings.html.j2").read_text()
    script = (root / "web/static/js/settings.js").read_text()
    assert 'id="retry-failures"' in template
    assert 'id="retry-status"' in template
    assert "Retry Deferred Files" in template
    assert "status.retry_policy" in script
    assert "/api/retry/reset" in script
    assert "if (!window.confirm(" in script
    assert "scanning || transitioning" in script


def test_encrypted_pdf_is_held_before_a_slow_powerpoint_converter_starts(tmp_path, monkeypatch):
    """A GUI-dependency stall must not block recording independent PDF holds."""
    cfg, root = _config(tmp_path, ["pdf", "pptx"])
    locked = root / "locked.pdf"
    _pdf(locked, encrypted=True)
    (root / "nonworking.pptx").write_bytes(b"Synthetic PowerPoint source")
    observed: list[int] = []

    class PowerPoint:
        def start(self):
            # The PDF hold is already durable before touching Office.
            observed.append(RetryState(cfg).status()["encrypted_held"])

        def stop(self):
            pass

        def export_slides(self, *_args):
            raise RuntimeError("PowerPoint conversion -9074")

    monkeypatch.setattr(pipeline, "create_pptx_renderer", lambda _config: PowerPoint())
    first = pipeline.run_scan(cfg)
    assert observed == [1]
    assert first["processed_err"] == 2
    assert RetryState(cfg).status()["encrypted_held"] == 1
    second = pipeline.run_scan(cfg)
    assert second["retry_held"] == 1 and second["retry_backoff"] == 1
    assert second["processed_err"] == second["processed_ok"] == 0
    assert observed == [1]  # not even an Office renderer start during backoff
