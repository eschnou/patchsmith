"""Test script to verify Live + Progress maintains logging coordination under stress."""

import logging
import time
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text
from rich.logging import RichHandler
from rich.layout import Layout

# Shared console instance (this is the critical requirement)
console = Console()

# Setup logging with shared console
rich_handler = RichHandler(console=console, show_time=False, show_level=True)
logging.basicConfig(
    format="%(message)s",
    level=logging.INFO,
    handlers=[rich_handler],
)
logger = logging.getLogger(__name__)


def test_live_with_progress_stress():
    """Test Live + Progress with frequent log messages to verify coordination."""
    console.print("\n[bold cyan]Stress Test: Live + Progress + Frequent Logging[/bold cyan]\n")

    # Create progress with console parameter
    progress = Progress(
        TextColumn("  "),
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,  # CRITICAL - same console as RichHandler
    )

    # Create a table to hold thinking text + progress
    layout = Table.grid(padding=(0, 0))
    layout.add_column()

    thinking_panel = Panel(
        Text("💭 Starting...", style="dim italic"),
        title="Agent Thinking",
        border_style="blue",
    )
    layout.add_row(thinking_panel)
    layout.add_row("")  # Spacer
    layout.add_row(progress)

    # Use Live to update the entire display
    with Live(layout, console=console, refresh_per_second=10) as live:
        task = progress.add_task("Processing files...", total=100)

        for i in range(20):
            # Update thinking text
            thinking_panel.renderable = Text(
                f"💭 Agent: Analyzing file_{i:03d}.py\n"
                f"   Step {i+1}/20 - Checking security patterns...",
                style="dim italic"
            )

            # Emit frequent logs at different levels
            if i % 2 == 0:
                logger.info(f"Processing file {i}")
            if i % 5 == 0:
                logger.warning(f"Warning at iteration {i}")
            if i == 15:
                logger.error("Simulated error condition")

            time.sleep(0.2)
            progress.update(task, advance=5)

            # Refresh the live display
            live.update(layout)

    console.print("[green]✓ Stress test complete - check if logs appeared cleanly above progress[/green]\n")


def test_live_with_progress_no_console():
    """Test what happens when Live doesn't get console parameter (for comparison)."""
    console.print("\n[bold yellow]Comparison Test: Live WITHOUT console parameter[/bold yellow]\n")

    # Create progress with console parameter
    progress = Progress(
        TextColumn("  "),
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,  # Progress still has console
    )

    # Create layout
    layout = Table.grid(padding=(0, 0))
    layout.add_column()

    thinking_panel = Panel(
        Text("💭 Starting...", style="dim italic"),
        title="Agent Thinking",
        border_style="blue",
    )
    layout.add_row(thinking_panel)
    layout.add_row("")
    layout.add_row(progress)

    # DON'T pass console to Live (test if this breaks coordination)
    with Live(layout, refresh_per_second=10) as live:  # No console parameter
        task = progress.add_task("Processing files...", total=100)

        for i in range(10):
            # Update thinking text
            thinking_panel.renderable = Text(
                f"💭 Agent: Analyzing file_{i:03d}.py",
                style="dim italic"
            )

            # Emit logs
            if i % 3 == 0:
                logger.info(f"Checkpoint {i}")

            time.sleep(0.2)
            progress.update(task, advance=10)
            live.update(layout)

    console.print("[yellow]✓ Test complete - check if logging was affected[/yellow]\n")


def test_approach_2_stress():
    """Test Approach 2 (status task) under stress for comparison."""
    console.print("\n[bold cyan]Comparison: Approach 2 (Status Task) Stress Test[/bold cyan]\n")

    progress = Progress(
        TextColumn("  "),
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )

    with progress:
        # Add status task (no progress bar, just text)
        status_task = progress.add_task("💭 Thinking: Starting...", total=None)
        main_task = progress.add_task("Processing files...", total=100)

        for i in range(20):
            # Update thinking text
            progress.update(
                status_task,
                description=f"💭 Agent: Analyzing file_{i:03d}.py - Step {i+1}/20"
            )

            # Emit frequent logs
            if i % 2 == 0:
                logger.info(f"Processing file {i}")
            if i % 5 == 0:
                logger.warning(f"Warning at iteration {i}")
            if i == 15:
                logger.error("Simulated error condition")

            time.sleep(0.2)
            progress.update(main_task, advance=5)

    console.print("[green]✓ Approach 2 stress test complete[/green]\n")


if __name__ == "__main__":
    console.print("[bold]Testing Live + Progress with Logging Coordination[/bold]")
    console.print("[dim]Verifying that console parameter maintains proper stderr coordination[/dim]\n")

    try:
        # Test the recommended Live + Progress approach
        test_live_with_progress_stress()

        # Test what happens without console parameter on Live
        test_live_with_progress_no_console()

        # Compare with simpler Approach 2
        test_approach_2_stress()

        console.print("\n[bold green]All stress tests completed![/bold green]")
        console.print("\n[bold]Analysis:[/bold]")
        console.print("If logs appeared cleanly above progress in all tests, coordination is maintained.")
        console.print("If any test showed interleaved logs, that approach breaks coordination.")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
