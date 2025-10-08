"""Init command for initializing Patchsmith configuration."""

import os
from pathlib import Path

import click

from patchsmith.cli.progress import console, print_error, print_info, print_success
from patchsmith.core.user_config import (
    UserConfig,
    get_api_key,
    get_user_config_path,
    save_user_config,
)
from patchsmith.models.config import PatchsmithConfig


@click.command()
@click.argument("path", type=click.Path(file_okay=False, path_type=Path), required=False)
@click.option(
    "--name",
    "-n",
    help="Project name (default: directory name)"
)
@click.option(
    "--save-api-key",
    is_flag=True,
    help="Save API key to user config (~/.patchsmith/config.yaml)"
)
def init(path: Path | None, name: str | None, save_api_key: bool) -> None:
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
    gitignore_content = """# Patchsmith temporary files - do not commit
# Only config.json should be committed

# Analysis results cache
results.json

# CodeQL databases
db_*/

# SARIF results
*.sarif
results_*.sarif

# Temporary directories
results/
cache/

# Reports are generated, not source files
reports/
"""
    gitignore_path.write_text(gitignore_content)
    print_success(f"Created .gitignore: {gitignore_path}")

    # Create reports directory
    reports_dir = config_dir / "reports"
    reports_dir.mkdir(exist_ok=True)
    print_success(f"Created reports directory: {reports_dir}")

    # Handle API key setup
    _handle_api_key_setup(save_api_key)

    # Show summary
    console.print()
    console.print("[bold green]✓ Initialization Complete![/bold green]")
    console.print()
    console.print("[bold cyan]Next Steps:[/bold cyan]")
    console.print(f"  1. Review configuration: [yellow]{config_file}[/yellow]")

    # Only show API key setup if not already configured
    if not get_api_key():
        console.print(f"  2. Set up API key (see instructions above)")
        console.print(f"  3. Run analysis: [green]patchsmith analyze[/green]")
    else:
        console.print(f"  2. Run analysis: [green]patchsmith analyze[/green]")
    console.print()


def _handle_api_key_setup(save_to_user_config: bool) -> None:
    """Handle API key setup during initialization.

    Args:
        save_to_user_config: Whether to prompt for and save API key to user config
    """
    # Check if API key is already available
    existing_key = get_api_key()

    if existing_key:
        console.print()
        print_success("✓ API key found and configured")
        return

    # API key not found
    console.print()
    print_info("API Key Setup Required")
    console.print()
    console.print("Patchsmith needs an Anthropic API key to use Claude AI.")
    console.print("Get your key from: [cyan]https://console.anthropic.com/[/cyan]")
    console.print()

    if save_to_user_config or click.confirm("Would you like to save your API key to user config now?", default=True):
        # Prompt for API key
        api_key = click.prompt(
            "Enter your Anthropic API key",
            hide_input=True,
            type=str,
            default="",
            show_default=False
        )

        if api_key and api_key.strip():
            api_key = api_key.strip()

            # Save to user config
            try:
                user_config = UserConfig(anthropic_api_key=api_key)
                save_user_config(user_config)
                user_config_path = get_user_config_path()
                print_success(f"API key saved to: {user_config_path}")
                console.print()
                console.print("[dim]Note: File permissions set to 600 (owner read/write only)[/dim]")
            except Exception as e:
                print_error(f"Failed to save API key: {e}")
                console.print()
                _show_manual_api_key_instructions()
        else:
            console.print()
            _show_manual_api_key_instructions()
    else:
        console.print()
        _show_manual_api_key_instructions()


def _show_manual_api_key_instructions() -> None:
    """Show instructions for manually setting up the API key."""
    user_config_path = get_user_config_path()

    console.print("[bold yellow]Manual Setup Options:[/bold yellow]")
    console.print()
    console.print("1. Environment variable (temporary):")
    console.print("   [green]export ANTHROPIC_API_KEY='your-api-key-here'[/green]")
    console.print()
    console.print("2. Shell profile (persistent):")
    console.print("   [green]echo 'export ANTHROPIC_API_KEY=\"your-key\"' >> ~/.zshrc[/green]")
    console.print()
    console.print(f"3. User config file ({user_config_path}):")
    console.print("   Create the file with:")
    console.print("   [green]anthropic_api_key: 'your-api-key-here'[/green]")
    console.print()
    console.print("   Or run:")
    console.print("   [green]patchsmith init --save-api-key[/green]")
    console.print()
