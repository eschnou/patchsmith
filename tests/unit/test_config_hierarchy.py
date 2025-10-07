"""Tests for configuration hierarchy and loading."""

import tempfile
from pathlib import Path

import pytest
from patchsmith.core.config import (
    ConfigError,
    ensure_initialized,
    load_config,
    validate_config,
)
from patchsmith.models.config import PatchsmithConfig


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_from_explicit_path(self) -> None:
        """Test loading config from explicitly provided path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create and save config
            config = PatchsmithConfig.create_default(Path.cwd(), "test")
            config.save(config_path)

            # Load from explicit path
            loaded = load_config(config_path=config_path)

            assert loaded.project.name == "test"

    def test_load_config_from_current_directory(self) -> None:
        """Test loading config from current directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            config_dir = tmppath / ".patchsmith"
            config_dir.mkdir()
            config_path = config_dir / "config.json"

            # Create and save config
            config = PatchsmithConfig.create_default(tmppath, "test")
            config.save(config_path)

            # Load from current directory
            loaded = load_config(project_root=tmppath)

            assert loaded.project.name == "test"

    def test_load_config_searches_parent_directories(self) -> None:
        """Test that config loading searches parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create config in root
            config_dir = tmppath / ".patchsmith"
            config_dir.mkdir()
            config_path = config_dir / "config.json"

            config = PatchsmithConfig.create_default(tmppath, "test")
            config.save(config_path)

            # Create subdirectory
            subdir = tmppath / "src" / "module"
            subdir.mkdir(parents=True)

            # Load from subdirectory should find parent config
            loaded = load_config(project_root=subdir)

            assert loaded.project.name == "test"

    def test_load_config_raises_error_if_not_found(self) -> None:
        """Test that loading config raises error if not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ConfigError, match="Configuration file not found"):
                load_config(project_root=Path(tmpdir))

    def test_load_config_raises_error_on_invalid_json(self) -> None:
        """Test that loading config raises error on invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text("invalid json{")

            with pytest.raises(ConfigError, match="Failed to load configuration"):
                load_config(config_path=config_path)


class TestEnvOverrides:
    """Tests for environment variable overrides."""

    def test_env_override_llm_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test PATCHSMITH_MODEL environment variable override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            config = PatchsmithConfig.create_default(Path.cwd(), "test")
            config.save(config_path)

            # Set environment variable
            monkeypatch.setenv("PATCHSMITH_MODEL", "custom-model")

            loaded = load_config(config_path=config_path)

            assert loaded.llm.model == "custom-model"

    def test_env_override_temperature(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test PATCHSMITH_TEMPERATURE environment variable override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            config = PatchsmithConfig.create_default(Path.cwd(), "test")
            config.save(config_path)

            monkeypatch.setenv("PATCHSMITH_TEMPERATURE", "0.8")

            loaded = load_config(config_path=config_path)

            assert loaded.llm.temperature == 0.8

    def test_env_override_min_severity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test PATCHSMITH_MIN_SEVERITY environment variable override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            config = PatchsmithConfig.create_default(Path.cwd(), "test")
            config.save(config_path)

            monkeypatch.setenv("PATCHSMITH_MIN_SEVERITY", "HIGH")

            loaded = load_config(config_path=config_path)

            assert loaded.analysis.min_severity == "high"

    def test_env_override_filter_false_positives(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test PATCHSMITH_FILTER_FALSE_POSITIVES environment variable override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            config = PatchsmithConfig.create_default(Path.cwd(), "test")
            config.save(config_path)

            # Test various true values
            for value in ["true", "1", "yes"]:
                monkeypatch.setenv("PATCHSMITH_FILTER_FALSE_POSITIVES", value)
                loaded = load_config(config_path=config_path)
                assert loaded.analysis.filter_false_positives is True

            # Test various false values
            for value in ["false", "0", "no"]:
                monkeypatch.setenv("PATCHSMITH_FILTER_FALSE_POSITIVES", value)
                loaded = load_config(config_path=config_path)
                assert loaded.analysis.filter_false_positives is False

    def test_env_override_invalid_values_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that invalid environment variable values are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            config = PatchsmithConfig.create_default(Path.cwd(), "test")
            original_temp = config.llm.temperature
            config.save(config_path)

            # Set invalid temperature
            monkeypatch.setenv("PATCHSMITH_TEMPERATURE", "invalid")

            loaded = load_config(config_path=config_path)

            # Should keep original value
            assert loaded.llm.temperature == original_temp


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_validate_valid_config(self) -> None:
        """Test validation of valid config returns no issues."""
        config = PatchsmithConfig.create_default(Path.cwd(), "test")
        config.project.languages = ["python", "javascript"]

        issues = validate_config(config)

        assert len(issues) == 0

    def test_validate_nonexistent_project_root(self) -> None:
        """Test validation detects nonexistent project root."""
        config = PatchsmithConfig.create_default(Path("/nonexistent/path"), "test")

        issues = validate_config(config)

        assert len(issues) > 0
        assert any("Project root does not exist" in issue for issue in issues)

    def test_validate_unsupported_language(self) -> None:
        """Test validation detects unsupported languages."""
        config = PatchsmithConfig.create_default(Path.cwd(), "test")
        config.project.languages = ["python", "unsupported_lang"]

        issues = validate_config(config)

        assert len(issues) > 0
        assert any("Unsupported language" in issue for issue in issues)


class TestEnsureInitialized:
    """Tests for ensure_initialized function."""

    def test_ensure_initialized_succeeds_when_config_exists(self) -> None:
        """Test ensure_initialized succeeds when config exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            config_dir = tmppath / ".patchsmith"
            config_dir.mkdir()
            config_path = config_dir / "config.json"

            config = PatchsmithConfig.create_default(tmppath, "test")
            config.save(config_path)

            # Should not raise
            ensure_initialized(tmppath)

    def test_ensure_initialized_raises_when_not_initialized(self) -> None:
        """Test ensure_initialized raises error when not initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ConfigError, match="Project is not initialized"):
                ensure_initialized(Path(tmpdir))
