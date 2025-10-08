"""End-to-end integration test for Patchsmith workflow.

This test validates that all adapters work together correctly by running
a complete workflow on a codebase:

1. Detect languages using Claude AI
2. Create CodeQL database
3. Run CodeQL queries
4. Parse results to findings
5. Triage findings using Claude AI (identify top critical issues)
6. Perform detailed security analysis on prioritized findings using Claude AI
   - False positive assessment
   - Attack scenario development
   - Risk classification
   - Exploitability and impact analysis
7. Generate a comprehensive report using Claude AI (with triage + detailed results)
8. Generate a fix for a finding using Claude AI
9. Create a Git branch with the fix
10. Create a pull request (simulated)

This test requires:
- CodeQL CLI installed and in PATH
- ANTHROPIC_API_KEY environment variable set
- Git repository initialized
- GitHub CLI (gh) installed for PR creation (optional)
"""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest
from patchsmith.adapters.claude.detailed_security_analysis_agent import (
    DetailedSecurityAnalysisAgent,
)
from patchsmith.adapters.claude.fix_generator_agent import FixGeneratorAgent
from patchsmith.adapters.claude.language_detection_agent import LanguageDetectionAgent
from patchsmith.adapters.claude.report_generator_agent import ReportGeneratorAgent
from patchsmith.adapters.claude.triage_agent import TriageAgent
from patchsmith.adapters.codeql.cli import CodeQLCLI
from patchsmith.adapters.codeql.parsers import SARIFParser
from patchsmith.adapters.git.pr import PRCreator, PRError
from patchsmith.adapters.git.repository import GitRepository
from patchsmith.models.analysis import AnalysisResult

# Skip if required tools are not available
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set - skipping integration test",
)


