"""Configuration hierarchy and loading with environment variable support."""

import os
from pathlib import Path
from typing import Optional

from patchsmith.core.user_config import get_api_key
from patchsmith.models.config import PatchsmithConfig


class ConfigError(Exception):
    """Configuration loading or validation error."""

    pass


def load_config(
    config_path: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> PatchsmithConfig:
    """
    Load configuration with hierarchy: CLI args > env vars > user config > file > defaults.

    Priority order (highest to lowest):
    1. Explicitly provided config_path parameter
    2. Environment variables (PATCHSMITH_*, ANTHROPIC_API_KEY)
    3. User-level config (~/.patchsmith/config.yaml)
    4. .patchsmith/config.json in current or project directory
    5. Error if not found

    Args:
        config_path: Optional explicit path to config file
        project_root: Optional project root directory

    Returns:
        Loaded PatchsmithConfig instance

    Raises:
        ConfigError: If configuration cannot be loaded or is invalid
    """
    # Ensure API key is available from env var or user config
    _ensure_api_key_available()

    # Determine config file path
    if config_path is None:
        config_path = _find_config_file(project_root)

    if config_path is None or not config_path.exists():
        raise ConfigError(
            "Configuration file not found. Run 'patchsmith init' first to initialize the project."
        )

    # Load from file
    try:
        config = PatchsmithConfig.load(config_path)
    except Exception as e:
        raise ConfigError(f"Failed to load configuration from {config_path}: {e}") from e

    # Apply environment variable overrides
    config = _apply_env_overrides(config)

    return config


def _find_config_file(project_root: Optional[Path] = None) -> Optional[Path]:
    """
    Find the configuration file by searching upwards from current directory.

    Args:
        project_root: Optional starting point, defaults to current directory

    Returns:
        Path to config file if found, None otherwise
    """
    if project_root is None:
        project_root = Path.cwd()

    # Check current directory first
    config_path = project_root / ".patchsmith" / "config.json"
    if config_path.exists():
        return config_path

    # Search upwards (max 5 levels)
    current = project_root.resolve()
    for _ in range(5):
        config_path = current / ".patchsmith" / "config.json"
        if config_path.exists():
            return config_path

        # Stop at filesystem root
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def _apply_env_overrides(config: PatchsmithConfig) -> PatchsmithConfig:
    """
    Apply environment variable overrides to configuration.

    Environment variables supported:
    - PATCHSMITH_MODEL: Override LLM model
    - PATCHSMITH_TEMPERATURE: Override LLM temperature
    - PATCHSMITH_MAX_TOKENS: Override LLM max tokens
    - PATCHSMITH_TIMEOUT: Override LLM timeout
    - PATCHSMITH_MIN_SEVERITY: Override minimum severity
    - PATCHSMITH_FILTER_FALSE_POSITIVES: Override false positive filtering (true/false)

    Args:
        config: Base configuration to override

    Returns:
        Configuration with environment variable overrides applied
    """
    # LLM configuration overrides
    if model := os.getenv("PATCHSMITH_MODEL"):
        config.llm.model = model

    if temperature := os.getenv("PATCHSMITH_TEMPERATURE"):
        try:
            config.llm.temperature = float(temperature)
        except ValueError:
            pass  # Ignore invalid values

    if max_tokens := os.getenv("PATCHSMITH_MAX_TOKENS"):
        try:
            config.llm.max_tokens = int(max_tokens)
        except ValueError:
            pass

    if timeout := os.getenv("PATCHSMITH_TIMEOUT"):
        try:
            config.llm.timeout = int(timeout)
        except ValueError:
            pass

    # Analysis configuration overrides
    if min_severity := os.getenv("PATCHSMITH_MIN_SEVERITY"):
        config.analysis.min_severity = min_severity.lower()

    if filter_fp := os.getenv("PATCHSMITH_FILTER_FALSE_POSITIVES"):
        if filter_fp.lower() in ("true", "1", "yes"):
            config.analysis.filter_false_positives = True
        elif filter_fp.lower() in ("false", "0", "no"):
            config.analysis.filter_false_positives = False

    # Git configuration overrides
    if remote := os.getenv("PATCHSMITH_GIT_REMOTE"):
        config.git.remote = remote

    if base_branch := os.getenv("PATCHSMITH_GIT_BASE_BRANCH"):
        config.git.base_branch = base_branch

    return config


def validate_config(config: PatchsmithConfig) -> list[str]:
    """
    Validate configuration and return list of issues.

    Args:
        config: Configuration to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    issues = []

    # Validate project root exists
    if not config.project.root.exists():
        issues.append(f"Project root does not exist: {config.project.root}")

    # Validate languages are supported
    supported_languages = [
        "python",
        "javascript",
        "typescript",
        "java",
        "go",
        "cpp",
        "csharp",
        "ruby",
    ]
    for lang in config.project.languages:
        if lang.lower() not in supported_languages:
            issues.append(
                f"Unsupported language: {lang}. Supported: {', '.join(supported_languages)}"
            )

    # Note: We don't validate CodeQL database path exists since it will be created during init

    return issues


def _ensure_api_key_available() -> None:
    """
    Ensure Anthropic API key is available from env var or user config.

    If API key is found in user config but not in environment, sets it in the environment
    so that the Claude SDK can use it.

    Raises:
        ConfigError: If API key is not found anywhere
    """
    # Check if already set in environment
    if os.getenv("ANTHROPIC_API_KEY"):
        return

    # Try to load from user config
    api_key = get_api_key()

    if api_key:
        # Set in environment for Claude SDK to use
        os.environ["ANTHROPIC_API_KEY"] = api_key
        return

    # Not found anywhere - raise error with helpful message
    from patchsmith.core.user_config import get_user_config_path

    config_path = get_user_config_path()
    raise ConfigError(
        "Anthropic API key not found.\n\n"
        "Please set it using one of these methods:\n\n"
        "1. Environment variable:\n"
        "   export ANTHROPIC_API_KEY='your-api-key-here'\n\n"
        f"2. User config file ({config_path}):\n"
        "   anthropic_api_key: 'your-api-key-here'\n\n"
        "   Or run: patchsmith init --save-api-key\n\n"
        "Get your API key from: https://console.anthropic.com/"
    )


def ensure_initialized(project_root: Optional[Path] = None) -> None:
    """
    Ensure project is initialized with Patchsmith.

    Args:
        project_root: Optional project root, defaults to current directory

    Raises:
        ConfigError: If project is not initialized
    """
    if project_root is None:
        project_root = Path.cwd()

    config_path = _find_config_file(project_root)
    if config_path is None:
        raise ConfigError(
            "Project is not initialized. Run 'patchsmith init' first.\n"
            f"Searched in: {project_root} and parent directories."
        )
