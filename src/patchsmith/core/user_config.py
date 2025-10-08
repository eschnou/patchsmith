"""User-level configuration management (~/.patchsmith/config.yaml)."""

import os
import stat
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

from patchsmith.utils.logging import get_logger

logger = get_logger()


class UserConfig(BaseModel):
    """User-level Patchsmith configuration.

    Stored in ~/.patchsmith/config.yaml for user convenience.
    """

    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude AI",
    )

    # Optional: Default settings for all projects
    default_model: Optional[str] = Field(
        default=None,
        description="Default LLM model to use",
    )
    default_temperature: Optional[float] = Field(
        default=None,
        description="Default LLM temperature",
    )
    default_min_severity: Optional[str] = Field(
        default=None,
        description="Default minimum severity for findings",
    )


def get_user_config_path() -> Path:
    """Get the path to the user-level config file.

    Returns:
        Path to ~/.patchsmith/config.yaml
    """
    return Path.home() / ".patchsmith" / "config.yaml"


def load_user_config() -> Optional[UserConfig]:
    """Load user-level configuration if it exists.

    Returns:
        UserConfig instance if file exists, None otherwise
    """
    config_path = get_user_config_path()

    if not config_path.exists():
        logger.debug("user_config_not_found", path=str(config_path))
        return None

    # Check file permissions for security
    _check_config_permissions(config_path)

    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        config = UserConfig(**data)
        logger.info("user_config_loaded", path=str(config_path))
        return config

    except Exception as e:
        logger.warning(
            "user_config_load_failed",
            path=str(config_path),
            error=str(e),
        )
        return None


def save_user_config(config: UserConfig) -> None:
    """Save user-level configuration.

    Args:
        config: UserConfig instance to save

    Raises:
        IOError: If save fails
    """
    config_path = get_user_config_path()
    config_dir = config_path.parent

    # Create directory if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)

    # Convert to dict and filter out None values
    data = config.model_dump(exclude_none=True)

    # Write config file
    try:
        with open(config_path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

        # Set secure permissions (600 - owner read/write only)
        os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)

        logger.info("user_config_saved", path=str(config_path))

    except Exception as e:
        logger.error("user_config_save_failed", path=str(config_path), error=str(e))
        raise IOError(f"Failed to save user config: {e}") from e


def _check_config_permissions(config_path: Path) -> None:
    """Check that config file has secure permissions.

    Warns if permissions are too open (readable by group/others).

    Args:
        config_path: Path to config file
    """
    try:
        file_stat = config_path.stat()
        mode = file_stat.st_mode

        # Check if file is readable by group or others
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            logger.warning(
                "user_config_insecure_permissions",
                path=str(config_path),
                message="Config file has overly permissive permissions. "
                f"Run: chmod 600 {config_path}",
            )
    except Exception as e:
        logger.debug("permission_check_failed", error=str(e))


def get_api_key() -> Optional[str]:
    """Get Anthropic API key from configuration hierarchy.

    Priority order (highest to lowest):
    1. ANTHROPIC_API_KEY environment variable
    2. User-level config (~/.patchsmith/config.yaml)
    3. None (not found)

    Returns:
        API key if found, None otherwise
    """
    # Priority 1: Environment variable
    if api_key := os.getenv("ANTHROPIC_API_KEY"):
        logger.debug("api_key_source", source="environment_variable")
        return api_key

    # Priority 2: User-level config
    if user_config := load_user_config():
        if user_config.anthropic_api_key:
            logger.debug("api_key_source", source="user_config")
            return user_config.anthropic_api_key

    # Not found
    logger.debug("api_key_not_found")
    return None


def ensure_api_key() -> str:
    """Ensure API key is available, or raise error with helpful message.

    Returns:
        API key string

    Raises:
        RuntimeError: If API key is not found
    """
    api_key = get_api_key()

    if not api_key:
        config_path = get_user_config_path()
        raise RuntimeError(
            "Anthropic API key not found.\n\n"
            "Please set it using one of these methods:\n\n"
            "1. Environment variable:\n"
            "   export ANTHROPIC_API_KEY='your-api-key-here'\n\n"
            f"2. User config file ({config_path}):\n"
            "   Run: patchsmith init --save-api-key\n\n"
            "Get your API key from: https://console.anthropic.com/"
        )

    return api_key
