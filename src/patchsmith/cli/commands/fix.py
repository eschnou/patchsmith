"""Fix command for generating and applying security fixes."""

import asyncio
import json
from pathlib import Path

import click

from patchsmith.cli.progress import (
    ProgressTracker,
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from patchsmith.models.config import PatchsmithConfig
from patchsmith.models.finding import CWE, Finding, Severity
from patchsmith.services.analysis_service import AnalysisService
from patchsmith.services.fix_service import FixService


@click.command()
@click.argument("finding_id", required=True)
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project path (default: current directory)"
)
@click.option(
    "--with-pr",
    is_flag=True,
    help="Commit changes, push branch, and create PR (for CI/CD automation)"
)
def fix(
    finding_id: str,
    path: Path | None,
    with_pr: bool,
) -> None:
    """Autonomously fix a security vulnerability.

    \b
    Process:
      1. Creates a Git branch (fix/<finding-id>)
      2. Launches AI agent with Write access
      3. Agent examines code and writes fix
      4. Leaves changes uncommitted (default)
      5. With --with-pr: commits, pushes, and creates PR

    \b
    Examples:
        patchsmith fix F-1                     # Fix locally (no commit/PR)
        patchsmith fix F-1 --with-pr           # Fix, commit, push, create PR
        patchsmith fix F-5 --path /path        # Fix in specific project
    """
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    console.print(f"\n[bold cyan]🤖 Patchsmith Autonomous Fix[/bold cyan]")
    console.print(f"Project: [yellow]{path}[/yellow]")
    console.print(f"Finding: [yellow]{finding_id}[/yellow]")
    if with_pr:
        console.print(f"[green]Mode: Commit + Push + PR (CI/CD)[/green]")
    else:
        console.print(f"[yellow]Mode: Local fix only (no commit)[/yellow]")
    console.print()

    # Run autonomous fix
    asyncio.run(_autonomous_fix(path, finding_id, with_pr))


async def _autonomous_fix(path: Path, finding_id: str, with_pr: bool) -> None:
    """Run autonomous fix workflow.

    Args:
        path: Project path
        finding_id: Finding ID to fix
        with_pr: If True, commit changes, push branch, and create PR
    """
    try:
        # Load finding from cache
        results_file = path / ".patchsmith" / "results.json"
        if not results_file.exists():
            print_error("No cached analysis results found")
            print_info("Run 'patchsmith analyze' first to analyze the project")
            raise click.Abort()

        print_info(f"Loading finding: {finding_id}")

        with open(results_file) as f:
            data = json.load(f)

        # Find the specific finding
        finding_dict = next((f for f in data.get("findings", []) if f["id"] == finding_id), None)
        if not finding_dict:
            print_error(f"Finding {finding_id} not found in cached results")
            print_info("Available findings:")
            for f in data.get("findings", [])[:10]:
                console.print(f"  • {f['id']}: {f['rule_id']}")
            if len(data.get("findings", [])) > 10:
                console.print(f"  ... and {len(data['findings']) - 10} more")
            print_info("\nTip: Run 'patchsmith list' to see all findings")
            raise click.Abort()

        # Reconstruct Finding object
        finding = Finding(
            id=finding_dict["id"],
            rule_id=finding_dict["rule_id"],
            severity=Severity(finding_dict["severity"]),
            cwe=CWE(id=finding_dict["cwe"]["id"]) if finding_dict.get("cwe") else None,
            file_path=Path(finding_dict["file_path"]),
            start_line=finding_dict["start_line"],
            end_line=finding_dict.get("end_line", finding_dict["start_line"]),
            message=finding_dict["message"],
            snippet=finding_dict.get("snippet"),
        )

        # Show finding details
        console.print()
        console.print(f"[bold]Finding:[/bold] {finding.id}")
        console.print(f"[bold]Rule:[/bold] {finding.rule_id}")
        console.print(f"[bold]Severity:[/bold] {finding.severity.value.upper()}")
        console.print(f"[bold]Location:[/bold] {finding.file_path}:{finding.start_line}")
        console.print(f"[bold]Message:[/bold] {finding.message}")
        console.print()

        # Create configuration
        config = PatchsmithConfig.create_default(
            project_root=path,
            project_name=path.name
        )

        # Run autonomous fix with progress tracking
        print_info("Launching autonomous fix agent...\n")

        with ProgressTracker() as tracker:
            fix_service = FixService(
                config=config,
                progress_callback=tracker.handle_progress,
                thinking_callback=tracker.update_thinking,
            )

            result, message = await fix_service.autonomous_fix(
                finding=finding,
                working_dir=path,
                commit_and_pr=with_pr,
            )

        console.print()

        if result and result.success:
            print_success("✓ Autonomous fix completed!\n")
            console.print(f"[bold]Description:[/bold] {result.description}")
            console.print(f"[bold]Confidence:[/bold] {result.confidence:.0%}")
            console.print(f"[bold]Files Modified:[/bold] {len(result.files_modified)}")
            for file in result.files_modified:
                console.print(f"  • {file}")
            console.print()
            console.print(f"[bold green]🔗 {message}[/bold green]")
            console.print()
        else:
            print_error("Autonomous fix failed")
            console.print(f"\n{message}\n")
            raise click.Abort()

    except Exception as e:
        console.print()
        print_error(f"Fix failed: {e}")
        if click.get_current_context().obj and click.get_current_context().obj.get("debug", False):
            console.print_exception()
        raise click.Abort()
