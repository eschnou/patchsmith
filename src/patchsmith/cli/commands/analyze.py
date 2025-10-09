"""Analyze command for running security analysis."""

import asyncio
from pathlib import Path

import click

from patchsmith.cli.progress import (
    ProgressTracker,
    console,
    print_analysis_summary,
    print_error,
    print_findings_table,
    print_success,
)
from patchsmith.models.config import PatchsmithConfig
from patchsmith.services.analysis_service import AnalysisService


@click.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path), required=False)
@click.option(
    "--investigate",
    is_flag=True,
    default=False,
    help="Run triage and investigate recommended findings with AI"
)
@click.option(
    "--investigate-all",
    is_flag=True,
    default=False,
    help="Investigate ALL findings with AI (skip triage)"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save analysis results to file (JSON format)"
)
@click.option(
    "--custom-only",
    is_flag=True,
    default=False,
    help="Run only custom queries (skip standard CodeQL queries)"
)
def analyze(
    path: Path | None,
    investigate: bool,
    investigate_all: bool,
    output: Path | None,
    custom_only: bool,
) -> None:
    """Run security analysis on a project.

    \b
    Analysis Modes:
      • Default: CodeQL analysis only (fast, no AI)
      • --investigate: Triage + investigate recommended findings (AI-powered)
      • --investigate-all: Investigate ALL findings (AI-powered, thorough)

    \b
    Examples:
        patchsmith analyze                        # Quick CodeQL scan
        patchsmith analyze --investigate          # Triage + investigate top findings
        patchsmith analyze --investigate-all      # Deep analysis of all findings
        patchsmith analyze --custom-only          # Run only custom queries
        patchsmith analyze -o results.json        # Save results to file
    """
    # Validate mutually exclusive flags
    if investigate and investigate_all:
        print_error("Cannot use both --investigate and --investigate-all")
        raise click.Abort()
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    console.print(f"\n[bold cyan]🔒 Patchsmith Security Analysis[/bold cyan]")
    console.print(f"Project: [yellow]{path}[/yellow]")

    # Show mode
    if investigate_all:
        console.print(f"Mode: [yellow]Investigate all findings (AI)[/yellow]")
    elif investigate:
        console.print(f"Mode: [yellow]Triage + investigate recommended (AI)[/yellow]")
    else:
        console.print(f"Mode: [yellow]Quick scan (CodeQL only)[/yellow]")

    if custom_only:
        console.print(f"Queries: [yellow]Custom only[/yellow]")
    console.print()

    # Run analysis
    asyncio.run(_run_analysis(path, investigate, investigate_all, output, custom_only))


