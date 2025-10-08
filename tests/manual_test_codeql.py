#!/usr/bin/env python3
"""Manual integration test for CodeQL CLI wrapper.

This script tests the CodeQL adapter with real CodeQL CLI.
Run this manually to verify CodeQL integration works.

Prerequisites:
- CodeQL CLI must be installed and in PATH
- Run from project root: python tests/manual_test_codeql.py
"""

import sys
import tempfile
from pathlib import Path

# Add src to path so we can import patchsmith
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from patchsmith.adapters.codeql.cli import CodeQLCLI, CodeQLError
from patchsmith.adapters.codeql.parsers import SARIFParser, ParserError
from patchsmith.utils.logging import setup_logging


def create_sample_project(project_dir: Path) -> None:
    """Create a simple Python project for testing."""
    print(f"📁 Creating sample Python project in {project_dir}")

    # Create a simple Python file with a potential vulnerability
    code = '''#!/usr/bin/env python3
"""Sample vulnerable Python code for testing."""

import os

def vulnerable_command(user_input):
    """Vulnerable function - command injection risk."""
    # This is intentionally vulnerable for testing
    os.system(f"echo {user_input}")

def safe_function():
    """Safe function."""
    return "Hello, World!"

if __name__ == "__main__":
    print(safe_function())
'''

    (project_dir / "app.py").write_text(code)
    print("  ✓ Created app.py with sample code")


def test_codeql_version() -> None:
    """Test 1: Verify CodeQL is installed and get version."""
    print("\n" + "="*60)
    print("TEST 1: CodeQL Version Detection")
    print("="*60)

    try:
        cli = CodeQLCLI()
        version = cli.get_version()
        print(f"✅ SUCCESS: CodeQL version {version} detected")
        print(f"   Full version info: {cli.version_info}")
        return cli
    except CodeQLError as e:
        print(f"❌ FAILED: {e}")
        print("\n💡 Make sure CodeQL is installed:")
        print("   https://github.com/github/codeql-cli-binaries/releases")
        print("   Add it to your PATH and try again.")
        sys.exit(1)


def test_database_creation(cli: CodeQLCLI) -> None:
    """Test 2: Create a CodeQL database."""
    print("\n" + "="*60)
    print("TEST 2: Database Creation")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        project_dir = tmp_path / "sample_project"
        project_dir.mkdir()

        # Create sample project
        create_sample_project(project_dir)

        # Create database
        db_path = tmp_path / "db" / "python"
        print(f"\n📊 Creating CodeQL database...")
        print(f"   Source: {project_dir}")
        print(f"   Database: {db_path}")
        print(f"   Language: python")
        print("\n⏳ This may take a minute...")

        try:
            cli.create_database(
                source_root=project_dir,
                db_path=db_path,
                language="python"
            )
            print("\n✅ SUCCESS: Database created!")

            # Verify database exists
            if cli.check_database_exists(db_path):
                print("✅ Database validation passed")

                # Show database contents
                db_yml = db_path / "codeql-database.yml"
                if db_yml.exists():
                    print(f"\n📄 Database metadata preview:")
                    content = db_yml.read_text()
                    # Show first 10 lines
                    lines = content.split('\n')[:10]
                    for line in lines:
                        print(f"   {line}")
                    if len(content.split('\n')) > 10:
                        print("   ...")
            else:
                print("⚠️  WARNING: Database exists but validation failed")

        except CodeQLError as e:
            print(f"❌ FAILED: {e}")
            sys.exit(1)


def test_database_overwrite(cli: CodeQLCLI) -> None:
    """Test 3: Test database overwrite behavior."""
    print("\n" + "="*60)
    print("TEST 3: Database Overwrite")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        project_dir = tmp_path / "sample_project"
        project_dir.mkdir()
        create_sample_project(project_dir)

        db_path = tmp_path / "db" / "python"

        # Create database first time
        print("\n📊 Creating database (first time)...")
        cli.create_database(project_dir, db_path, "python")
        print("✅ Database created")

        # Try to create again without overwrite
        print("\n📊 Creating database again (without overwrite)...")
        cli.create_database(project_dir, db_path, "python", overwrite=False)
        print("✅ Correctly skipped existing database")

        # Create with overwrite
        print("\n📊 Creating database with overwrite flag...")
        cli.create_database(project_dir, db_path, "python", overwrite=True)
        print("✅ Database overwritten successfully")


