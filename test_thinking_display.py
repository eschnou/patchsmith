"""Test script to verify different approaches for displaying thinking text with Progress."""

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


def test_approach_1_progress_console_print():
    """Approach 1: Use Progress.console.print() with transient=True for thinking."""
    console.print("\n[bold cyan]Testing Approach 1: Progress.console.print(transient=True)[/bold cyan]\n")

    progress = Progress(
        TextColumn("  "),
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,  # CRITICAL - same console as RichHandler
    )

    with progress:
        task = progress.add_task("Processing files...", total=100)

        for i in range(10):
            # Show thinking text transiently (disappears on next update)
            progress.console.print(f"💭 Thinking: Analyzing file {i}...", style="dim italic")

            # Emit a log to test coordination
            if i % 3 == 0:
                logger.info(f"Checkpoint at iteration {i}")

            time.sleep(0.3)
            progress.update(task, advance=10)

    console.print("[green]✓ Approach 1 complete[/green]\n")


def test_approach_2_status_above_progress():
    """Approach 2: Add a status task above the main progress bar."""
    console.print("\n[bold cyan]Testing Approach 2: Status as separate Progress task[/bold cyan]\n")

    progress = Progress(
        TextColumn("  "),
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,  # CRITICAL - same console as RichHandler
    )

    with progress:
        # Add status task (no progress bar, just text)
        status_task = progress.add_task("💭 Thinking: Starting...", total=None)
        main_task = progress.add_task("Processing files...", total=100)

        for i in range(10):
            # Update thinking text by updating status task description
            progress.update(status_task, description=f"💭 Thinking: Analyzing file {i}...")

            # Emit a log to test coordination
            if i % 3 == 0:
                logger.info(f"Checkpoint at iteration {i}")

            time.sleep(0.3)
            progress.update(main_task, advance=10)

        # Clear status when done
        progress.update(status_task, description="💭 Thinking: Done!", visible=False)

    console.print("[green]✓ Approach 2 complete[/green]\n")


def test_approach_3_live_with_progress():
    """Approach 3: Use Live with Progress and dynamic text panel."""
    console.print("\n[bold cyan]Testing Approach 3: Live + Progress with dynamic text[/bold cyan]\n")

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
    layout = Table.grid(padding=(0, 1))
    layout.add_column()

    thinking_text = Text("💭 Thinking: Starting...", style="dim italic")
    layout.add_row(thinking_text)
    layout.add_row(progress)

    # Use Live to update the entire display
    with Live(layout, console=console, refresh_per_second=10) as live:
        task = progress.add_task("Processing files...", total=100)

        for i in range(10):
            # Update thinking text
            thinking_text.plain = f"💭 Thinking: Analyzing file {i}..."

            # Emit a log to test coordination
            if i % 3 == 0:
                logger.info(f"Checkpoint at iteration {i}")

            time.sleep(0.3)
            progress.update(task, advance=10)

            # Refresh the live display
            live.update(layout)

    console.print("[green]✓ Approach 3 complete[/green]\n")


def test_approach_4_progress_console_status():
    """Approach 4: Use Console.status() for thinking, separate from Progress."""
    console.print("\n[bold cyan]Testing Approach 4: Console.status() with Progress[/bold cyan]\n")

    # Note: This approach may not work well since status() is a context manager
    # and Progress is also a context manager. Testing anyway.

    progress = Progress(
        TextColumn("  "),
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,  # CRITICAL - same console as RichHandler
    )

    with progress:
        task = progress.add_task("Processing files...", total=100)

        # Note: Can't use nested context managers easily, so just test sequential
        for i in range(10):
            # Print thinking without status context
            progress.console.print(f"[dim italic]💭 Thinking: Analyzing file {i}...[/dim italic]")

            # Emit a log to test coordination
            if i % 3 == 0:
                logger.info(f"Checkpoint at iteration {i}")

            time.sleep(0.3)
            progress.update(task, advance=10)

    console.print("[green]✓ Approach 4 complete[/green]\n")


if __name__ == "__main__":
    console.print("[bold]Testing different approaches for displaying thinking text with Progress[/bold]")
    console.print("[dim]All approaches maintain console=console for logging coordination[/dim]\n")

    try:
        test_approach_1_progress_console_print()
        test_approach_2_status_above_progress()
        test_approach_3_live_with_progress()
        test_approach_4_progress_console_status()

        console.print("\n[bold green]All tests completed![/bold green]")
        console.print("\n[bold]Recommendations:[/bold]")
        console.print("1. Approach 2 (status task) is simplest and maintains all coordination")
        console.print("2. Approach 1 (console.print) works but creates many lines")
        console.print("3. Approach 3 (Live) may work but needs testing with complex scenarios")
        console.print("4. Approach 4 is same as 1 but less flexible")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
