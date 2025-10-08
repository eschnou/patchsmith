"""Tests for Git repository wrapper."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from patchsmith.adapters.git.repository import GitError, GitRepository


class TestGitRepository:
    """Tests for GitRepository."""

    def test_init_valid_repo(self, tmp_path: Path) -> None:
        """Test initialization with valid Git repository."""
        # Create a .git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        repo = GitRepository(tmp_path)

        assert repo.repo_path == tmp_path.resolve()

    def test_init_invalid_repo(self, tmp_path: Path) -> None:
        """Test initialization with invalid repository."""
        # No .git directory
        with pytest.raises(GitError, match="Not a Git repository"):
            GitRepository(tmp_path)

    def test_is_git_repo_valid(self, tmp_path: Path) -> None:
        """Test Git repository detection."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        repo = GitRepository(tmp_path)

        assert repo._is_git_repo() is True

    def test_is_git_repo_invalid(self, tmp_path: Path) -> None:
        """Test non-Git directory detection."""
        # Create valid repo first
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        repo = GitRepository(tmp_path)

        # Remove .git to make it invalid
        import shutil
        shutil.rmtree(git_dir)

        assert repo._is_git_repo() is False

    @patch("subprocess.run")
    def test_run_git_command_success(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test successful Git command execution."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status"],
            returncode=0,
            stdout="On branch main",
            stderr="",
        )

        repo = GitRepository(tmp_path)
        result = repo._run_git_command(["status"])

        assert result.returncode == 0
        assert "On branch main" in result.stdout
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_run_git_command_failure(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test failed Git command execution."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["git", "status"],
            stderr="fatal: error",
        )

        repo = GitRepository(tmp_path)

        with pytest.raises(GitError, match="Git command failed"):
            repo._run_git_command(["status"])

    @patch("subprocess.run")
    def test_get_current_branch(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test getting current branch."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "branch", "--show-current"],
            returncode=0,
            stdout="main\n",
            stderr="",
        )

        repo = GitRepository(tmp_path)
        branch = repo.get_current_branch()

        assert branch == "main"

    @patch("subprocess.run")
    def test_get_current_branch_detached(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test getting branch when HEAD is detached."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "branch", "--show-current"],
            returncode=0,
            stdout="",  # Empty = detached HEAD
            stderr="",
        )

        repo = GitRepository(tmp_path)

        with pytest.raises(GitError, match="Could not determine current branch"):
            repo.get_current_branch()

    @patch("subprocess.run")
    def test_branch_exists_true(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test checking if branch exists (exists)."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "rev-parse", "--verify", "feature-branch"],
            returncode=0,
            stdout="abc123",
            stderr="",
        )

        repo = GitRepository(tmp_path)
        exists = repo.branch_exists("feature-branch")

        assert exists is True

    @patch("subprocess.run")
    def test_branch_exists_false(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test checking if branch exists (doesn't exist)."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "rev-parse", "--verify", "nonexistent"],
            returncode=1,
            stdout="",
            stderr="fatal: no such ref",
        )

        repo = GitRepository(tmp_path)
        exists = repo.branch_exists("nonexistent")

        assert exists is False

    @patch("subprocess.run")
    def test_create_branch(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test creating a new branch."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Mock branch_exists to return False, then checkout, then get_current_branch for logging
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=["git", "rev-parse"], returncode=1, stdout="", stderr=""
            ),
            subprocess.CompletedProcess(
                args=["git", "checkout"], returncode=0, stdout="", stderr=""
            ),
            subprocess.CompletedProcess(
                args=["git", "branch"], returncode=0, stdout="feature-branch\n", stderr=""
            ),
        ]

        repo = GitRepository(tmp_path)
        repo.create_branch("feature-branch")

        assert mock_run.call_count == 3

    @patch("subprocess.run")
    def test_create_branch_already_exists(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test creating branch that already exists."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Mock branch_exists to return True
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "rev-parse"], returncode=0, stdout="abc123", stderr=""
        )

        repo = GitRepository(tmp_path)

        with pytest.raises(GitError, match="Branch already exists"):
            repo.create_branch("existing-branch")

    @patch("subprocess.run")
    def test_checkout_branch(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test checking out a branch."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.side_effect = [
            # branch_exists check
            subprocess.CompletedProcess(
                args=["git", "rev-parse"], returncode=0, stdout="abc123", stderr=""
            ),
            # checkout
            subprocess.CompletedProcess(
                args=["git", "checkout"], returncode=0, stdout="", stderr=""
            ),
        ]

        repo = GitRepository(tmp_path)
        repo.checkout_branch("main")

        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_has_uncommitted_changes_true(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test detecting uncommitted changes."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout=" M file.txt\n",
            stderr="",
        )

        repo = GitRepository(tmp_path)
        has_changes = repo.has_uncommitted_changes()

        assert has_changes is True

    @patch("subprocess.run")
    def test_has_uncommitted_changes_false(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test detecting clean working directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout="",
            stderr="",
        )

        repo = GitRepository(tmp_path)
        has_changes = repo.has_uncommitted_changes()

        assert has_changes is False

    @patch("subprocess.run")
    def test_stage_file(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test staging a file."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "add"], returncode=0, stdout="", stderr=""
        )

        repo = GitRepository(tmp_path)
        test_file = tmp_path / "test.txt"
        repo.stage_file(test_file)

        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_commit(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test creating a commit."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.side_effect = [
            # has_uncommitted_changes
            subprocess.CompletedProcess(
                args=["git", "status"], returncode=0, stdout=" M file.txt", stderr=""
            ),
            # is_protected_branch -> get_current_branch
            subprocess.CompletedProcess(
                args=["git", "branch"], returncode=0, stdout="feature\n", stderr=""
            ),
            # commit
            subprocess.CompletedProcess(
                args=["git", "commit"], returncode=0, stdout="", stderr=""
            ),
            # rev-parse to get SHA
            subprocess.CompletedProcess(
                args=["git", "rev-parse"], returncode=0, stdout="abc123def\n", stderr=""
            ),
        ]

        repo = GitRepository(tmp_path)
        commit_sha = repo.commit("Test commit message")

        assert commit_sha == "abc123def"
        assert mock_run.call_count == 4

    @patch("subprocess.run")
    def test_commit_no_changes(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test commit with no changes."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status"], returncode=0, stdout="", stderr=""
        )

        repo = GitRepository(tmp_path)

        with pytest.raises(GitError, match="No changes to commit"):
            repo.commit("Test message")

    @patch("subprocess.run")
    def test_get_remote_url(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test getting remote URL."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "remote", "get-url"],
            returncode=0,
            stdout="https://github.com/user/repo.git\n",
            stderr="",
        )

        repo = GitRepository(tmp_path)
        url = repo.get_remote_url()

        assert url == "https://github.com/user/repo.git"

    @patch("subprocess.run")
    def test_get_remote_url_not_found(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test getting URL for non-existent remote."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "remote", "get-url"],
            returncode=2,
            stdout="",
            stderr="fatal: no such remote",
        )

        repo = GitRepository(tmp_path)
        url = repo.get_remote_url("nonexistent")

        assert url is None

    @patch("subprocess.run")
    def test_push_branch(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test pushing a branch."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.side_effect = [
            # get_current_branch
            subprocess.CompletedProcess(
                args=["git", "branch"], returncode=0, stdout="feature\n", stderr=""
            ),
            # push
            subprocess.CompletedProcess(
                args=["git", "push"], returncode=0, stdout="", stderr=""
            ),
        ]

        repo = GitRepository(tmp_path)
        repo.push_branch()

        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_get_diff(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test getting diff."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "diff"],
            returncode=0,
            stdout="diff --git a/file.txt b/file.txt\n...",
            stderr="",
        )

        repo = GitRepository(tmp_path)
        diff = repo.get_diff()

        assert "diff --git" in diff

    @patch("subprocess.run")
    def test_reset_hard(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test hard reset."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "reset"], returncode=0, stdout="", stderr=""
        )

        repo = GitRepository(tmp_path)
        repo.reset_hard("HEAD")

        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_is_clean_true(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test checking clean working directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout="",
            stderr="",
        )

        repo = GitRepository(tmp_path)
        is_clean = repo.is_clean()

        assert is_clean is True

    @patch("subprocess.run")
    def test_is_clean_false(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test checking dirty working directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout=" M file.txt\n",
            stderr="",
        )

        repo = GitRepository(tmp_path)
        is_clean = repo.is_clean()

        assert is_clean is False

    @patch("subprocess.run")
    def test_is_protected_branch_main(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test detecting protected branch (main)."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "branch", "--show-current"],
            returncode=0,
            stdout="main\n",
            stderr="",
        )

        repo = GitRepository(tmp_path)
        is_protected = repo.is_protected_branch()

        assert is_protected is True

    @patch("subprocess.run")
    def test_is_protected_branch_master(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test detecting protected branch (master)."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=["git", "branch"], returncode=0, stdout="master\n", stderr=""
            ),
        ]

        repo = GitRepository(tmp_path)
        is_protected = repo.is_protected_branch("master")

        assert is_protected is True

    @patch("subprocess.run")
    def test_is_protected_branch_feature(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test detecting non-protected branch."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "branch", "--show-current"],
            returncode=0,
            stdout="feature/new-feature\n",
            stderr="",
        )

        repo = GitRepository(tmp_path)
        is_protected = repo.is_protected_branch()

        assert is_protected is False

    @patch("subprocess.run")
    def test_commit_protected_branch_fails(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test that commit fails on protected branch."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.side_effect = [
            # has_uncommitted_changes
            subprocess.CompletedProcess(
                args=["git", "status"], returncode=0, stdout=" M file.txt", stderr=""
            ),
            # is_protected_branch -> get_current_branch (first call)
            subprocess.CompletedProcess(
                args=["git", "branch"], returncode=0, stdout="main\n", stderr=""
            ),
            # is_protected_branch -> get_current_branch (second call for error message)
            subprocess.CompletedProcess(
                args=["git", "branch"], returncode=0, stdout="main\n", stderr=""
            ),
        ]

        repo = GitRepository(tmp_path)

        with pytest.raises(GitError, match="Cannot commit directly to protected branch"):
            repo.commit("Test commit message")

    @patch("subprocess.run")
    def test_commit_protected_branch_with_override(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test that commit succeeds on protected branch with override."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_run.side_effect = [
            # has_uncommitted_changes
            subprocess.CompletedProcess(
                args=["git", "status"], returncode=0, stdout=" M file.txt", stderr=""
            ),
            # commit (no protected branch check since allow_protected=True)
            subprocess.CompletedProcess(
                args=["git", "commit"], returncode=0, stdout="", stderr=""
            ),
            # rev-parse to get SHA
            subprocess.CompletedProcess(
                args=["git", "rev-parse"], returncode=0, stdout="abc123def\n", stderr=""
            ),
        ]

        repo = GitRepository(tmp_path)
        commit_sha = repo.commit("Test commit message", allow_protected=True)

        assert commit_sha == "abc123def"
        assert mock_run.call_count == 3
