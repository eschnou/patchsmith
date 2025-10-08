"""Completion command for installing shell autocomplete."""

import os
import subprocess
from pathlib import Path

import click

from patchsmith.cli.progress import console, print_error, print_info, print_success


@click.command()
@click.argument(
    "shell",
    type=click.Choice(["bash", "zsh", "fish"], case_sensitive=False),
    required=False,
)
@click.option(
    "--show",
    is_flag=True,
    help="Show completion script without installing",
)
def completion(shell: str | None, show: bool) -> None:
    """Install shell completion for patchsmith and psmith.

    \b
    Supports: bash, zsh, fish

    \b
    Examples:
        patchsmith completion bash       # Install bash completion
        patchsmith completion zsh        # Install zsh completion
        patchsmith completion --show     # Show script for auto-detected shell
    """
    # Auto-detect shell if not provided
    if not shell:
        shell_env = os.environ.get("SHELL", "")
        if "bash" in shell_env:
            shell = "bash"
        elif "zsh" in shell_env:
            shell = "zsh"
        elif "fish" in shell_env:
            shell = "fish"
        else:
            print_error("Could not auto-detect shell")
            print_info("Please specify shell: patchsmith completion [bash|zsh|fish]")
            raise click.Abort()

    console.print(f"\n[bold cyan]Shell Completion Setup ({shell})[/bold cyan]\n")

    # Generate completion script for both patchsmith and psmith
    env_var_patchsmith = f"_PATCHSMITH_COMPLETE={shell}_source"
    env_var_psmith = f"_PSMITH_COMPLETE={shell}_source"

    try:
        # Generate patchsmith completion
        result_patchsmith = subprocess.run(
            ["patchsmith"],
            env={**os.environ, env_var_patchsmith: "1"},
            capture_output=True,
            text=True,
        )

        # Generate psmith completion
        result_psmith = subprocess.run(
            ["psmith"],
            env={**os.environ, env_var_psmith: "1"},
            capture_output=True,
            text=True,
        )

        if result_patchsmith.returncode != 0 or result_psmith.returncode != 0:
            print_error("Failed to generate completion script")
            raise click.Abort()

        completion_script = result_patchsmith.stdout + "\n" + result_psmith.stdout

    except FileNotFoundError:
        print_error("patchsmith/psmith not found in PATH")
        print_info("Make sure you installed with: poetry install")
        raise click.Abort()

    # Show script if requested
    if show:
        console.print("[bold]Completion script:[/bold]\n")
        console.print(completion_script)
        return

    # Install completion
    home = Path.home()

    if shell == "bash":
        completion_file = home / ".patchsmith-complete.bash"
        rc_file = home / ".bashrc"
        source_line = f"source {completion_file}"

    elif shell == "zsh":
        completion_file = home / ".patchsmith-complete.zsh"
        rc_file = home / ".zshrc"
        source_line = f"source {completion_file}"

    else:  # fish
        completion_dir = home / ".config" / "fish" / "completions"
        completion_dir.mkdir(parents=True, exist_ok=True)
        completion_file = completion_dir / "patchsmith.fish"
        rc_file = None
        source_line = None

    # Write completion script
    completion_file.write_text(completion_script)
    print_success(f"Completion script written to: {completion_file}")

    # Add source line to RC file (bash/zsh only)
    if rc_file and source_line:
        if rc_file.exists():
            rc_content = rc_file.read_text()
            if source_line not in rc_content:
                with open(rc_file, "a") as f:
                    f.write(f"\n# Patchsmith completion\n{source_line}\n")
                print_success(f"Added source line to: {rc_file}")
            else:
                print_info(f"Source line already in: {rc_file}")
        else:
            print_info(f"{rc_file} not found, skipping auto-source")
            console.print(f"\n[yellow]Add this to your {rc_file}:[/yellow]")
            console.print(f"  {source_line}\n")

    # Final instructions
    console.print("\n[bold green]✓ Completion installed![/bold green]\n")
    console.print("[bold]To activate:[/bold]")

    if shell == "bash":
        console.print(f"  source {rc_file}")
        console.print("  OR restart your terminal\n")
    elif shell == "zsh":
        console.print(f"  source {rc_file}")
        console.print("  OR restart your terminal\n")
    else:  # fish
        console.print("  Restart your terminal\n")

    console.print("[bold]Test it:[/bold]")
    console.print("  patchsmith <TAB>")
    console.print("  psmith <TAB>\n")
