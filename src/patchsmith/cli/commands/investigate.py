"""Investigate command for detailed security analysis of specific findings."""

import asyncio
import json
from pathlib import Path

import click

from patchsmith.adapters.claude.detailed_security_analysis_agent import (
    DetailedSecurityAnalysisAgent,
)
from patchsmith.cli.progress import (
    ProgressTracker,
    console,
    print_error,
    print_success,
)
from patchsmith.models.config import PatchsmithConfig
from patchsmith.models.finding import Finding
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table


@click.command()
@click.argument("finding_id", required=True)
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project path (default: current directory)",
)
def investigate(finding_id: str, path: Path | None) -> None:
    """Perform detailed security analysis on a specific finding.

    \b
    This provides comprehensive analysis including:
      • False positive assessment
      • Attack scenario description
      • Risk classification
      • Exploitability analysis
      • Impact assessment
      • Remediation prioritization

    \b
    Examples:
        patchsmith investigate F-1
        patchsmith investigate F-5 --path /path/to/project
    """
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    console.print(f"\n[bold cyan]🔍 Investigating Finding: {finding_id}[/bold cyan]\n")

    try:
        # Run async investigation
        asyncio.run(_run_investigation(finding_id, path))
    except KeyboardInterrupt:
        console.print("\n[yellow]Investigation interrupted by user[/yellow]")
    except Exception as e:
        print_error(f"Investigation failed: {e}")
        raise click.Abort()


async def _run_investigation(finding_id: str, project_path: Path) -> None:
    """Run the investigation workflow.

    Args:
        finding_id: ID of the finding to investigate
        project_path: Path to project
    """
    # Load previous analysis results
    results_file = project_path / ".patchsmith" / "results.json"
    if not results_file.exists():
        print_error(
            f"No analysis results found. Run 'patchsmith analyze' first."
        )
        raise click.Abort()

    # Load findings
    with open(results_file) as f:
        data = json.load(f)
        findings_data = data.get("findings", [])

    # Find the specific finding
    finding_dict = next((f for f in findings_data if f["id"] == finding_id), None)
    if not finding_dict:
        print_error(f"Finding {finding_id} not found in analysis results")
        console.print(f"\nAvailable findings: {', '.join(f['id'] for f in findings_data[:10])}")
        if len(findings_data) > 10:
            console.print(f"... and {len(findings_data) - 10} more")
        console.print("\nTip: Run [green]patchsmith list[/green] to see all findings")
        raise click.Abort()

    # Reconstruct Finding object
    from patchsmith.models.finding import CWE, Severity

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

    console.print(f"[bold]Finding:[/bold] {finding.id}")
    console.print(f"[bold]Rule:[/bold] {finding.rule_id}")
    console.print(f"[bold]Severity:[/bold] {finding.severity.value.upper()}")
    console.print(f"[bold]Location:[/bold] {finding.file_path}:{finding.start_line}")
    console.print()

    # Create configuration
    config = PatchsmithConfig.create_default(
        project_root=project_path, project_name=project_path.name
    )

    # Run detailed analysis with progress tracking
    console.print("[bold cyan]Running detailed security analysis...[/bold cyan]\n")

    with ProgressTracker() as tracker:
        # Create agent progress callback
        def agent_progress_callback(current_turn: int, max_turns: int):
            tracker.handle_progress(
                "agent_turn_progress",
                {
                    "current_turn": current_turn,
                    "max_turns": max_turns,
                },
            )

        analysis_agent = DetailedSecurityAnalysisAgent(
            working_dir=project_path,
            thinking_callback=tracker.update_thinking,
            progress_callback=agent_progress_callback,
        )
        result = await analysis_agent.execute([finding])

        # Clear thinking display when agent completes
        tracker.update_thinking("")

    if not result or finding.id not in result:
        print_error("Failed to generate detailed analysis")
        raise click.Abort()

    assessment = result[finding.id]

    # Save assessment back to cache for future report generation
    _save_assessment_to_cache(project_path, finding.id, assessment)

    # Display results
    console.print()
    print_success("Detailed analysis completed!\n")

    # False Positive Assessment
    fp_color = "red" if not assessment.is_false_positive else "green"
    console.print(
        Panel(
            f"[{fp_color} bold]{'FALSE POSITIVE' if assessment.is_false_positive else 'VALID SECURITY ISSUE'}[/{fp_color} bold]\n\n"
            f"{assessment.false_positive_reasoning}",
            title="False Positive Assessment",
            border_style=fp_color,
        )
    )
    console.print()

    # Attack Scenario
    if not assessment.is_false_positive:
        console.print(
            Panel(
                assessment.attack_scenario,
                title="Attack Scenario",
                border_style="yellow",
            )
        )
        console.print()

        # Risk Analysis Table
        risk_table = Table(title="Risk Analysis", show_header=False, box=None)
        risk_table.add_column("Metric", style="cyan", width=25)
        risk_table.add_column("Value", style="white")

        risk_table.add_row("Risk Type", assessment.risk_type)
        risk_table.add_row(
            "Exploitability",
            f"{assessment.exploitability_score:.1%} - {'[red]High[/red]' if assessment.exploitability_score >= 0.7 else '[yellow]Medium[/yellow]' if assessment.exploitability_score >= 0.4 else '[green]Low[/green]'}",
        )
        risk_table.add_row(
            "Impact",
            assessment.impact_description,
        )
        risk_table.add_row(
            "Remediation Priority",
            f"[{'red' if assessment.remediation_priority == 'immediate' else 'yellow' if assessment.remediation_priority == 'high' else 'blue'}]{assessment.remediation_priority.upper()}[/]",
        )

        console.print(risk_table)
        console.print()

    # Next Steps
    console.print("[bold cyan]Next Steps:[/bold cyan]")
    if not assessment.is_false_positive:
        console.print(f"  • Fix this issue: [green]patchsmith fix {finding.id}[/green]")
        console.print("  • View all findings: [green]patchsmith list[/green]")
    else:
        console.print(
            f"  • This appears to be a false positive. Consider excluding it from reports."
        )
    console.print()


def _save_assessment_to_cache(
    project_path: Path, finding_id: str, assessment: "DetailedSecurityAssessment"
) -> None:
    """Save detailed assessment back to cache for future report generation.

    Args:
        project_path: Path to project
        finding_id: ID of the finding
        assessment: Detailed security assessment to save
    """
    results_file = project_path / ".patchsmith" / "results.json"
    if not results_file.exists():
        return

    # Load existing data
    with open(results_file) as f:
        data = json.load(f)

    # Update or add detailed assessments
    if "detailed_assessments" not in data:
        data["detailed_assessments"] = {}

    data["detailed_assessments"][finding_id] = {
        "is_false_positive": assessment.is_false_positive,
        "false_positive_score": assessment.false_positive_score,
        "false_positive_reasoning": assessment.false_positive_reasoning,
        "attack_scenario": assessment.attack_scenario,
        "risk_type": assessment.risk_type,
        "exploitability_score": assessment.exploitability_score,
        "impact_description": assessment.impact_description,
        "remediation_priority": assessment.remediation_priority,
    }

    # Save back to file
    results_file.write_text(json.dumps(data, indent=2))
