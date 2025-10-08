"""Report command for generating security reports."""

import asyncio
from pathlib import Path

import click

from patchsmith.cli.progress import (
    ProgressTracker,
    console,
    print_error,
    print_info,
    print_success,
)
from patchsmith.models.config import PatchsmithConfig
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
    "--no-analysis",
    is_flag=True,
    help="Skip analysis and only generate report from existing data"
)
def report(
    path: Path | None,
    format: str,
    output: Path | None,
    no_analysis: bool,
) -> None:
    """Generate a comprehensive security report.

    \b
    The report includes:
      • Executive summary
      • Detailed findings with triage
      • Security assessments
      • Recommendations

    \b
    Examples:
        patchsmith report                        # Report on current directory
        patchsmith report /path/to/project
        patchsmith report --format html          # Generate HTML report
        patchsmith report -o my_report.md        # Custom output path
        patchsmith report --no-analysis          # Use existing analysis data
    """
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    console.print(f"\n[bold cyan]📄 Patchsmith Security Report[/bold cyan]")
    console.print(f"Project: [yellow]{path}[/yellow]")
    console.print(f"Format: [yellow]{format}[/yellow]\n")

    # Run report generation
    asyncio.run(_generate_report(path, format, output, no_analysis))


async def _generate_report(
    path: Path,
    report_format: str,
    output_path: Path | None,
    no_analysis: bool,
) -> None:
    """Generate the report.

    Args:
        path: Path to project
        report_format: Report format (markdown, html, text)
        output_path: Optional output path
        no_analysis: Whether to skip running analysis
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

        if not no_analysis:
            print_info("Running analysis (this may take a few minutes)...")

            with ProgressTracker() as tracker:
                analysis_service = AnalysisService(
                    config=config,
                    progress_callback=tracker.handle_progress
                )

                analysis_result, triage_results, detailed_assessments = await analysis_service.analyze_project(
                    project_path=path,
                    perform_triage=True,
                    perform_detailed_analysis=True,
                    detailed_analysis_limit=10,
                )

            console.print()
            print_success("Analysis completed!")
        else:
            # TODO: Load from cached analysis results
            print_error("Loading cached results not yet implemented")
            print_info("Please run without --no-analysis flag")
            raise click.Abort()

        # Generate report
        if analysis_result is None:
            print_error("No analysis data available")
            raise click.Abort()

        print_info(f"Generating {report_format} report...")

        with ProgressTracker() as tracker:
            report_service = ReportService(
                config=config,
                progress_callback=tracker.handle_progress
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
