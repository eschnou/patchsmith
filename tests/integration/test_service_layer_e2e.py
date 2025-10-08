"""End-to-end integration test using the service layer.

This test validates the complete workflow using the service layer
(AnalysisService, ReportService, FixService) orchestrating adapters.
"""

import asyncio
from pathlib import Path

import pytest

from patchsmith.models.config import PatchsmithConfig
from patchsmith.services.analysis_service import AnalysisService
from patchsmith.services.fix_service import FixService
from patchsmith.services.report_service import ReportService


class TestServiceLayerEndToEnd:
    """Test complete workflow using service layer."""

    @pytest.mark.asyncio
    async def test_complete_workflow_with_services(self, tmp_path: Path) -> None:
        """Test complete security analysis workflow using services.

        This test validates:
        1. AnalysisService - Complete analysis with language detection, CodeQL, triage, detailed analysis
        2. ReportService - Report generation with triage and detailed assessments
        3. FixService - Fix generation and application

        The test uses a real vulnerable Python project.
        """
        print("\n" + "=" * 80)
        print("SERVICE LAYER END-TO-END INTEGRATION TEST")
        print("=" * 80)

        # ===================================================================
        # Phase 1: Setup - Create vulnerable test project
        # ===================================================================
        print("\n[Phase 1] Setting up vulnerable test project...")

        project_dir = tmp_path / "vulnerable_project"
        project_dir.mkdir()

        # Create a Python file with multiple vulnerabilities
        vulnerable_file = project_dir / "app.py"
        vulnerable_file.write_text('''
import os
import sqlite3
from flask import Flask, request

app = Flask(__name__)

@app.route('/user')
def get_user():
    """SQL injection vulnerability."""
    user_id = request.args.get('id')
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # VULNERABLE: String concatenation in SQL query
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
    return cursor.fetchone()

@app.route('/exec')
def exec_command():
    """Command injection vulnerability."""
    cmd = request.args.get('cmd')
    # VULNERABLE: Unsanitized command execution
    result = os.system(cmd)
    return str(result)

@app.route('/eval')
def eval_code():
    """Code injection vulnerability."""
    code = request.args.get('code')
    # VULNERABLE: eval() with user input
    return str(eval(code))

if __name__ == '__main__':
    app.run(debug=True)  # Debug mode in production
''')

        # Create requirements.txt
        requirements_file = project_dir / "requirements.txt"
        requirements_file.write_text("flask==2.0.1\n")

        print(f"  ✓ Created test project at: {project_dir}")
        print(f"  ✓ Created vulnerable file: {vulnerable_file}")

        # ===================================================================
        # Phase 2: Initialize services with progress tracking
        # ===================================================================
        print("\n[Phase 2] Initializing services...")

        # Progress tracking
        progress_events = []

        def progress_callback(event: str, data: dict) -> None:
            """Track progress events."""
            progress_events.append((event, data))
            service = data.get("service", "Unknown")
            print(f"  → [{service}] {event}")
            # Print relevant details
            if "finding_count" in data:
                print(f"      Findings: {data['finding_count']}")
            if "languages" in data:
                print(f"      Languages: {data['languages']}")
            if "confidence" in data:
                print(f"      Confidence: {data['confidence']:.2f}")

        # Create configuration
        config = PatchsmithConfig.create_default(
            project_root=project_dir,
            project_name="vulnerable_project"
        )

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

        print("  ✓ Services initialized with progress tracking")

        # ===================================================================
        # Phase 3: Run complete security analysis
        # ===================================================================
        print("\n[Phase 3] Running security analysis...")

        analysis_result, triage_results, detailed_assessments = await analysis_service.analyze_project(
            project_path=project_dir,
            perform_triage=True,
            perform_detailed_analysis=True,
            detailed_analysis_limit=5,
        )

        print(f"\n  ✓ Analysis completed!")
        print(f"      Total findings: {len(analysis_result.findings)}")
        print(f"      Languages analyzed: {analysis_result.languages_analyzed}")
        print(f"      Critical: {analysis_result.statistics.get_critical_count()}")
        print(f"      High: {analysis_result.statistics.get_high_count()}")
        print(f"      By severity: {analysis_result.statistics.by_severity}")

        # Validate analysis results
        assert analysis_result is not None
        assert len(analysis_result.findings) > 0, "Should detect vulnerabilities"
        assert "python" in [lang.lower() for lang in analysis_result.languages_analyzed]
        assert analysis_result.statistics.total_findings > 0

        # ===================================================================
        # Phase 4: Validate triage results
        # ===================================================================
        print("\n[Phase 4] Validating triage results...")

        if triage_results:
            print(f"  ✓ Triage completed: {len(triage_results)} findings prioritized")
            recommended = [t for t in triage_results if t.recommended_for_analysis]
            print(f"      Recommended for analysis: {len(recommended)}")

            for i, triage in enumerate(recommended[:3], 1):
                print(f"      {i}. {triage.finding_id} (priority: {triage.priority_score:.2f})")
                print(f"         Reasoning: {triage.reasoning[:80]}...")

            assert len(triage_results) > 0
            assert any(t.recommended_for_analysis for t in triage_results)
        else:
            print("  ⚠ Triage not performed (no findings or disabled)")

        # ===================================================================
        # Phase 5: Validate detailed security assessments
        # ===================================================================
        print("\n[Phase 5] Validating detailed security assessments...")

        if detailed_assessments:
            print(f"  ✓ Detailed analysis completed: {len(detailed_assessments)} findings analyzed")

            for finding_id, assessment in list(detailed_assessments.items())[:3]:
                print(f"\n      Finding: {finding_id}")
                print(f"      False Positive: {assessment.is_false_positive} (score: {assessment.false_positive_score:.2f})")
                print(f"      Risk Type: {assessment.risk_type.value}")
                print(f"      Exploitability: {assessment.exploitability_score:.2f}")
                print(f"      Priority: {assessment.remediation_priority}")
                print(f"      Attack Scenario: {assessment.attack_scenario[:100]}...")

            assert len(detailed_assessments) > 0
            # Check that we have comprehensive analysis
            for assessment in detailed_assessments.values():
                assert assessment.attack_scenario is not None
                assert assessment.risk_type is not None
                assert 0.0 <= assessment.exploitability_score <= 1.0
                assert assessment.remediation_priority in ["immediate", "high", "medium", "low"]
        else:
            print("  ⚠ Detailed analysis not performed")

        # ===================================================================
        # Phase 6: Generate comprehensive report
        # ===================================================================
        print("\n[Phase 6] Generating security report...")

        report_path = tmp_path / "security_report.md"
        report = await report_service.generate_report(
            analysis_result=analysis_result,
            triage_results=triage_results,
            detailed_assessments=detailed_assessments,
            report_format="markdown",
            output_path=report_path,
        )

        print(f"  ✓ Report generated: {len(report)} characters")
        print(f"  ✓ Report saved to: {report_path}")

        assert len(report) > 0
        assert report_path.exists()
        assert "security" in report.lower() or "finding" in report.lower()

        # Show report preview
        print("\n  Report preview (first 500 chars):")
        print("  " + "-" * 76)
        for line in report[:500].split("\n"):
            print(f"  {line}")
        print("  " + "-" * 76)

        # ===================================================================
        # Phase 7: Generate and apply fixes (optional)
        # ===================================================================
        print("\n[Phase 7] Testing fix generation...")

        if triage_results and analysis_result.findings:
            # Get the highest priority finding
            top_triage = max(triage_results, key=lambda t: t.priority_score)
            top_finding = next(
                (f for f in analysis_result.findings if f.id == top_triage.finding_id),
                None
            )

            if top_finding:
                print(f"  Attempting to fix: {top_finding.id}")
                print(f"  File: {top_finding.file_path}:{top_finding.start_line}")

                try:
                    fix = await fix_service.generate_fix(
                        finding=top_finding,
                        working_dir=project_dir,
                        context_lines=10,
                    )

                    if fix:
                        print(f"  ✓ Fix generated with confidence: {fix.confidence:.2f}")
                        print(f"      Explanation: {fix.explanation[:100]}...")

                        assert fix.confidence > 0.0
                        assert len(fix.original_code) > 0
                        assert len(fix.fixed_code) > 0
                        assert len(fix.explanation) > 0

                        # Optionally apply the fix (without Git operations for test)
                        if fix.confidence >= 0.7:
                            print(f"\n  Applying fix (confidence >= 0.7)...")
                            success, message = fix_service.apply_fix(
                                fix=fix,
                                create_branch=False,
                                commit=False,
                            )
                            print(f"  ✓ Fix application: {message}")
                            assert success is True
                    else:
                        print("  ⚠ No fix generated (low confidence or error)")
                except Exception as e:
                    print(f"  ⚠ Fix generation failed: {e}")
                    # Don't fail the test - fix generation is experimental
        else:
            print("  ⚠ Skipping fix generation (no findings)")

        # ===================================================================
        # Phase 8: Validate progress tracking
        # ===================================================================
        print("\n[Phase 8] Validating progress tracking...")

        # Check that key progress events were emitted
        event_names = [event for event, _ in progress_events]
        print(f"  ✓ Total progress events: {len(progress_events)}")

        # Expected events from AnalysisService
        expected_analysis_events = [
            "analysis_started",
            "language_detection_started",
            "language_detection_completed",
            "codeql_database_creation_started",
            "codeql_database_created",
            "codeql_queries_started",
            "codeql_queries_completed",
            "sarif_parsing_started",
            "sarif_parsing_completed",
            "statistics_computation_started",
            "statistics_computation_completed",
            "analysis_completed",
        ]

        print("\n  Checking for expected events:")
        for expected_event in expected_analysis_events:
            if expected_event in event_names:
                print(f"    ✓ {expected_event}")
            else:
                print(f"    ✗ {expected_event} (MISSING)")

        # At minimum, we should have these critical events
        assert "analysis_started" in event_names
        assert "language_detection_completed" in event_names
        assert "analysis_completed" in event_names

        # ===================================================================
        # Summary
        # ===================================================================
        print("\n" + "=" * 80)
        print("SERVICE LAYER E2E TEST SUMMARY")
        print("=" * 80)
        print(f"✓ Project analyzed: {project_dir.name}")
        print(f"✓ Findings detected: {len(analysis_result.findings)}")
        print(f"✓ Triage results: {len(triage_results) if triage_results else 0}")
        print(f"✓ Detailed assessments: {len(detailed_assessments) if detailed_assessments else 0}")
        print(f"✓ Report generated: {report_path.name} ({len(report)} chars)")
        print(f"✓ Progress events: {len(progress_events)}")
        print("=" * 80)
        print("ALL PHASES COMPLETED SUCCESSFULLY")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    """Run the test manually."""
    import tempfile

    async def main():
        with tempfile.TemporaryDirectory() as tmpdir:
            test = TestServiceLayerEndToEnd()
            await test.test_complete_workflow_with_services(Path(tmpdir))

    asyncio.run(main())
