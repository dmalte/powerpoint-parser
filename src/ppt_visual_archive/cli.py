"""CLI entry point."""

from __future__ import annotations

import os
import sys
from functools import wraps
from pathlib import Path

import click

from .config import AppConfig, default_config, load_config, save_config
from .platform_paths import default_archive_dir, default_config_path, default_log_dir
from .utils import add_file_logging, logger, setup_logging


def _resolve_config_path(config_path: str | None) -> Path:
    """Resolve an explicit or discovered config path."""
    if config_path:
        return Path(config_path).resolve()

    for candidate in _config_candidates():
        if candidate.exists():
            resolved = candidate.resolve()
            click.echo(f"Using config: {resolved}")
            return resolved

    click.echo(
        f"No config file found. Use --config or run 'pptviewer init-config'. "
        f"Default installed location: {default_config_path()}",
        err=True,
    )
    sys.exit(1)


def _resolve_config(config_path: str | None) -> AppConfig:
    """Load config from explicit path, or search default locations."""
    return load_config(_resolve_config_path(config_path))


def _config_candidates() -> list[Path]:
    """Return default config search paths in compatibility-preserving order."""
    return [
        Path("config.yaml"),
        Path("config") / "config.yaml",
        default_config_path(),
    ]


def common_options(command):
    """Apply common CLI options to subcommands.

    Keeping these options on each subcommand matches the documented command
    shape: `pptviewer scan --config config.yaml`.
    """

    @click.option("--config", "config_path", default=None, help="Path to config YAML file.")
    @click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
    @wraps(command)
    def wrapper(*args, config_path: str | None, verbose: bool, **kwargs):
        setup_logging(verbose)
        return command(*args, config_path=config_path, verbose=verbose, **kwargs)

    return wrapper


@click.group()
def main() -> None:
    """PowerPoint Visual Archive Viewer — local slide browser."""


@main.command("init-config")
@click.option(
    "--root",
    "scan_roots",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Folder to index. Can be repeated.",
)
@click.option("--config", "config_path", default=None, help="Config path; defaults to per-user app data.")
@click.option("--force", is_flag=True, help="Overwrite an existing config file.")
@click.option("--include-pdf", is_flag=True, help="Index PDF files as well as PowerPoint files.")
def init_config(
    scan_roots: tuple[Path, ...],
    config_path: str | None,
    force: bool,
    include_pdf: bool,
) -> None:
    """Create a per-user configuration without hand-editing YAML."""
    target = Path(config_path) if config_path else default_config_path()
    archive_dir = default_archive_dir()
    archive_dir.mkdir(parents=True, exist_ok=True)

    roots = [str(root.resolve()) for root in scan_roots]
    config = default_config(str(archive_dir), roots)
    if include_pdf:
        config.file_types = ["pptx", "pdf"]

    try:
        saved = save_config(config, target, overwrite=force)
    except FileExistsError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Config created: {saved}")
    click.echo(f"Archive directory: {config.output_dir}")
    if not roots:
        click.echo("No scan roots configured yet; add them before starting the agent.")


@main.command()
@click.option("--force", is_flag=True, help="Reprocess all files regardless of changes.")
@click.option(
    "--root",
    "scan_roots",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Only scan these folders for this run. Can be repeated.",
)
@common_options
def scan(
    force: bool,
    scan_roots: tuple[Path, ...],
    config_path: str | None,
    verbose: bool,
) -> None:
    """Scan folders, export slides, and update the index."""
    config = _resolve_config(config_path)
    from .pipeline import run_scan

    active_roots = [str(root.resolve()) for root in scan_roots] or None
    if active_roots:
        click.echo(f"Scanning {len(active_roots)} selected folder(s)")

    summary = run_scan(config, force=force, scan_roots=active_roots)
    click.echo(
        f"\nScan complete: "
        f"{summary['new']} new, {summary['changed']} changed, "
        f"{summary['unchanged']} unchanged, {summary['deleted']} deleted  |  "
        f"{summary['processed_ok']} processed OK, {summary['processed_err']} errors"
    )


@main.command()
@common_options
def build(config_path: str | None, verbose: bool) -> None:
    """Generate the HTML viewer from the existing index."""
    config = _resolve_config(config_path)
    from .builder import build_viewer

    build_viewer(config)
    click.echo("Viewer built successfully.")


def _retry_config(path: str | None) -> AppConfig:
    """Resolve without echoing private config paths into JSON CLI output."""
    if path is not None:
        return load_config(Path(path).expanduser().resolve())
    for candidate in _config_candidates():
        if candidate.is_file():
            return load_config(candidate)
    raise click.ClickException("A config file is required")


@main.command("retry-status")
@click.option("--config", "config_path", default=None, help="Archive configuration path")
def retry_status(config_path: str | None) -> None:
    """Show path-free counts of held encrypted and delayed transient errors."""
    import json
    from .retry_policy import RetryState

    status = RetryState(_retry_config(config_path)).status()
    click.echo(json.dumps(status, sort_keys=True))