async def _run_analysis(
    path: Path,
    investigate: bool,
    investigate_all: bool,
    output_path: Path | None,
    custom_only: bool = False,
) -> None:
    """Run the analysis workflow.

    Args:
        path: Path to project
        investigate: Whether to triage and investigate recommended findings
        investigate_all: Whether to investigate all findings (skip triage)
        output_path: Optional path to save results
        custom_only: Whether to run only custom queries
    """
    try:
        # Create configuration
        config = PatchsmithConfig.create_default(
            project_root=path,
            project_name=path.name
        )

        # Determine analysis parameters based on flags
        perform_triage = investigate  # Triage only when --investigate
        perform_detailed_analysis = investigate or investigate_all
        detailed_analysis_limit = None  # Analyze all that match criteria

        # Create progress tracker
        with ProgressTracker() as tracker:
            # Create analysis service with progress tracking and thinking display
            service = AnalysisService(
                config=config,
                progress_callback=tracker.handle_progress,
                thinking_callback=tracker.update_thinking,
            )

            # Run analysis with appropriate flags
            analysis_result, triage_results, detailed_assessments = await service.analyze_project(
                project_path=path,
                perform_triage=perform_triage,
                perform_detailed_analysis=perform_detailed_analysis,
                detailed_analysis_limit=detailed_analysis_limit,
                custom_only=custom_only,
            )

        # Display results
        console.print()
        print_success("Analysis completed!")

        # Show summary
        print_analysis_summary(
            finding_count=len(analysis_result.findings),
            languages=analysis_result.languages_analyzed,
            critical_count=analysis_result.statistics.get_critical_count(),
            high_count=analysis_result.statistics.get_high_count(),
            triage_count=len(triage_results) if triage_results else 0,
            detailed_count=len(detailed_assessments) if detailed_assessments else 0,
        )

        # Show top findings
        if analysis_result.findings:
            # Sort by severity
            sorted_findings = sorted(
                analysis_result.findings,
                key=lambda f: ["critical", "high", "medium", "low", "info"].index(f.severity.value),
            )
            print_findings_table(sorted_findings, limit=10)

            # Show next steps
            console.print("[bold cyan]Next Steps:[/bold cyan]")
            console.print("  • List all findings: [green]patchsmith list[/green]")

            # Suggest next steps based on what was done
            if detailed_assessments:
                # Already investigated, suggest report or fix
                console.print("  • Generate detailed report: [green]patchsmith report[/green]")
                if analysis_result.findings:
                    first_finding = analysis_result.findings[0]
                    console.print(f"  • Fix finding: [green]patchsmith fix {first_finding.id}[/green]")
            elif triage_results and any(t.recommended_for_analysis for t in triage_results):
                # Triaged but not investigated, suggest investigation
                top_finding = next(t for t in triage_results if t.recommended_for_analysis)
                console.print(f"  • Investigate top priority: [green]patchsmith investigate {top_finding.finding_id}[/green]")
                console.print(f"  • Fix top priority: [green]patchsmith fix {top_finding.finding_id}[/green]")
                console.print("  • Or re-run with: [green]patchsmith analyze --investigate[/green]")
            else:
                # Quick scan only, suggest investigation
                console.print("  • Investigate findings: [green]patchsmith analyze --investigate[/green]")
                console.print("  • Or investigate specific: [green]patchsmith investigate <finding-id>[/green]")
                console.print("  • Generate report: [green]patchsmith report[/green]")

            console.print()
        else:
            console.print("[green]✓ No security vulnerabilities found![/green]\n")

        # Always save results for investigate/list commands
        import json
        patchsmith_dir = path / ".patchsmith"
        patchsmith_dir.mkdir(exist_ok=True)
        results_file = patchsmith_dir / "results.json"

        # Merge detailed assessments: preserve existing + add new from this run
        all_assessments = {}
        if results_file.exists():
            try:
                with open(results_file) as f:
                    existing_data = json.load(f)
                    all_assessments = existing_data.get("detailed_assessments", {})
            except Exception:
                # If we can't read existing file, start fresh
                pass

        # Add new detailed assessments from this run
        if detailed_assessments:
            for finding_id, assessment in detailed_assessments.items():
                all_assessments[finding_id] = {
                    "is_false_positive": assessment.is_false_positive,
                    "false_positive_score": assessment.false_positive_score,
                    "false_positive_reasoning": assessment.false_positive_reasoning,
                    "attack_scenario": assessment.attack_scenario,
                    "risk_type": assessment.risk_type,
                    "exploitability_score": assessment.exploitability_score,
                    "impact_description": assessment.impact_description,
                    "remediation_priority": assessment.remediation_priority,
                }

        output_data = {
            "project_name": analysis_result.project_name,
            "timestamp": analysis_result.timestamp.isoformat(),
            "languages": analysis_result.languages_analyzed,
            "total_findings": len(analysis_result.findings),
            "statistics": {
                "critical": analysis_result.statistics.get_critical_count(),
                "high": analysis_result.statistics.get_high_count(),
                "actionable": analysis_result.statistics.get_actionable_count(),
            },
            "triage_results": [
                {
                    "finding_id": t.finding_id,
                    "priority_score": t.priority_score,
                    "recommended_for_analysis": t.recommended_for_analysis,
                    "reasoning": t.reasoning,
                }
                for t in (triage_results or [])
            ],
            "findings": [
                {
                    "id": f.id,
                    "rule_id": f.rule_id,
                    "severity": f.severity.value,
                    "message": f.message,
                    "file_path": str(f.file_path),
                    "start_line": f.start_line,
                    "end_line": f.end_line,
                    "cwe": {"id": f.cwe.id} if f.cwe else None,
                    "snippet": f.snippet,
                }
                for f in analysis_result.findings
            ],
            # Include all detailed assessments (existing + new from this run)
            "detailed_assessments": all_assessments,
        }

        # Save to project directory (always)
        results_file.write_text(json.dumps(output_data, indent=2))

        # Also save to custom output path if specified
        if output_path:
            output_path.write_text(json.dumps(output_data, indent=2))
            print_success(f"Results also saved to {output_path}")

    except Exception as e:
        console.print()
        print_error(f"Analysis failed: {e}")
        import traceback
        if click.get_current_context().obj.get("debug", False) if click.get_current_context().obj else False:
            console.print_exception()
        raise click.Abort()
