"""Tests for PR creator."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from patchsmith.adapters.git.pr import PRCreator, PRError


class TestPRCreator:
    """Tests for PRCreator."""

    @patch("subprocess.run")
    def test_init_gh_available(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test initialization with gh CLI available."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "--version"],
            returncode=0,
            stdout="gh version 2.40.0\n",
            stderr="",
        )

        creator = PRCreator(tmp_path)

        assert creator.repo_path == tmp_path.resolve()
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_init_gh_not_available(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test initialization when gh CLI not available."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(PRError, match="GitHub CLI.*not installed"):
            PRCreator(tmp_path)

    @patch("subprocess.run")
    def test_is_gh_available_true(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test gh CLI detection when available."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "--version"],
            returncode=0,
            stdout="gh version 2.40.0\n",
            stderr="",
        )

        creator = PRCreator(tmp_path)
        assert creator._is_gh_available() is True

    @patch("subprocess.run")
    def test_is_gh_available_false(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test gh CLI detection when not available."""
        mock_run.side_effect = [
            # First call for __init__
            subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="", stderr=""
            ),
            # Second call for _is_gh_available check
            FileNotFoundError(),
        ]

        creator = PRCreator(tmp_path)
        assert creator._is_gh_available() is False

    @patch("subprocess.run")
    def test_is_authenticated_true(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test authentication check when authenticated."""
        mock_run.side_effect = [
            # __init__ check
            subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="", stderr=""
            ),
            # is_authenticated check
            subprocess.CompletedProcess(
                args=["gh", "auth", "status"], returncode=0, stdout="", stderr=""
            ),
        ]

        creator = PRCreator(tmp_path)
        assert creator.is_authenticated() is True

    @patch("subprocess.run")
    def test_is_authenticated_false(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test authentication check when not authenticated."""
        mock_run.side_effect = [
            # __init__ check
            subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="", stderr=""
            ),
            # is_authenticated check
            subprocess.CompletedProcess(
                args=["gh", "auth", "status"], returncode=1, stdout="", stderr=""
            ),
        ]

        creator = PRCreator(tmp_path)
        assert creator.is_authenticated() is False

    @patch("subprocess.run")
    def test_create_pr_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful PR creation."""
        mock_run.side_effect = [
            # __init__ check
            subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="", stderr=""
            ),
            # is_authenticated check
            subprocess.CompletedProcess(
                args=["gh", "auth", "status"], returncode=0, stdout="", stderr=""
            ),
            # create PR
            subprocess.CompletedProcess(
                args=["gh", "pr", "create"],
                returncode=0,
                stdout="https://github.com/user/repo/pull/123\n",
                stderr="",
            ),
        ]

        creator = PRCreator(tmp_path)
        pr_url = creator.create_pr(
            title="Fix security issue",
            body="This PR fixes a security vulnerability",
            branch="fix/security",
            base="main",
        )

        assert pr_url == "https://github.com/user/repo/pull/123"

    @patch("subprocess.run")
    def test_create_pr_not_authenticated(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test PR creation when not authenticated."""
        mock_run.side_effect = [
            # __init__ check
            subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="", stderr=""
            ),
            # is_authenticated check
            subprocess.CompletedProcess(
                args=["gh", "auth", "status"], returncode=1, stdout="", stderr=""
            ),
        ]

        creator = PRCreator(tmp_path)

        with pytest.raises(PRError, match="not authenticated"):
            creator.create_pr(title="Test", body="Test PR")

    @patch("subprocess.run")
    def test_create_pr_draft(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test creating a draft PR."""
        mock_run.side_effect = [
            # __init__ check
            subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="", stderr=""
            ),
            # is_authenticated check
            subprocess.CompletedProcess(
                args=["gh", "auth", "status"], returncode=0, stdout="", stderr=""
            ),
            # create draft PR
            subprocess.CompletedProcess(
                args=["gh", "pr", "create"],
                returncode=0,
                stdout="https://github.com/user/repo/pull/124\n",
                stderr="",
            ),
        ]

        creator = PRCreator(tmp_path)
        pr_url = creator.create_pr(
            title="Draft PR",
            body="Work in progress",
            draft=True,
        )

        assert pr_url == "https://github.com/user/repo/pull/124"
        # Verify --draft flag was passed
        call_args = mock_run.call_args_list[2][0][0]
        assert "--draft" in call_args

    @patch("subprocess.run")
    def test_create_pr_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test PR creation failure."""
        mock_run.side_effect = [
            # __init__ check
            subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="", stderr=""
            ),
            # is_authenticated check
            subprocess.CompletedProcess(
                args=["gh", "auth", "status"], returncode=0, stdout="", stderr=""
            ),
            # create PR fails
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["gh", "pr", "create"],
                stderr="error: pull request already exists",
            ),
        ]

        creator = PRCreator(tmp_path)

        with pytest.raises(PRError, match="GitHub CLI command failed"):
            creator.create_pr(title="Test", body="Test PR")

    @patch("subprocess.run")
    def test_get_pr_url_exists(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test getting PR URL when PR exists."""
        mock_run.side_effect = [
            # __init__ check
            subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="", stderr=""
            ),
            # get PR URL
            subprocess.CompletedProcess(
                args=["gh", "pr", "view"],
                returncode=0,
                stdout="https://github.com/user/repo/pull/123\n",
                stderr="",
            ),
        ]

        creator = PRCreator(tmp_path)
        pr_url = creator.get_pr_url(branch="feature")

        assert pr_url == "https://github.com/user/repo/pull/123"

    @patch("subprocess.run")
    def test_get_pr_url_not_exists(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test getting PR URL when PR doesn't exist."""
        mock_run.side_effect = [
            # __init__ check
            subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="", stderr=""
            ),
            # get PR URL - not found
            subprocess.CompletedProcess(
                args=["gh", "pr", "view"],
                returncode=1,
                stdout="",
                stderr="no pull requests found",
            ),
        ]

        creator = PRCreator(tmp_path)
        pr_url = creator.get_pr_url()

        assert pr_url is None

    @patch("subprocess.run")
    def test_pr_exists_true(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test PR existence check when PR exists."""
        mock_run.side_effect = [
            # __init__ check
            subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="", stderr=""
            ),
            # get PR URL
            subprocess.CompletedProcess(
                args=["gh", "pr", "view"],
                returncode=0,
                stdout="https://github.com/user/repo/pull/123\n",
                stderr="",
            ),
        ]

        creator = PRCreator(tmp_path)
        exists = creator.pr_exists(branch="feature")

        assert exists is True

    @patch("subprocess.run")
    def test_pr_exists_false(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test PR existence check when PR doesn't exist."""
        mock_run.side_effect = [
            # __init__ check
            subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="", stderr=""
            ),
            # get PR URL - not found
            subprocess.CompletedProcess(
                args=["gh", "pr", "view"],
                returncode=1,
                stdout="",
                stderr="no pull requests found",
            ),
        ]

        creator = PRCreator(tmp_path)
        exists = creator.pr_exists()

        assert exists is False

    @patch("subprocess.run")
    def test_run_gh_command_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful gh command execution."""
        mock_run.side_effect = [
            # __init__ check
            subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="", stderr=""
            ),
            # actual command
            subprocess.CompletedProcess(
                args=["gh", "repo", "view"],
                returncode=0,
                stdout="repo info\n",
                stderr="",
            ),
        ]

        creator = PRCreator(tmp_path)
        result = creator._run_gh_command(["repo", "view"])

        assert result.returncode == 0
        assert "repo info" in result.stdout

    @patch("subprocess.run")
    def test_run_gh_command_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test failed gh command execution."""
        mock_run.side_effect = [
            # __init__ check
            subprocess.CompletedProcess(
                args=["gh", "--version"], returncode=0, stdout="", stderr=""
            ),
            # command fails
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["gh", "repo", "view"],
                stderr="error: repository not found",
            ),
        ]

        creator = PRCreator(tmp_path)

        with pytest.raises(PRError, match="GitHub CLI command failed"):
            creator._run_gh_command(["repo", "view"])
