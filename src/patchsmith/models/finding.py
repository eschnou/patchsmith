"""Security finding models."""

from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    """Security finding severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    def __str__(self) -> str:
        """String representation."""
        return self.value

    @classmethod
    def from_string(cls, value: str) -> "Severity":
        """
        Create Severity from string (case-insensitive).

        Args:
            value: Severity string

        Returns:
            Severity enum value

        Raises:
            ValueError: If value is not a valid severity
        """
        try:
            return cls(value.lower())
        except ValueError as e:
            valid = ", ".join([s.value for s in cls])
            raise ValueError(f"Invalid severity '{value}'. Must be one of: {valid}") from e


class CWE(BaseModel):
    """Common Weakness Enumeration identifier."""

    id: str = Field(..., description="CWE ID (e.g., 'CWE-89')")
    name: Optional[str] = Field(None, description="CWE name/description")

    @field_validator("id")
    @classmethod
    def validate_cwe_id(cls, v: str) -> str:
        """Validate CWE ID format."""
        v = v.upper()
        if not v.startswith("CWE-"):
            v = f"CWE-{v}"
        return v


class FalsePositiveScore(BaseModel):
    """False positive analysis result."""

    score: float = Field(
        ..., description="Confidence that this is a false positive (0.0-1.0)", ge=0.0, le=1.0
    )
    reasoning: str = Field(..., description="Explanation of the false positive assessment")
    is_false_positive: bool = Field(
        ..., description="Binary classification (true if likely false positive)"
    )

    @field_validator("is_false_positive", mode="before")
    @classmethod
    def derive_from_score(cls, v: Optional[bool], info: Any) -> bool:
        """Derive is_false_positive from score if not explicitly set."""
        if v is not None:
            return v
        # If score > 0.7, consider it a false positive
        if hasattr(info, "data") and "score" in info.data:
            return bool(info.data["score"] > 0.7)
        return False


class RiskType(str, Enum):
    """Security risk classification types."""

    EXTERNAL_PENTEST = "external_pentest"
    INTERNAL_ABUSE = "internal_abuse"
    SUPPLY_CHAIN = "supply_chain"
    CONFIGURATION = "configuration"
    DATA_EXPOSURE = "data_exposure"
    OTHER = "other"

    def __str__(self) -> str:
        """String representation."""
        return self.value


class DetailedSecurityAssessment(BaseModel):
    """Comprehensive security assessment of a finding."""

    finding_id: str = Field(..., description="ID of the finding being assessed")

    # False positive assessment
    is_false_positive: bool = Field(..., description="True if likely false positive")
    false_positive_score: float = Field(
        ..., description="Confidence score (0.0-1.0)", ge=0.0, le=1.0
    )
    false_positive_reasoning: str = Field(
        ..., description="Explanation for FP assessment"
    )

    # Security analysis
    attack_scenario: str = Field(
        ..., description="Description of how this vulnerability could be exploited"
    )
    risk_type: RiskType = Field(..., description="Classification of security risk")
    exploitability_score: float = Field(
        ..., description="How easily this can be exploited (0.0-1.0)", ge=0.0, le=1.0
    )
    impact_description: str = Field(
        ..., description="Description of potential impact if exploited"
    )
    remediation_priority: str = Field(
        ..., description="Priority level: immediate, high, medium, low"
    )

    @field_validator("remediation_priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        """Validate remediation priority is one of expected values."""
        valid = {"immediate", "high", "medium", "low"}
        if v.lower() not in valid:
            raise ValueError(f"Priority must be one of: {', '.join(valid)}")
        return v.lower()


class Finding(BaseModel):
    """A security vulnerability finding."""

    id: str = Field(..., description="Unique finding identifier")
    rule_id: str = Field(..., description="CodeQL rule/query ID")
    severity: Severity = Field(..., description="Finding severity")
    cwe: Optional[CWE] = Field(None, description="Associated CWE")

    file_path: Path = Field(..., description="File containing the finding")
    start_line: int = Field(..., description="Starting line number", ge=1)
    end_line: int = Field(..., description="Ending line number", ge=1)

    message: str = Field(..., description="Description of the finding")
    snippet: Optional[str] = Field(None, description="Code snippet")

    false_positive_score: Optional[FalsePositiveScore] = Field(
        None, description="False positive analysis result"
    )

    @field_validator("end_line")
    @classmethod
    def validate_line_range(cls, v: int, info: Any) -> int:
        """Ensure end_line >= start_line."""
        if hasattr(info, "data") and "start_line" in info.data and v < info.data["start_line"]:
            raise ValueError("end_line must be >= start_line")
        return v

    @property
    def location(self) -> str:
        """
        Get formatted location string.

        Returns:
            Location string (e.g., "src/main.py:42-45")
        """
        if self.start_line == self.end_line:
            return f"{self.file_path}:{self.start_line}"
        return f"{self.file_path}:{self.start_line}-{self.end_line}"

    @property
    def is_likely_false_positive(self) -> bool:
        """
        Check if finding is likely a false positive.

        Returns:
            True if false positive score indicates likely false positive
        """
        if self.false_positive_score is None:
            return False
        return self.false_positive_score.is_false_positive

    def get_severity_rank(self) -> int:
        """
        Get numeric rank for severity (higher = more severe).

        Returns:
            Severity rank (4=critical, 3=high, 2=medium, 1=low, 0=info)
        """
        severity_ranks = {
            Severity.CRITICAL: 4,
            Severity.HIGH: 3,
            Severity.MEDIUM: 2,
            Severity.LOW: 1,
            Severity.INFO: 0,
        }
        return severity_ranks[self.severity]
