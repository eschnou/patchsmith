"""Pydantic configuration models for Patchsmith."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class ProjectConfig(BaseModel):
    """Project-specific configuration."""

    name: str = Field(..., description="Project name")
    root: Path = Field(..., description="Project root directory")
    languages: list[str] = Field(default_factory=list, description="Detected languages")
    ignore_paths: list[str] = Field(
        default_factory=lambda: ["tests/", "test/", "node_modules/", "vendor/", ".git/"],
        description="Paths to ignore during analysis",
    )

    @field_validator("root")
    @classmethod
    def validate_root(cls, v: Path) -> Path:
        """Ensure root is an absolute path."""
        return v.resolve()

    @field_validator("languages")
    @classmethod
    def validate_languages(cls, v: list[str]) -> list[str]:
        """Normalize language names to lowercase."""
        return [lang.lower() for lang in v]


class CodeQLConfig(BaseModel):
    """CodeQL-specific configuration."""

    database_path: Path = Field(
        default=Path(".patchsmith/db"), description="Path to CodeQL databases"
    )
    query_paths: list[Path] = Field(
        default_factory=list, description="Paths to CodeQL query directories"
    )
    timeout: int = Field(
        default=3600, description="Query execution timeout in seconds", ge=60, le=7200
    )
    threads: int = Field(default=0, description="Number of threads for CodeQL (0 = auto)", ge=0)

    @field_validator("database_path", "query_paths", mode="before")
    @classmethod
    def resolve_paths(cls, v: Any) -> Any:
        """Resolve paths to absolute."""
        if isinstance(v, (str, Path)):
            return Path(v).resolve()
        elif isinstance(v, list):
            return [Path(p).resolve() for p in v]
        return v


class AnalysisConfig(BaseModel):
    """Analysis behavior configuration."""

    filter_false_positives: bool = Field(
        default=True, description="Enable LLM-based false positive filtering"
    )
    min_severity: str = Field(
        default="low",
        description="Minimum severity level to report (critical/high/medium/low/info)",
    )
    max_results: int = Field(
        default=1000, description="Maximum number of results to process", ge=1, le=10000
    )
    batch_size: int = Field(
        default=5, description="Batch size for concurrent LLM calls", ge=1, le=20
    )

    @field_validator("min_severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        """Validate severity level."""
        allowed = ["critical", "high", "medium", "low", "info"]
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(f"Severity must be one of {allowed}, got '{v}'")
        return v_lower


class LLMConfig(BaseModel):
    """LLM configuration."""

    model: str = Field(default="claude-sonnet-4-5-20251022", description="Claude model to use")
    temperature: float = Field(default=0.2, description="Temperature for LLM calls", ge=0.0, le=1.0)
    max_tokens: int = Field(
        default=4000, description="Maximum tokens per LLM call", ge=100, le=8000
    )
    timeout: int = Field(default=120, description="LLM API timeout in seconds", ge=10, le=300)
    max_retries: int = Field(default=3, description="Maximum retry attempts", ge=1, le=10)


class GitConfig(BaseModel):
    """Git configuration."""

    remote: str = Field(default="origin", description="Git remote name")
    base_branch: str = Field(default="main", description="Base branch for PRs")
    create_prs: bool = Field(default=True, description="Automatically create pull requests")
    commit_message_suffix: str = Field(
        default="\n\n🤖 Generated with [Patchsmith](https://github.com/patchsmith)\n\nCo-Authored-By: Patchsmith <noreply@patchsmith.dev>",
        description="Suffix to add to commit messages",
    )


class PatchsmithConfig(BaseModel):
    """Root configuration for Patchsmith."""

    version: str = Field(default="1.0", description="Config version")
    project: ProjectConfig
    codeql: CodeQLConfig = Field(default_factory=CodeQLConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    git: GitConfig = Field(default_factory=GitConfig)
    initialized_at: datetime = Field(default_factory=datetime.now)
    last_analysis: Optional[datetime] = None

    model_config = {"json_encoders": {Path: str, datetime: lambda v: v.isoformat()}}

    def save(self, path: Path) -> None:
        """
        Save configuration to JSON file.

        Args:
            path: Path to save configuration file
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict with proper serialization
        config_dict = self.model_dump(mode="json")

        # Handle datetime serialization
        def serialize_datetime(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, Path):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: serialize_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_datetime(item) for item in obj]
            return obj

        config_dict = serialize_datetime(config_dict)

        with open(path, "w") as f:
            json.dump(config_dict, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "PatchsmithConfig":
        """
        Load configuration from JSON file.

        Args:
            path: Path to configuration file

        Returns:
            Loaded PatchsmithConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path) as f:
            config_dict = json.load(f)

        # Parse datetime fields
        if "initialized_at" in config_dict and isinstance(config_dict["initialized_at"], str):
            config_dict["initialized_at"] = datetime.fromisoformat(config_dict["initialized_at"])

        if "last_analysis" in config_dict and config_dict["last_analysis"]:
            if isinstance(config_dict["last_analysis"], str):
                config_dict["last_analysis"] = datetime.fromisoformat(config_dict["last_analysis"])

        return cls(**config_dict)

    @classmethod
    def create_default(
        cls, project_root: Path, project_name: Optional[str] = None
    ) -> "PatchsmithConfig":
        """
        Create a default configuration.

        Args:
            project_root: Root directory of the project
            project_name: Optional project name, defaults to directory name

        Returns:
            Default PatchsmithConfig instance
        """
        if project_name is None:
            project_name = project_root.name

        return cls(
            project=ProjectConfig(
                name=project_name,
                root=project_root,
            )
        )
