"""Rich-based progress tracking for CLI commands."""

from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

console = Console()


class ProgressTracker:
    """Tracks and displays progress for service operations."""

    def __init__(self) -> None:
        """Initialize progress tracker."""
        self.progress = Progress(
            TextColumn("  "),  # Fixed 2-space indent for alignment
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,  # CRITICAL: Keep this for logging coordination
        )
        self.tasks: dict[str, TaskID] = {}
        self.current_phase: str | None = None
        self.thinking_panel: Panel | None = None
        self.live: Live | None = None

    def __enter__(self) -> "ProgressTracker":
        """Enter context manager."""
        # Wrap progress + thinking panel in Live for stable display
        self.live = Live(
            self._get_renderable(),
            console=console,
            refresh_per_second=10,
        )
        self.live.__enter__()
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager."""
        if self.live:
            self.live.__exit__(*args)

    def _get_renderable(self) -> Group:
        """Get the renderable group with progress and optional thinking panel."""
        renderables = []

        # Add thinking panel if present
        if self.thinking_panel:
            renderables.append(self.thinking_panel)

        # Add progress
        renderables.append(self.progress)

        return Group(*renderables)

    def update_thinking(self, message: str) -> None:
        """Update agent thinking status.

        Args:
            message: Agent thinking message
        """
        if message:
            # Create/update thinking panel (blue box that doesn't move)
            self.thinking_panel = Panel(
                Text(message, style="cyan"),
                title="💭 Agent Thinking",
                border_style="blue",
                padding=(0, 1),
            )
        else:
            # Clear thinking panel
            self.thinking_panel = None

        # Update the live display
        if self.live:
            self.live.update(self._get_renderable())

    def handle_progress(self, event: str, data: dict[str, Any]) -> None:
        """Handle progress event from service layer.

        Args:
            event: Event name
            data: Event data
        """
        # Handle agent turn progress
        if event == "agent_turn_progress":
            current_turn = data.get("current_turn", 0)
            max_turns = data.get("max_turns", 100)
            # Update current phase task with percentage based on turns
            if self.current_phase and self.current_phase in self.tasks:
                percentage = (current_turn / max_turns) * 100
                self.progress.update(
                    self.tasks[self.current_phase],
                    completed=percentage,
                )
            return

        # Map events to user-friendly descriptions
        descriptions = {
            "analysis_started": "Starting security analysis...",
            "language_detection_started": "Detecting programming languages...",
            "language_detection_completed": "✓ Languages detected",
            "codeql_database_creation_started": "Creating CodeQL database...",
            "codeql_database_created": "✓ CodeQL database created",
            "codeql_queries_started": "Running security queries...",
            "codeql_queries_completed": "✓ Security queries completed",
            "sarif_parsing_started": "Parsing results...",
            "sarif_parsing_completed": "✓ Results parsed",
            "triage_started": "Triaging findings (AI prioritization)...",
            "triage_completed": "✓ Triage completed",
            "detailed_analysis_started": "Performing detailed security analysis (AI)...",
            "detailed_analysis_completed": "✓ Detailed analysis completed",
            "statistics_computation_started": "Computing statistics...",
            "statistics_computation_completed": "✓ Statistics computed",
            "analysis_completed": "✓ Analysis completed!",
            "report_generation_started": "Generating report (AI)...",
            "report_generation_completed": "✓ Report generated",
            "report_saving": "Saving report...",
            "report_saved": "✓ Report saved",
            "fix_generation_started": "Generating fix (AI)...",
            "fix_generation_completed": "✓ Fix generated",
            "fix_application_started": "Applying fix...",
            "fix_applied_to_file": "✓ Fix applied to file",
            "fix_application_completed": "✓ Fix applied successfully",
        }

        # Special handling for per-finding detailed analysis progress
        if event == "detailed_analysis_finding_progress":
            current = data.get("current", 0)
            total = data.get("total", 1)
            finding_id = data.get("finding_id", "unknown")
            severity = data.get("severity", "unknown")

            description = f"Analyzing finding {current}/{total} ({severity})"

            # Update or create detailed analysis task with actual progress
            base_event = "detailed_analysis_started"
            if base_event in self.tasks:
                # Calculate percentage based on current/total
                percentage = (current / total) * 100
                self.progress.update(
                    self.tasks[base_event],
                    completed=percentage,
                    description=description,
                )
            return

        description = descriptions.get(event, event)

        # Handle task lifecycle
        if event.endswith("_started"):
            # Start new task
            # For detailed analysis, start with 0 progress (will be updated by per-finding events)
            if event == "detailed_analysis_started":
                total_findings = data.get("finding_count", 100)
                task_id = self.progress.add_task(description, total=100)
            else:
                task_id = self.progress.add_task(description, total=100)
            self.tasks[event] = task_id
            self.current_phase = event
        elif event.endswith("_completed") or event.endswith("_created") or event.endswith("_saved"):
            # Complete task
            base_event = event.replace("_completed", "_started").replace("_created", "_creation_started").replace("_saved", "_saving")
            if base_event in self.tasks:
                self.progress.update(self.tasks[base_event], completed=100, description=description)
            else:
                # Task wasn't started explicitly, just show completion
                console.print(f"  {description}")
        else:
            # Update current task or show info
            if self.current_phase and self.current_phase in self.tasks:
                # Increment progress slightly for intermediate events
                self.progress.update(self.tasks[self.current_phase], advance=10)
            else:
                console.print(f"  {description}")


def print_analysis_summary(
    finding_count: int,
    languages: list[str],
    critical_count: int,
    high_count: int,
    triage_count: int,
    detailed_count: int,
) -> None:
    """Print analysis summary table.

    Args:
        finding_count: Total number of findings
        languages: List of detected languages
        critical_count: Number of critical findings
        high_count: Number of high severity findings
        triage_count: Number of triaged findings
        detailed_count: Number of detailed assessments
    """
    table = Table(title="Analysis Summary", show_header=False, box=None)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold white")

    table.add_row("Languages", ", ".join(languages))
    table.add_row("Total Findings", str(finding_count))
    table.add_row("Critical", f"[red]{critical_count}[/red]" if critical_count > 0 else "0")
    table.add_row("High", f"[yellow]{high_count}[/yellow]" if high_count > 0 else "0")
    table.add_row("Triaged", str(triage_count))
    table.add_row("Detailed Assessments", str(detailed_count))

    console.print()
    console.print(table)
    console.print()


def print_findings_table(findings: list[Any], limit: int = 10) -> None:
    """Print findings in a formatted table.

    Args:
        findings: List of Finding objects
        limit: Maximum number of findings to display
    """
    table = Table(title=f"Top {min(limit, len(findings))} Findings", show_lines=True)

    table.add_column("ID", style="cyan bold", no_wrap=True, width=8)
    table.add_column("Severity", style="bold", width=10)
    table.add_column("Rule", style="yellow", width=35)
    table.add_column("Location", style="green", width=45)

    for finding in findings[:limit]:
        severity_color = {
            "critical": "red",
            "high": "yellow",
            "medium": "blue",
            "low": "dim",
        }.get(finding.severity.value, "white")

        table.add_row(
            finding.id,  # No truncation - short IDs like F-1, F-2
            f"[{severity_color}]{finding.severity.value.upper()}[/{severity_color}]",
            finding.rule_id[:35],  # Truncate rule name if needed
            f"{finding.file_path.name}:{finding.start_line}",
        )

    console.print(table)
    console.print()


def print_error(message: str) -> None:
    """Print an error message.

    Args:
        message: Error message
    """
    console.print(f"[red]✗ Error:[/red] {message}")


def print_success(message: str) -> None:
    """Print a success message.

    Args:
        message: Success message
    """
    console.print(f"[green]✓[/green] {message}")


def print_warning(message: str) -> None:
    """Print a warning message.

    Args:
        message: Warning message
    """
    console.print(f"[yellow]⚠[/yellow]  {message}")


def print_info(message: str) -> None:
    """Print an info message.

    Args:
        message: Info message
    """
    console.print(f"[blue]ℹ[/blue]  {message}")
