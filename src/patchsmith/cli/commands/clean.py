"""Clean command for removing cached results and databases."""

import shutil
from pathlib import Path

import click

from patchsmith.cli.progress import console, print_error, print_info, print_success


@click.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project path (default: current directory)",
)
@click.option(
    "--hard",
    is_flag=True,
    help="Also delete CodeQL database (requires re-analysis)",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompts",
)
def clean(path: Path | None, hard: bool, yes: bool) -> None:
    """Clean cached analysis results and reports.

    \b
    By default, removes:
      • .patchsmith/results.json (cached analysis data)
      • .patchsmith/reports/ (generated reports)

    \b
    With --hard flag, also removes:
      • CodeQL database (requires full re-analysis)

    \b
    Examples:
        patchsmith clean                 # Clean reports and cache
        patchsmith clean --hard          # Clean everything including CodeQL DB
        patchsmith clean --yes           # Skip confirmation
        patchsmith clean -p /path/to/project
    """
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    console.print(f"\n[bold cyan]🧹 Patchsmith Clean[/bold cyan]")
    console.print(f"Project: [yellow]{path}[/yellow]\n")

    # Identify items to clean
    items_to_clean = []

    results_file = path / ".patchsmith" / "results.json"
    if results_file.exists():
        items_to_clean.append(("Cached results", results_file, "file"))

    reports_dir = path / ".patchsmith" / "reports"
    if reports_dir.exists():
        items_to_clean.append(("Reports directory", reports_dir, "dir"))

    if hard:
        # Look for .patchsmith directory (contains CodeQL database and SARIF results)
        patchsmith_dir = path / ".patchsmith"
        if patchsmith_dir.exists():
            items_to_clean.append(("Patchsmith data directory (.patchsmith/)", patchsmith_dir, "dir"))

    # Check if there's anything to clean
    if not items_to_clean:
        print_info("Nothing to clean - workspace is already clean")
        console.print()
        return

    # Show what will be deleted
    console.print("[bold]Items to be deleted:[/bold]")
    for name, item_path, _ in items_to_clean:
        console.print(f"  • {name}: [yellow]{item_path}[/yellow]")
    console.print()

    # Confirm deletion
    if not yes:
        if hard:
            print_info("[yellow]Warning:[/yellow] Using --hard will delete the CodeQL database")
            print_info("This will require a full re-analysis (5-10 minutes)")
            console.print()

        confirmed = click.confirm("Proceed with deletion?", default=False)
        if not confirmed:
            print_info("Cancelled - no files were deleted")
            console.print()
            return

    # Perform deletion
    deleted_count = 0
    for name, item_path, item_type in items_to_clean:
        try:
            if item_type == "file":
                item_path.unlink()
            else:  # dir
                shutil.rmtree(item_path)
            console.print(f"  [green]✓[/green] Deleted {name}")
            deleted_count += 1
        except Exception as e:
            print_error(f"Failed to delete {name}: {e}")

    console.print()
    if deleted_count == len(items_to_clean):
        print_success(f"Successfully cleaned {deleted_count} item(s)")
    else:
        print_info(f"Cleaned {deleted_count}/{len(items_to_clean)} item(s)")

    # Show next steps
    if deleted_count > 0:
        console.print("\n[bold cyan]Next Steps:[/bold cyan]")
        console.print("  • Run [green]patchsmith analyze[/green] to re-analyze the project")
        console.print()
