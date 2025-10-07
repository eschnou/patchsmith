"""Tests for project models."""

from pathlib import Path

import pytest
from patchsmith.models.project import LanguageDetection, ProjectInfo


class TestLanguageDetection:
    """Tests for LanguageDetection model."""

    def test_create_language_detection(self) -> None:
        """Test creating a language detection."""
        lang = LanguageDetection(
            name="Python", confidence=0.95, evidence=["*.py files", "requirements.txt"]
        )

        assert lang.name == "python"  # Normalized to lowercase
        assert lang.confidence == 0.95
        assert len(lang.evidence) == 2

    def test_confidence_must_be_between_zero_and_one(self) -> None:
        """Test confidence validation."""
        with pytest.raises(ValueError):
            LanguageDetection(name="python", confidence=1.5)

        with pytest.raises(ValueError):
            LanguageDetection(name="python", confidence=-0.1)

    def test_language_name_normalized(self) -> None:
        """Test language name is normalized to lowercase."""
        lang = LanguageDetection(name="JavaScript", confidence=0.9)
        assert lang.name == "javascript"


class TestProjectInfo:
    """Tests for ProjectInfo model."""

    def test_create_project_info(self) -> None:
        """Test creating project info."""
        project = ProjectInfo(
            name="test_project",
            root=Path.cwd(),
            languages=[
                LanguageDetection(name="python", confidence=0.95),
                LanguageDetection(name="javascript", confidence=0.8),
            ],
        )

        assert project.name == "test_project"
        assert project.root.is_absolute()
        assert len(project.languages) == 2

    def test_get_language_names(self) -> None:
        """Test getting list of language names."""
        project = ProjectInfo(
            name="test",
            root=Path.cwd(),
            languages=[
                LanguageDetection(name="python", confidence=0.95),
                LanguageDetection(name="javascript", confidence=0.8),
            ],
        )

        names = project.get_language_names()

        assert names == ["python", "javascript"]

    def test_has_language(self) -> None:
        """Test checking if project has a language."""
        project = ProjectInfo(
            name="test",
            root=Path.cwd(),
            languages=[LanguageDetection(name="python", confidence=0.95)],
        )

        assert project.has_language("python") is True
        assert project.has_language("Python") is True  # Case insensitive
        assert project.has_language("javascript") is False

    def test_get_high_confidence_languages(self) -> None:
        """Test filtering languages by confidence threshold."""
        project = ProjectInfo(
            name="test",
            root=Path.cwd(),
            languages=[
                LanguageDetection(name="python", confidence=0.95),
                LanguageDetection(name="javascript", confidence=0.75),
                LanguageDetection(name="go", confidence=0.85),
            ],
        )

        high_conf = project.get_high_confidence_languages(threshold=0.8)

        assert set(high_conf) == {"python", "go"}

    def test_project_with_optional_fields(self) -> None:
        """Test project with description and repository URL."""
        project = ProjectInfo(
            name="test",
            root=Path.cwd(),
            description="A test project",
            repository_url="https://github.com/test/repo",
            custom_queries=["queries/custom.ql"],
        )

        assert project.description == "A test project"
        assert project.repository_url == "https://github.com/test/repo"
        assert len(project.custom_queries) == 1
