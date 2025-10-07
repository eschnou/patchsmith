"""Project-related domain models."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LanguageDetection(BaseModel):
    """Detected programming language with confidence."""

    name: str = Field(..., description="Language name (e.g., 'python', 'javascript')")
    confidence: float = Field(
        ..., description="Confidence score between 0.0 and 1.0", ge=0.0, le=1.0
    )
    evidence: list[str] = Field(default_factory=list, description="Evidence for language detection")

    @field_validator("name")
    @classmethod
    def normalize_language_name(cls, v: str) -> str:
        """Normalize language name to lowercase."""
        return v.lower()


class ProjectInfo(BaseModel):
    """Information about a project being analyzed."""

    name: str = Field(..., description="Project name")
    root: Path = Field(..., description="Project root directory")
    languages: list[LanguageDetection] = Field(
        default_factory=list, description="Detected languages"
    )
    description: Optional[str] = Field(None, description="Project description")
    repository_url: Optional[str] = Field(None, description="Repository URL if available")
    custom_queries: list[str] = Field(
        default_factory=list, description="Paths to custom CodeQL queries"
    )

    @field_validator("root")
    @classmethod
    def ensure_absolute_path(cls, v: Path) -> Path:
        """Ensure root path is absolute."""
        return v.resolve()

    def get_language_names(self) -> list[str]:
        """
        Get list of language names (without confidence scores).

        Returns:
            List of language names
        """
        return [lang.name for lang in self.languages]

    def has_language(self, language: str) -> bool:
        """
        Check if project has a specific language.

        Args:
            language: Language name to check

        Returns:
            True if language is detected
        """
        return language.lower() in [lang.name.lower() for lang in self.languages]

    def get_high_confidence_languages(self, threshold: float = 0.8) -> list[str]:
        """
        Get languages with confidence above threshold.

        Args:
            threshold: Minimum confidence threshold (default: 0.8)

        Returns:
            List of high-confidence language names
        """
        return [lang.name for lang in self.languages if lang.confidence >= threshold]
