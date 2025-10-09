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
from patchsmith.models.finding import DetailedSecurityAssessment, Finding
from patchsmith.presentation.formatters import BaseFormatter, CVEFormatter, MarkdownFormatter


@click.command()
@click.argument("finding_id", required=True)
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project path (default: current directory)",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["markdown", "cve"], case_sensitive=False),
    default="markdown",
    help="Output format (default: markdown)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save output to file instead of console",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force re-investigation even if cached",
)
def investigate(finding_id: str, path: Path | None, format: str, output: Path | None, force: bool) -> None:
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
    Uses cached investigation if available. Change output format without re-analyzing.

    \b
    Examples:
        patchsmith investigate F-1                 # Use cache if available
        patchsmith investigate F-1 --force         # Force re-investigation
        patchsmith investigate F-1 -f cve          # Switch format (uses cache)
        patchsmith investigate F-1 -f markdown -o finding.md
    """
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    console.print(f"\n[bold cyan]🔍 Investigating Finding: {finding_id}[/bold cyan]\n")

    try:
        # Run async investigation
        asyncio.run(_run_investigation(finding_id, path, format, output, force))
    except KeyboardInterrupt:
        console.print("\n[yellow]Investigation interrupted by user[/yellow]")
    except Exception as e:
        print_error(f"Investigation failed: {e}")
        raise click.Abort() from e


async def _run_investigation(
    finding_id: str, project_path: Path, format: str, output: Path | None, force: bool
) -> None:
    """Run the investigation workflow.

    Args:
        finding_id: ID of the finding to investigate
        project_path: Path to project
        format: Output format (markdown or cve)
        output: Optional output file path
        force: Force re-investigation even if cached
    """
    # Load previous analysis results
    results_file = project_path / ".patchsmith" / "results.json"
    if not results_file.exists():
        print_error(
            "No analysis results found. Run 'patchsmith analyze' first."
        )
        raise click.Abort()

    # Load findings and cached assessments
    with open(results_file) as f:
        data = json.load(f)
        findings_data = data.get("findings", [])
        cached_assessments = data.get("detailed_assessments", {})

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
        cwe=CWE(id=finding_dict["cwe"]["id"], name=None) if finding_dict.get("cwe") else None,
        file_path=Path(finding_dict["file_path"]),
        start_line=finding_dict["start_line"],
        end_line=finding_dict.get("end_line", finding_dict["start_line"]),
        message=finding_dict["message"],
        snippet=finding_dict.get("snippet"),
        false_positive_score=None,
    )

    console.print(f"[bold]Finding:[/bold] {finding.id}")
    console.print(f"[bold]Rule:[/bold] {finding.rule_id}")
    console.print(f"[bold]Severity:[/bold] {finding.severity.value.upper()}")
    console.print(f"[bold]Location:[/bold] {finding.file_path}:{finding.start_line}")
    console.print()

    # Check for cached assessment
    assessment = None
    if not force and finding_id in cached_assessments:
        # Use cached assessment
        print_success("Using cached investigation results")
        console.print("[dim]Tip: Use --force to re-investigate[/dim]\n")

        assessment_data = cached_assessments[finding_id]
        assessment = DetailedSecurityAssessment(
            finding_id=finding_id,
            is_false_positive=assessment_data["is_false_positive"],
            false_positive_score=assessment_data.get("false_positive_score", 0.0),
            false_positive_reasoning=assessment_data["false_positive_reasoning"],
            attack_scenario=assessment_data.get("attack_scenario", ""),
            risk_type=assessment_data.get("risk_type", "other"),
            exploitability_score=assessment_data.get("exploitability_score", 0.0),
            impact_description=assessment_data.get("impact_description", ""),
            remediation_priority=assessment_data.get("remediation_priority", "low"),
        )
    else:
        # Run detailed analysis with progress tracking
        if force:
            console.print("[bold cyan]Re-investigating (--force)...[/bold cyan]\n")
        else:
            console.print("[bold cyan]Running detailed security analysis...[/bold cyan]\n")

        with ProgressTracker() as tracker:
            # Create agent progress callback
            def agent_progress_callback(current_turn: int, max_turns: int) -> None:
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

    # Format results
    console.print()
    print_success("Detailed analysis completed!\n")

    # Select formatter based on format option
    formatter: BaseFormatter
    if format.lower() == "cve":
        formatter = CVEFormatter()
    else:
        formatter = MarkdownFormatter()

    # Generate formatted output
    formatted_output = formatter.format(finding, assessment)

    # Output to file or console
    if output:
        try:
            output.write_text(formatted_output)
            print_success(f"Report saved to: {output}")
        except Exception as e:
            print_error(f"Failed to write output file: {e}")
            raise click.Abort() from e
    else:
        # Display to console
        console.print(formatted_output)


def _save_assessment_to_cache(
    project_path: Path, finding_id: str, assessment: DetailedSecurityAssessment
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
