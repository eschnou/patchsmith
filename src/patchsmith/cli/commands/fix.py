"""Fix command for generating and applying security fixes."""

import asyncio
from pathlib import Path

import click

from patchsmith.cli.progress import (
    ProgressTracker,
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from patchsmith.models.config import PatchsmithConfig
from patchsmith.models.finding import Finding
from patchsmith.services.analysis_service import AnalysisService
from patchsmith.services.fix_service import FixService


@click.command()
@click.argument("finding_id", required=False)
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project path (default: current directory)"
)
@click.option(
    "--apply/--no-apply",
    default=False,
    help="Automatically apply the fix (use with caution!)"
)
@click.option(
    "--branch/--no-branch",
    default=True,
    help="Create a Git branch for the fix"
)
@click.option(
    "--commit/--no-commit",
    default=True,
    help="Commit the fix"
)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="Interactive mode: select finding to fix"
)
def fix(
    finding_id: str | None,
    path: Path | None,
    apply: bool,
    branch: bool,
    commit: bool,
    interactive: bool,
) -> None:
    """Generate and optionally apply a security fix.

    \b
    Process:
      1. Analyze the vulnerability
      2. Generate AI-powered fix
      3. Show proposed changes
      4. Optionally apply the fix

    \b
    Examples:
        patchsmith fix                           # Interactive mode
        patchsmith fix FINDING_ID                # Fix specific finding
        patchsmith fix FINDING_ID --apply        # Generate and apply fix
        patchsmith fix --no-branch --no-commit   # Just apply changes
    """
    # Use current directory if no path provided
    if path is None:
        path = Path.cwd()

    if not finding_id and not interactive:
        print_error("Please provide a FINDING_ID or use --interactive mode")
        print_info("Tip: Run 'patchsmith analyze' first to see available findings")
        raise click.Abort()

    console.print(f"\n[bold cyan]🔧 Patchsmith Fix Generator[/bold cyan]")
    console.print(f"Project: [yellow]{path}[/yellow]\n")

    # Run fix generation
    asyncio.run(_generate_and_apply_fix(
        path,
        finding_id,
        apply,
        branch,
        commit,
        interactive,
    ))


