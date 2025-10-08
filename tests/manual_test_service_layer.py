"""Manual test for service layer end-to-end workflow.

Run this script directly to test the complete workflow using the service layer.
You can provide a path to any repository to analyze.

Usage:
    poetry run python tests/manual_test_service_layer.py [path_to_repo]

Example:
    poetry run python tests/manual_test_service_layer.py ~/code/my-project
    poetry run python tests/manual_test_service_layer.py tests/fixtures/vulnerable_flask_app
"""

import asyncio
import sys
from pathlib import Path

from patchsmith.models.config import PatchsmithConfig
from patchsmith.services.analysis_service import AnalysisService
from patchsmith.services.fix_service import FixService
from patchsmith.services.report_service import ReportService


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'─' * 80}")
    print(f"  {title}")
    print(f"{'─' * 80}")


def print_progress(event: str, data: dict) -> None:
    """Print progress events from services."""
    service = data.get("service", "Unknown")
    print(f"  → [{service}] {event}")

    # Print relevant details
    if "finding_count" in data:
        print(f"      Findings: {data['finding_count']}")
    if "languages" in data:
        print(f"      Languages: {data['languages']}")
    if "count" in data:
        print(f"      Count: {data['count']}")
    if "confidence" in data:
        print(f"      Confidence: {data['confidence']:.2f}")
    if "priority_score" in data:
        print(f"      Priority: {data['priority_score']:.2f}")


