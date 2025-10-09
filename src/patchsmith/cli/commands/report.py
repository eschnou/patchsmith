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
from patchsmith.services.report_service import ReportService


@click.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path), required=False)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["markdown", "html"], case_sensitive=False),
    default="markdown",
    help="Report format"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path (default: .patchsmith/reports/<project>_report.<format>)"
)
def report(
    path: Path | None,
    format: str,
    output: Path | None,
) -> None:
    """Generate a comprehensive security report from cached analysis results.

    \b
    The report includes:
      • Executive summary
      • Detailed findings with triage
      • Security assessments (if available)
      • Recommendations

    \b
    Requires prior analysis. Run 'patchsmith analyze' first.

    \b
    Examples:
        patchsmith report                        # Generate report
        patchsmith report /path/to/project
        patchsmith report --format html          # Generate HTML report
        patchsmith report -o my_report.md        # Custom output path
    """
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    console.print("\n[bold cyan]📄 Patchsmith Security Report[/bold cyan]")
    console.print(f"Project: [yellow]{path}[/yellow]")
    console.print(f"Format: [yellow]{format}[/yellow]\n")

    # Run report generation
    asyncio.run(_generate_report(path, format, output))


async def _generate_report(
    path: Path,
    report_format: str,
    output_path: Path | None,
) -> None:
    """Generate the report from cached analysis results.

    Args:
        path: Path to project
        report_format: Report format (markdown, html, text)
        output_path: Optional output path
    """
    try:
        # Create configuration
        config = PatchsmithConfig.create_default(
            project_root=path,
            project_name=path.name
        )

        # Determine output path
        if output_path is None:
            report_dir = path / ".patchsmith" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            extension = {"markdown": "md", "html": "html"}[report_format]
            output_path = report_dir / f"{path.name}_security_report.{extension}"

        # Load from cached results
        results_file = path / ".patchsmith" / "results.json"
        if not results_file.exists():
            print_error("No analysis results found")
            print_info("Run 'patchsmith analyze' first to generate analysis data")
            console.print("\nTip: Use [green]patchsmith analyze --investigate[/green] for comprehensive analysis with AI triage")
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
                cwe=CWE(id=f_data["cwe"]["id"], name=f_data["cwe"].get("name")) if f_data.get("cwe") else None,
                file_path=Path(f_data["file_path"]),
                start_line=f_data["start_line"],
                end_line=f_data.get("end_line", f_data["start_line"]),
                message=f_data["message"],
                snippet=f_data.get("snippet"),
                false_positive_score=None,  # Not stored in cached results
            )
            findings.append(finding)

        # Compute statistics from findings
        # The cached statistics are incomplete, so we compute them from the findings
        by_severity: dict[Severity, int] = {}
        by_cwe: dict[str, int] = {}
        by_language: dict[str, int] = {}

        for finding in findings:
            # Count by severity
            by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1

            # Count by CWE
            if finding.cwe:
                by_cwe[finding.cwe.id] = by_cwe.get(finding.cwe.id, 0) + 1

            # Count by language (infer from file extension)
            file_path_str = str(finding.file_path)
            if file_path_str.endswith(('.ts', '.tsx', '.js', '.jsx')):
                lang = 'javascript'
            elif file_path_str.endswith('.py'):
                lang = 'python'
            elif file_path_str.endswith(('.c', '.cpp', '.h', '.hpp')):
                lang = 'cpp'
            elif file_path_str.endswith('.go'):
                lang = 'go'
            elif file_path_str.endswith('.java'):
                lang = 'java'
            else:
                lang = 'other'
            by_language[lang] = by_language.get(lang, 0) + 1

        statistics = AnalysisStatistics(
            total_findings=len(findings),
            by_severity=by_severity,
            by_cwe=by_cwe,
            by_language=by_language,
            false_positives_filtered=0,  # Not tracked in cached results
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
