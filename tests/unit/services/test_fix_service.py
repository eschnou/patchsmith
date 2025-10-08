"""Tests for FixService class."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from patchsmith.adapters.claude.fix_generator_agent import Fix
from patchsmith.models.config import PatchsmithConfig
from patchsmith.models.finding import CWE, Finding, Severity
from patchsmith.services.fix_service import FixService


class TestFixService:
    """Test FixService functionality."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> PatchsmithConfig:
        """Create test configuration."""
        return PatchsmithConfig.create_default(project_root=tmp_path)

    @pytest.fixture
    def service(self, config: PatchsmithConfig) -> FixService:
        """Create FixService instance."""
        return FixService(config=config)

    @pytest.fixture
    def mock_finding(self, tmp_path: Path) -> Finding:
        """Create a mock finding."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def vulnerable():\n    query = 'SELECT * WHERE id=' + user_input\n")

        return Finding(
            id="test-finding-1",
            rule_id="py/sql-injection",
            message="SQL injection vulnerability",
            severity=Severity.HIGH,
            file_path=test_file,
            start_line=2,
            end_line=2,
            snippet="query = 'SELECT * WHERE id=' + user_input",
            cwe=CWE(id="CWE-89", name="SQL Injection"),
        )

    @pytest.fixture
    def mock_fix(self, tmp_path: Path) -> Fix:
        """Create a mock fix."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def vulnerable():\n    query = 'SELECT * WHERE id=' + user_input\n")

        return Fix(
            finding_id="test-finding-1",
            file_path=test_file,
            original_code="    query = 'SELECT * WHERE id=' + user_input",
            fixed_code="    query = 'SELECT * WHERE id=?'\n    cursor.execute(query, (user_input,))",
            explanation="Use parameterized query to prevent SQL injection",
            confidence=0.95,
        )

    def test_init(self, config: PatchsmithConfig) -> None:
        """Test service initialization."""
        service = FixService(config=config)

        assert service.config == config
        assert service.service_name == "FixService"

    def test_init_with_callback(self, config: PatchsmithConfig) -> None:
        """Test service initialization with progress callback."""
        callback = MagicMock()
        service = FixService(config=config, progress_callback=callback)

        assert service.progress_callback == callback

    @pytest.mark.asyncio
    async def test_generate_fix_success(
        self,
        service: FixService,
        mock_finding: Finding,
        mock_fix: Fix,
        tmp_path: Path,
    ) -> None:
        """Test successful fix generation."""
        with patch(
            "patchsmith.services.fix_service.FixGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = mock_fix
            mock_agent.return_value = mock_instance

            result = await service.generate_fix(
                finding=mock_finding,
                working_dir=tmp_path,
                context_lines=10,
            )

            assert result == mock_fix
            mock_agent.assert_called_once_with(
                working_dir=tmp_path,
                max_turns=service.config.llm.max_turns,
            )
            mock_instance.execute.assert_called_once_with(
                finding=mock_finding,
                context_lines=10,
            )

    @pytest.mark.asyncio
    async def test_generate_fix_no_result(
        self,
        service: FixService,
        mock_finding: Finding,
        tmp_path: Path,
    ) -> None:
        """Test fix generation with no result (low confidence)."""
        with patch(
            "patchsmith.services.fix_service.FixGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = None
            mock_agent.return_value = mock_instance

            result = await service.generate_fix(
                finding=mock_finding,
                working_dir=tmp_path,
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_generate_fix_progress_callbacks(
        self,
        config: PatchsmithConfig,
        mock_finding: Finding,
        mock_fix: Fix,
        tmp_path: Path,
    ) -> None:
        """Test that progress callbacks are emitted during fix generation."""
        callback = MagicMock()
        service = FixService(config=config, progress_callback=callback)

        with patch(
            "patchsmith.services.fix_service.FixGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = mock_fix
            mock_agent.return_value = mock_instance

            await service.generate_fix(
                finding=mock_finding,
                working_dir=tmp_path,
            )

            callback_events = [call[0][0] for call in callback.call_args_list]
            assert "fix_generation_started" in callback_events
            assert "fix_generation_completed" in callback_events

    @pytest.mark.asyncio
    async def test_generate_fix_error_handling(
        self,
        config: PatchsmithConfig,
        mock_finding: Finding,
        tmp_path: Path,
    ) -> None:
        """Test error handling during fix generation."""
        callback = MagicMock()
        service = FixService(config=config, progress_callback=callback)

        with patch(
            "patchsmith.services.fix_service.FixGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.side_effect = Exception("Fix generation failed")
            mock_agent.return_value = mock_instance

            with pytest.raises(Exception, match="Fix generation failed"):
                await service.generate_fix(
                    finding=mock_finding,
                    working_dir=tmp_path,
                )

            callback_events = [call[0][0] for call in callback.call_args_list]
            assert "fix_generation_failed" in callback_events

    def test_apply_fix_success(
        self,
        service: FixService,
        mock_fix: Fix,
    ) -> None:
        """Test successful fix application without Git operations."""
        original_content = mock_fix.file_path.read_text()
        assert mock_fix.original_code in original_content

        success, message = service.apply_fix(
            fix=mock_fix,
            create_branch=False,
            commit=False,
        )

        assert success is True
        assert "applied" in message.lower()

        # Verify fix was applied
        new_content = mock_fix.file_path.read_text()
        assert mock_fix.original_code not in new_content
        assert mock_fix.fixed_code in new_content

    def test_apply_fix_file_not_found(
        self,
        service: FixService,
        tmp_path: Path,
    ) -> None:
        """Test fix application when file doesn't exist."""
        fix = Fix(
            finding_id="test-1",
            file_path=tmp_path / "nonexistent.py",
            original_code="old code",
            fixed_code="new code",
            explanation="Test fix",
            confidence=0.95,
        )

        success, message = service.apply_fix(fix, create_branch=False, commit=False)

        assert success is False
        assert "not found" in message.lower()

    def test_apply_fix_original_code_not_found(
        self,
        service: FixService,
        tmp_path: Path,
    ) -> None:
        """Test fix application when original code doesn't match."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def func():\n    pass\n")

        fix = Fix(
            finding_id="test-1",
            file_path=test_file,
            original_code="different code",
            fixed_code="new code",
            explanation="Test fix",
            confidence=0.95,
        )

        success, message = service.apply_fix(fix, create_branch=False, commit=False)

        assert success is False
        assert "not found" in message.lower()

    def test_apply_fix_with_git_branch(
        self,
        service: FixService,
        mock_fix: Fix,
    ) -> None:
        """Test fix application with Git branch creation."""
        with patch("patchsmith.services.fix_service.GitRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo

            success, message = service.apply_fix(
                fix=mock_fix,
                create_branch=True,
                commit=False,
                branch_name="custom-branch",
            )

            assert success is True
            mock_repo.create_branch.assert_called_once_with("custom-branch")

    def test_apply_fix_with_git_commit(
        self,
        service: FixService,
        mock_fix: Fix,
    ) -> None:
        """Test fix application with Git commit."""
        with patch("patchsmith.services.fix_service.GitRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.commit.return_value = "abc123"
            mock_repo_class.return_value = mock_repo

            success, message = service.apply_fix(
                fix=mock_fix,
                create_branch=False,
                commit=True,
            )

            assert success is True
            assert "committed" in message.lower()
            mock_repo.stage_file.assert_called_once_with(mock_fix.file_path)
            mock_repo.commit.assert_called_once()

    def test_apply_fix_with_branch_and_commit(
        self,
        service: FixService,
        mock_fix: Fix,
    ) -> None:
        """Test fix application with both branch creation and commit."""
        with patch("patchsmith.services.fix_service.GitRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.commit.return_value = "abc123"
            mock_repo_class.return_value = mock_repo

            success, message = service.apply_fix(
                fix=mock_fix,
                create_branch=True,
                commit=True,
            )

            assert success is True
            mock_repo.create_branch.assert_called_once()
            mock_repo.stage_file.assert_called_once()
            mock_repo.commit.assert_called_once()

    def test_apply_fix_branch_already_exists(
        self,
        service: FixService,
        mock_fix: Fix,
    ) -> None:
        """Test fix application when branch already exists."""
        with patch("patchsmith.services.fix_service.GitRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.create_branch.side_effect = Exception("Branch already exists")
            mock_repo_class.return_value = mock_repo

            # Should continue despite branch creation failure
            success, message = service.apply_fix(
                fix=mock_fix,
                create_branch=True,
                commit=False,
            )

            assert success is True

    def test_apply_fix_progress_callbacks(
        self,
        config: PatchsmithConfig,
        mock_fix: Fix,
    ) -> None:
        """Test that progress callbacks are emitted during fix application."""
        callback = MagicMock()
        service = FixService(config=config, progress_callback=callback)

        service.apply_fix(
            fix=mock_fix,
            create_branch=False,
            commit=False,
        )

        callback_events = [call[0][0] for call in callback.call_args_list]
        assert "fix_application_started" in callback_events
        assert "fix_applied_to_file" in callback_events
        assert "fix_application_completed" in callback_events

    def test_apply_fix_error_handling(
        self,
        config: PatchsmithConfig,
        tmp_path: Path,
    ) -> None:
        """Test error handling during fix application."""
        callback = MagicMock()
        service = FixService(config=config, progress_callback=callback)

        # Create a fix with a file that will cause an error
        fix = Fix(
            finding_id="test-1",
            file_path=tmp_path / "test.py",
            original_code="code",
            fixed_code="new code",
            explanation="Test",
            confidence=0.95,
        )

        with patch.object(Path, "read_text", side_effect=Exception("Read error")):
            with pytest.raises(Exception, match="Read error"):
                service.apply_fix(fix, create_branch=False, commit=False)

            callback_events = [call[0][0] for call in callback.call_args_list]
            assert "fix_application_failed" in callback_events

    @pytest.mark.asyncio
    async def test_generate_and_apply_fix_success(
        self,
        service: FixService,
        mock_finding: Finding,
        mock_fix: Fix,
        tmp_path: Path,
    ) -> None:
        """Test combined generate and apply operation."""
        with patch(
            "patchsmith.services.fix_service.FixGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = mock_fix
            mock_agent.return_value = mock_instance

            fix, applied, message = await service.generate_and_apply_fix(
                finding=mock_finding,
                working_dir=tmp_path,
                create_branch=False,
                commit=False,
            )

            assert fix == mock_fix
            assert applied is True
            assert "applied" in message.lower()

    @pytest.mark.asyncio
    async def test_generate_and_apply_fix_no_fix_generated(
        self,
        service: FixService,
        mock_finding: Finding,
        tmp_path: Path,
    ) -> None:
        """Test combined operation when no fix is generated."""
        with patch(
            "patchsmith.services.fix_service.FixGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = None
            mock_agent.return_value = mock_instance

            fix, applied, message = await service.generate_and_apply_fix(
                finding=mock_finding,
                working_dir=tmp_path,
            )

            assert fix is None
            assert applied is False
            assert "no fix generated" in message.lower()

    @pytest.mark.asyncio
    async def test_generate_and_apply_fix_application_fails(
        self,
        service: FixService,
        mock_finding: Finding,
        tmp_path: Path,
    ) -> None:
        """Test combined operation when fix application fails."""
        # Create fix with file that doesn't exist
        bad_fix = Fix(
            finding_id="test-1",
            file_path=tmp_path / "nonexistent.py",
            original_code="old",
            fixed_code="new",
            explanation="Test",
            confidence=0.95,
        )

        with patch(
            "patchsmith.services.fix_service.FixGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = bad_fix
            mock_agent.return_value = mock_instance

            fix, applied, message = await service.generate_and_apply_fix(
                finding=mock_finding,
                working_dir=tmp_path,
                create_branch=False,
                commit=False,
            )

            assert fix == bad_fix
            assert applied is False
            assert "not found" in message.lower()
