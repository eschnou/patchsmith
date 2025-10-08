"""Fix service for generating and applying security patches."""

from pathlib import Path
from typing import Any, Callable

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
