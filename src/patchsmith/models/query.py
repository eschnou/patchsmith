"""CodeQL query models."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from patchsmith.models.finding import Severity


class Query(BaseModel):
    """CodeQL query definition."""

    id: str = Field(..., description="Unique query identifier")
    name: str = Field(..., description="Human-readable query name")
    description: Optional[str] = Field(None, description="Query description")
    path: Path = Field(..., description="Path to query file (.ql)")
    severity: Severity = Field(default=Severity.MEDIUM, description="Default severity for findings")
    language: str = Field(..., description="Target language (python, javascript, etc.)")
    tags: list[str] = Field(default_factory=list, description="Query tags (e.g., security, cwe)")
    is_custom: bool = Field(default=False, description="Whether this is a custom query")

    def __str__(self) -> str:
        """String representation."""
        return f"{self.name} ({self.id})"


class QuerySuite(BaseModel):
    """Collection of CodeQL queries."""

    name: str = Field(..., description="Suite name")
    description: Optional[str] = Field(None, description="Suite description")
    queries: list[Query] = Field(default_factory=list, description="Queries in this suite")
    language: Optional[str] = Field(None, description="Target language (if language-specific)")

    def add_query(self, query: Query) -> None:
        """
        Add a query to the suite.

        Args:
            query: Query to add
        """
        self.queries.append(query)

    def get_by_severity(self, severity: Severity) -> list[Query]:
        """
        Get queries of a specific severity.

        Args:
            severity: Severity level to filter by

        Returns:
            Queries with the specified severity
        """
        return [q for q in self.queries if q.severity == severity]

    def get_custom_queries(self) -> list[Query]:
        """
        Get only custom queries.

        Returns:
            Custom queries in this suite
        """
        return [q for q in self.queries if q.is_custom]

    def get_standard_queries(self) -> list[Query]:
        """
        Get only standard (non-custom) queries.

        Returns:
            Standard queries in this suite
        """
        return [q for q in self.queries if not q.is_custom]

    def __len__(self) -> int:
        """Get number of queries in suite."""
        return len(self.queries)