async def _generate_and_apply_fix(
    path: Path,
    finding_id: str | None,
    auto_apply: bool,
    create_branch: bool,
    create_commit: bool,
    interactive: bool,
) -> None:
    """Generate and apply fix.

    Args:
        path: Project path
        finding_id: Finding ID to fix
        auto_apply: Whether to automatically apply
        create_branch: Whether to create Git branch
        create_commit: Whether to create Git commit
        interactive: Whether to use interactive mode
    """
    try:
        # Create configuration
        config = PatchsmithConfig.create_default(
            project_root=path,
            project_name=path.name
        )

        # Get finding (either from analysis or provided ID)
        finding = None

        if interactive or finding_id is None:
            print_info("Running analysis to find fixable issues...")

            with ProgressTracker() as tracker:
                analysis_service = AnalysisService(
                    config=config,
                    progress_callback=tracker.handle_progress
                )

                analysis_result, triage_results, _ = await analysis_service.analyze_project(
                    project_path=path,
                    perform_triage=True,
                    perform_detailed_analysis=False,
                )

            console.print()

            if not analysis_result.findings:
                print_success("No vulnerabilities found!")
                return

            # Show top findings and let user pick
            if interactive:
                console.print("[bold cyan]Top Priority Findings:[/bold cyan]\n")
                recommended = []
                if triage_results:
                    recommended = [t for t in triage_results if t.recommended_for_analysis][:10]

                for i, triage in enumerate(recommended, 1):
                    f = next((f for f in analysis_result.findings if f.id == triage.finding_id), None)
                    if f:
                        console.print(f"  {i}. [{f.severity.value}] {f.rule_id}")
                        console.print(f"     Location: {f.file_path}:{f.start_line}")
                        console.print(f"     Priority: {triage.priority_score:.2f}")
                        console.print()

                choice = click.prompt("Select finding number to fix (or 'q' to quit)", type=str)
                if choice.lower() == 'q':
                    return

                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(recommended):
                        finding_id = recommended[idx].finding_id
                    else:
                        print_error("Invalid selection")
                        return
                except ValueError:
                    print_error("Invalid input")
                    return

        # Get the finding
        if finding_id:
            # Try to find it in recent analysis or search project
            # For now, we'll need to run analysis to get the finding
            print_info(f"Looking up finding: {finding_id}")

            with ProgressTracker() as tracker:
                analysis_service = AnalysisService(
                    config=config,
                    progress_callback=tracker.handle_progress
                )

                analysis_result, _, _ = await analysis_service.analyze_project(
                    project_path=path,
                    perform_triage=False,
                    perform_detailed_analysis=False,
                )

            finding = next((f for f in analysis_result.findings if f.id == finding_id), None)

            if not finding:
                print_error(f"Finding not found: {finding_id}")
                print_info("Run 'patchsmith analyze' to see available findings")
                return

        if not finding:
            print_error("No finding selected")
            return

        # Show finding details
        console.print()
        console.print(f"[bold cyan]Finding Details:[/bold cyan]")
        console.print(f"  ID: [yellow]{finding.id}[/yellow]")
        console.print(f"  Rule: [yellow]{finding.rule_id}[/yellow]")
        console.print(f"  Severity: [{finding.severity.value}]{finding.severity.value.upper()}[/{finding.severity.value}]")
        console.print(f"  Location: [yellow]{finding.file_path}:{finding.start_line}[/yellow]")
        console.print(f"  Message: {finding.message}")
        console.print()

        # Generate fix
        print_info("Generating fix using AI...")

        with ProgressTracker() as tracker:
            fix_service = FixService(
                config=config,
                progress_callback=tracker.handle_progress
            )

            fix = await fix_service.generate_fix(
                finding=finding,
                working_dir=path,
                context_lines=15,
            )

        console.print()

        if not fix:
            print_warning("Could not generate a fix for this finding")
            print_info("This might be because:")
            print_info("  • The vulnerability requires manual review")
            print_info("  • The code context is too complex")
            print_info("  • The AI confidence is too low")
            return

        # Show fix details
        console.print(f"[bold green]✓ Fix Generated![/bold green]")
        console.print(f"  Confidence: [yellow]{fix.confidence:.2%}[/yellow]")
        console.print(f"  Explanation: {fix.explanation}\n")

        # Show diff
        console.print("[bold cyan]Proposed Changes:[/bold cyan]")
        console.print("─" * 80)
        console.print("[red]- Original Code:[/red]")
        for line in fix.original_code.split('\n')[:10]:
            console.print(f"  [red]- {line}[/red]")
        console.print()
        console.print("[green]+ Fixed Code:[/green]")
        for line in fix.fixed_code.split('\n')[:10]:
            console.print(f"  [green]+ {line}[/green]")
        console.print("─" * 80)
        console.print()

        # Apply fix if requested or prompt
        should_apply = auto_apply
        if not auto_apply and fix.confidence >= 0.7:
            should_apply = click.confirm("Apply this fix?", default=False)

        if should_apply:
            print_info("Applying fix...")

            success, message = fix_service.apply_fix(
                fix=fix,
                create_branch=create_branch,
                commit=create_commit,
            )

            console.print()
            if success:
                print_success(message)
                if create_commit:
                    print_info("Fix has been committed. Review with 'git log' and 'git diff HEAD~1'")
                    print_info("To undo: git reset --hard HEAD~1")
            else:
                print_error(f"Failed to apply fix: {message}")
        else:
            print_info("Fix not applied. You can:")
            print_info("  • Review the proposed changes above")
            print_info("  • Apply manually")
            print_info(f"  • Run with --apply flag: patchsmith fix {finding.id} --apply")

        console.print()

    except Exception as e:
        console.print()
        print_error(f"Fix generation failed: {e}")
        if click.get_current_context().obj.get("debug", False) if click.get_current_context().obj else False:
            console.print_exception()
        raise click.Abort()
