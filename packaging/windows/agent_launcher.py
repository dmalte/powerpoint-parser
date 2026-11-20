"""Windowless entry point for the frozen per-user Windows agent."""

import sys

from ppt_visual_archive.cli import main


if __name__ == "__main__":
    # No args: normal installed 8080 agent. Flags: isolated GUI smoke port/config.
    main(args=["agent", *sys.argv[1:]])
