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
    "--triage/--no-triage",
    default=True,
    help="Perform AI-powered triage to prioritize findings"
)
@click.option(
    "--detailed/--no-detailed",
    default=True,
    help="Perform detailed security analysis on top findings"
)
@click.option(
    "--detailed-limit",
    type=int,
    default=5,
    help="Maximum number of findings for detailed analysis"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save analysis results to file (JSON format)"
)
def analyze(
    path: Path | None,
    triage: bool,
    detailed: bool,
    detailed_limit: int,
    output: Path | None,
) -> None:
    """Run complete security analysis on a project.

    \b
    Performs:
      • Language detection
      • CodeQL static analysis
      • AI-powered triage (prioritization)
      • Detailed security assessment
      • Statistics computation

    \b
    Examples:
        patchsmith analyze /path/to/project
        patchsmith analyze .                     # Analyze current directory
        patchsmith analyze --no-triage           # Skip triage step
        patchsmith analyze --detailed-limit 10   # Analyze top 10 findings
        patchsmith analyze -o results.json       # Save results to file
    """
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    console.print(f"\n[bold cyan]🔒 Patchsmith Security Analysis[/bold cyan]")
    console.print(f"Project: [yellow]{path}[/yellow]\n")

    # Run analysis
    asyncio.run(_run_analysis(path, triage, detailed, detailed_limit, output))


async def _run_analysis(
    path: Path,
    perform_triage: bool,
    perform_detailed: bool,
    detailed_limit: int,
    output_path: Path | None,
) -> None:
    """Run the analysis workflow.

    Args:
        path: Path to project
        perform_triage: Whether to perform triage
        perform_detailed: Whether to perform detailed analysis
        detailed_limit: Max findings for detailed analysis
        output_path: Optional path to save results
    """
    try:
        # Create configuration
        config = PatchsmithConfig.create_default(
            project_root=path,
            project_name=path.name
        )

        # Create progress tracker
        with ProgressTracker() as tracker:
            # Create analysis service with progress tracking
            service = AnalysisService(
                config=config,
                progress_callback=tracker.handle_progress
            )

            # Run analysis
            analysis_result, triage_results, detailed_assessments = await service.analyze_project(
                project_path=path,
                perform_triage=perform_triage,
                perform_detailed_analysis=perform_detailed,
                detailed_analysis_limit=detailed_limit,
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
            console.print("  • Generate detailed report: [green]patchsmith report[/green]")
            if triage_results and any(t.recommended_for_analysis for t in triage_results):
                top_finding = next(t for t in triage_results if t.recommended_for_analysis)
                console.print(f"  • Fix top priority: [green]patchsmith fix {top_finding.finding_id}[/green]")
            console.print()
        else:
            console.print("[green]✓ No security vulnerabilities found![/green]\n")

        # Save results if requested
        if output_path:
            import json
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
                "findings": [
                    {
                        "id": f.id,
                        "rule_id": f.rule_id,
                        "severity": f.severity.value,
                        "message": f.message,
                        "file_path": str(f.file_path),
                        "start_line": f.start_line,
                        "end_line": f.end_line,
                    }
                    for f in analysis_result.findings
                ],
            }
            output_path.write_text(json.dumps(output_data, indent=2))
            print_success(f"Results saved to {output_path}")

    except Exception as e:
        console.print()
        print_error(f"Analysis failed: {e}")
        import traceback
        if click.get_current_context().obj.get("debug", False) if click.get_current_context().obj else False:
            console.print_exception()
        raise click.Abort()
