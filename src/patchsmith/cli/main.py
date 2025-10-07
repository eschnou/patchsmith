"""Main CLI entry point for Patchsmith."""

import click

from patchsmith import __version__


@click.group()
@click.version_option(version=__version__, prog_name="patchsmith")
def cli() -> None:
    """Patchsmith - AI-powered security vulnerability detection and fixing"""
    pass


if __name__ == "__main__":
    cli()
