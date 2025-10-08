"""Report command for generating security reports."""

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
)
from patchsmith.models.analysis import AnalysisResult, AnalysisStatistics, TriageResult
from patchsmith.models.config import PatchsmithConfig
from patchsmith.models.finding import CWE, DetailedSecurityAssessment, Finding, Severity
from patchsmith.services.analysis_service import AnalysisService
from patchsmith.services.report_service import ReportService


@click.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path), required=False)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["markdown", "html", "text"], case_sensitive=False),
    default="markdown",
    help="Report format"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path (default: .patchsmith_reports/<project>_report.<format>)"
)
@click.option(
    "--force-analysis",
    is_flag=True,
    help="Force re-running analysis instead of using cached results"
)
def report(
    path: Path | None,
    format: str,
    output: Path | None,
    force_analysis: bool,
) -> None:
    """Generate a comprehensive security report.

    \b
    The report includes:
      • Executive summary
      • Detailed findings with triage
      • Security assessments
      • Recommendations

    \b
    By default, uses cached analysis results from the last 'patchsmith analyze' run.
    Use --force-analysis to re-run the analysis.

    \b
    Examples:
        patchsmith report                        # Report from cached data
        patchsmith report /path/to/project
        patchsmith report --format html          # Generate HTML report
        patchsmith report -o my_report.md        # Custom output path
        patchsmith report --force-analysis       # Re-run analysis first
    """
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    console.print(f"\n[bold cyan]📄 Patchsmith Security Report[/bold cyan]")
    console.print(f"Project: [yellow]{path}[/yellow]")
    console.print(f"Format: [yellow]{format}[/yellow]\n")

    # Run report generation
    asyncio.run(_generate_report(path, format, output, force_analysis))


async def _generate_report(
    path: Path,
    report_format: str,
    output_path: Path | None,
    force_analysis: bool,
) -> None:
    """Generate the report.

    Args:
        path: Path to project
        report_format: Report format (markdown, html, text)
        output_path: Optional output path
        force_analysis: Whether to force re-running analysis
    """
    try:
        # Create configuration
        config = PatchsmithConfig.create_default(
            project_root=path,
            project_name=path.name
        )

        # Determine output path
        if output_path is None:
            report_dir = path.parent / ".patchsmith_reports"
            report_dir.mkdir(exist_ok=True)
            extension = {"markdown": "md", "html": "html", "text": "txt"}[report_format]
            output_path = report_dir / f"{path.name}_security_report.{extension}"

        # Get or generate analysis data
        analysis_result = None
        triage_results = None
        detailed_assessments = None

        if force_analysis:
            # Force re-run analysis
            print_info("Running analysis (this may take a few minutes)...")

            with ProgressTracker() as tracker:
                analysis_service = AnalysisService(
                    config=config,
                    progress_callback=tracker.handle_progress,
                    thinking_callback=tracker.update_thinking,
                )

                analysis_result, triage_results, detailed_assessments = await analysis_service.analyze_project(
                    project_path=path,
                    perform_triage=True,
                    perform_detailed_analysis=True,
                    detailed_analysis_limit=None,  # Analyze all recommended findings
                )

            console.print()
            print_success("Analysis completed!")
        else:
            # Load from cached results (default)
            results_file = path / ".patchsmith_results.json"
            if not results_file.exists():
                print_error("No cached analysis results found")
                print_info("Run 'patchsmith analyze' first, or use --force-analysis to run analysis now")
                raise click.Abort()

            print_info("Loading cached analysis results...")

            with open(results_file) as f:
                data = json.load(f)

            # Reconstruct analysis result
            findings = []
            for f_data in data.get("findings", []):
                finding = Finding(
                    id=f_data["id"],
                    rule_id=f_data["rule_id"],
                    severity=Severity(f_data["severity"]),
                    cwe=CWE(id=f_data["cwe"]["id"]) if f_data.get("cwe") else None,
                    file_path=Path(f_data["file_path"]),
                    start_line=f_data["start_line"],
                    end_line=f_data.get("end_line", f_data["start_line"]),
                    message=f_data["message"],
                    snippet=f_data.get("snippet"),
                )
                findings.append(finding)

            # Reconstruct statistics
            stats_data = data.get("statistics", {})
            statistics = AnalysisStatistics(
                total_findings=data.get("total_findings", len(findings)),
                by_severity={},
                by_cwe={},
                by_language={},
            )

            # Reconstruct triage results
            triage_results = []
            for t_data in data.get("triage_results", []):
                triage = TriageResult(
                    finding_id=t_data["finding_id"],
                    priority_score=t_data["priority_score"],
                    recommended_for_analysis=t_data.get("recommended_for_analysis", False),
                    reasoning=t_data.get("reasoning", ""),
                )
                triage_results.append(triage)

            # Reconstruct detailed assessments
            detailed_assessments = {}
            for finding_id, assessment_data in data.get("detailed_assessments", {}).items():
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
                detailed_assessments[finding_id] = assessment

            # Create AnalysisResult
            from datetime import datetime
            analysis_result = AnalysisResult(
                project_name=data.get("project_name", path.name),
                timestamp=datetime.fromisoformat(data["timestamp"]),
                languages_analyzed=data.get("languages", []),
                findings=findings,
                statistics=statistics,
            )

            print_success(f"Loaded {len(findings)} findings from cache")
            console.print()

        # Generate report
        if analysis_result is None:
            print_error("No analysis data available")
            raise click.Abort()

        print_info(f"Generating {report_format} report...")

        with ProgressTracker() as tracker:
            report_service = ReportService(
                config=config,
                progress_callback=tracker.handle_progress,
                thinking_callback=tracker.update_thinking,
            )

            report_content = await report_service.generate_report(
                analysis_result=analysis_result,
                triage_results=triage_results,
                detailed_assessments=detailed_assessments,
                report_format=report_format,
                output_path=output_path,
            )

        console.print()
        print_success(f"Report generated: {output_path}")
        console.print(f"  Size: [yellow]{len(report_content):,}[/yellow] characters")
        console.print(f"  Path: [yellow]{output_path.absolute()}[/yellow]")

        # Show preview
        if report_format == "markdown":
            console.print("\n[bold cyan]Report Preview:[/bold cyan]")
            console.print("─" * 80)
            preview_lines = report_content.split('\n')[:20]
            for line in preview_lines:
                console.print(f"  {line}")
            if len(report_content.split('\n')) > 20:
                console.print(f"  ... ({len(report_content.split('\n')) - 20} more lines)")
            console.print("─" * 80)

        console.print()

    except Exception as e:
        console.print()
        print_error(f"Report generation failed: {e}")
        if click.get_current_context().obj.get("debug", False) if click.get_current_context().obj else False:
            console.print_exception()
        raise click.Abort()
