"""Init command for initializing Patchsmith configuration."""

from pathlib import Path

import click

from patchsmith.cli.progress import console, print_error, print_info, print_success
from patchsmith.models.config import PatchsmithConfig


@click.command()
@click.argument("path", type=click.Path(file_okay=False, path_type=Path), required=False)
@click.option(
    "--name",
    "-n",
    help="Project name (default: directory name)"
)
def init(path: Path | None, name: str | None) -> None:
    """Initialize Patchsmith configuration for a project.

    \b
    Creates a .patchsmith directory with:
      • config.json - Project configuration
      • .gitignore - Ignore temporary files

    \b
    Examples:
        patchsmith init                    # Initialize current directory
        patchsmith init /path/to/project   # Initialize specific project
        patchsmith init --name my-project  # Set custom project name
    """
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    # Create directory if it doesn't exist
    if not path.exists():
        if click.confirm(f"Directory {path} does not exist. Create it?"):
            path.mkdir(parents=True, exist_ok=True)
        else:
            return

    console.print(f"\n[bold cyan]🔧 Initializing Patchsmith[/bold cyan]")
    console.print(f"Path: [yellow]{path}[/yellow]\n")

    # Check if already initialized
    config_dir = path / ".patchsmith"
    config_file = config_dir / "config.json"

    if config_file.exists():
        if not click.confirm("Patchsmith already initialized. Reinitialize?"):
            print_info("Initialization cancelled")
            return

    # Create config directory
    config_dir.mkdir(exist_ok=True)

    # Determine project name
    if name is None:
        name = path.name

    print_info(f"Creating configuration for project: {name}")

    # Create default configuration
    config = PatchsmithConfig.create_default(
        project_root=path,
        project_name=name
    )

    # Save configuration
    config.save(config_file)
    print_success(f"Configuration saved: {config_file}")

    # Create .gitignore
    gitignore_path = config_dir / ".gitignore"
    gitignore_content = """# Patchsmith temporary files
*.db
*.sarif
results/
reports/
cache/
"""
    gitignore_path.write_text(gitignore_content)
    print_success(f"Created .gitignore: {gitignore_path}")

    # Create reports directory
    reports_dir = config_dir / "reports"
    reports_dir.mkdir(exist_ok=True)
    print_success(f"Created reports directory: {reports_dir}")

    # Show summary
    console.print()
    console.print("[bold green]✓ Initialization Complete![/bold green]")
    console.print()
    console.print("[bold cyan]Next Steps:[/bold cyan]")
    console.print(f"  1. Review configuration: [yellow]{config_file}[/yellow]")
    console.print(f"  2. Set ANTHROPIC_API_KEY environment variable")
    console.print(f"  3. Run analysis: [green]patchsmith analyze[/green]")
    console.print()

    # Show API key setup if not present
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        print_info("API Key Setup:")
        console.print("    export ANTHROPIC_API_KEY='your-api-key-here'")
        console.print("  Or add to your shell profile (~/.bashrc, ~/.zshrc)")
        console.print()
