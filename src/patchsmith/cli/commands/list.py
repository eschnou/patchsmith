"""List command for displaying all findings from the last analysis."""

import json
from pathlib import Path

import click
from rich.table import Table

from patchsmith.cli.progress import console, print_error


@click.command(name="list")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project path (default: current directory)",
)
@click.option(
    "--severity",
    "-s",
    type=click.Choice(["critical", "high", "medium", "low", "info"], case_sensitive=False),
    help="Filter by minimum severity",
)
@click.option(
    "--limit",
    "-l",
    type=int,
    default=None,
    help="Limit number of results",
)
def list_findings(path: Path | None, severity: str | None, limit: int | None) -> None:
    """List all security findings from the last analysis.

    \b
    Displays all findings in order of priority based on triage results.

    \b
    Examples:
        patchsmith list                    # List all findings
        patchsmith list --severity high    # List only high+ findings
        patchsmith list --limit 20         # List top 20 findings
        patchsmith list -s medium -l 10    # Top 10 medium+ findings
    """
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    # Load analysis results
    results_file = path / ".patchsmith_results.json"
    if not results_file.exists():
        print_error(
            "No analysis results found. Run 'patchsmith analyze' first."
        )
        raise click.Abort()

    with open(results_file) as f:
        data = json.load(f)

    findings = data.get("findings", [])
    triage_results = data.get("triage_results", [])

    if not findings:
        console.print("[green]No findings in last analysis[/green]")
        return

    # Filter by severity if specified
    if severity:
        severity_order = ["critical", "high", "medium", "low", "info"]
        min_severity_index = severity_order.index(severity.lower())
        findings = [
            f
            for f in findings
            if severity_order.index(f["severity"]) <= min_severity_index
        ]

    # Sort by triage priority if available
    if triage_results:
        # Create a mapping of finding_id to priority_score
        priority_map = {t["finding_id"]: t["priority_score"] for t in triage_results}
        findings.sort(
            key=lambda f: priority_map.get(f["id"], 0.0), reverse=True
        )
    else:
        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        findings.sort(key=lambda f: severity_order.get(f["severity"], 99))

    # Apply limit
    if limit:
        findings = findings[:limit]

    # Display table
    console.print()
    console.print(f"[bold cyan]Security Findings[/bold cyan] ({len(findings)} shown)")
    console.print()

    table = Table(show_lines=True)
    table.add_column("ID", style="cyan bold", width=8)
    table.add_column("Priority", style="magenta", width=10)
    table.add_column("Severity", style="bold", width=10)
    table.add_column("Rule", style="yellow", width=35)
    table.add_column("Location", style="green", width=45)

    for finding in findings:
        # Get priority score from triage
        priority_score = 0.0
        if triage_results:
            triage = next(
                (t for t in triage_results if t["finding_id"] == finding["id"]), None
            )
            if triage:
                priority_score = triage["priority_score"]

        # Color priority score
        if priority_score >= 8.0:
            priority_color = "red"
        elif priority_score >= 6.0:
            priority_color = "yellow"
        elif priority_score >= 4.0:
            priority_color = "blue"
        else:
            priority_color = "dim"

        # Color severity
        severity_color = {
            "critical": "red",
            "high": "yellow",
            "medium": "blue",
            "low": "dim",
            "info": "dim",
        }.get(finding["severity"], "white")

        table.add_row(
            finding["id"],
            f"[{priority_color}]{priority_score:.1f}[/{priority_color}]"
            if priority_score > 0
            else "-",
            f"[{severity_color}]{finding['severity'].upper()}[/{severity_color}]",
            finding["rule_id"][:35],
            f"{Path(finding['file_path']).name}:{finding['start_line']}",
        )

    console.print(table)
    console.print()

    # Show next steps
    console.print("[bold cyan]Next Steps:[/bold cyan]")
    if findings:
        top_id = findings[0]["id"]
        console.print(
            f"  • Investigate top finding: [green]patchsmith investigate {top_id}[/green]"
        )
        console.print(
            f"  • Fix top finding: [green]patchsmith fix {top_id}[/green]"
        )
    console.print("  • Generate detailed report: [green]patchsmith report[/green]")
    console.print()
