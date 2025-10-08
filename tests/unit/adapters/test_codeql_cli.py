"""Tests for CodeQL CLI wrapper."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from patchsmith.adapters.codeql.cli import CodeQLCLI, CodeQLError


class TestCodeQLCLI:
    """Tests for CodeQLCLI class."""

    @patch("subprocess.run")
    def test_initialization_success(self, mock_run: Mock) -> None:
        """Test successful initialization with version check."""
        version_info = {"version": "2.15.3", "features": {}}
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(version_info),
            stderr="",
        )

        cli = CodeQLCLI()

        assert cli.codeql_path == "codeql"
        assert cli.version_info["version"] == "2.15.3"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_initialization_custom_path(self, mock_run: Mock) -> None:
        """Test initialization with custom CodeQL path."""
        version_info = {"version": "2.15.3"}
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(version_info),
            stderr="",
        )

        cli = CodeQLCLI(codeql_path="/custom/path/codeql")

        assert cli.codeql_path == "/custom/path/codeql"

    @patch("subprocess.run")
    def test_initialization_codeql_not_found(self, mock_run: Mock) -> None:
        """Test initialization fails when CodeQL is not installed."""
        mock_run.side_effect = FileNotFoundError("codeql not found")

        with pytest.raises(CodeQLError, match="CodeQL executable not found"):
            CodeQLCLI()

    @patch("subprocess.run")
    def test_initialization_invalid_json(self, mock_run: Mock) -> None:
        """Test initialization fails with invalid JSON response."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="not valid json",
            stderr="",
        )

        with pytest.raises(CodeQLError, match="Failed to parse CodeQL version"):
            CodeQLCLI()

    @patch("subprocess.run")
    def test_get_version(self, mock_run: Mock) -> None:
        """Test getting CodeQL version."""
        version_info = {"version": "2.15.3"}
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(version_info),
            stderr="",
        )

        cli = CodeQLCLI()
        version = cli.get_version()

        assert version == "2.15.3"

    @patch("subprocess.run")
    def test_run_command_success(self, mock_run: Mock) -> None:
        """Test successful command execution."""
        # First call for initialization
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        # Second call for actual command
        mock_run.return_value = Mock(
            returncode=0,
            stdout="command output",
            stderr="",
        )

        result = cli._run(["test", "command"])

        assert result.returncode == 0
        assert result.stdout == "command output"

    @patch("subprocess.run")
    def test_run_command_failure(self, mock_run: Mock) -> None:
        """Test command execution failure."""
        # First call for initialization
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        # Second call fails
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["codeql", "test"],
            stderr="Error message",
        )

        with pytest.raises(CodeQLError, match="CodeQL command failed"):
            cli._run(["test", "command"])

    @patch("subprocess.run")
    def test_run_command_timeout(self, mock_run: Mock) -> None:
        """Test command timeout."""
        # First call for initialization
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        # Second call times out
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["codeql", "test"],
            timeout=10,
        )

        with pytest.raises(CodeQLError, match="timed out"):
            cli._run(["test", "command"], timeout=10)

    @patch("subprocess.run")
    def test_run_command_with_cwd(self, mock_run: Mock) -> None:
        """Test command execution with custom working directory."""
        # First call for initialization
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        # Second call with cwd
        mock_run.return_value = Mock(
            returncode=0,
            stdout="output",
            stderr="",
        )

        cwd = Path("/custom/dir")
        cli._run(["test"], cwd=cwd)

        # Check that subprocess.run was called with cwd
        call_args = mock_run.call_args
        assert call_args.kwargs["cwd"] == cwd

    @patch("subprocess.run")
    def test_check_database_exists_true(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test checking for existing database."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        # Create a fake database directory with marker file
        db_path = tmp_path / "test-db"
        db_path.mkdir()
        (db_path / "codeql-database.yml").write_text("# Database metadata")

        assert cli.check_database_exists(db_path) is True

    @patch("subprocess.run")
    def test_check_database_exists_false(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test checking for non-existent database."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        db_path = tmp_path / "nonexistent-db"

        assert cli.check_database_exists(db_path) is False

    @patch("subprocess.run")
    def test_check_database_exists_invalid(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test checking for invalid database (directory exists but no marker file)."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        # Create directory but no marker file
        db_path = tmp_path / "invalid-db"
        db_path.mkdir()

        assert cli.check_database_exists(db_path) is False


class TestCodeQLDatabase:
    """Tests for CodeQL database operations."""

    @patch("subprocess.run")
    def test_create_database_success(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test successful database creation."""
        # First call for initialization
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        # Create source directory
        source_root = tmp_path / "source"
        source_root.mkdir()
        (source_root / "test.py").write_text("print('hello')")

        db_path = tmp_path / "db" / "python"

        # Second call for database creation
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        cli.create_database(source_root, db_path, "python")

        # Verify database creation was called
        call_args = mock_run.call_args_list[-1]
        cmd = call_args[0][0]
        assert "database" in cmd
        assert "create" in cmd
        assert str(db_path) in cmd
        assert "--language=python" in cmd
        assert f"--source-root={source_root}" in cmd

    @patch("subprocess.run")
    def test_create_database_with_threads(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test database creation with custom thread count."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        source_root = tmp_path / "source"
        source_root.mkdir()
        db_path = tmp_path / "db"

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        cli.create_database(source_root, db_path, "python", threads=4)

        call_args = mock_run.call_args_list[-1]
        cmd = call_args[0][0]
        assert "--threads=4" in cmd

    @patch("subprocess.run")
    def test_create_database_source_not_exists(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test database creation fails when source doesn't exist."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        source_root = tmp_path / "nonexistent"
        db_path = tmp_path / "db"

        with pytest.raises(CodeQLError, match="Source root does not exist"):
            cli.create_database(source_root, db_path, "python")

    @patch("subprocess.run")
    def test_create_database_source_not_directory(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test database creation fails when source is not a directory."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        # Create a file, not a directory
        source_root = tmp_path / "file.py"
        source_root.write_text("code")
        db_path = tmp_path / "db"

        with pytest.raises(CodeQLError, match="Source root is not a directory"):
            cli.create_database(source_root, db_path, "python")

    @patch("subprocess.run")
    def test_create_database_already_exists_no_overwrite(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test database creation skips if database exists and no overwrite."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        source_root = tmp_path / "source"
        source_root.mkdir()

        # Create existing database
        db_path = tmp_path / "db"
        db_path.mkdir()
        (db_path / "codeql-database.yml").write_text("existing")

        # Should return early without calling subprocess again
        initial_call_count = mock_run.call_count
        cli.create_database(source_root, db_path, "python", overwrite=False)

        # Verify no additional subprocess call was made
        assert mock_run.call_count == initial_call_count

    @patch("subprocess.run")
    def test_create_database_overwrite(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test database creation with overwrite flag."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        source_root = tmp_path / "source"
        source_root.mkdir()

        # Create existing database
        db_path = tmp_path / "db"
        db_path.mkdir()
        (db_path / "codeql-database.yml").write_text("existing")

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        cli.create_database(source_root, db_path, "python", overwrite=True)

        # Verify --overwrite was passed
        call_args = mock_run.call_args_list[-1]
        cmd = call_args[0][0]
        assert "--overwrite" in cmd

    @patch("subprocess.run")
    def test_create_database_failure(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test database creation handles failures."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        source_root = tmp_path / "source"
        source_root.mkdir()
        db_path = tmp_path / "db"

        # Fail on database creation
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["codeql", "database", "create"],
            stderr="Database creation failed",
        )

        with pytest.raises(CodeQLError, match="CodeQL command failed"):
            cli.create_database(source_root, db_path, "python")


class TestCodeQLQueryExecution:
    """Tests for CodeQL query execution."""

    @patch("subprocess.run")
    def test_run_queries_success(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test successful query execution."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        # Create fake database
        db_path = tmp_path / "db"
        db_path.mkdir()
        (db_path / "codeql-database.yml").write_text("metadata")

        # Create fake query file
        query_path = tmp_path / "test.ql"
        query_path.write_text("select 1")

        # Mock query execution
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result_path = cli.run_queries(db_path, query_path)

        # Verify command was called
        call_args = mock_run.call_args_list[-1]
        cmd = call_args[0][0]
        assert "database" in cmd
        assert "analyze" in cmd
        assert str(db_path) in cmd
        assert str(query_path) in cmd
        assert "--format=sarif-latest" in cmd
        assert "--rerun" in cmd

        # Verify result path
        assert result_path.suffix == ".sarif"

    @patch("subprocess.run")
    def test_run_queries_custom_output(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test query execution with custom output path."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        db_path = tmp_path / "db"
        db_path.mkdir()
        (db_path / "codeql-database.yml").write_text("metadata")

        query_path = tmp_path / "test.ql"
        query_path.write_text("select 1")

        custom_output = tmp_path / "custom" / "results.sarif"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result_path = cli.run_queries(db_path, query_path, output_path=custom_output)

        assert result_path == custom_output
        assert custom_output.parent.exists()  # Directory created

    @patch("subprocess.run")
    def test_run_queries_csv_format(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test query execution with CSV output format."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        db_path = tmp_path / "db"
        db_path.mkdir()
        (db_path / "codeql-database.yml").write_text("metadata")

        query_path = tmp_path / "test.ql"
        query_path.write_text("select 1")

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result_path = cli.run_queries(db_path, query_path, output_format="csv")

        call_args = mock_run.call_args_list[-1]
        cmd = call_args[0][0]
        assert "--format=csv" in cmd
        assert result_path.suffix == ".csv"

    @patch("subprocess.run")
    def test_run_queries_with_threads(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test query execution with custom thread count."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        db_path = tmp_path / "db"
        db_path.mkdir()
        (db_path / "codeql-database.yml").write_text("metadata")

        query_path = tmp_path / "test.ql"
        query_path.write_text("select 1")

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        cli.run_queries(db_path, query_path, threads=4)

        call_args = mock_run.call_args_list[-1]
        cmd = call_args[0][0]
        assert "--threads=4" in cmd

    @patch("subprocess.run")
    def test_run_queries_database_not_exists(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test query execution fails when database doesn't exist."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        db_path = tmp_path / "nonexistent-db"
        query_path = tmp_path / "test.ql"
        query_path.write_text("select 1")

        with pytest.raises(CodeQLError, match="Database does not exist"):
            cli.run_queries(db_path, query_path)

    @patch("subprocess.run")
    def test_run_queries_query_not_exists(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test query execution fails when query doesn't exist."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        db_path = tmp_path / "db"
        db_path.mkdir()
        (db_path / "codeql-database.yml").write_text("metadata")

        query_path = tmp_path / "nonexistent.ql"

        with pytest.raises(CodeQLError, match="Query path does not exist"):
            cli.run_queries(db_path, query_path)

    @patch("subprocess.run")
    def test_run_queries_execution_failure(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test query execution handles failures."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        db_path = tmp_path / "db"
        db_path.mkdir()
        (db_path / "codeql-database.yml").write_text("metadata")

        query_path = tmp_path / "test.ql"
        query_path.write_text("select 1")

        # Fail on query execution
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["codeql", "database", "analyze"],
            stderr="Query execution failed",
        )

        with pytest.raises(CodeQLError, match="CodeQL command failed"):
            cli.run_queries(db_path, query_path)

    @patch("subprocess.run")
    def test_get_extension_for_format(self, mock_run: Mock) -> None:
        """Test file extension mapping for different formats."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        assert cli._get_extension_for_format("sarif-latest") == "sarif"
        assert cli._get_extension_for_format("sarifv2.1.0") == "sarif"
        assert cli._get_extension_for_format("csv") == "csv"
        assert cli._get_extension_for_format("json") == "json"
        assert cli._get_extension_for_format("text") == "txt"
        assert cli._get_extension_for_format("unknown") == "unknown"

    @patch("subprocess.run")
    def test_delete_database_success(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test successful database deletion."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        # Create a database directory
        db_path = tmp_path / "db"
        db_path.mkdir()
        (db_path / "test.txt").write_text("test")

        # Delete it
        cli.delete_database(db_path)

        # Verify it's gone
        assert not db_path.exists()

    @patch("subprocess.run")
    def test_delete_database_not_exists(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test deleting non-existent database (should not raise)."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        # Try to delete non-existent database
        nonexistent = tmp_path / "nonexistent"

        # Should not raise an error
        cli.delete_database(nonexistent)

    @patch("subprocess.run")
    def test_get_database_info_success(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test getting database information."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        # Create a database with metadata
        db_path = tmp_path / "db"
        db_path.mkdir()
        db_yml = db_path / "codeql-database.yml"
        db_yml.write_text("""
name: test-db
primaryLanguage: python
creationMetadata:
  creationTime: 2024-01-01T00:00:00Z
""")

        info = cli.get_database_info(db_path)

        assert info["name"] == "test-db"
        assert info["language"] == "python"
        assert "2024-01-01" in info["created"]

    @patch("subprocess.run")
    def test_get_database_info_not_exists(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test getting info for non-existent database."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(CodeQLError, match="does not exist"):
            cli.get_database_info(nonexistent)

    @patch("subprocess.run")
    def test_get_database_info_missing_metadata(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test getting info when metadata file is missing."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        # Create database without metadata
        db_path = tmp_path / "db"
        db_path.mkdir()
        (db_path / "codeql-database.yml").touch()  # Create marker but no metadata

        with pytest.raises(CodeQLError, match="metadata file missing"):
            cli.get_database_info(db_path)

    @patch("subprocess.run")
    def test_upgrade_database_success(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test successful database upgrade."""
        # First call: get version
        # Second call: check database exists
        # Third call: upgrade database
        mock_run.side_effect = [
            Mock(
                returncode=0,
                stdout=json.dumps({"version": "2.15.3"}),
                stderr="",
            ),
            Mock(returncode=0, stdout="", stderr=""),  # upgrade command
        ]

        cli = CodeQLCLI()

        # Create a database
        db_path = tmp_path / "db"
        db_path.mkdir()
        (db_path / "codeql-database.yml").write_text("metadata")

        cli.upgrade_database(db_path)

        # Verify upgrade command was called
        upgrade_call = mock_run.call_args_list[1]
        assert "database" in upgrade_call[0][0]
        assert "upgrade" in upgrade_call[0][0]

    @patch("subprocess.run")
    def test_upgrade_database_not_exists(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test upgrading non-existent database."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"version": "2.15.3"}),
            stderr="",
        )
        cli = CodeQLCLI()

        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(CodeQLError, match="does not exist"):
            cli.upgrade_database(nonexistent)

    @patch("subprocess.run")
    def test_upgrade_database_fails(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test database upgrade failure."""
        # Fail on upgrade command
        mock_run.side_effect = [
            Mock(
                returncode=0,
                stdout=json.dumps({"version": "2.15.3"}),
                stderr="",
            ),
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["codeql", "database", "upgrade"],
                stderr="Upgrade failed",
            ),
        ]

        cli = CodeQLCLI()

        db_path = tmp_path / "db"
        db_path.mkdir()
        (db_path / "codeql-database.yml").write_text("metadata")

        with pytest.raises(CodeQLError, match="CodeQL command failed"):
            cli.upgrade_database(db_path)
