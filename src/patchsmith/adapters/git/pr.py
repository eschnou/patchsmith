"""Pull request creation using GitHub CLI."""

import subprocess
from pathlib import Path

from patchsmith.utils.logging import get_logger

logger = get_logger()


class PRError(Exception):
    """Pull request creation error."""

    pass


class PRCreator:
    """Wrapper for GitHub pull request operations using gh CLI.

    Requires GitHub CLI (gh) to be installed and authenticated.
    """

    def __init__(self, repo_path: Path):
        """
        Initialize PR creator.

        Args:
            repo_path: Path to Git repository root

        Raises:
            PRError: If gh CLI is not available
        """
        self.repo_path = repo_path.resolve()

        if not self._is_gh_available():
            raise PRError("GitHub CLI (gh) is not installed or not in PATH")

        logger.info("pr_creator_initialized", repo_path=str(self.repo_path))

    def _is_gh_available(self) -> bool:
        """
        Check if gh CLI is available.

        Returns:
            True if gh CLI is available
        """
        try:
            subprocess.run(
                ["gh", "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _run_gh_command(
        self,
        args: list[str],
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """
        Run a gh command.

        Args:
            args: gh command arguments (without 'gh')
            check: Raise error if command fails

        Returns:
            CompletedProcess result

        Raises:
            PRError: If command fails and check=True
        """
        cmd = ["gh", "-R", str(self.repo_path)] + args

        logger.debug(
            "gh_command_starting",
            command=" ".join(args),
            cwd=str(self.repo_path),
        )

        try:
            result = subprocess.run(
                cmd,
                check=check,
                capture_output=True,
                text=True,
            )

            logger.debug(
                "gh_command_completed",
                command=" ".join(args),
                returncode=result.returncode,
            )

            return result

        except subprocess.CalledProcessError as e:
            logger.error(
                "gh_command_failed",
                command=" ".join(args),
                returncode=e.returncode,
                stderr=e.stderr,
            )
            raise PRError(f"GitHub CLI command failed: {' '.join(args)}\n{e.stderr}") from e

    def is_authenticated(self) -> bool:
        """
        Check if gh CLI is authenticated.

        Returns:
            True if authenticated
        """
        result = self._run_gh_command(["auth", "status"], check=False)
        return result.returncode == 0

    def create_pr(
        self,
        title: str,
        body: str,
        branch: str | None = None,
        base: str = "main",
        draft: bool = False,
    ) -> str:
        """
        Create a pull request.

        Args:
            title: PR title
            body: PR description
            branch: Source branch (defaults to current branch)
            base: Target branch (default: main)
            draft: Create as draft PR

        Returns:
            PR URL

        Raises:
            PRError: If PR creation fails
        """
        if not self.is_authenticated():
            raise PRError("GitHub CLI is not authenticated. Run 'gh auth login'")

        args = [
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body,
            "--base",
            base,
        ]

        if branch:
            args.extend(["--head", branch])

        if draft:
            args.append("--draft")

        result = self._run_gh_command(args)
        pr_url = str(result.stdout.strip())

        logger.info(
            "pr_created",
            title=title,
            branch=branch or "current",
            base=base,
            url=pr_url,
        )

        return pr_url

    def get_pr_url(self, branch: str | None = None) -> str | None:
        """
        Get PR URL for a branch.

        Args:
            branch: Branch name (defaults to current branch)

        Returns:
            PR URL or None if no PR exists
        """
        args = ["pr", "view", "--json", "url", "--jq", ".url"]
        if branch:
            args.extend(["--branch", branch])

        result = self._run_gh_command(args, check=False)

        if result.returncode == 0 and result.stdout.strip():
            return str(result.stdout.strip())

        return None

    def pr_exists(self, branch: str | None = None) -> bool:
        """
        Check if PR exists for a branch.

        Args:
            branch: Branch name (defaults to current branch)

        Returns:
            True if PR exists
        """
        return self.get_pr_url(branch) is not None
