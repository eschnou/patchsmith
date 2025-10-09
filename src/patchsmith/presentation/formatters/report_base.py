"""Base formatter interface for security report output."""

from abc import ABC, abstractmethod

from patchsmith.models.report import SecurityReportData


class BaseReportFormatter(ABC):
    """Base class for security report formatters.

    Formatters take structured SecurityReportData and convert it
    into various output formats (markdown, HTML, PDF, etc.).
    """

    @abstractmethod
    def format(self, report_data: SecurityReportData) -> str:
        """Format the security report data.

        Args:
            report_data: Structured security report data

        Returns:
            Formatted report string
        """
        pass

    def _format_severity_badge(self, severity: str) -> str:
        """Format severity badge (override in subclasses for format-specific rendering).

        Args:
            severity: Severity level (critical, high, medium, low, info)

        Returns:
            Formatted severity badge string
        """
        return severity.upper()

    def _format_priority_level(self, priority: str) -> str:
        """Format priority level (override in subclasses for format-specific rendering).

        Args:
            priority: Priority level (immediate, high, medium, low)

        Returns:
            Formatted priority level string
        """
        return priority.upper()

    def _get_severity_emoji(self, severity: str) -> str:
        """Get emoji for severity level.

        Args:
            severity: Severity level

        Returns:
            Emoji character
        """
        emoji_map = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
            "info": "ℹ️",
        }
        return emoji_map.get(severity.lower(), "⚪")

    def _get_priority_emoji(self, priority: str) -> str:
        """Get emoji for priority level.

        Args:
            priority: Priority level

        Returns:
            Emoji character
        """
        emoji_map = {
            "immediate": "🚨",
            "high": "⚠️",
            "medium": "📌",
            "low": "📝",
        }
        return emoji_map.get(priority.lower(), "📋")
