"""Finetune command for generating custom CodeQL queries."""

import asyncio
from pathlib import Path

import click

from patchsmith.cli.progress import (
    ProgressTracker,
    console,
    print_error,
    print_success,
)
from patchsmith.models.config import PatchsmithConfig
from patchsmith.services.query_finetune_service import QueryFinetuneService


@click.command()
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=False,
)
@click.option(
    "--focus",
    "-f",
    multiple=True,
    help="Specific security areas to target (e.g., 'SQL injection', 'authentication')",
)
@click.option(
    "--max-queries",
    "-n",
    type=int,
    default=5,
    help="Maximum number of queries to generate (default: 5)",
)
@click.option(
    "--languages",
    "-l",
    multiple=True,
    help="Target specific languages (auto-detect if not provided)",
)
def finetune(
    path: Path | None,
    focus: tuple[str, ...],
    max_queries: int,
    languages: tuple[str, ...],
) -> None:
    """Generate custom CodeQL queries tailored to your project.

    This command analyzes your project and generates custom security queries
    that target vulnerabilities specific to your technology stack, frameworks,
    and architectural patterns.

    Generated queries are:
      • Validated through CodeQL compilation
      • Stored in .patchsmith/queries/<language>/
      • Automatically used in future analyses

    \b
    Examples:
        patchsmith finetune                              # Auto-detect and generate
        patchsmith finetune --focus "SQL injection"      # Focus on specific areas
        patchsmith finetune --max-queries 10             # Generate more queries
        patchsmith finetune --languages python           # Target specific language
        patchsmith finetune -f "auth" -f "XSS" -n 3      # Multiple focus areas
    """
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    console.print(f"\n[bold cyan]🔒 Patchsmith Query Finetuning[/bold cyan]")
    console.print(f"Project: [yellow]{path}[/yellow]")

    if focus:
        console.print(f"Focus areas: [yellow]{', '.join(focus)}[/yellow]")
    if languages:
        console.print(f"Target languages: [yellow]{', '.join(languages)}[/yellow]")

    console.print(f"Max queries: [yellow]{max_queries}[/yellow]\n")

    # Run query generation
    asyncio.run(
        _run_finetune(
            path,
            list(focus) if focus else None,
            max_queries,
            list(languages) if languages else None,
        )
    )


async def _run_finetune(
    path: Path,
    focus_areas: list[str] | None,
    max_queries: int,
    languages: list[str] | None,
) -> None:
    """
    Run the finetune workflow.

    Args:
        path: Path to project
        focus_areas: Optional focus areas
        max_queries: Maximum queries to generate
        languages: Optional target languages
    """
    try:
        # Create configuration
        config = PatchsmithConfig.create_default(
            project_root=path, project_name=path.name
        )

        # Create progress tracker
        with ProgressTracker() as tracker:
            # Create finetune service with progress tracking
            service = QueryFinetuneService(
                config=config,
                progress_callback=tracker.handle_progress,
                thinking_callback=tracker.update_thinking,
            )

            # Run query generation
            query_suite = await service.finetune_queries(
                project_path=path,
                focus_areas=focus_areas,
                max_queries=max_queries,
                languages=languages,
            )

        # Display results
        console.print()
        print_success("Query finetuning completed!")

        # Show summary
        console.print(f"\n[bold]Generated Queries:[/bold]")
        console.print(
            f"  • Total: [green]{len(query_suite.queries)}[/green] custom queries"
        )

        if query_suite.queries:
            # Group by language
            by_language: dict[str, int] = {}
            for q in query_suite.queries:
                by_language[q.language] = by_language.get(q.language, 0) + 1

            console.print(f"\n[bold]By Language:[/bold]")
            for lang, count in by_language.items():
                console.print(f"  • {lang}: [green]{count}[/green] queries")

            # Show query details
            console.print(f"\n[bold]Query Details:[/bold]")
            from rich.table import Table

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("ID", style="cyan")
            table.add_column("Language", style="yellow")
            table.add_column("Severity", style="magenta")
            table.add_column("Name")

            for q in query_suite.queries:
                severity_color = {
                    "critical": "red",
                    "high": "orange1",
                    "medium": "yellow",
                    "low": "blue",
                    "info": "cyan",
                }.get(q.severity.value, "white")

                table.add_row(
                    q.id,
                    q.language,
                    f"[{severity_color}]{q.severity.value.upper()}[/{severity_color}]",
                    q.name or "N/A",
                )

            console.print(table)

            # Show storage location
            console.print(f"\n[bold]Storage:[/bold]")
            console.print(
                f"  • Queries saved to: [cyan]{path}/.patchsmith/queries/[/cyan]"
            )
            console.print(
                f"  • Metadata: [cyan]{path}/.patchsmith/queries/metadata.json[/cyan]"
            )

            # Show next steps
            console.print(f"\n[bold cyan]Next Steps:[/bold cyan]")
            console.print(
                "  • Run analysis to use custom queries: [green]patchsmith analyze[/green]"
            )
            console.print(
                "  • Review generated queries: [green]ls .patchsmith/queries/[/green]"
            )
            console.print(
                "  • Edit queries manually if needed (they will still be used)"
            )
            console.print()
        else:
            console.print(
                "[yellow]⚠ No queries were successfully generated.[/yellow]"
            )
            console.print(
                "This might be due to compilation failures or unsupported languages."
            )
            console.print()

    except Exception as e:
        console.print()
        print_error(f"Query finetuning failed: {e}")
        if (
            click.get_current_context().obj.get("debug", False)
            if click.get_current_context().obj
            else False
        ):
            console.print_exception()
        raise click.Abort()