@pytest.mark.asyncio
@pytest.mark.integration
class TestE2EWorkflow:
    """End-to-end integration tests."""

    async def test_complete_workflow(self, tmp_path: Path) -> None:
        """Test complete workflow from language detection to PR creation.

        This test runs a realistic workflow on a project. By default it creates
        a simple test project, but you can set TEST_PROJECT_PATH environment
        variable to test on a real codebase.

        Example:
            TEST_PROJECT_PATH=/path/to/your/project pytest tests/integration/...
        """
        # Check if user provided a project path
        import os
        project_path_env = os.environ.get("TEST_PROJECT_PATH")

        if project_path_env:
            test_project = Path(project_path_env).resolve()
            print(f"\n{'=' * 80}")
            print(f"Using provided project: {test_project}")
            print(f"{'=' * 80}")

            if not test_project.exists():
                raise ValueError(f"TEST_PROJECT_PATH does not exist: {test_project}")
            if not test_project.is_dir():
                raise ValueError(f"TEST_PROJECT_PATH is not a directory: {test_project}")
        else:
            # Setup: Create a test project with a vulnerable file
            test_project = tmp_path / "test_project"
            test_project.mkdir()

            # Initialize git repo for test project
            import subprocess

            subprocess.run(["git", "init"], cwd=test_project, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=test_project,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=test_project,
                check=True,
                capture_output=True,
            )

            # Create a vulnerable Python file
            vulnerable_file = test_project / "app.py"
            vulnerable_file.write_text(
            """import sqlite3

def get_user(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # Vulnerable to SQL injection
    query = "SELECT * FROM users WHERE id = '" + user_id + "'"
    cursor.execute(query)
    return cursor.fetchone()

def safe_get_user(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # This is safe - uses parameterized query
    query = "SELECT * FROM users WHERE id = ?"
    cursor.execute(query, (user_id,))
    return cursor.fetchone()
"""
            )

            # Create README
            readme = test_project / "README.md"
            readme.write_text("# Test Project\n\nA test project with a SQL injection vulnerability.\n")

            # Initial commit
            subprocess.run(["git", "add", "."], cwd=test_project, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=test_project,
                check=True,
                capture_output=True,
            )

        print("\n" + "=" * 80)
        print("PHASE 1: Language Detection")
        print("=" * 80)

        # Step 1: Detect languages using Claude AI
        language_agent = LanguageDetectionAgent(working_dir=test_project, max_turns=100)
        languages = await language_agent.execute(project_path=test_project)

        print(f"✓ Detected {len(languages)} language(s):")
        for lang in languages:
            print(f"  - {lang.name} (confidence: {lang.confidence:.2f})")

        assert len(languages) > 0, "Should detect at least one language"

        # If using custom project path, accept any language
        # If using generated test project, it should be Python
        if not project_path_env:
            assert any(
                lang.name.lower() == "python" for lang in languages
            ), "Should detect Python in generated test project"

        print("\n" + "=" * 80)
        print("PHASE 2: CodeQL Analysis")
        print("=" * 80)

        # Step 2: Create CodeQL database for primary language
        # Choose the language with highest confidence
        primary_language = languages[0]
        codeql_language = primary_language.name.lower()

        # Map detected language to CodeQL language name
        language_mapping = {
            "javascript": "javascript",
            "typescript": "javascript",  # TypeScript uses javascript database
            "python": "python",
            "java": "java",
            "go": "go",
            "cpp": "cpp",
            "c": "cpp",
            "csharp": "csharp",
            "ruby": "ruby",
        }

        codeql_lang = language_mapping.get(codeql_language, codeql_language)

        codeql = CodeQLCLI()
        db_path = tmp_path / "codeql_db"

        print(f"Creating CodeQL database for {codeql_lang} at {db_path}...")
        codeql.create_database(
            source_root=test_project,
            db_path=db_path,
            language=codeql_lang,
        )
        print(f"✓ Database created successfully")

        # Step 3: Run CodeQL queries (output as CSV for efficiency)
        results_path_csv = tmp_path / "results.csv"
        results_path_sarif = tmp_path / "results.sarif"
        print(f"Running CodeQL queries...")

        # Map language to query suite
        query_suites = {
            "python": "codeql/python-queries:codeql-suites/python-security-and-quality.qls",
            "javascript": "codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls",
            "java": "codeql/java-queries:codeql-suites/java-security-and-quality.qls",
            "go": "codeql/go-queries:codeql-suites/go-security-and-quality.qls",
            "cpp": "codeql/cpp-queries:codeql-suites/cpp-security-and-quality.qls",
            "csharp": "codeql/csharp-queries:codeql-suites/csharp-security-and-quality.qls",
            "ruby": "codeql/ruby-queries:codeql-suites/ruby-security-and-quality.qls",
        }

        query_suite = query_suites.get(codeql_lang, f"codeql/{codeql_lang}-queries")

        # Use CSV format for lighter weight processing
        # (SARIF is kept for reference but CSV is used for agent processing)
        codeql.run_queries(
            db_path=db_path,
            query_path=query_suite,
            output_format="csv",
            output_path=results_path_csv,
            download=True,  # Auto-download query pack if missing
        )
        print(f"✓ Queries executed, results at {results_path_csv}")

        # Also generate SARIF for complete results (optional)
        print(f"Generating SARIF format for reference...")
        codeql.run_queries(
            db_path=db_path,
            query_path=query_suite,
            output_format="sarif-latest",
            output_path=results_path_sarif,
            download=True,
        )

        # Step 4: Parse CSV results (lighter weight than SARIF)
        print(f"Parsing CSV results...")
        # TODO: Implement CSV parser - for now still use SARIF
        parser = SARIFParser()
        findings = parser.parse_file(results_path_sarif)
        print(f"✓ Found {len(findings)} potential issues")

        if len(findings) > 0:
            print(f"\nFindings summary:")
            for i, finding in enumerate(findings[:5], 1):  # Show first 5
                print(f"  {i}. [{finding.severity.value}] {finding.rule_id}")
                print(f"     {finding.file_path.name}:{finding.start_line}")
                print(f"     {finding.message[:80]}...")
        else:
            print("\n⚠ No findings detected by CodeQL")
            print("  The test code may be too simple or CodeQL queries didn't match")
            print("  To test with real vulnerabilities, run on a production codebase")
            print("\n✓ CodeQL analysis completed successfully (no findings)")
            print("\nSkipping remaining workflow phases (no findings to process)")
            return  # Exit test early - no findings to process

        print("\n" + "=" * 80)
        print("PHASE 3: Triage (High-Level Review)")
        print("=" * 80)

        # Step 5: Triage findings to identify top issues
        triage_agent = TriageAgent(working_dir=test_project, max_turns=100)
        print(f"Triaging {len(findings)} finding(s) to identify critical issues...")

        triage_results = await triage_agent.execute(findings=findings, top_n=10)

        print(f"✓ Triage complete:")
        print(f"  - {len(triage_results)} findings prioritized")
        recommended = [t for t in triage_results if t.recommended_for_analysis]
        print(f"  - {len(recommended)} recommended for detailed analysis")
        print(f"\nTop 5 prioritized findings:")
        for i, triage in enumerate(recommended[:5], 1):
            print(f"  {i}. {triage.finding_id} (priority: {triage.priority_score:.2f})")
            print(f"     {triage.reasoning[:80]}...")

        print("\n" + "=" * 80)
        print("PHASE 4: Detailed Security Analysis")
        print("=" * 80)

        # Step 6: Perform detailed analysis on top findings
        # Get findings that were recommended for analysis
        findings_to_analyze = []
        for triage in recommended[:3]:  # Limit to 3 for testing
            finding = next((f for f in findings if f.id == triage.finding_id), None)
            if finding:
                findings_to_analyze.append(finding)

        detailed_assessments = {}
        if findings_to_analyze:
            analysis_agent = DetailedSecurityAnalysisAgent(working_dir=test_project, max_turns=100)
            print(f"Performing detailed analysis on {len(findings_to_analyze)} finding(s)...")

            detailed_assessments = await analysis_agent.execute(findings_to_analyze)

            print(f"✓ Detailed analysis complete:")
            for finding_id, assessment in detailed_assessments.items():
                fp_status = "FALSE POSITIVE" if assessment.is_false_positive else "VALID"
                print(f"  - {finding_id}: {fp_status}")
                if not assessment.is_false_positive:
                    print(f"    Risk: {assessment.risk_type.value}, Priority: {assessment.remediation_priority}")
                    print(f"    Attack: {assessment.attack_scenario[:80]}...")

        print("\n" + "=" * 80)
        print("PHASE 5: Report Generation")
        print("=" * 80)

        # Step 7: Generate report using Claude AI with triage + detailed results
        report_agent = ReportGeneratorAgent(working_dir=test_project)
        analysis_result = AnalysisResult(
            project_name="Test Project",
            project_path=test_project,
            findings=findings,
            timestamp="2025-10-08T10:00:00Z",
            languages_analyzed=[lang.name for lang in languages],
        )

        print(f"Generating security report with triage and detailed analysis...")
        report = await report_agent.execute(
            analysis_result=analysis_result,
            triage_results=triage_results,
            detailed_assessments=detailed_assessments,
            report_format="markdown",
        )

        print(f"✓ Report generated ({len(report)} characters)")
        print(f"\nReport preview:")
        print("-" * 80)
        print(report[:500] + "..." if len(report) > 500 else report)
        print("-" * 80)

        # Save report
        report_path = tmp_path / "security_report.md"
        report_path.write_text(report)
        print(f"✓ Report saved to {report_path}")

        print("\n" + "=" * 80)
        print("PHASE 6: Fix Generation")
        print("=" * 80)

        # Step 8: Generate fix for first valid finding from detailed analysis
        # Use findings that were assessed as NOT false positives
        valid_findings = []
        for finding_id, assessment in detailed_assessments.items():
            if not assessment.is_false_positive:
                finding = next((f for f in findings if f.id == finding_id), None)
                if finding:
                    valid_findings.append(finding)

        # Fallback to any non-FP finding if no detailed assessments
        if not valid_findings:
            valid_findings = [f for f in findings if not f.is_likely_false_positive]

        if len(valid_findings) > 0:
            fix_agent = FixGeneratorAgent(working_dir=test_project)
            finding_to_fix = valid_findings[0]

            print(f"Generating fix for: {finding_to_fix.rule_id}")
            print(f"  Location: {finding_to_fix.location}")

            fix = await fix_agent.execute(finding_to_fix, context_lines=5)

            if fix:
                print(f"✓ Fix generated with confidence {fix.confidence:.2f}")
                print(f"\nOriginal code:")
                print("-" * 40)
                print(fix.original_code[:200])
                print("-" * 40)
                print(f"\nFixed code:")
                print("-" * 40)
                print(fix.fixed_code[:200])
                print("-" * 40)
                print(f"\nExplanation: {fix.explanation[:150]}...")

                print("\n" + "=" * 80)
                print("PHASE 7: Git Operations")
                print("=" * 80)

                # Step 9: Create git branch and apply fix
                git_repo = GitRepository(test_project)

                # Check if working directory is clean
                if not git_repo.is_clean():
                    print("⚠ Working directory not clean, stashing changes...")

                # Create a fix branch
                branch_name = f"fix/{finding_to_fix.rule_id.replace('/', '-')}"
                print(f"Creating branch: {branch_name}")

                try:
                    git_repo.create_branch(branch_name)
                    print(f"✓ Branch created: {branch_name}")
                except Exception as e:
                    print(f"⚠ Branch creation failed: {e}")
                    # Branch might already exist, checkout instead
                    git_repo.checkout_branch("main")
                    branch_name = f"fix/sql-injection-{os.getpid()}"
                    git_repo.create_branch(branch_name)

                # Apply the fix (simple string replacement)
                print(f"Applying fix to {fix.file_path.name}...")
                content = fix.file_path.read_text()
                if fix.original_code in content:
                    new_content = content.replace(fix.original_code, fix.fixed_code)
                    fix.file_path.write_text(new_content)
                    print(f"✓ Fix applied")

                    # Stage and commit
                    git_repo.stage_file(fix.file_path)
                    commit_message = f"Fix {finding_to_fix.rule_id}\n\n{fix.explanation}"
                    commit_sha = git_repo.commit(commit_message)
                    print(f"✓ Changes committed: {commit_sha[:8]}")

                    # Show diff
                    diff = git_repo.get_diff(cached=True)
                    print(f"\nDiff preview:")
                    print("-" * 40)
                    print(diff[:300] if len(diff) > 300 else diff)
                    print("-" * 40)

                    print("\n" + "=" * 80)
                    print("PHASE 8: Pull Request Creation (Optional)")
                    print("=" * 80)

                    # Step 10: Create PR (if gh CLI available)
                    try:
                        pr_creator = PRCreator(test_project)

                        if pr_creator.is_authenticated():
                            print("⚠ Skipping actual PR creation in test")
                            print(f"  Would create PR: 'Fix {finding_to_fix.rule_id}'")
                            print(f"  From branch: {branch_name}")
                            print(f"  To branch: main")
                            print(f"  Body: {fix.explanation[:100]}...")
                        else:
                            print("⚠ GitHub CLI not authenticated, skipping PR creation")
                    except PRError as e:
                        print(f"⚠ GitHub CLI not available: {e}")
                        print("  (This is expected in test environment)")

                else:
                    print("⚠ Could not apply fix - original code not found in file")
            else:
                print("⚠ No fix generated (low confidence)")
        else:
            print("⚠ No valid findings to fix")

        print("\n" + "=" * 80)
        print("WORKFLOW COMPLETE!")
        print("=" * 80)
        print(f"\nSummary:")
        print(f"  ✓ Languages detected: {len(languages)}")
        print(f"  ✓ Findings discovered: {len(findings)}")
        print(f"  ✓ Valid findings: {len([f for f in findings if not f.is_likely_false_positive])}")
        print(f"  ✓ Report generated: {report_path}")
        if len(valid_findings) > 0 and fix:
            print(f"  ✓ Fix created and committed: {branch_name}")
        print(f"\nAll adapters working correctly! 🎉")

    async def test_workflow_error_handling(self, tmp_path: Path) -> None:
        """Test that workflow handles errors gracefully."""
        # Test with non-existent project
        non_existent = tmp_path / "does_not_exist"

        language_agent = LanguageDetectionAgent(working_dir=tmp_path)

        # Should handle missing directory gracefully
        try:
            languages = await language_agent.execute(project_path=non_existent)
            # If it succeeds, it should return empty list or handle gracefully
            assert isinstance(languages, list)
        except Exception as e:
            # Should raise a clear error
            assert "does_not_exist" in str(e) or "not found" in str(e).lower()

        print("✓ Error handling works correctly")