async def run_service_layer_workflow(project_path: Path) -> None:
    """Run complete workflow using service layer."""

    print_header("SERVICE LAYER END-TO-END TEST")
    print(f"Project: {project_path}")
    print(f"Absolute path: {project_path.resolve()}")

    if not project_path.exists():
        print(f"\n❌ Error: Path does not exist: {project_path}")
        return

    if not project_path.is_dir():
        print(f"\n❌ Error: Path is not a directory: {project_path}")
        return

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 1: Initialize Configuration and Services
    # ═══════════════════════════════════════════════════════════════════════════
    print_section("Phase 1: Initializing Services")

    # Track all progress events
    all_events = []

    def progress_callback(event: str, data: dict) -> None:
        all_events.append((event, data))
        print_progress(event, data)

    # Create configuration
    config = PatchsmithConfig.create_default(
        project_root=project_path.resolve(),
        project_name=project_path.name
    )

    print(f"  ✓ Configuration created")
    print(f"      Project name: {config.project.name}")
    print(f"      Project root: {config.project.root}")

    # Initialize services
    analysis_service = AnalysisService(
        config=config,
        progress_callback=progress_callback
    )

    report_service = ReportService(
        config=config,
        progress_callback=progress_callback
    )

    fix_service = FixService(
        config=config,
        progress_callback=progress_callback
    )

    print(f"  ✓ Services initialized: AnalysisService, ReportService, FixService")

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 2: Run Complete Security Analysis
    # ═══════════════════════════════════════════════════════════════════════════
    print_section("Phase 2: Running Security Analysis")
    print("  This will:")
    print("    1. Detect programming languages")
    print("    2. Create CodeQL database")
    print("    3. Run security queries")
    print("    4. Parse results")
    print("    5. Triage findings (prioritize)")
    print("    6. Detailed analysis (top findings)")
    print("    7. Compute statistics")
    print()

    try:
        analysis_result, triage_results, detailed_assessments = await analysis_service.analyze_project(
            project_path=project_path.resolve(),
            perform_triage=True,
            perform_detailed_analysis=True,
            detailed_analysis_limit=5,
        )

        print_section("Phase 2: Analysis Results")
        print(f"  ✓ Analysis completed successfully!")
        print(f"\n  📊 Summary Statistics:")
        print(f"      Total findings: {len(analysis_result.findings)}")
        print(f"      Languages: {', '.join(analysis_result.languages_analyzed)}")
        print(f"      Critical: {analysis_result.statistics.get_critical_count()}")
        print(f"      High: {analysis_result.statistics.get_high_count()}")
        print(f"      Actionable: {analysis_result.statistics.get_actionable_count()}")
        print(f"      False positives filtered: {analysis_result.statistics.false_positives_filtered}")

        if analysis_result.statistics.by_cwe:
            print(f"\n  🔍 Top CWEs:")
            sorted_cwes = sorted(
                analysis_result.statistics.by_cwe.items(),
                key=lambda x: x[1],
                reverse=True
            )
            for cwe, count in sorted_cwes[:5]:
                print(f"      {cwe}: {count} finding(s)")

    except Exception as e:
        print(f"\n  ❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 3: Display Triage Results
    # ═══════════════════════════════════════════════════════════════════════════
    if triage_results:
        print_section("Phase 3: Triage Results")
        print(f"  ✓ Triaged {len(triage_results)} findings")

        recommended = [t for t in triage_results if t.recommended_for_analysis]
        print(f"  ✓ Recommended for detailed analysis: {len(recommended)}")

        if recommended:
            print(f"\n  🎯 Top Priority Findings:")
            for i, triage in enumerate(recommended[:5], 1):
                finding = next((f for f in analysis_result.findings if f.id == triage.finding_id), None)
                if finding:
                    print(f"\n      {i}. {finding.rule_id} (Priority: {triage.priority_score:.2f})")
                    print(f"         Location: {finding.file_path}:{finding.start_line}")
                    print(f"         Severity: {finding.severity.value.upper()}")
                    print(f"         Message: {finding.message[:80]}...")
                    print(f"         Reasoning: {triage.reasoning[:100]}...")
    else:
        print_section("Phase 3: Triage Results")
        print("  ⚠️  No triage results (no findings or triage disabled)")

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 4: Display Detailed Security Assessments
    # ═══════════════════════════════════════════════════════════════════════════
    if detailed_assessments:
        print_section("Phase 4: Detailed Security Assessments")
        print(f"  ✓ Detailed analysis completed for {len(detailed_assessments)} findings")

        for i, (finding_id, assessment) in enumerate(list(detailed_assessments.items())[:3], 1):
            finding = next((f for f in analysis_result.findings if f.id == finding_id), None)
            if finding:
                print(f"\n  🔬 Assessment {i}: {finding.rule_id}")
                print(f"      Location: {finding.file_path}:{finding.start_line}")
                print(f"      False Positive: {assessment.is_false_positive} (confidence: {assessment.false_positive_score:.2f})")
                print(f"      Risk Type: {assessment.risk_type.value}")
                print(f"      Exploitability: {assessment.exploitability_score:.2f}/1.0")
                print(f"      Remediation Priority: {assessment.remediation_priority.upper()}")
                print(f"      Attack Scenario:")
                for line in assessment.attack_scenario[:200].split('\n'):
                    print(f"        {line}")
                if len(assessment.attack_scenario) > 200:
                    print("        ...")
    else:
        print_section("Phase 4: Detailed Security Assessments")
        print("  ⚠️  No detailed assessments (no findings or analysis disabled)")

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 5: Generate Report
    # ═══════════════════════════════════════════════════════════════════════════
    print_section("Phase 5: Generating Security Report")

    try:
        report_output_dir = project_path.parent / ".patchsmith_reports"
        report_output_dir.mkdir(exist_ok=True)
        report_path = report_output_dir / f"{project_path.name}_security_report.md"

        report = await report_service.generate_report(
            analysis_result=analysis_result,
            triage_results=triage_results,
            detailed_assessments=detailed_assessments,
            report_format="markdown",
            output_path=report_path,
        )

        print(f"  ✓ Report generated: {len(report)} characters")
        print(f"  ✓ Saved to: {report_path}")

        # Show preview
        print(f"\n  📄 Report Preview (first 800 characters):")
        print("  " + "─" * 78)
        for line in report[:800].split('\n'):
            print(f"  {line}")
        print("  " + "─" * 78)
        if len(report) > 800:
            print(f"  ... ({len(report) - 800} more characters)")

    except Exception as e:
        print(f"\n  ❌ Report generation failed: {e}")
        import traceback
        traceback.print_exc()

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 6: Generate Fixes (Optional)
    # ═══════════════════════════════════════════════════════════════════════════
    if triage_results and analysis_result.findings:
        print_section("Phase 6: Fix Generation (Top Finding)")

        # Get highest priority finding
        recommended = [t for t in triage_results if t.recommended_for_analysis]
        if recommended:
            top_triage = max(recommended, key=lambda t: t.priority_score)
            top_finding = next(
                (f for f in analysis_result.findings if f.id == top_triage.finding_id),
                None
            )

            if top_finding:
                print(f"  🔧 Attempting to fix: {top_finding.rule_id}")
                print(f"      Location: {top_finding.file_path}:{top_finding.start_line}")
                print(f"      Severity: {top_finding.severity.value.upper()}")
                print(f"      Message: {top_finding.message}")

                try:
                    fix = await fix_service.generate_fix(
                        finding=top_finding,
                        working_dir=project_path.resolve(),
                        context_lines=15,
                    )

                    if fix:
                        print(f"\n  ✓ Fix generated!")
                        print(f"      Confidence: {fix.confidence:.2f}")
                        print(f"      Explanation: {fix.explanation}")

                        print(f"\n  📝 Original Code:")
                        print("  " + "─" * 78)
                        for line in fix.original_code.split('\n')[:10]:
                            print(f"  - {line}")
                        print("  " + "─" * 78)

                        print(f"\n  ✨ Fixed Code:")
                        print("  " + "─" * 78)
                        for line in fix.fixed_code.split('\n')[:10]:
                            print(f"  + {line}")
                        print("  " + "─" * 78)

                        # Ask if user wants to apply (in real scenario)
                        if fix.confidence >= 0.7:
                            print(f"\n  💡 High confidence fix (>= 0.7)")
                            print(f"     In production, this could be auto-applied with:")
                            print(f"     fix_service.apply_fix(fix, create_branch=True, commit=True)")
                        else:
                            print(f"\n  ⚠️  Lower confidence fix (< 0.7) - manual review recommended")
                    else:
                        print(f"\n  ⚠️  No fix generated (low confidence or unable to generate)")

                except Exception as e:
                    print(f"\n  ❌ Fix generation failed: {e}")
                    # Don't stop - fix generation is experimental
            else:
                print("  ⚠️  Could not find top priority finding")
        else:
            print("  ⚠️  No findings recommended for fix generation")
    else:
        print_section("Phase 6: Fix Generation")
        print("  ⚠️  Skipped (no findings to fix)")

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 7: Progress Event Summary
    # ═══════════════════════════════════════════════════════════════════════════
    print_section("Phase 7: Progress Event Summary")

    event_names = [event for event, _ in all_events]
    print(f"  ✓ Total progress events emitted: {len(all_events)}")

    # Key events to check
    key_events = [
        "analysis_started",
        "language_detection_started",
        "language_detection_completed",
        "codeql_database_creation_started",
        "codeql_database_created",
        "codeql_queries_started",
        "codeql_queries_completed",
        "sarif_parsing_started",
        "sarif_parsing_completed",
        "triage_started",
        "triage_completed",
        "detailed_analysis_started",
        "detailed_analysis_completed",
        "statistics_computation_started",
        "statistics_computation_completed",
        "analysis_completed",
        "report_generation_started",
        "report_generation_completed",
    ]

    print(f"\n  📋 Event Checklist:")
    for event in key_events:
        status = "✓" if event in event_names else "✗"
        count = event_names.count(event)
        print(f"      {status} {event} ({count}x)")

    # ═══════════════════════════════════════════════════════════════════════════
    # Final Summary
    # ═══════════════════════════════════════════════════════════════════════════
    print_header("SERVICE LAYER TEST SUMMARY")
    print(f"✅ Project: {project_path.name}")
    print(f"✅ Languages: {', '.join(analysis_result.languages_analyzed)}")
    print(f"✅ Total findings: {len(analysis_result.findings)}")
    print(f"✅ Critical/High: {analysis_result.statistics.get_critical_count()}/{analysis_result.statistics.get_high_count()}")
    print(f"✅ Triaged: {len(triage_results) if triage_results else 0}")
    print(f"✅ Detailed assessments: {len(detailed_assessments) if detailed_assessments else 0}")
    print(f"✅ Report saved: {report_path if 'report_path' in locals() else 'N/A'}")
    print(f"✅ Progress events: {len(all_events)}")
    print("=" * 80)
    print("✅ ALL PHASES COMPLETED SUCCESSFULLY")
    print("=" * 80)


async def main():
    """Main entry point."""
    # Get project path from command line or use default
    # Take the last argument as the path (in case user provides multiple)
    if len(sys.argv) > 1:
        project_path = Path(sys.argv[-1])
    else:
        # Default to fixtures if available
        fixtures_path = Path(__file__).parent / "fixtures" / "vulnerable_flask_app"
        if fixtures_path.exists():
            project_path = fixtures_path
        else:
            print("Usage: python tests/manual_test_service_layer.py [path_to_repo]")
            print("\nExample:")
            print("  python tests/manual_test_service_layer.py ~/code/my-project")
            print("  python tests/manual_test_service_layer.py tests/fixtures/vulnerable_flask_app")
            sys.exit(1)

    await run_service_layer_workflow(project_path)


if __name__ == "__main__":
    asyncio.run(main())