@main.command("retry-reset")
@click.option("--config", "config_path", default=None, help="Archive configuration path")
@click.option("--all", "all_entries", is_flag=True, help="Reset all deferred failures")
@click.option("--path", "file_path", default=None, help="Reset one path within a configured scan root")
def retry_reset(config_path: str | None, all_entries: bool, file_path: str | None) -> None:
    """Explicitly clear a held retry when the live agent is paused/stopped.

    For a live unpaused agent, use Settings > Retry Deferred Files so a reset
    is serialized with its scan lock and starts an immediate incremental scan.
    """
    import json
    from .retry_policy import RetryState

    if all_entries == (file_path is not None):
        raise click.ClickException("Specify exactly one of --all or --path")
    config = _retry_config(config_path)
    if file_path is not None:
        resolved = Path(file_path).expanduser().resolve()
        if (resolved.suffix.lower() not in {".pdf", ".pptx", ".md"} or not any(
            resolved.is_relative_to(Path(root).resolve()) for root in config.scan_roots
        )):
            raise click.ClickException("File is outside configured scan roots or unsupported")
        file_path = str(resolved)
    try:
        count = RetryState(config).clear(file_path=file_path, all_entries=all_entries)
    except (ValueError, OSError) as exc:
        raise click.ClickException("Retry state could not be reset") from exc
    click.echo(json.dumps({"reset": count, "scan_started": False, "retry_policy_applied": True}, sort_keys=True))


@main.command()
@click.option("--port", default=8080, help="Port for local server.")
@common_options
def serve(port: int, config_path: str | None, verbose: bool) -> None:
    """Start a local HTTP server for the viewer."""
    config = _resolve_config(config_path)
    from .server import run_server

    run_server(config.output_dir, port)


@main.command()
@click.option("--port", default=8080, show_default=True, help="Port for local server.")
@click.option("--log-dir", type=click.Path(file_okay=False, path_type=Path), default=None,
              help="Explicit agent log directory; defaults to installed user's log directory.")
@click.option(
    "--scan-interval",
    default=None,
    type=click.IntRange(min=0),
    help="Override the persisted refresh interval in seconds; 0 disables periodic refresh.",
)
@common_options
def agent(
    port: int,
    log_dir: Path | None,
    scan_interval: int | None,
    config_path: str | None,
    verbose: bool,
) -> None:
    """Run the per-user archive agent: refresh, build, serve, and rescan."""
    resolved_config_path = _resolve_config_path(config_path)
    config = load_config(resolved_config_path)
    if not config.scan_roots:
        raise click.ClickException(
            "No scan roots configured. Run 'pptviewer init-config --root <folder>' first."
        )

    from .agent import run_agent

    log_path = add_file_logging((log_dir if log_dir is not None else default_log_dir()) / "agent.log", verbose=verbose)
    logger.info("Agent log: %s", log_path)
    # A dev agent's background scanner, builder and /api/performance share
    # these isolated logs; the packaged process gets no new setting.
    from .perf_metrics import AGENT_LOG_DIR_OVERRIDE

    prior = os.environ.get(AGENT_LOG_DIR_OVERRIDE)
    if log_dir is not None:
        os.environ[AGENT_LOG_DIR_OVERRIDE] = str(log_dir.resolve())
    try:
        run_agent(
            config,
            config_path=resolved_config_path,
            port=port,
            scan_interval_seconds=scan_interval,
        )
    finally:
        if log_dir is not None:
            if prior is None:
                os.environ.pop(AGENT_LOG_DIR_OVERRIDE, None)
            else:
                os.environ[AGENT_LOG_DIR_OVERRIDE] = prior


@main.command()
@common_options
def clean(config_path: str | None, verbose: bool) -> None:
    """Remove orphaned assets and deleted deck records."""
    config = _resolve_config(config_path)
    from .index_db import IndexDB
    from .models import DeckStatus

    db = IndexDB(config.db_path)
    deleted = db._conn.execute(
        "SELECT deck_id FROM decks WHERE status = ?",
        (DeckStatus.DELETED.value,),
    ).fetchall()

    import shutil
    count = 0
    for row in deleted:
        deck_id = row["deck_id"]
        assets_dir = os.path.join(config.output_dir, "assets", "decks", deck_id)
        if os.path.isdir(assets_dir):
            shutil.rmtree(assets_dir, ignore_errors=True)
        db.purge_deck(deck_id)
        count += 1

    db.close()
    click.echo(f"Cleaned {count} deleted deck(s)")


@main.command()
@common_options
def rebuild(config_path: str | None, verbose: bool) -> None:
    """Full reprocess — scan all files and regenerate viewer."""
    config = _resolve_config(config_path)
    from .pipeline import run_scan
    from .builder import build_viewer

    summary = run_scan(config, force=True)
    build_viewer(config)
    click.echo(
        f"\nRebuild complete: "
        f"{summary['processed_ok']} processed OK, {summary['processed_err']} errors"
    )
