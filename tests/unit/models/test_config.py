"""Unit tests for configuration models."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from patchsmith.models.config import (
    AnalysisConfig,
    CodeQLConfig,
    GitConfig,
    LLMConfig,
    PatchsmithConfig,
    ProjectConfig,
)


class TestProjectConfig:
    """Tests for ProjectConfig model."""

    def test_create_valid_project_config(self) -> None:
        """Test creating a valid project configuration."""
        config = ProjectConfig(name="test_project", root=Path.cwd(), languages=["python"])

        assert config.name == "test_project"
        assert config.root.is_absolute()
        assert config.languages == ["python"]
        assert "node_modules/" in config.ignore_paths

    def test_languages_normalized_to_lowercase(self) -> None:
        """Test that language names are normalized to lowercase."""
        config = ProjectConfig(name="test", root=Path.cwd(), languages=["Python", "JavaScript"])

        assert config.languages == ["python", "javascript"]

    def test_root_path_resolved_to_absolute(self) -> None:
        """Test that root path is converted to absolute."""
        config = ProjectConfig(name="test", root=Path("."), languages=[])

        assert config.root.is_absolute()


class TestCodeQLConfig:
    """Tests for CodeQLConfig model."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = CodeQLConfig()

        assert config.database_path == Path(".patchsmith/db")
        assert config.query_paths == []
        assert config.timeout == 3600
        assert config.threads == 0

    def test_timeout_validation(self) -> None:
        """Test timeout must be within valid range."""
        with pytest.raises(ValueError):
            CodeQLConfig(timeout=30)  # Too low

        with pytest.raises(ValueError):
            CodeQLConfig(timeout=10000)  # Too high


class TestAnalysisConfig:
    """Tests for AnalysisConfig model."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = AnalysisConfig()

        assert config.filter_false_positives is True
        assert config.min_severity == "low"
        assert config.max_results == 1000
        assert config.batch_size == 5

    def test_severity_validation(self) -> None:
        """Test severity level validation."""
        valid_severities = ["critical", "high", "medium", "low", "info"]

        for severity in valid_severities:
            config = AnalysisConfig(min_severity=severity)
            assert config.min_severity == severity.lower()

        with pytest.raises(ValueError, match="Severity must be one of"):
            AnalysisConfig(min_severity="invalid")

    def test_severity_case_insensitive(self) -> None:
        """Test severity normalization is case-insensitive."""
        config = AnalysisConfig(min_severity="CRITICAL")
        assert config.min_severity == "critical"


class TestLLMConfig:
    """Tests for LLMConfig model."""

    def test_default_values(self) -> None:
        """Test default LLM configuration."""
        config = LLMConfig()

        assert config.model == "claude-sonnet-4-5-20251022"
        assert config.temperature == 0.2
        assert config.max_tokens == 4000
        assert config.timeout == 120
        assert config.max_retries == 3

    def test_temperature_validation(self) -> None:
        """Test temperature must be between 0 and 1."""
        with pytest.raises(ValueError):
            LLMConfig(temperature=-0.1)

        with pytest.raises(ValueError):
            LLMConfig(temperature=1.5)


class TestGitConfig:
    """Tests for GitConfig model."""

    def test_default_values(self) -> None:
        """Test default Git configuration."""
        config = GitConfig()

        assert config.remote == "origin"
        assert config.base_branch == "main"
        assert config.create_prs is True
        assert "Patchsmith" in config.commit_message_suffix


class TestPatchsmithConfig:
    """Tests for root PatchsmithConfig model."""

    def test_create_default_config(self) -> None:
        """Test creating a default configuration."""
        config = PatchsmithConfig.create_default(Path.cwd(), "test_project")

        assert config.project.name == "test_project"
        assert config.project.root == Path.cwd().resolve()
        assert config.version == "1.0"
        assert config.last_analysis is None
        assert isinstance(config.initialized_at, datetime)

    def test_create_default_uses_directory_name(self) -> None:
        """Test that create_default uses directory name if no name provided."""
        config = PatchsmithConfig.create_default(Path.cwd())

        assert config.project.name == Path.cwd().name

    def test_save_and_load_config(self) -> None:
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create and save
            original = PatchsmithConfig.create_default(Path.cwd(), "test_project")
            original.save(config_path)

            assert config_path.exists()

            # Load
            loaded = PatchsmithConfig.load(config_path)

            assert loaded.project.name == original.project.name
            assert loaded.project.root == original.project.root
            assert loaded.version == original.version
            assert loaded.initialized_at == original.initialized_at

    def test_load_nonexistent_file_raises_error(self) -> None:
        """Test loading non-existent config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            PatchsmithConfig.load(Path("/nonexistent/config.json"))

    def test_datetime_serialization(self) -> None:
        """Test datetime fields are properly serialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            config = PatchsmithConfig.create_default(Path.cwd(), "test")
            config.last_analysis = datetime.now()
            config.save(config_path)

            # Check JSON contains ISO format datetime
            with open(config_path) as f:
                data = json.load(f)

            assert isinstance(data["initialized_at"], str)
            assert "T" in data["initialized_at"]  # ISO format

            # Load and verify
            loaded = PatchsmithConfig.load(config_path)
            assert isinstance(loaded.initialized_at, datetime)
            assert isinstance(loaded.last_analysis, datetime)

    def test_path_serialization(self) -> None:
        """Test Path fields are properly serialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            config = PatchsmithConfig.create_default(Path.cwd(), "test")
            config.save(config_path)

            # Check JSON contains string paths
            with open(config_path) as f:
                data = json.load(f)

            assert isinstance(data["project"]["root"], str)

    def test_config_with_all_optional_fields(self) -> None:
        """Test configuration with all fields populated."""
        config = PatchsmithConfig(
            version="1.0",
            project=ProjectConfig(
                name="full_config_test",
                root=Path.cwd(),
                languages=["python", "javascript"],
                ignore_paths=["custom_ignore/"],
            ),
            codeql=CodeQLConfig(
                database_path=Path("/custom/db"), query_paths=[Path("/custom/queries")]
            ),
            analysis=AnalysisConfig(
                filter_false_positives=False, min_severity="high", max_results=500
            ),
            llm=LLMConfig(model="custom-model", temperature=0.5),
            git=GitConfig(remote="upstream", base_branch="develop"),
        )

        assert config.project.languages == ["python", "javascript"]
        assert config.codeql.database_path == Path("/custom/db").resolve()
        assert config.analysis.min_severity == "high"
        assert config.llm.model == "custom-model"
        assert config.git.remote == "upstream"
