"""Git repository operations wrapper."""

import subprocess
from pathlib import Path

from patchsmith.utils.logging import get_logger

logger = get_logger()


class GitError(Exception):
    """Git operation error."""

    pass


class GitRepository:
    """Wrapper for Git repository operations.

    Provides safe, validated Git operations for creating branches,
    committing changes, and managing repository state.
    """

    def __init__(self, repo_path: Path):
        """
        Initialize Git repository wrapper.

        Args:
            repo_path: Path to Git repository root

        Raises:
            GitError: If path is not a valid Git repository
        """
        self.repo_path = repo_path.resolve()

        if not self._is_git_repo():
            raise GitError(f"Not a Git repository: {self.repo_path}")

        logger.info("git_repository_initialized", repo_path=str(self.repo_path))

    def _is_git_repo(self) -> bool:
        """
        Check if path is a Git repository.

        Returns:
            True if valid Git repository
        """
        git_dir = self.repo_path / ".git"
        return git_dir.exists() and git_dir.is_dir()

    def _run_git_command(
        self,
        args: list[str],
        check: bool = True,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess:
        """
        Run a Git command.

        Args:
            args: Git command arguments (without 'git')
            check: Raise error if command fails
            capture_output: Capture stdout/stderr

        Returns:
            CompletedProcess result

        Raises:
            GitError: If command fails and check=True
        """
        cmd = ["git", "-C", str(self.repo_path)] + args

        logger.debug(
            "git_command_starting",
            command=" ".join(args),
            cwd=str(self.repo_path),
        )

        try:
            result = subprocess.run(
                cmd,
                check=check,
                capture_output=capture_output,
                text=True,
            )

            logger.debug(
                "git_command_completed",
                command=" ".join(args),
                returncode=result.returncode,
            )

            return result

        except subprocess.CalledProcessError as e:
            logger.error(
                "git_command_failed",
                command=" ".join(args),
                returncode=e.returncode,
                stderr=e.stderr if capture_output else None,
            )
            raise GitError(f"Git command failed: {' '.join(args)}\n{e.stderr}") from e

    def get_current_branch(self) -> str:
        """
        Get current branch name.

        Returns:
            Current branch name

        Raises:
            GitError: If operation fails
        """
        result = self._run_git_command(["branch", "--show-current"])
        branch = result.stdout.strip()

        if not branch:
            raise GitError("Could not determine current branch (detached HEAD?)")

        return str(branch)

    def branch_exists(self, branch_name: str) -> bool:
        """
        Check if a branch exists.

        Args:
            branch_name: Branch name to check

        Returns:
            True if branch exists
        """
        result = self._run_git_command(
            ["rev-parse", "--verify", branch_name],
            check=False,
        )
        return result.returncode == 0

    def create_branch(self, branch_name: str, from_branch: str | None = None) -> None:
        """
        Create a new branch.

        Args:
            branch_name: Name of branch to create
            from_branch: Base branch (defaults to current branch)

        Raises:
            GitError: If branch exists or creation fails
        """
        if self.branch_exists(branch_name):
            raise GitError(f"Branch already exists: {branch_name}")

        args = ["checkout", "-b", branch_name]
        if from_branch:
            args.append(from_branch)

        self._run_git_command(args)

        logger.info(
            "git_branch_created",
            branch_name=branch_name,
            from_branch=from_branch or self.get_current_branch(),
        )

    def checkout_branch(self, branch_name: str) -> None:
        """
        Checkout an existing branch.

        Args:
            branch_name: Branch to checkout

        Raises:
            GitError: If branch doesn't exist or checkout fails
        """
        if not self.branch_exists(branch_name):
            raise GitError(f"Branch does not exist: {branch_name}")

        self._run_git_command(["checkout", branch_name])

        logger.info("git_branch_checked_out", branch_name=branch_name)

    def has_uncommitted_changes(self) -> bool:
        """
        Check if repository has uncommitted changes.

        Returns:
            True if there are uncommitted changes
        """
        result = self._run_git_command(["status", "--porcelain"])
        return bool(result.stdout.strip())

    def is_clean(self) -> bool:
        """
        Check if repository working directory is clean.

        Returns:
            True if no uncommitted changes
        """
        return not self.has_uncommitted_changes()

    def is_protected_branch(self, branch_name: str | None = None) -> bool:
        """
        Check if a branch is protected (main, master, develop, production).

        Args:
            branch_name: Branch name to check (defaults to current branch)

        Returns:
            True if branch is protected
        """
        if branch_name is None:
            branch_name = self.get_current_branch()

        protected_branches = {"main", "master", "develop", "production"}
        return branch_name.lower() in protected_branches

    def stage_file(self, file_path: Path) -> None:
        """
        Stage a file for commit.

        Args:
            file_path: Path to file to stage (relative or absolute)

        Raises:
            GitError: If staging fails
        """
        # Convert to relative path if absolute
        if file_path.is_absolute():
            try:
                file_path = file_path.relative_to(self.repo_path)
            except ValueError as e:
                raise GitError(f"File not in repository: {file_path}") from e

        self._run_git_command(["add", str(file_path)])

        logger.debug("git_file_staged", file_path=str(file_path))

    def stage_all(self) -> None:
        """
        Stage all modified and new files in the repository.

        This is equivalent to `git add -A`.

        Raises:
            GitError: If staging fails
        """
        self._run_git_command(["add", "-A"])

        logger.debug("git_all_files_staged")

    def commit(
        self,
        message: str,
        author_name: str | None = None,
        author_email: str | None = None,
        allow_protected: bool = False,
    ) -> str:
        """
        Create a commit with staged changes.

        Args:
            message: Commit message
            author_name: Optional author name override
            author_email: Optional author email override
            allow_protected: Allow commits to protected branches (default: False)

        Returns:
            Commit SHA

        Raises:
            GitError: If commit fails or attempting to commit to protected branch
        """
        if not self.has_uncommitted_changes():
            raise GitError("No changes to commit")

        # Safety check: prevent commits to protected branches
        if not allow_protected and self.is_protected_branch():
            current_branch = self.get_current_branch()
            raise GitError(
                f"Cannot commit directly to protected branch '{current_branch}'. "
                "Create a feature branch instead."
            )

        args = ["commit", "-m", message]

        if author_name and author_email:
            args.extend(["--author", f"{author_name} <{author_email}>"])

        self._run_git_command(args)

        # Get commit SHA
        result = self._run_git_command(["rev-parse", "HEAD"])
        commit_sha = str(result.stdout.strip())

        logger.info(
            "git_commit_created",
            commit_sha=commit_sha[:8],
            message=message[:50],
        )

        return commit_sha

    def get_remote_url(self, remote: str = "origin") -> str | None:
        """
        Get URL of a remote.

        Args:
            remote: Remote name (default: origin)

        Returns:
            Remote URL or None if remote doesn't exist
        """
        result = self._run_git_command(
            ["remote", "get-url", remote],
            check=False,
        )

        if result.returncode == 0:
            return str(result.stdout.strip())

        return None

    def push_branch(
        self,
        branch_name: str | None = None,
        remote: str = "origin",
        set_upstream: bool = True,
    ) -> None:
        """
        Push branch to remote.

        Args:
            branch_name: Branch to push (defaults to current branch)
            remote: Remote name (default: origin)
            set_upstream: Set upstream tracking

        Raises:
            GitError: If push fails
        """
        if branch_name is None:
            branch_name = self.get_current_branch()

        args = ["push"]
        if set_upstream:
            args.extend(["-u", remote, branch_name])
        else:
            args.extend([remote, branch_name])

        self._run_git_command(args)

        logger.info(
            "git_branch_pushed",
            branch_name=branch_name,
            remote=remote,
        )

    def get_diff(
        self,
        cached: bool = False,
        file_path: Path | None = None,
    ) -> str:
        """
        Get diff of changes.

        Args:
            cached: Show staged changes only
            file_path: Limit to specific file

        Returns:
            Diff output
        """
        args = ["diff"]
        if cached:
            args.append("--cached")
        if file_path:
            args.append(str(file_path))

        result = self._run_git_command(args)
        return str(result.stdout)

    def get_file_content(self, file_path: Path, ref: str = "HEAD") -> str:
        """
        Get file content at a specific ref.

        Args:
            file_path: Path to file (relative to repo root)
            ref: Git ref (default: HEAD)

        Returns:
            File content

        Raises:
            GitError: If file doesn't exist at ref
        """
        result = self._run_git_command(["show", f"{ref}:{file_path}"])
        return str(result.stdout)

    def reset_hard(self, ref: str = "HEAD") -> None:
        """
        Hard reset to a ref. USE WITH CAUTION.

        Args:
            ref: Git ref to reset to

        Raises:
            GitError: If reset fails
        """
        logger.warning("git_hard_reset", ref=ref, repo_path=str(self.repo_path))
        self._run_git_command(["reset", "--hard", ref])
