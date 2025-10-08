"""Fix service for generating and applying security patches."""

import subprocess
from pathlib import Path
from typing import Any, Callable

from patchsmith.adapters.claude.autonomous_fix_agent import (
    AutonomousFixAgent,
    FixResult,
)
from patchsmith.adapters.claude.fix_generator_agent import Fix, FixGeneratorAgent
from patchsmith.adapters.git.repository import GitRepository
from patchsmith.models.config import PatchsmithConfig
from patchsmith.models.finding import Finding
from patchsmith.services.base_service import BaseService
from patchsmith.utils.logging import get_logger

logger = get_logger()


class FixService(BaseService):
    """Service for generating and applying security fixes.

    This service coordinates fix generation (via Claude AI) and optional
    application of fixes via Git operations.
    """

    def __init__(
        self,
        config: PatchsmithConfig,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        """
        Initialize fix service.

        Args:
            config: Patchsmith configuration
            progress_callback: Optional progress callback
        """
        super().__init__(config, progress_callback)

    async def generate_fix(
        self,
        finding: Finding,
        working_dir: Path,
        context_lines: int = 10,
    ) -> Fix | None:
        """
        Generate a fix for a security finding.

        Args:
            finding: Finding to generate fix for
            working_dir: Working directory (project root)
            context_lines: Number of context lines around vulnerability

        Returns:
            Fix object if successful, None otherwise

        Raises:
            Exception: If fix generation fails
        """
        self._emit_progress(
            "fix_generation_started",
            finding_id=finding.id,
            rule_id=finding.rule_id,
        )

        try:
            # Initialize fix generator agent
            fix_agent = FixGeneratorAgent(
                working_dir=working_dir,
            )

            # Generate fix
            fix = await fix_agent.execute(
                finding=finding,
                context_lines=context_lines,
            )

            if fix:
                self._emit_progress(
                    "fix_generation_completed",
                    finding_id=finding.id,
                    confidence=fix.confidence,
                )
            else:
                self._emit_progress(
                    "fix_generation_no_result",
                    finding_id=finding.id,
                )

            return fix

        except Exception as e:
            self._emit_progress(
                "fix_generation_failed",
                finding_id=finding.id,
                error=str(e),
            )
            logger.error(
                "fix_service_generate_error",
                finding_id=finding.id,
                error=str(e),
            )
            raise

    def apply_fix(
        self,
        fix: Fix,
        create_branch: bool = True,
        commit: bool = True,
        branch_name: str | None = None,
    ) -> tuple[bool, str]:
        """
        Apply a fix to the codebase.

        Args:
            fix: Fix to apply
            create_branch: Whether to create a new Git branch
            commit: Whether to commit the changes
            branch_name: Optional custom branch name

        Returns:
            Tuple of (success: bool, message: str)

        Raises:
            Exception: If fix application fails
        """
        self._emit_progress(
            "fix_application_started",
            finding_id=fix.finding_id,
            file_path=str(fix.file_path),
        )

        try:
            # Read file content
            if not fix.file_path.exists():
                error_msg = f"File not found: {fix.file_path}"
                self._emit_progress("fix_application_failed", error=error_msg)
                return False, error_msg

            content = fix.file_path.read_text()

            # Check if original code exists in file
            if fix.original_code not in content:
                error_msg = f"Original code not found in {fix.file_path}"
                self._emit_progress("fix_application_failed", error=error_msg)
                return False, error_msg

            # Apply fix (string replacement)
            new_content = content.replace(fix.original_code, fix.fixed_code)
            fix.file_path.write_text(new_content)

            self._emit_progress(
                "fix_applied_to_file",
                file_path=str(fix.file_path),
            )

            # Git operations (if requested)
            if create_branch or commit:
                repo = GitRepository(fix.file_path.parent)

                if create_branch:
                    # Generate branch name if not provided
                    if not branch_name:
                        branch_name = f"fix/{fix.finding_id.replace('/', '-')}"

                    self._emit_progress("git_branch_creating", branch_name=branch_name)
                    try:
                        repo.create_branch(branch_name)
                        self._emit_progress("git_branch_created", branch_name=branch_name)
                    except Exception as e:
                        logger.warning(
                            "branch_creation_failed",
                            branch_name=branch_name,
                            error=str(e),
                        )
                        # Branch might already exist, continue anyway
                        self._emit_progress(
                            "git_branch_exists",
                            branch_name=branch_name,
                        )

                if commit:
                    self._emit_progress("git_committing")
                    repo.stage_file(fix.file_path)
                    commit_message = f"Fix {fix.finding_id}\n\n{fix.explanation}"
                    commit_sha = repo.commit(commit_message)
                    self._emit_progress(
                        "git_committed",
                        commit_sha=commit_sha,
                        branch_name=branch_name or "current",
                    )

            self._emit_progress(
                "fix_application_completed",
                finding_id=fix.finding_id,
            )

            success_msg = f"Fix applied to {fix.file_path.name}"
            if commit:
                success_msg += f" and committed"
            return True, success_msg

        except Exception as e:
            self._emit_progress(
                "fix_application_failed",
                finding_id=fix.finding_id,
                error=str(e),
            )
            logger.error(
                "fix_service_apply_error",
                finding_id=fix.finding_id,
                error=str(e),
            )
            raise

    async def generate_and_apply_fix(
        self,
        finding: Finding,
        working_dir: Path,
        create_branch: bool = True,
        commit: bool = True,
        context_lines: int = 10,
    ) -> tuple[Fix | None, bool, str]:
        """
        Generate and optionally apply a fix in one operation.

        Args:
            finding: Finding to fix
            working_dir: Working directory (project root)
            create_branch: Whether to create a Git branch
            commit: Whether to commit changes
            context_lines: Number of context lines

        Returns:
            Tuple of (fix: Fix | None, applied: bool, message: str)
        """
        # Generate fix
        fix = await self.generate_fix(finding, working_dir, context_lines)

        if not fix:
            return None, False, "No fix generated (low confidence or error)"

        # Apply fix if generated
        try:
            applied, message = self.apply_fix(
                fix=fix,
                create_branch=create_branch,
                commit=commit,
            )
            return fix, applied, message
        except Exception as e:
            return fix, False, f"Fix generated but application failed: {e}"

    async def autonomous_fix(
        self,
        finding: Finding,
        working_dir: Path,
        skip_push_and_pr: bool = False,
    ) -> tuple[FixResult | None, str]:
        """
        Autonomously fix a vulnerability using AI agent with Write access.

        This workflow:
        1. Creates a Git branch
        2. Launches autonomous agent with Write access
        3. Agent modifies files directly to fix vulnerability
        4. Commits all changes
        5. Pushes branch and creates PR (unless skip_push_and_pr=True)

        Args:
            finding: Finding to fix
            working_dir: Working directory (project root)
            skip_push_and_pr: If True, keep branch local (don't push or create PR)

        Returns:
            Tuple of (result: FixResult | None, message: str with PR URL or error)

        Raises:
            Exception: If fix fails (after rollback)
        """
        self._emit_progress(
            "autonomous_fix_started",
            finding_id=finding.id,
        )

        repo = GitRepository(working_dir)
        branch_name = f"fix/{finding.id.replace('/', '-')}"
        original_branch = repo.get_current_branch()

        try:
            # 1. Create branch BEFORE agent runs
            self._emit_progress("git_branch_creating", branch_name=branch_name)
            try:
                repo.create_branch(branch_name)
            except Exception as e:
                # Branch might exist, try to checkout
                if repo.branch_exists(branch_name):
                    logger.warning(
                        "branch_exists_checking_out",
                        branch_name=branch_name,
                    )
                    repo.checkout_branch(branch_name)
                else:
                    raise

            self._emit_progress("git_branch_created", branch_name=branch_name)

            # 2. Launch autonomous agent with Write access
            self._emit_progress("agent_launching", finding_id=finding.id)

            agent = AutonomousFixAgent(working_dir=working_dir)
            result = await agent.execute(finding=finding)

            if not result.success:
                # Agent failed or abandoned - rollback
                self._emit_progress(
                    "autonomous_fix_failed",
                    reason=result.reason,
                )
                logger.warning(
                    "autonomous_fix_abandoned",
                    finding_id=finding.id,
                    reason=result.reason,
                )

                # Rollback branch
                repo.checkout_branch(original_branch)
                # Note: We don't delete the branch in case user wants to inspect

                return None, f"Fix abandoned: {result.reason}"

            # 3. Agent succeeded - commit all changes
            self._emit_progress("git_committing", finding_id=finding.id)

            if not repo.has_uncommitted_changes():
                # Agent completed but made no changes - unexpected
                logger.warning(
                    "autonomous_fix_no_changes",
                    finding_id=finding.id,
                )
                repo.checkout_branch(original_branch)
                return None, "Agent completed but made no file changes"

            # Stage all modified files
            repo.stage_all()

            # Create commit message
            commit_message = self._generate_commit_message(finding, result)
            repo.commit(commit_message, allow_protected=False)

            self._emit_progress("git_committed", branch_name=branch_name)

            # 4. Push branch (unless skipped)
            if not skip_push_and_pr:
                self._emit_progress("git_pushing", branch_name=branch_name)
                try:
                    repo.push_branch(set_upstream=True)
                    self._emit_progress("git_pushed", branch_name=branch_name)
                except Exception as e:
                    logger.warning("git_push_failed", error=str(e))
                    # Continue anyway - local branch is created
                    skip_push_and_pr = True  # Don't try PR if push failed

                # 5. Create PR
                if not skip_push_and_pr:
                    pr_url = self._create_pull_request(finding, result, branch_name, working_dir)

                    self._emit_progress(
                        "autonomous_fix_completed",
                        finding_id=finding.id,
                        pr_url=pr_url or "no PR created",
                    )

                    if pr_url:
                        return result, pr_url
                    else:
                        return result, f"Branch {branch_name} created and pushed (no PR - install 'gh' CLI)"

            # Local only mode
            self._emit_progress(
                "autonomous_fix_completed",
                finding_id=finding.id,
                local_only=True,
            )

            return result, f"Branch {branch_name} created locally (not pushed)"

        except Exception as e:
            # Rollback on any error
            logger.error(
                "autonomous_fix_error",
                finding_id=finding.id,
                error=str(e),
            )

            try:
                repo.reset_hard("HEAD")
                repo.checkout_branch(original_branch)
            except Exception as rollback_error:
                logger.error("rollback_failed", error=str(rollback_error))

            self._emit_progress(
                "autonomous_fix_failed",
                finding_id=finding.id,
                error=str(e),
            )

            raise

    def _generate_commit_message(
        self,
        finding: Finding,
        result: FixResult,
    ) -> str:
        """
        Generate commit message for autonomous fix.

        Args:
            finding: Finding that was fixed
            result: Fix result from agent

        Returns:
            Commit message
        """
        cwe_info = f" ({finding.cwe.id})" if finding.cwe else ""

        message = f"""Fix {finding.id}: {finding.rule_id}

{result.description}

Finding Details:
- Severity: {finding.severity.value.upper()}{cwe_info}
- Location: {finding.file_path}:{finding.start_line}
- Message: {finding.message}

Fix Details:
- Confidence: {result.confidence:.0%}
- Files Modified: {len(result.files_modified)}
  {chr(10).join(f'  - {f}' for f in result.files_modified[:10])}

🤖 Autonomous fix generated by Patchsmith
"""
        return message

    def _create_pull_request(
        self,
        finding: Finding,
        result: FixResult,
        branch_name: str,
        working_dir: Path,
    ) -> str | None:
        """
        Create GitHub PR using gh CLI.

        Args:
            finding: Finding that was fixed
            result: Fix result
            branch_name: Branch name with fix
            working_dir: Working directory

        Returns:
            PR URL if successful, None if gh CLI not available or failed
        """
        cwe_info = f" ({finding.cwe.id})" if finding.cwe else ""

        pr_body = f"""## 🔒 Security Fix: {finding.rule_id}

{result.description}

### Finding Details
- **ID:** {finding.id}
- **Severity:** {finding.severity.value.upper()}{cwe_info}
- **Location:** `{finding.file_path}:{finding.start_line}`
- **Message:** {finding.message}

### Fix Details
- **Confidence:** {result.confidence:.0%}
- **Files Modified:** {len(result.files_modified)}
{chr(10).join(f'  - `{f}`' for f in result.files_modified)}

### Review Checklist
- [ ] Fix addresses the security vulnerability
- [ ] No functionality broken
- [ ] Tests pass (if applicable)
- [ ] Code style consistent with project

---
🤖 **Autonomous fix generated by [Patchsmith](https://github.com/patchsmith/patchsmith)**
"""

        try:
            # Check if gh is available
            result_check = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                timeout=5,
            )

            if result_check.returncode != 0:
                logger.info("gh_cli_not_available")
                return None

            # Create PR
            logger.info("creating_pull_request", branch=branch_name)

            result_pr = subprocess.run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--title",
                    f"[Security] Fix {finding.id}: {finding.rule_id}",
                    "--body",
                    pr_body,
                    "--base",
                    "main",
                ],
                capture_output=True,
                text=True,
                cwd=working_dir,
                timeout=30,
            )

            if result_pr.returncode == 0:
                pr_url = result_pr.stdout.strip()
                logger.info("pull_request_created", pr_url=pr_url)
                return pr_url
            else:
                logger.warning(
                    "pull_request_creation_failed",
                    stderr=result_pr.stderr,
                )
                return None

        except FileNotFoundError:
            logger.info("gh_cli_not_installed")
            return None
        except subprocess.TimeoutExpired:
            logger.warning("gh_cli_timeout")
            return None
        except Exception as e:
            logger.warning("pull_request_error", error=str(e))
            return None
