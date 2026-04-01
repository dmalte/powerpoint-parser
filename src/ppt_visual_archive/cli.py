"""CLI entry point."""

from __future__ import annotations

import os
import sys
from functools import wraps
from pathlib import Path

import click

from .config import AppConfig, load_config
from .utils import logger, setup_logging


def _resolve_config(config_path: str | None) -> AppConfig:
    """Load config from explicit path, or search default locations."""
    if config_path:
        return load_config(config_path)

    # Search order: ./config.yaml, ./config/config.yaml
    candidates = [
        Path("config.yaml"),
        Path("config") / "config.yaml",
    ]
    for c in candidates:
        if c.exists():
            click.echo(f"Using config: {c.resolve()}")
            return load_config(c)

    click.echo("No config file found. Use --config or create config.yaml", err=True)
    sys.exit(1)


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
