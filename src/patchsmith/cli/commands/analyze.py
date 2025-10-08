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
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save analysis results to file (JSON format)"
)
def analyze(
    path: Path | None,
    triage: bool,
    output: Path | None,
) -> None:
    """Run complete security analysis on a project.

    \b
    Performs:
      • Language detection
      • CodeQL static analysis
      • AI-powered triage (prioritization)
      • Statistics computation

    \b
    For detailed analysis of specific findings, use:
      patchsmith investigate <finding-id>

    \b
    Examples:
        patchsmith analyze /path/to/project
        patchsmith analyze .                     # Analyze current directory
        patchsmith analyze --no-triage     # Skip triage step
        patchsmith analyze -o results.json # Save results to file
    """
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    console.print(f"\n[bold cyan]🔒 Patchsmith Security Analysis[/bold cyan]")
    console.print(f"Project: [yellow]{path}[/yellow]\n")

    # Run analysis
    asyncio.run(_run_analysis(path, triage, output))


async def _run_analysis(
    path: Path,
    perform_triage: bool,
    output_path: Path | None,
) -> None:
    """Run the analysis workflow.

    Args:
        path: Path to project
        perform_triage: Whether to perform triage
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

            # Run analysis (no detailed analysis in main flow)
            analysis_result, triage_results, _ = await service.analyze_project(
                project_path=path,
                perform_triage=perform_triage,
                perform_detailed_analysis=False,  # Detailed analysis moved to 'investigate' command
                detailed_analysis_limit=0,
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
            detailed_count=0,  # No detailed analysis in main flow
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
            if triage_results and any(t.recommended_for_analysis for t in triage_results):
                top_finding = next(t for t in triage_results if t.recommended_for_analysis)
                console.print(f"  • Investigate top priority: [green]patchsmith investigate {top_finding.finding_id}[/green]")
                console.print(f"  • Fix top priority: [green]patchsmith fix {top_finding.finding_id}[/green]")
            console.print("  • Generate detailed report: [green]patchsmith report[/green]")
            console.print()
        else:
            console.print("[green]✓ No security vulnerabilities found![/green]\n")

        # Always save results for investigate/list commands
        import json
        results_file = path / ".patchsmith_results.json"

        # Preserve existing detailed assessments from previous investigations
        existing_assessments = {}
        if results_file.exists():
            try:
                with open(results_file) as f:
                    existing_data = json.load(f)
                    existing_assessments = existing_data.get("detailed_assessments", {})
            except Exception:
                # If we can't read existing file, start fresh
                pass

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
            # Preserve existing detailed assessments from previous 'investigate' commands
            "detailed_assessments": existing_assessments,
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
