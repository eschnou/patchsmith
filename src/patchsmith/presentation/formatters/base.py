"""Base formatter interface for investigation results."""

from abc import ABC, abstractmethod

from patchsmith.models.finding import DetailedSecurityAssessment, Finding


class BaseFormatter(ABC):
    """Base class for investigation result formatters."""

    @abstractmethod
    def format(self, finding: Finding, assessment: DetailedSecurityAssessment) -> str:
        """Format the investigation results.

        Args:
            finding: The security finding
            assessment: Detailed security assessment

        Returns:
            Formatted output string
        """
        pass
