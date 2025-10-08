"""Main CLI entry point for Patchsmith."""

import click

from patchsmith import __version__
from patchsmith.utils.logging import setup_logging

# Import command modules
from patchsmith.cli.commands import (
    analyze,
    clean,
    completion,
    fix,
    init,
    investigate,
    list,
    report,
)


@click.group()
@click.version_option(version=__version__, prog_name="patchsmith")
@click.help_option("-h", "--help")
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging (shows all logs)",
)
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """🔒 Patchsmith - AI-powered security vulnerability detection and fixing.

    Patchsmith combines CodeQL static analysis with Claude AI to detect,
    triage, and automatically fix security vulnerabilities in your codebase.

    \b
    Quick Start:
        patchsmith analyze /path/to/project    # Run security analysis (or: psmith analyze)
        patchsmith list                        # List all findings
        patchsmith investigate <finding-id>    # Deep analysis of a finding
        patchsmith fix <finding-id>            # Fix a specific vulnerability
        patchsmith report                      # Generate detailed report
        patchsmith clean                       # Clean cached results

    \b
    Shell Completion:
        patchsmith completion bash       # Install bash completion
        patchsmith completion zsh        # Install zsh completion

    \b
    Short alias: Use 'psmith' instead of 'patchsmith' (e.g., psmith analyze)

    \b
    Documentation: https://github.com/patchsmith/patchsmith
    """
    # Setup logging based on debug flag
    setup_logging(verbose=debug)

    # Store debug flag in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


# Register commands
cli.add_command(analyze.analyze)
cli.add_command(list.list_findings)
cli.add_command(investigate.investigate)
cli.add_command(report.report)
cli.add_command(fix.fix)
cli.add_command(init.init)
cli.add_command(clean.clean)
cli.add_command(completion.completion)


if __name__ == "__main__":
    cli()
