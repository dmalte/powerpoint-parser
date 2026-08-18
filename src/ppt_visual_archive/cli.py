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


def _resolve_config(config_path: str | None) -> AppConfig:
    """Load config from explicit path, or search default locations."""
    if config_path:
        return load_config(config_path)

    for c in _config_candidates():
        if c.exists():
            click.echo(f"Using config: {c.resolve()}")
            return load_config(c)

    click.echo(
        f"No config file found. Use --config or run 'pptviewer init-config'. "
        f"Default installed location: {default_config_path()}",
        err=True,
    )
    sys.exit(1)


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
    click.echo(f"Viewer built → {os.path.join(config.output_dir, 'index.html')}")


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
@click.option(
    "--scan-interval",
    default=1800,
    show_default=True,
    type=click.IntRange(min=0),
    help="Seconds between incremental refreshes; 0 disables periodic refresh.",
)
@common_options
def agent(
    port: int,
    scan_interval: int,
    config_path: str | None,
    verbose: bool,
) -> None:
    """Run the per-user archive agent: refresh, build, serve, and rescan."""
    config = _resolve_config(config_path)
    if not config.scan_roots:
        raise click.ClickException(
            "No scan roots configured. Run 'pptviewer init-config --root <folder>' first."
        )

    from .agent import run_agent

    log_path = add_file_logging(default_log_dir() / "agent.log", verbose=verbose)
    logger.info("Agent log: %s", log_path)
    run_agent(config, port=port, scan_interval_seconds=scan_interval)


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
