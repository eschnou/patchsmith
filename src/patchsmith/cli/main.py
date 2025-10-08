"""Main CLI entry point for Patchsmith."""

import click

from patchsmith import __version__

# Import command modules
from patchsmith.cli.commands import analyze, fix, init, report


@click.group()
@click.version_option(version=__version__, prog_name="patchsmith")
@click.help_option("-h", "--help")
def cli() -> None:
    """🔒 Patchsmith - AI-powered security vulnerability detection and fixing.

    Patchsmith combines CodeQL static analysis with Claude AI to detect,
    triage, and automatically fix security vulnerabilities in your codebase.

    \b
    Quick Start:
        patchsmith analyze /path/to/project    # Run security analysis
        patchsmith report                      # Generate detailed report
        patchsmith fix <finding-id>            # Fix a specific vulnerability

    \b
    Documentation: https://github.com/patchsmith/patchsmith
    """
    pass


# Register commands
cli.add_command(analyze.analyze)
cli.add_command(report.report)
cli.add_command(fix.fix)
cli.add_command(init.init)


if __name__ == "__main__":
    cli()