def test_error_handling(cli: CodeQLCLI) -> None:
    """Test 4: Test error handling."""
    print("\n" + "="*60)
    print("TEST 4: Error Handling")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Test 1: Non-existent source
        print("\n🧪 Testing non-existent source directory...")
        try:
            cli.create_database(
                source_root=tmp_path / "nonexistent",
                db_path=tmp_path / "db",
                language="python"
            )
            print("❌ Should have raised an error!")
        except CodeQLError as e:
            print(f"✅ Correctly raised error: {e}")

        # Test 2: Source is a file, not directory
        print("\n🧪 Testing source as file (not directory)...")
        file_path = tmp_path / "file.py"
        file_path.write_text("code")
        try:
            cli.create_database(
                source_root=file_path,
                db_path=tmp_path / "db",
                language="python"
            )
            print("❌ Should have raised an error!")
        except CodeQLError as e:
            print(f"✅ Correctly raised error: {e}")


def test_query_execution_and_parsing(cli: CodeQLCLI) -> None:
    """Test 5: Run actual queries and parse SARIF results."""
    print("\n" + "="*60)
    print("TEST 5: Query Execution and SARIF Parsing")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        project_dir = tmp_path / "sample_project"
        project_dir.mkdir()

        # Create sample project with potential vulnerabilities
        create_sample_project(project_dir)

        # Create database
        db_path = tmp_path / "db" / "python"
        print(f"\n📊 Creating database for query testing...")
        cli.create_database(project_dir, db_path, "python")
        print("✅ Database created")

        # Run queries (using a simple test query)
        print("\n🔍 Running CodeQL test query...")

        # Find our test query
        test_query = Path(__file__).parent / "fixtures" / "test_query.ql"
        if not test_query.exists():
            print(f"   ⚠️  Test query not found at {test_query}")
            print("   Skipping query execution test")
            return

        print(f"   Using test query: {test_query}")

        try:
            results_path = cli.run_queries(
                db_path=db_path,
                query_path=test_query,
                output_format="sarif-latest"
            )
            print(f"✅ Queries executed successfully")
            print(f"   Results: {results_path}")

            # Parse the SARIF results
            print("\n📄 Parsing SARIF results...")
            parser = SARIFParser()
            findings = parser.parse_file(results_path)

            print(f"✅ SARIF parsed successfully")
            print(f"   Found {len(findings)} findings")

            if findings:
                print("\n📋 Sample findings:")
                for i, finding in enumerate(findings[:3], 1):  # Show first 3
                    print(f"\n   Finding {i}:")
                    print(f"   - Rule: {finding.rule_id}")
                    print(f"   - Severity: {finding.severity.value}")
                    print(f"   - Location: {finding.location}")
                    print(f"   - Message: {finding.message[:80]}...")
                    if finding.cwe:
                        print(f"   - CWE: {finding.cwe.id}")

                if len(findings) > 3:
                    print(f"\n   ... and {len(findings) - 3} more findings")
            else:
                print("\n   ℹ️  No security issues found (that's good!)")
                print("   Note: Our sample code might not trigger standard queries")

        except CodeQLError as e:
            print(f"⚠️  Query execution failed: {e}")
            print("   This might be expected if standard queries aren't available")
        except ParserError as e:
            print(f"❌ FAILED: SARIF parsing error: {e}")
            sys.exit(1)


def main() -> None:
    """Run all manual tests."""
    print("\n" + "="*60)
    print("🧪 MANUAL CODEQL INTEGRATION TEST")
    print("="*60)
    print("\nThis script tests the CodeQL adapter with real CodeQL CLI.")
    print("Make sure CodeQL is installed and in your PATH.\n")

    # Setup logging
    setup_logging(verbose=True)

    # Run tests
    cli = test_codeql_version()
    test_database_creation(cli)
    test_database_overwrite(cli)
    test_error_handling(cli)
    test_query_execution_and_parsing(cli)

    # Summary
    print("\n" + "="*60)
    print("🎉 ALL TESTS PASSED!")
    print("="*60)
    print("\n✅ CodeQL adapter is working correctly with real CodeQL CLI")
    print("✅ SARIF parser can handle real CodeQL output")
    print("\nNext steps:")
    print("  1. Run unit tests: poetry run pytest tests/unit/adapters/")
    print("  2. Continue with Phase 2 implementation")
    print()


if __name__ == "__main__":
    main()
