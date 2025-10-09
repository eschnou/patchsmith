# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Patchsmith** is an AI-powered CLI tool that automates security vulnerability detection and fixing using CodeQL for analysis and Claude for intelligent processing. The project is designed with a layered architecture to support future SaaS evolution.

**Current Status**: Phase 1 (Foundation) complete - 69 tests passing, 62% coverage, all domain models implemented.

## Development Workflow

### Spec-Driven Development

Patchsmith uses **spec-driven development** for major release iterations. This ensures thorough planning, clear requirements, and systematic implementation.

**Specification Structure:**

Each major version has a dedicated specification folder in `specs/` with incremental versioning:

```
specs/
├── 1_initial_version/     # v0.1.0 specs
│   ├── requirements.md    # Full requirements specification
│   ├── design.md          # Technical design and architecture
│   └── tasks.md           # Implementation tasks and checklist
├── 2_next_version/        # v0.2.0 specs (future)
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
└── 3_future_version/      # v0.3.0 specs (future)
    └── ...
```

**Development Process:**

1. **Planning Phase** - Create spec folder for next version:
   - `requirements.md` - Define features, user stories, acceptance criteria
   - `design.md` - Design architecture, data models, API contracts
   - `tasks.md` - Break down into actionable tasks with checkboxes

2. **Implementation Phase** - Work through tasks systematically:
   - Check off tasks as completed in `tasks.md`
   - Update specs if requirements change during implementation
   - Keep specs accurate as living documentation

3. **Release** - Version is complete when all tasks checked off

**Spec File Purposes:**

- **requirements.md** - What we're building and why (product requirements)
- **design.md** - How we're building it (technical architecture, patterns, decisions)
- **tasks.md** - Detailed implementation checklist (broken down by component/phase)

**Important:** For large features or architectural changes, always consult the relevant spec files in `specs/` before making changes. These documents contain the authoritative design decisions and requirements.

## Development Commands

### Setup
```bash
poetry install                    # Install all dependencies
```

### Testing
```bash
poetry run pytest                                    # Run all tests
poetry run pytest tests/unit/models/                # Run specific test directory
poetry run pytest tests/unit/models/test_finding.py # Run single test file
poetry run pytest -v                                # Verbose output
poetry run pytest -k "test_name"                    # Run tests matching name
poetry run pytest --cov-report=html                 # Generate HTML coverage report
```

### Code Quality
```bash
poetry run mypy src/patchsmith    # Type checking (must pass)
poetry run ruff check src/        # Linting
poetry run ruff check --fix src/  # Auto-fix linting issues
poetry run black src/ tests/      # Format code
```

### Running the CLI
```bash
poetry run patchsmith --help      # Show CLI help
poetry run patchsmith --version   # Show version
```

## Architecture

Patchsmith uses a **layered architecture** designed to be presentation-agnostic:

```
Presentation Layer (CLI)
    ↓
Service Layer (Business Logic) ← Core of the application
    ↓
Adapter Layer (External Integrations: CodeQL, Claude, Git)
    ↓
Infrastructure Layer (Config, Logging, I/O)
```

### Key Architectural Principles

1. **Service Layer Independence**: The service layer (`src/patchsmith/services/`) contains all business logic and MUST NOT depend on the presentation layer (`cli/` or `presentation/`). Services accept progress callbacks and return domain models.

2. **Progress Callbacks**: Services emit progress events via callbacks rather than directly outputting to console. This allows the same service to work with CLI progress bars, WebSocket updates, or API responses.

3. **Dependency Injection**: Services receive their dependencies (adapters) through constructor injection, making them testable in isolation.

4. **Repository Pattern**: Data access is abstracted through repositories (`src/patchsmith/repositories/`). Currently file-based, designed to swap to database for SaaS.

5. **Domain Models First**: All data structures are Pydantic models (`src/patchsmith/models/`) with validation and serialization built-in.

## Project Structure

```
src/patchsmith/
├── cli/              # CLI commands (thin wrappers around services)
├── services/         # Business logic layer (presentation-agnostic)
├── adapters/         # External integrations (CodeQL, Claude, Git)
│   ├── codeql/      # CodeQL CLI wrapper
│   ├── claude/      # Claude AI agents
│   └── git/         # Git operations
├── core/            # Config management, orchestration
├── models/          # Pydantic domain models
│   ├── config.py    # Configuration models
│   ├── finding.py   # Security finding models (Severity, CWE, Finding)
│   ├── analysis.py  # Analysis result models
│   ├── project.py   # Project info models
│   └── query.py     # CodeQL query models
├── repositories/    # Data access layer (file-based → future: database)
├── presentation/    # CLI output utilities (Rich-based)
└── utils/           # Logging, retry logic, validation
```

## Important Implementation Details

### Configuration Hierarchy
Configuration is loaded with the following priority (highest to lowest):
1. CLI arguments
2. Environment variables (`PATCHSMITH_*`, `ANTHROPIC_API_KEY`)
3. Config file (`.patchsmith/config.json`)
4. Defaults

