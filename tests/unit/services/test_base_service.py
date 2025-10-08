"""Tests for BaseService class."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from patchsmith.models.config import PatchsmithConfig
from patchsmith.services.base_service import BaseService


class TestBaseService:
    """Test BaseService functionality."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> PatchsmithConfig:
        """Create test configuration."""
        return PatchsmithConfig.create_default(project_root=tmp_path)

    def test_init_without_callback(self, config: PatchsmithConfig) -> None:
        """Test initialization without progress callback."""
        service = BaseService(config=config)

        assert service.config == config
        assert service.progress_callback is None
        assert service.service_name == "BaseService"

    def test_init_with_callback(self, config: PatchsmithConfig) -> None:
        """Test initialization with progress callback."""
        callback = MagicMock()
        service = BaseService(config=config, progress_callback=callback)

        assert service.config == config
        assert service.progress_callback == callback
        assert service.service_name == "BaseService"

    def test_emit_progress_without_callback(self, config: PatchsmithConfig) -> None:
        """Test emitting progress without callback (should not error)."""
        service = BaseService(config=config)

        # Should not raise
        service._emit_progress("test_event", detail="test")

    def test_emit_progress_with_callback(self, config: PatchsmithConfig) -> None:
        """Test emitting progress with callback."""
        callback = MagicMock()
        service = BaseService(config=config, progress_callback=callback)

        service._emit_progress("test_event", detail="test", count=42)

        callback.assert_called_once_with(
            "test_event",
            {
                "service": "BaseService",
                "detail": "test",
                "count": 42,
            },
        )

    def test_emit_progress_callback_error_handled(self, config: PatchsmithConfig) -> None:
        """Test that callback errors don't break the service."""
        callback = MagicMock(side_effect=Exception("Callback error"))
        service = BaseService(config=config, progress_callback=callback)

        # Should not raise - errors are caught and logged
        service._emit_progress("test_event")

        callback.assert_called_once()

    def test_subclass_service_name(self, config: PatchsmithConfig) -> None:
        """Test that subclasses have correct service name."""

        class MyCustomService(BaseService):
            pass

        service = MyCustomService(config=config)

        assert service.service_name == "MyCustomService"