### Testing Strategy
- **Unit tests**: Mock all external dependencies (subprocess, API calls)
- **Integration tests**: Use fixture projects with known vulnerabilities
- **All services must be testable without CLI or external systems**
- Target: >85% coverage overall, >90% for services

### Model Validation
- All Pydantic models use Pydantic v2 syntax
- Field validators use `@field_validator` decorator
- Complex validators need `Any` type hint and `hasattr(info, "data")` checks
- All models should have comprehensive unit tests

### Code Quality Requirements
- **Type hints**: Required on all function signatures
- **Docstrings**: Google-style docstrings on all public APIs
- **Line length**: 100 characters (enforced by black)
- **Imports**: Automatically sorted by ruff (use `ruff check --fix`)
- **Mypy**: Must pass in strict mode with no errors

## Domain Model Overview

### Finding Models (`models/finding.py`)
- `Severity`: Enum (CRITICAL, HIGH, MEDIUM, LOW, INFO)
- `CWE`: Common Weakness Enumeration with ID validation
- `FalsePositiveScore`: AI-assessed false positive likelihood
- `Finding`: Complete vulnerability finding with location, severity, CWE

### Analysis Models (`models/analysis.py`)
- `AnalysisStatistics`: Aggregated stats (counts by severity, CWE, language)
- `AnalysisResult`: Complete analysis with findings, statistics, timestamp
  - Methods: `filter_by_severity()`, `sort_by_severity()`, `compute_statistics()`

### Project Models (`models/project.py`)
- `LanguageDetection`: Detected language with confidence score
- `ProjectInfo`: Project metadata with detected languages

### Query Models (`models/query.py`)
- `Query`: CodeQL query definition with metadata
- `QuerySuite`: Collection of queries with filtering methods

### Configuration Models (`models/config.py`)
- `PatchsmithConfig`: Root config with nested configs for project, CodeQL, analysis, LLM, Git
- Methods: `save()`, `load()`, `create_default()`

## Common Patterns

### Creating a New Service
```python
from patchsmith.services.base_service import BaseService
from patchsmith.models.config import PatchsmithConfig
from typing import Optional, Callable

class MyService(BaseService):
    def __init__(
        self,
        config: PatchsmithConfig,
        some_adapter: SomeAdapter,
        progress_callback: Optional[Callable[[str, dict], None]] = None
    ):
        super().__init__(config, progress_callback)
        self.adapter = some_adapter

    async def do_something(self) -> ResultModel:
        self._emit_progress("step_started", detail="info")
        # ... business logic ...
        self._emit_progress("step_completed")
        return result
```

### Creating a New Model
```python
from pydantic import BaseModel, Field, field_validator
from typing import Any

class MyModel(BaseModel):
    field: str = Field(..., description="Field description")

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        # validation logic
        return v
```

### Writing Tests
```python
import pytest
from pathlib import Path

class TestMyModel:
    def test_create_model(self) -> None:
        """Test creating a basic model."""
        model = MyModel(field="value")
        assert model.field == "value"
```

## External Dependencies

- **CodeQL CLI**: Must be installed and in PATH (not part of Python dependencies)
- **Git**: Required for project operations
- **Claude API**: Requires `ANTHROPIC_API_KEY` environment variable
- All Python dependencies managed via Poetry

## Phase 1 Completion Checklist

Phase 1 (Foundation) is complete with:
- ✅ Project structure and Poetry setup
- ✅ Git repository initialized
- ✅ Code quality tools configured (black, mypy, ruff)
- ✅ Structured logging with structlog
- ✅ Audit logging with rotation
- ✅ Configuration management with Pydantic
- ✅ Configuration hierarchy (CLI > env > file > defaults)
- ✅ All domain models (project, finding, analysis, query)
- ✅ 69 unit tests passing (62% coverage)
- ✅ Type checking clean (mypy)
- ✅ Linting clean (ruff)

## Next Phase: Phase 2 - Core Integrations (Adapters)

The next phase involves implementing:
1. CodeQL CLI wrapper (`adapters/codeql/`)
2. Claude AI agents (`adapters/claude/`)
3. Git operations wrapper (`adapters/git/`)

See `specs/1_initial_version/tasks.md` for detailed task breakdown.

## Design Documents

### Current Version (v0.1.0)

- `specs/1_initial_version/requirements.md` - Full requirements specification
- `specs/1_initial_version/design.md` - Complete technical design (2000+ lines)
- `specs/1_initial_version/tasks.md` - All 124 implementation tasks across 11 phases

### General Documentation

- `documentation/product.md` - Product pitch and business case (if exists)

**Note:** Always refer to `specs/<version>/` for version-specific requirements and design decisions.

## Important Notes

- **Never bypass the service layer**: CLI commands should be thin wrappers
- **Always emit progress**: Services should call `_emit_progress()` at key steps
- **Test in isolation**: Mock external dependencies, test service logic independently
- **Pydantic v2**: Use v2 syntax (`@field_validator`, not `@validator`)
- **Type safety**: Mypy must pass - no `type: ignore` unless absolutely necessary
- **SaaS-ready**: Keep services presentation-agnostic for future HTTP API
