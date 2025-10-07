# Patchsmith - Technical Design Document

## 1. Overview

This document outlines the technical architecture, design decisions, and implementation strategy for Patchsmith - a Python-based security analysis tool that integrates CodeQL, Git, and Claude AI to automate security vulnerability detection and remediation.

**Key Architectural Principle**: Patchsmith is designed with a **layered architecture** that separates the service layer (business logic) from the presentation layer (CLI). This enables future extension to a SaaS model with HTTP API endpoints while reusing all core functionality.

### 1.1 Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│            Presentation Layer (Future)                   │
│  ┌──────────────────┐  ┌──────────────────────────┐    │
│  │   HTTP API       │  │   Web Dashboard          │    │
│  │  (FastAPI/Flask) │  │   (React/Vue)            │    │
│  └──────────────────┘  └──────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│            Presentation Layer (v1.0)                     │
│  ┌──────────────────────────────────────────────────┐  │
│  │              CLI (Click)                          │  │
│  │  Commands: init, analyze, fix, report             │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│              Service Layer (Core)                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Services: ProjectService, AnalysisService,       │  │
│  │           QueryService, FixService, ReportService │  │
│  │                                                    │  │
│  │  - Business logic                                 │  │
│  │  - Workflow orchestration                         │  │
│  │  - No CLI/HTTP dependencies                       │  │
│  │  - Fully testable in isolation                    │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│            Integration Layer                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ CodeQL   │  │ Claude   │  │   Git    │             │
│  │ Adapter  │  │ Agents   │  │ Adapter  │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│            Infrastructure Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  Config  │  │  Logging │  │   I/O    │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
```

**Benefits of This Architecture**:
- CLI commands are thin wrappers around service methods
- Services can be called from CLI, HTTP API, or background jobs
- Easy to add new interfaces (GraphQL, gRPC, webhooks)
- Services are independently testable without CLI/HTTP concerns
- Clear separation of concerns

---

## 2. Technology Stack

### 2.1 Core Technologies

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Language** | Python 3.9+ | Rich ecosystem for CLI tools, excellent subprocess management, native async support |
| **CLI Framework** | Click 8.x | Industry standard, excellent argument parsing, composable commands, built-in help generation |
| **LLM Integration** | Anthropic Python SDK + Claude Code Agent SDK | Official SDK with streaming support, agent framework for complex workflows |
| **CodeQL Integration** | Subprocess + CodeQL CLI | Direct CLI invocation for maximum control and compatibility |
| **Configuration** | Pydantic + JSON | Type-safe config with validation, human-readable format |
| **Output/Display** | Rich | Beautiful terminal output, progress bars, syntax highlighting, tables |
| **Logging** | structlog | Structured logging with context, JSON output for debugging |
| **Async Runtime** | asyncio | Native Python async for concurrent LLM calls and CodeQL operations |
| **Testing** | pytest + pytest-asyncio | Comprehensive testing with async support |
| **Packaging** | Poetry | Modern dependency management, easy distribution |
| **Future: HTTP API** | FastAPI | Async-native, automatic OpenAPI docs, type hints |
| **Future: Background Jobs** | Celery or Dramatiq | Async task queue for long-running operations |
| **Future: Database** | PostgreSQL + SQLAlchemy | For multi-user SaaS: projects, users, analyses |

### 2.2 External Dependencies

- **CodeQL CLI**: Assumed pre-installed, version ≥ 2.12.0
- **Git**: Assumed pre-installed, version ≥ 2.30.0
- **Claude API**: Requires API key in environment (`ANTHROPIC_API_KEY`)

---

## 3. Project Structure (Service Layer Architecture)

```
patchsmith/
├── pyproject.toml              # Poetry config, dependencies
├── README.md
├── documentation/
│   ├── requirements.md
│   ├── product.md
│   └── design.md
├── src/
│   └── patchsmith/
│       ├── __init__.py
│       ├── __main__.py         # Entry point for `python -m patchsmith`
│       │
│       ├── cli/                # ═══ PRESENTATION LAYER (CLI) ═══
│       │   ├── __init__.py
│       │   ├── main.py         # Click command group, main entry
│       │   ├── init.py         # `init` command (thin wrapper)
│       │   ├── analyze.py      # `analyze` command (thin wrapper)
│       │   ├── fix.py          # `fix` command (thin wrapper)
│       │   └── report.py       # `report` command (thin wrapper)
│       │
│       │   # Future: HTTP API presentation layer
│       │   # ├── api/
│       │   # │   ├── __init__.py
│       │   # │   ├── main.py            # FastAPI app
│       │   # │   ├── routes/
│       │   # │   │   ├── projects.py
│       │   # │   │   ├── analyses.py
│       │   # │   │   └── fixes.py
│       │   # │   ├── schemas.py         # Pydantic request/response models
│       │   # │   ├── auth.py            # Authentication/authorization
│       │   # │   └── websockets.py      # Real-time progress updates
│       │
│       ├── services/           # ═══ SERVICE LAYER (Core Business Logic) ═══
│       │   ├── __init__.py
│       │   ├── project_service.py      # Project initialization & detection
│       │   ├── analysis_service.py     # Analysis orchestration
│       │   ├── query_service.py        # Query generation & execution
│       │   ├── fix_service.py          # Fix generation & application
│       │   ├── report_service.py       # Report generation
│       │   └── base_service.py         # Base service with common functionality
│       │
│       ├── core/               # ═══ INFRASTRUCTURE (Config, Orchestration) ═══
│       │   ├── __init__.py
│       │   ├── config.py       # Configuration management (Pydantic models)
│       │   ├── project.py      # Project detection and validation
│       │   ├── orchestrator.py # Workflow orchestration and error handling
│       │   └── events.py       # Event system for progress tracking
│       │
│       ├── adapters/           # ═══ INTEGRATION LAYER (External Systems) ═══
│       │   ├── __init__.py
│       │   ├── codeql/
│       │   │   ├── __init__.py
│       │   │   ├── cli.py          # CodeQL CLI wrapper
│       │   │   ├── database.py     # Database creation and management
│       │   │   ├── query.py        # Query execution and result parsing
│       │   │   └── parsers.py      # SARIF/CSV/JSON result parsing
│       │   ├── claude/
│       │   │   ├── __init__.py
│       │   │   ├── base.py         # Base agent class with retry logic
│       │   │   ├── language_detector.py
│       │   │   ├── query_generator.py
│       │   │   ├── false_positive_filter.py
│       │   │   ├── report_generator.py
│       │   │   └── fix_generator.py
│       │   └── git/
│       │       ├── __init__.py
│       │       ├── repository.py   # Git operations wrapper
│       │       └── pr.py           # Pull request creation
│       │
│       ├── presentation/       # ═══ PRESENTATION UTILITIES ═══
│       │   ├── __init__.py
│       │   ├── console.py      # Rich console output utilities
│       │   ├── progress.py     # Progress tracking and display (CLI)
│       │   └── formatters.py   # Report formatting (MD, JSON, etc.)
│       │
│       ├── models/             # ═══ DOMAIN MODELS ═══
│       │   ├── __init__.py
│       │   ├── config.py       # Pydantic models for configuration
│       │   ├── finding.py      # Vulnerability finding models
│       │   ├── analysis.py     # Analysis result models
│       │   ├── project.py      # Project models
│       │   └── query.py        # Query models
│       │
│       ├── repositories/       # ═══ DATA LAYER (Future: DB access) ═══
│       │   ├── __init__.py
│       │   ├── base.py         # Base repository interface
│       │   ├── file_repository.py      # File-based storage (v1.0)
│       │   # Future SaaS:
│       │   # ├── db_repository.py      # Database storage
│       │   # ├── project_repository.py
│       │   # ├── analysis_repository.py
│       │   # └── user_repository.py
│       │
│       └── utils/              # ═══ UTILITIES ═══
│           ├── __init__.py
│           ├── logging.py      # Structured logging setup
│           ├── filesystem.py   # Safe file operations
│           ├── retry.py        # Retry logic with exponential backoff
│           └── validation.py   # Input validation utilities
│
├── tests/
│   ├── unit/
│   │   ├── services/           # Test services in isolation
│   │   │   ├── test_project_service.py
│   │   │   ├── test_analysis_service.py
│   │   │   └── ...
│   │   ├── adapters/           # Test adapters with mocks
│   │   │   ├── test_codeql_cli.py
│   │   │   └── ...
│   │   └── models/
│   │       └── test_config.py
│   ├── integration/
│   │   ├── test_init_workflow.py
│   │   ├── test_analyze_workflow.py
│   │   └── ...
│   └── fixtures/
│       └── sample_vulnerable_projects/
└── examples/
    ├── vulnerable_python/      # Sample projects for testing
    └── vulnerable_javascript/
```

### 3.1 Key Architectural Decisions

**Service Layer Principles**:
- **No presentation dependencies**: Services don't import from `cli/` or `presentation/`
- **Progress callbacks**: Services accept optional callback functions for progress updates
- **Return domain models**: Services return Pydantic models, not CLI-specific output
- **Dependency injection**: Services receive adapters (CodeQL, Claude, Git) via constructor
- **Stateless where possible**: Services operate on provided data, minimal internal state

---

## 4. Service Layer Design (SaaS-Ready Architecture)

### 4.1 Service Layer Principles

The service layer contains all business logic and is completely independent of presentation (CLI/API). This enables:
- Same code powers CLI and future HTTP API
- Easy unit testing without CLI/HTTP overhead
- Background job processing
- Multi-tenancy for SaaS

### 4.2 Service Architecture Pattern

**Base Service** (`src/patchsmith/services/base_service.py`):

```python
from typing import Optional, Callable, Any
from patchsmith.utils.logging import get_logger
from patchsmith.models.config import PatchsmithConfig

class BaseService:
    """Base class for all services"""

    def __init__(self, config: PatchsmithConfig,
                 progress_callback: Optional[Callable[[str, dict], None]] = None):
        """
        Args:
            config: Project configuration
            progress_callback: Optional callback for progress updates
                              Signature: (event: str, data: dict) -> None
        """
        self.config = config
        self.progress_callback = progress_callback
        self.logger = get_logger().bind(service=self.__class__.__name__)

    def _emit_progress(self, event: str, **data):
        """Emit progress event to callback (if registered)"""
        if self.progress_callback:
            self.progress_callback(event, data)

        # Always log
        self.logger.info(event, **data)
```

### 4.3 Example: ProjectService (Init Command)

**Service Implementation** (`src/patchsmith/services/project_service.py`):

```python
from pathlib import Path
from typing import List, Dict, Any
from patchsmith.services.base_service import BaseService
from patchsmith.adapters.codeql.cli import CodeQLCLI
from patchsmith.adapters.claude.language_detector import LanguageDetectorAgent
from patchsmith.adapters.claude.query_generator import QueryGeneratorAgent
from patchsmith.models.project import ProjectInfo, LanguageDetection
from patchsmith.models.config import PatchsmithConfig
from patchsmith.core.project import ProjectDetector

class ProjectService(BaseService):
    """Service for project initialization and detection"""

    def __init__(self, config: PatchsmithConfig,
                 codeql_cli: CodeQLCLI,
                 language_detector: LanguageDetectorAgent,
                 query_generator: QueryGeneratorAgent,
                 progress_callback=None):
        super().__init__(config, progress_callback)
        self.codeql = codeql_cli
        self.language_detector = language_detector
        self.query_generator = query_generator

    async def initialize_project(self,
                                 project_root: Path,
                                 languages: Optional[List[str]] = None) -> ProjectInfo:
        """
        Initialize a project for security analysis.

        Args:
            project_root: Path to project root
            languages: Optional list of languages to override detection

        Returns:
            ProjectInfo with initialization results

        Raises:
            ProjectServiceError: If initialization fails
        """
        self._emit_progress("project_init_started", root=str(project_root))

        # Step 1: Detect project structure
        self._emit_progress("detecting_project", root=str(project_root))
        detector = ProjectDetector(project_root)
        project_info = detector.detect()

        # Step 2: Detect or validate languages
        if languages:
            detected_languages = self._validate_languages(languages)
        else:
            self._emit_progress("detecting_languages")
            detected_languages = await self._detect_languages(project_root)

        project_info.languages = detected_languages

        # Step 3: Create CodeQL databases
        self._emit_progress("creating_databases",
                           languages=[lang.name for lang in detected_languages])

        for lang in detected_languages:
            await self._create_database(project_root, lang)

        # Step 4: Generate custom queries
        self._emit_progress("generating_queries")
        queries = await self._generate_custom_queries(project_info)
        project_info.custom_queries = queries

        self._emit_progress("project_init_completed", project=project_info.name)

        return project_info

    async def _detect_languages(self, project_root: Path) -> List[LanguageDetection]:
        """Detect languages using LLM"""
        # Get file tree and samples
        file_tree = self._get_file_tree(project_root)
        samples = self._get_file_samples(project_root)

        # Use LLM to detect
        result = await self.language_detector.detect_languages(file_tree, samples)

        return [
            LanguageDetection(
                name=lang['name'],
                confidence=lang['confidence'],
                evidence=lang['evidence']
            )
            for lang in result['languages']
        ]

    async def _create_database(self, project_root: Path,
                              language: LanguageDetection) -> None:
        """Create CodeQL database for a language"""
        db_path = Path(".patchsmith/db") / language.name

        self._emit_progress("creating_database",
                           language=language.name,
                           confidence=language.confidence)

        try:
            self.codeql.create_database(
                source_root=project_root,
                db_path=db_path,
                language=language.name
            )
            self._emit_progress("database_created", language=language.name)
        except Exception as e:
            self._emit_progress("database_creation_failed",
                               language=language.name,
                               error=str(e))
            raise

    # ... additional methods ...
```

### 4.4 CLI Integration (Thin Wrapper)

**CLI Command** (`src/patchsmith/cli/init.py`):

```python
import asyncio
import click
from pathlib import Path
from rich.progress import Progress, SpinnerColumn, TextColumn
from patchsmith.presentation.console import console
from patchsmith.services.project_service import ProjectService
from patchsmith.adapters.codeql.cli import CodeQLCLI
from patchsmith.adapters.claude.language_detector import LanguageDetectorAgent
from patchsmith.adapters.claude.query_generator import QueryGeneratorAgent
from patchsmith.repositories.file_repository import FileRepository
from patchsmith.models.config import PatchsmithConfig

@click.command()
@click.option('--languages', help='Comma-separated list of languages')
@click.pass_context
def init(ctx, languages):
    """Initialize Patchsmith for the current project"""
    asyncio.run(run_init(languages))

async def run_init(languages: Optional[str]):
    """Execute init workflow using service layer"""

    # Setup progress display (CLI-specific)
    progress_display = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    )

    current_task = None

    def progress_callback(event: str, data: dict):
        """Handle progress events from service"""
        nonlocal current_task

        # Map service events to CLI display
        event_messages = {
            "project_init_started": "Initializing project...",
            "detecting_languages": "Analyzing codebase to detect languages...",
            "creating_databases": f"Creating CodeQL databases for {len(data.get('languages', []))} languages...",
            "creating_database": f"Creating {data['language']} database...",
            "generating_queries": "Generating custom security queries...",
            "project_init_completed": "✓ Initialization complete!"
        }

        message = event_messages.get(event, event)

        if current_task:
            progress_display.update(current_task, description=message)
        else:
            current_task = progress_display.add_task(message)

    # Instantiate service with dependencies (Dependency Injection)
    codeql_cli = CodeQLCLI()
    language_detector = LanguageDetectorAgent()
    query_generator = QueryGeneratorAgent()
    repository = FileRepository()

    # Create temporary config for initialization
    temp_config = PatchsmithConfig.create_default(Path.cwd())

    service = ProjectService(
        config=temp_config,
        codeql_cli=codeql_cli,
        language_detector=language_detector,
        query_generator=query_generator,
        progress_callback=progress_callback
    )

    # Execute service method
    with progress_display:
        try:
            lang_list = languages.split(',') if languages else None
            project_info = await service.initialize_project(
                project_root=Path.cwd(),
                languages=lang_list
            )

            # Save configuration
            config = project_info.to_config()
            repository.save_config(config)

            # Display success (CLI-specific formatting)
            console.print("\n[green]✓[/green] Project initialized successfully!")
            console.print(f"  Languages: {', '.join([l.name for l in project_info.languages])}")
            console.print(f"  Custom queries: {len(project_info.custom_queries)}")

        except Exception as e:
            console.print(f"\n[red]✗[/red] Initialization failed: {e}")
            raise click.Abort()
```

### 4.5 Future: HTTP API Integration (Same Service)

**API Endpoint** (`src/patchsmith/api/routes/projects.py` - Future):

```python
from fastapi import APIRouter, BackgroundTasks, WebSocket
from patchsmith.services.project_service import ProjectService
from patchsmith.api.schemas import InitProjectRequest, InitProjectResponse
from patchsmith.api.auth import get_current_user

router = APIRouter()

@router.post("/projects/init")
async def init_project(
    request: InitProjectRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Initialize a project via HTTP API"""

    # Same service, different presentation layer!
    service = ProjectService(
        config=await load_config(current_user.id, request.project_id),
        codeql_cli=CodeQLCLI(),
        language_detector=LanguageDetectorAgent(),
        query_generator=QueryGeneratorAgent(),
        progress_callback=None  # Will use WebSocket for progress
    )

    # Run in background
    background_tasks.add_task(
        service.initialize_project,
        project_root=request.project_root,
        languages=request.languages
    )

    return InitProjectResponse(
        status="initiated",
        project_id=request.project_id,
        message="Initialization started"
    )

@router.websocket("/projects/{project_id}/init/progress")
async def init_project_progress(websocket: WebSocket, project_id: str):
    """Real-time progress updates via WebSocket"""
    await websocket.accept()

    def progress_callback(event: str, data: dict):
        # Send progress to WebSocket client
        asyncio.create_task(
            websocket.send_json({"event": event, "data": data})
        )

    # Execute with WebSocket progress updates
    service = ProjectService(
        config=await load_config_by_project(project_id),
        codeql_cli=CodeQLCLI(),
        language_detector=LanguageDetectorAgent(),
        query_generator=QueryGeneratorAgent(),
        progress_callback=progress_callback
    )

    await service.initialize_project(...)
```

### 4.6 Repository Pattern (Data Layer)

**File-based Repository** (`src/patchsmith/repositories/file_repository.py`):

```python
from pathlib import Path
from patchsmith.models.config import PatchsmithConfig
from patchsmith.models.analysis import AnalysisResult

class FileRepository:
    """File-based storage for v1.0 (local CLI)"""

    def __init__(self, base_path: Path = Path(".patchsmith")):
        self.base_path = base_path

    def save_config(self, config: PatchsmithConfig):
        """Save configuration to JSON file"""
        config_path = self.base_path / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config.save(config_path)

    def load_config(self) -> PatchsmithConfig:
        """Load configuration from JSON file"""
        config_path = self.base_path / "config.json"
        return PatchsmithConfig.load(config_path)

    def save_analysis(self, analysis: AnalysisResult):
        """Save analysis results"""
        # Implementation...
        pass
```

**Future: Database Repository** (`src/patchsmith/repositories/db_repository.py` - Future):

```python
from sqlalchemy.orm import Session
from patchsmith.models.config import PatchsmithConfig

class DatabaseRepository:
    """Database storage for SaaS (multi-user)"""

    def __init__(self, db_session: Session):
        self.db = db_session

    def save_config(self, user_id: str, project_id: str,
                   config: PatchsmithConfig):
        """Save configuration to database"""
        # Store in PostgreSQL with user/project association
        pass

    def load_config(self, user_id: str, project_id: str) -> PatchsmithConfig:
        """Load configuration from database"""
        pass
```

### 4.7 Dependency Injection

**Service Factory** (`src/patchsmith/services/factory.py`):

```python
from patchsmith.services.project_service import ProjectService
from patchsmith.services.analysis_service import AnalysisService
from patchsmith.adapters.codeql.cli import CodeQLCLI
from patchsmith.adapters.claude import *
from patchsmith.repositories.file_repository import FileRepository

class ServiceFactory:
    """Factory for creating services with proper dependencies"""

    def __init__(self, repository: FileRepository):
        self.repository = repository
        self.codeql_cli = CodeQLCLI()

    def create_project_service(self, config, progress_callback=None):
        return ProjectService(
            config=config,
            codeql_cli=self.codeql_cli,
            language_detector=LanguageDetectorAgent(),
            query_generator=QueryGeneratorAgent(),
            progress_callback=progress_callback
        )

    def create_analysis_service(self, config, progress_callback=None):
        return AnalysisService(
            config=config,
            codeql_cli=self.codeql_cli,
            false_positive_filter=FalsePositiveFilterAgent(),
            report_generator=ReportGeneratorAgent(),
            progress_callback=progress_callback
        )
```

### 4.8 Benefits for SaaS Migration

| Aspect | v1.0 (CLI) | Future (SaaS) |
|--------|------------|---------------|
| **Storage** | FileRepository (JSON files) | DatabaseRepository (PostgreSQL) |
| **Progress** | Rich console callbacks | WebSocket callbacks |
| **Auth** | None (local user) | JWT/OAuth in API layer |
| **Multi-user** | N/A | User/project association in DB |
| **Background Jobs** | Async in CLI process | Celery/Dramatiq workers |
| **Service Layer** | **Same code** | **Same code** |

**Key Insight**: By keeping services independent of presentation, the core logic needs **zero changes** when adding the HTTP API.

---

## 5. Command Line Interface Design

### 4.1 CLI Framework: Click

**Why Click?**
- Declarative command definition with decorators
- Automatic help generation
- Type validation and conversion
- Composable command groups
- Context management for shared state
- Excellent documentation

**Example Structure**:

```python
# src/patchsmith/cli/main.py
import click
from patchsmith.output.console import console
from patchsmith.utils.logging import setup_logging

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--no-color', is_flag=True, help='Disable colored output')
@click.pass_context
def cli(ctx, verbose, no_color):
    """Patchsmith - AI-powered security vulnerability detection and fixing"""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    setup_logging(verbose=verbose)
    if no_color:
        console.no_color = True

@cli.command()
@click.option('--languages', help='Comma-separated list of languages')
@click.option('--query-templates', type=click.Path(exists=True))
@click.pass_context
def init(ctx, languages, query_templates):
    """Initialize Patchsmith for the current project"""
    from patchsmith.cli.init import run_init
    run_init(languages=languages, query_templates=query_templates,
             verbose=ctx.obj['verbose'])

# Similar for analyze, fix, report...
```

### 4.2 Argument Parsing Strategy

**Global Options** (available to all commands):
- `--verbose/-v`: Enable debug logging
- `--no-color`: Disable colored output
- `--config <path>`: Use alternative config file
- `--help`: Show help message

**Command-Specific Options**:
- Type validation via Click (paths, choices, integers)
- Required vs optional arguments
- Mutually exclusive options via Click groups
- Environment variable support (e.g., `PATCHSMITH_API_KEY`)

**Configuration Hierarchy** (highest to lowest priority):
1. Command-line arguments
2. Environment variables
3. Configuration file (`.patchsmith/config.json`)
4. Defaults

---

## 5. User Output and Logging

### 5.1 Display Framework: Rich

**Why Rich?**
- Beautiful terminal output with minimal effort
- Progress bars, spinners, tables
- Syntax highlighting for code snippets
- Markdown rendering
- Live updates
- Tree views for file structures

**Usage Patterns**:

```python
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown

console = Console()

# Progress tracking
with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    console=console
) as progress:
    task = progress.add_task("Creating CodeQL database...", total=None)
    # ... do work ...
    progress.update(task, completed=True)

# Tables for results
table = Table(title="Vulnerabilities Found")
table.add_column("ID", style="cyan")
table.add_column("Severity", style="red")
table.add_column("File", style="green")
# ... add rows ...
console.print(table)

# Code syntax highlighting
code = Syntax(code_snippet, "python", theme="monokai", line_numbers=True)
console.print(code)

# Markdown reports
md = Markdown(report_content)
console.print(md)
```

### 5.2 Logging Strategy: structlog

**Why structlog?**
- Structured logging (JSON format)
- Context binding (attach request IDs, command names)
- Performance (lazy evaluation)
- Easy filtering and searching
- Integration with external log aggregators

**Logging Levels**:
- `DEBUG`: Detailed diagnostic info (enabled with `--verbose`)
- `INFO`: General informational messages (default)
- `WARNING`: Recoverable errors, important notices
- `ERROR`: Errors that prevent operation
- `CRITICAL`: System-level failures

**Log Destinations**:
- **Console** (stderr): Human-readable format with colors
- **File** (`.patchsmith/audit.log`): Structured JSON for debugging
- **Optional**: External services (future: Sentry, DataDog)

**Example**:

```python
import structlog

logger = structlog.get_logger()

# Bind context
logger = logger.bind(command="init", project="/path/to/project")

logger.info("starting_language_detection", files_scanned=1250)
logger.warning("codeql_database_partial", language="go", reason="compilation_errors")
logger.error("llm_api_failure", status_code=429, retry_in=30)
```

**Log File Format** (`.patchsmith/audit.log`):
```json
{"event": "starting_language_detection", "level": "info", "timestamp": "2025-10-07T10:30:00Z", "command": "init", "files_scanned": 1250}
{"event": "codeql_database_partial", "level": "warning", "timestamp": "2025-10-07T10:31:15Z", "language": "go", "reason": "compilation_errors"}
```

---

## 6. CodeQL Integration

### 6.1 Integration Approach: Direct CLI Invocation

**Decision: Use subprocess to call CodeQL CLI directly (NOT MCP)**

**Rationale**:
- **Control**: Full control over database creation, query execution, output formats
- **Compatibility**: Works with any CodeQL version, no dependency on MCP server availability
- **Simplicity**: Direct mapping of CodeQL commands to Python functions
- **Offline Support**: Works without network access after database creation
- **Error Handling**: Full access to stdout/stderr/exit codes for detailed error reporting

**Trade-offs**:
- More verbose than MCP integration
- Need to parse CodeQL output formats manually
- No automatic caching (we implement our own)

### 6.2 CodeQL CLI Wrapper Design

**Module**: `src/patchsmith/codeql/cli.py`

```python
import subprocess
import json
from pathlib import Path
from typing import Optional, List, Dict
from patchsmith.utils.logging import get_logger

logger = get_logger()

class CodeQLCLI:
    """Wrapper around CodeQL CLI"""

    def __init__(self, codeql_path: str = "codeql"):
        self.codeql_path = codeql_path
        self._verify_installation()

    def _verify_installation(self):
        """Verify CodeQL is installed and get version"""
        result = self._run(["version", "--format=json"])
        version_info = json.loads(result.stdout)
        logger.info("codeql_detected", version=version_info.get("version"))

    def _run(self, args: List[str], cwd: Optional[Path] = None,
             timeout: int = 3600) -> subprocess.CompletedProcess:
        """Execute CodeQL command with error handling"""
        cmd = [self.codeql_path] + args
        logger.debug("codeql_command", cmd=" ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )
            return result
        except subprocess.CalledProcessError as e:
            logger.error("codeql_error",
                        cmd=" ".join(cmd),
                        returncode=e.returncode,
                        stderr=e.stderr)
            raise CodeQLError(f"CodeQL command failed: {e.stderr}") from e
        except subprocess.TimeoutExpired:
            logger.error("codeql_timeout", cmd=" ".join(cmd), timeout=timeout)
            raise CodeQLError(f"CodeQL command timed out after {timeout}s")

    def create_database(self, source_root: Path, db_path: Path,
                       language: str, threads: int = 0) -> None:
        """Create CodeQL database for a language"""
        args = [
            "database", "create",
            str(db_path),
            f"--language={language}",
            f"--source-root={source_root}",
        ]
        if threads > 0:
            args.append(f"--threads={threads}")

        logger.info("creating_codeql_database", language=language, path=str(db_path))
        self._run(args, timeout=1800)  # 30 min timeout

    def run_queries(self, db_path: Path, query_path: Path,
                   output_format: str = "sarif-latest") -> Path:
        """Execute queries against database"""
        output_path = db_path.parent / f"results.{output_format}"

        args = [
            "database", "analyze",
            str(db_path),
            str(query_path),
            f"--format={output_format}",
            f"--output={output_path}",
            "--rerun"
        ]

        logger.info("running_codeql_queries",
                   database=str(db_path),
                   queries=str(query_path))
        self._run(args, timeout=3600)  # 60 min timeout

        return output_path

class CodeQLError(Exception):
    """CodeQL operation failed"""
    pass
```

### 6.3 CodeQL Operations

**Key Operations**:
1. **Database Creation**: `codeql database create`
2. **Query Execution**: `codeql database analyze`
3. **Result Export**: SARIF format (structured, machine-readable)
4. **Query Validation**: `codeql query compile` (for custom queries)

**Output Format**: SARIF (Static Analysis Results Interchange Format)
- Industry standard JSON format
- Contains: rules, results, locations, code flows, fixes
- Parseable with standard libraries

---

## 7. Claude AI Integration

### 7.1 Integration Approach: Anthropic Python SDK + Agent Pattern

**Components**:
1. **Anthropic Python SDK**: Direct API access for streaming, message handling
2. **Agent Pattern**: Structured workflows with retry logic, context management
3. **Prompt Engineering**: Carefully crafted system prompts for each task

### 7.2 Agent Architecture

**Base Agent** (`src/patchsmith/agents/base.py`):

```python
import anthropic
from typing import Optional, Dict, Any
from patchsmith.utils.retry import retry_with_backoff
from patchsmith.utils.logging import get_logger

logger = get_logger()

class BaseAgent:
    """Base class for all Claude-powered agents"""

    def __init__(self,
                 model: str = "claude-sonnet-4-5-20251022",
                 temperature: float = 0.2,
                 max_tokens: int = 4000):
        self.client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    async def _call_claude(self,
                          system: str,
                          user_message: str,
                          streaming: bool = False) -> str:
        """Make API call with retry logic"""

        logger.debug("claude_api_call",
                    model=self.model,
                    system_prompt_length=len(system),
                    user_message_length=len(user_message))

        try:
            if streaming:
                return await self._call_streaming(system, user_message)
            else:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=system,
                    messages=[{"role": "user", "content": user_message}]
                )

                response = message.content[0].text
                logger.info("claude_api_success",
                           input_tokens=message.usage.input_tokens,
                           output_tokens=message.usage.output_tokens)

                return response

        except anthropic.RateLimitError as e:
            logger.warning("claude_rate_limit", retry_after=e.retry_after)
            raise  # Will be retried by decorator
        except anthropic.APIError as e:
            logger.error("claude_api_error", error=str(e))
            raise

    async def _call_streaming(self, system: str, user_message: str) -> str:
        """Streaming API call with progress updates"""
        from patchsmith.output.console import console

        full_response = []

        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": user_message}]
        ) as stream:
            for text in stream.text_stream:
                full_response.append(text)
                console.print(text, end="")

        return "".join(full_response)
```

### 7.3 Specialized Agents

**Language Detection Agent** (`agents/language_detector.py`):
```python
class LanguageDetectorAgent(BaseAgent):
    """Detect programming languages in a project"""

    SYSTEM_PROMPT = """You are an expert at analyzing codebases and identifying programming languages.

    Given a file tree and sample file contents, identify:
    1. Primary programming languages (with confidence scores)
    2. Build systems and frameworks
    3. Recommended CodeQL analysis languages

    Return JSON only."""

    async def detect_languages(self, file_tree: str,
                              sample_files: Dict[str, str]) -> Dict[str, Any]:
        user_message = f"""File tree:
{file_tree}

Sample files:
{json.dumps(sample_files, indent=2)}

Identify languages and return JSON with this schema:
{{
  "languages": [
    {{"name": "python", "confidence": 0.95, "evidence": ["*.py files", "requirements.txt"]}},
    ...
  ],
  "frameworks": ["django", "react"],
  "codeql_languages": ["python", "javascript"]
}}"""

        response = await self._call_claude(self.SYSTEM_PROMPT, user_message)
        return json.loads(response)
```

**Similar patterns for**:
- `QueryGeneratorAgent`: Generate custom CodeQL queries
- `FalsePositiveFilterAgent`: Analyze findings for false positives
- `ReportGeneratorAgent`: Create human-readable reports
- `FixGeneratorAgent`: Generate code fixes

### 7.4 Token Management

**Strategy**:
- Monitor token usage per agent call
- Implement context window management (truncate large files)
- Use extended thinking for complex analysis tasks
- Batch similar operations to reduce API calls

**Example**:
```python
def truncate_code_context(code: str, max_lines: int = 100) -> str:
    """Keep relevant context within token limits"""
    lines = code.split('\n')
    if len(lines) <= max_lines:
        return code

    # Keep lines around the vulnerability (intelligent truncation)
    # ... implementation ...
```

---

## 8. Orchestration Layer

### 8.1 Need for Orchestration

**Challenges**:
- Multiple async operations (LLM calls, CodeQL runs)
- Complex error handling (retry logic, partial failures)
- State management across workflow steps
- Progress tracking for long-running operations
- Rollback on failure

### 8.2 Orchestrator Design

**Module**: `src/patchsmith/core/orchestrator.py`

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable, Any
import asyncio

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class WorkflowStep:
    name: str
    description: str
    function: Callable
    status: StepStatus = StepStatus.PENDING
    error: Optional[Exception] = None
    result: Any = None
    required: bool = True  # If False, failure doesn't stop workflow

class WorkflowOrchestrator:
    """Orchestrate multi-step workflows with error handling"""

    def __init__(self, name: str):
        self.name = name
        self.steps: List[WorkflowStep] = []
        self.logger = get_logger().bind(workflow=name)

    def add_step(self, name: str, description: str,
                 function: Callable, required: bool = True):
        """Add a step to the workflow"""
        step = WorkflowStep(name, description, function, required=required)
        self.steps.append(step)
        return step

    async def execute(self, show_progress: bool = True) -> Dict[str, Any]:
        """Execute workflow with progress tracking"""
        from patchsmith.output.progress import WorkflowProgress

        results = {}

        with WorkflowProgress(self.steps) as progress:
            for step in self.steps:
                if step.status == StepStatus.SKIPPED:
                    continue

                progress.update_step(step.name, StepStatus.RUNNING)
                self.logger.info("step_starting", step=step.name)

                try:
                    # Execute step (async or sync)
                    if asyncio.iscoroutinefunction(step.function):
                        step.result = await step.function()
                    else:
                        step.result = step.function()

                    step.status = StepStatus.COMPLETED
                    results[step.name] = step.result
                    progress.update_step(step.name, StepStatus.COMPLETED)
                    self.logger.info("step_completed", step=step.name)

                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.error = e
                    progress.update_step(step.name, StepStatus.FAILED, str(e))
                    self.logger.error("step_failed", step=step.name, error=str(e))

                    if step.required:
                        # Required step failed, abort workflow
                        self._mark_remaining_skipped(step)
                        raise WorkflowError(f"Required step '{step.name}' failed: {e}") from e
                    else:
                        # Optional step failed, continue
                        self.logger.warning("optional_step_failed_continuing", step=step.name)

        return results

    def _mark_remaining_skipped(self, failed_step: WorkflowStep):
        """Mark all steps after failed step as skipped"""
        skip = False
        for step in self.steps:
            if skip:
                step.status = StepStatus.SKIPPED
            if step == failed_step:
                skip = True

class WorkflowError(Exception):
    """Workflow execution failed"""
    pass
```

### 8.3 Example: Init Command Workflow

```python
# In cli/init.py
async def run_init(languages: Optional[str], query_templates: Optional[str], verbose: bool):
    """Execute init command workflow"""

    orchestrator = WorkflowOrchestrator("init")

    # Step 1: Detect project
    orchestrator.add_step(
        "detect_project",
        "Detecting project root and validating Git repository",
        lambda: ProjectDetector().detect()
    )

    # Step 2: Detect languages (uses LLM)
    orchestrator.add_step(
        "detect_languages",
        "Analyzing codebase to detect programming languages",
        lambda: detect_languages_step(languages)
    )

    # Step 3: Create CodeQL databases
    orchestrator.add_step(
        "create_databases",
        "Creating CodeQL databases for detected languages",
        lambda: create_codeql_databases_step()
    )

    # Step 4: Generate custom queries (uses LLM)
    orchestrator.add_step(
        "generate_queries",
        "Generating custom security queries for your codebase",
        lambda: generate_custom_queries_step()
    )

    # Step 5: Save configuration
    orchestrator.add_step(
        "save_config",
        "Saving configuration to .patchsmith/config.json",
        lambda: save_configuration_step()
    )

    try:
        results = await orchestrator.execute()
        console.print("[green]✓[/green] Initialization complete!")
        return results
    except WorkflowError as e:
        console.print(f"[red]✗[/red] Initialization failed: {e}")
        raise click.Abort()
```

---

## 9. Configuration Management

### 9.1 Configuration Schema (Pydantic)

**Module**: `src/patchsmith/models/config.py`

```python
from pydantic import BaseModel, Field, validator
from pathlib import Path
from typing import List, Optional
from datetime import datetime

class ProjectConfig(BaseModel):
    name: str
    root: Path
    languages: List[str]
    ignore_paths: List[str] = Field(default_factory=lambda: ["tests/", "node_modules/", "vendor/"])

class CodeQLConfig(BaseModel):
    database_path: Path = Field(default=Path(".patchsmith/db"))
    query_paths: List[Path] = Field(default_factory=list)

class AnalysisConfig(BaseModel):
    filter_false_positives: bool = True
    min_severity: str = "low"
    max_results: int = 1000

    @validator('min_severity')
    def validate_severity(cls, v):
        allowed = ['critical', 'high', 'medium', 'low', 'info']
        if v.lower() not in allowed:
            raise ValueError(f"Severity must be one of {allowed}")
        return v.lower()

class LLMConfig(BaseModel):
    model: str = "claude-sonnet-4-5-20251022"
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4000, ge=100, le=8000)

class GitConfig(BaseModel):
    remote: str = "origin"
    base_branch: str = "main"

class PatchsmithConfig(BaseModel):
    version: str = "1.0"
    project: ProjectConfig
    codeql: CodeQLConfig = Field(default_factory=CodeQLConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    git: GitConfig = Field(default_factory=GitConfig)
    initialized_at: datetime
    last_analysis: Optional[datetime] = None

    class Config:
        json_encoders = {
            Path: str,
            datetime: lambda v: v.isoformat()
        }

    def save(self, path: Path):
        """Save configuration to JSON file"""
        with open(path, 'w') as f:
            f.write(self.json(indent=2))

    @classmethod
    def load(cls, path: Path) -> 'PatchsmithConfig':
        """Load configuration from JSON file"""
        with open(path) as f:
            return cls.parse_raw(f.read())
```

### 9.2 Configuration Loading

**Priority order**:
1. CLI arguments (highest)
2. Environment variables (`PATCHSMITH_*`)
3. Config file (`.patchsmith/config.json`)
4. Defaults (lowest)

```python
def load_config() -> PatchsmithConfig:
    """Load configuration with priority hierarchy"""
    config_path = Path(".patchsmith/config.json")

    if not config_path.exists():
        raise ConfigError("Not a Patchsmith project. Run 'patchsmith init' first.")

    config = PatchsmithConfig.load(config_path)

    # Override with environment variables
    if api_key := os.getenv("ANTHROPIC_API_KEY"):
        # Already handled by Anthropic SDK
        pass

    if model := os.getenv("PATCHSMITH_MODEL"):
        config.llm.model = model

    return config
```

---

## 10. Error Handling Strategy

### 10.1 Error Hierarchy

```python
class PatchsmithError(Exception):
    """Base exception for all Patchsmith errors"""
    pass

class ConfigError(PatchsmithError):
    """Configuration related errors"""
    pass

class CodeQLError(PatchsmithError):
    """CodeQL operation errors"""
    pass

class LLMError(PatchsmithError):
    """LLM API errors"""
    pass

class GitError(PatchsmithError):
    """Git operation errors"""
    pass

class WorkflowError(PatchsmithError):
    """Workflow orchestration errors"""
    pass
```

### 10.2 Retry Logic

**Module**: `src/patchsmith/utils/retry.py`

```python
import asyncio
from functools import wraps
from typing import Callable, Type
import random

def retry_with_backoff(max_attempts: int = 3,
                       base_delay: float = 1.0,
                       max_delay: float = 60.0,
                       exponential_base: float = 2.0,
                       jitter: bool = True,
                       retryable_exceptions: tuple = (Exception,)):
    """Retry decorator with exponential backoff"""

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            attempt = 0
            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise

                    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
                    if jitter:
                        delay *= (0.5 + random.random())  # Add jitter

                    logger.warning("retrying_after_error",
                                 function=func.__name__,
                                 attempt=attempt,
                                 max_attempts=max_attempts,
                                 delay=delay,
                                 error=str(e))

                    await asyncio.sleep(delay)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Similar for sync functions
            pass

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator
```

### 10.3 Graceful Degradation

**Strategies**:
- LLM failure during false positive filtering → Use all findings (warn user)
- Custom query generation failure → Use only standard queries (warn user)
- Partial CodeQL database creation → Continue with successful languages
- Git operations failure → Save fixes locally, skip PR creation

---

## 11. Performance Considerations

### 11.1 Async Operations

**Concurrent LLM Calls**:
```python
async def analyze_findings_concurrently(findings: List[Finding]) -> List[AnalyzedFinding]:
    """Analyze multiple findings in parallel"""
    agent = FalsePositiveFilterAgent()

    # Batch into groups to respect rate limits
    batch_size = 5
    results = []

    for i in range(0, len(findings), batch_size):
        batch = findings[i:i+batch_size]
        batch_results = await asyncio.gather(
            *[agent.analyze_finding(f) for f in batch],
            return_exceptions=True  # Don't fail entire batch on one error
        )
        results.extend(batch_results)

    return results
```

### 11.2 Caching

**CodeQL Results Caching**:
- Cache SARIF results with hash of query files
- Invalidate on query changes or code changes
- Store in `.patchsmith/cache/`

**LLM Response Caching**:
- Cache language detection per file tree hash
- Cache false positive analysis per finding hash
- Use `pickle` or `joblib` for persistence

### 11.3 Progress Feedback

**Long-Running Operations**:
- CodeQL database creation: Show spinner with language
- Query execution: Show progress bar if possible
- LLM calls: Show "Analyzing..." with streaming output
- Batch operations: Show "X/Y completed"

---

## 12. Testing Strategy

### 12.1 Unit Tests

**Mocking Strategy**:
```python
# tests/unit/test_codeql_wrapper.py
from unittest.mock import Mock, patch
import pytest

@patch('subprocess.run')
def test_create_database_success(mock_run):
    mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

    cli = CodeQLCLI()
    cli.create_database(Path("/src"), Path("/db"), "python")

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "database" in args
    assert "create" in args
    assert "--language=python" in args
```

### 12.2 Integration Tests

**Fixture Projects**:
```python
# tests/fixtures/vulnerable_python/app.py
# Intentionally vulnerable code for testing

def login(username, password):
    # SQL Injection vulnerability
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return db.execute(query)
```

**Test Full Workflow**:
```python
@pytest.mark.integration
async def test_full_init_workflow(tmp_path):
    # Set up fixture project
    shutil.copytree("tests/fixtures/vulnerable_python", tmp_path / "project")
    os.chdir(tmp_path / "project")

    # Run init
    result = await run_init(languages="python", query_templates=None, verbose=True)

    # Verify outputs
    assert (tmp_path / "project" / ".patchsmith" / "config.json").exists()
    assert (tmp_path / "project" / ".patchsmith" / "db" / "python").exists()

    # Verify config
    config = PatchsmithConfig.load(tmp_path / "project" / ".patchsmith" / "config.json")
    assert "python" in config.project.languages
```

### 12.3 Mock LLM Responses

```python
@pytest.fixture
def mock_claude_response():
    with patch('anthropic.Anthropic') as mock:
        mock.return_value.messages.create.return_value = Mock(
            content=[Mock(text='{"languages": ["python"], "confidence": 0.95}')],
            usage=Mock(input_tokens=100, output_tokens=50)
        )
        yield mock
```

---

## 13. Packaging and Distribution

### 13.1 Poetry Configuration

**pyproject.toml**:
```toml
[tool.poetry]
name = "patchsmith"
version = "0.1.0"
description = "AI-powered security vulnerability detection and fixing"
authors = ["Your Name <you@example.com>"]
readme = "README.md"
homepage = "https://github.com/yourusername/patchsmith"
repository = "https://github.com/yourusername/patchsmith"
keywords = ["security", "codeql", "ai", "vulnerabilities"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Topic :: Security",
    "License :: OSI Approved :: MIT License",
]

[tool.poetry.dependencies]
python = "^3.9"
click = "^8.1.0"
anthropic = "^0.39.0"
rich = "^13.0.0"
structlog = "^24.0.0"
pydantic = "^2.0.0"
aiofiles = "^24.0.0"

[tool.poetry.dev-dependencies]
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
pytest-cov = "^4.1.0"
black = "^24.0.0"
mypy = "^1.8.0"
ruff = "^0.1.0"

[tool.poetry.scripts]
patchsmith = "patchsmith.cli.main:cli"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

### 13.2 Installation

```bash
# From PyPI (future)
pip install patchsmith

# From source
git clone https://github.com/yourusername/patchsmith
cd patchsmith
poetry install
poetry run patchsmith --help
```

---

## 14. Additional Architectural Considerations

### 14.1 Extensibility

**Plugin System** (future):
- Custom agents (user-defined LLM workflows)
- Custom output formatters (PDF, HTML reports)
- Custom CodeQL query templates
- Integration hooks (Slack notifications, JIRA tickets)

**Configuration**:
```json
{
  "plugins": [
    {
      "name": "slack-notifier",
      "enabled": true,
      "config": {"webhook_url": "..."}
    }
  ]
}
```

### 14.2 Security Considerations

**Sensitive Data Handling**:
- Never log API keys
- Redact sensitive code in LLM prompts (ask user first)
- Validate file paths to prevent directory traversal
- Secure temporary file handling

**Code Execution Safety**:
- Never execute generated fixes automatically
- Always create backups before modifications
- Validate syntax before committing
- Sandbox CodeQL queries (use CodeQL's built-in safety)

### 14.3 Cross-Platform Support

**Platform-Specific Handling**:
- Use `pathlib` for all path operations
- Handle Windows path separators
- Use `shutil` for file operations (cross-platform)
- Test on macOS, Linux, Windows

### 14.4 Dependency Management

**External Dependencies**:
- Check CodeQL version on startup
- Check Git version and configuration
- Validate Python version (>=3.9)
- Provide helpful error messages for missing deps

### 14.5 Documentation Generation

**Inline Documentation**:
- Docstrings for all public APIs (Google style)
- Type hints everywhere
- Examples in docstrings

**Auto-Generated Docs**:
- Sphinx for API documentation
- Click auto-generates CLI help
- Markdown for user guides

---

## 15. Development Workflow

### 15.1 Setup

```bash
# Clone and setup
git clone <repo>
cd patchsmith
poetry install

# Run tests
poetry run pytest

# Type checking
poetry run mypy src/

# Linting
poetry run ruff check src/

# Format
poetry run black src/
```

### 15.2 CI/CD

**GitHub Actions**:
- Run tests on PR
- Type checking and linting
- Test on multiple Python versions (3.9, 3.10, 3.11, 3.12)
- Test on multiple platforms (Ubuntu, macOS, Windows)
- Build and publish to PyPI on release

---

## 16. Migration Path

**From Design to Implementation**:

1. **Phase 1: Foundation** (Week 1)
   - Project structure setup
   - Poetry configuration
   - Basic CLI with Click
   - Configuration management (Pydantic models)
   - Logging setup (structlog)

2. **Phase 2: Core Integrations** (Week 2)
   - CodeQL CLI wrapper
   - Git operations wrapper
   - Claude API integration (base agent)
   - Orchestrator framework

3. **Phase 3: Command Implementation** (Week 3-4)
   - `init` command with language detection
   - `analyze` command with basic reporting
   - Basic output with Rich

4. **Phase 4: Intelligence** (Week 5-6)
   - Custom query generation agent
   - False positive filtering agent
   - Fix generation agent
   - `fix` command implementation

5. **Phase 5: Polish** (Week 7-8)
   - `report` command with formatting
   - Error handling improvements
   - Performance optimization
   - Testing and documentation

---

## 17. SaaS Architecture (Future Evolution)

### 17.1 Multi-Tenant SaaS Components

When extending to SaaS, the following components are added **without changing the service layer**:

**Database Schema**:
```sql
-- Users and authentication
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Organizations (for team plans)
CREATE TABLE organizations (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    plan VARCHAR(50) DEFAULT 'free',  -- free, pro, enterprise
    created_at TIMESTAMP DEFAULT NOW()
);

-- Projects (multi-tenant)
CREATE TABLE projects (
    id UUID PRIMARY KEY,
    organization_id UUID REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    repository_url VARCHAR(500),
    config JSONB,  -- PatchsmithConfig as JSON
    created_at TIMESTAMP DEFAULT NOW()
);

-- Analysis runs (audit trail)
CREATE TABLE analysis_runs (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(50),  -- running, completed, failed
    findings_count INTEGER,
    results JSONB  -- AnalysisResult as JSON
);

-- Findings (for querying and filtering)
CREATE TABLE findings (
    id UUID PRIMARY KEY,
    analysis_run_id UUID REFERENCES analysis_runs(id),
    project_id UUID REFERENCES projects(id),
    severity VARCHAR(20),
    cwe VARCHAR(20),
    file_path TEXT,
    line_number INTEGER,
    status VARCHAR(50) DEFAULT 'open',  -- open, fixed, false_positive, wont_fix
    raw_data JSONB
);
```

**FastAPI Application** (`src/patchsmith/api/main.py`):
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from patchsmith.api.routes import projects, analyses, fixes, auth
from patchsmith.api.database import init_db

app = FastAPI(title="Patchsmith API", version="1.0.0")

# CORS for web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.patchsmith.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
@app.on_event("startup")
async def startup():
    await init_db()

# Register routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(analyses.router, prefix="/api/v1/analyses", tags=["analyses"])
app.include_router(fixes.router, prefix="/api/v1/fixes", tags=["fixes"])

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

**Background Worker (Celery)** (`src/patchsmith/workers/tasks.py`):
```python
from celery import Celery
from patchsmith.services.analysis_service import AnalysisService
from patchsmith.repositories.db_repository import DatabaseRepository

celery_app = Celery('patchsmith', broker='redis://localhost:6379/0')

@celery_app.task
async def run_analysis(project_id: str, user_id: str):
    """Background task for running analysis"""

    # Load from database
    repo = DatabaseRepository()
    config = repo.load_config(user_id, project_id)

    # Create service (same service layer!)
    service = AnalysisService(
        config=config,
        codeql_cli=CodeQLCLI(),
        false_positive_filter=FalsePositiveFilterAgent(),
        report_generator=ReportGeneratorAgent(),
        progress_callback=lambda e, d: emit_websocket_event(project_id, e, d)
    )

    # Execute analysis
    result = await service.run_analysis()

    # Save to database
    repo.save_analysis_result(user_id, project_id, result)

    return {"status": "completed", "findings": len(result.findings)}
```

### 17.2 SaaS-Specific Features

**Authentication & Authorization**:
- JWT tokens for API authentication
- OAuth integration (GitHub, GitLab)
- Role-based access control (RBAC)
- Organization-level permissions

**Webhooks** (for CI/CD integration):
```python
# GitHub webhook handler
@app.post("/webhooks/github")
async def github_webhook(payload: GitHubWebhookPayload,
                        background_tasks: BackgroundTasks):
    """Trigger analysis on push/PR"""
    if payload.event == "push":
        background_tasks.add_task(
            run_analysis,
            project_id=payload.repository.id,
            user_id=payload.repository.owner.id
        )
    return {"status": "accepted"}
```

**Real-Time Dashboard** (WebSocket):
- Live progress updates during analysis
- Real-time finding notifications
- Multi-user collaboration

**API-First Features**:
- RESTful API for all operations
- GraphQL endpoint (optional)
- Pagination, filtering, sorting
- Rate limiting per organization
- API key management

### 17.3 Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Load Balancer (Nginx)                 │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
┌───────▼────────┐                 ┌────────▼───────┐
│  API Server 1  │                 │  API Server 2  │
│   (FastAPI)    │                 │   (FastAPI)    │
└───────┬────────┘                 └────────┬───────┘
        │                                   │
        └─────────────────┬─────────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
┌───────▼────────┐                 ┌────────▼───────┐
│  Celery Worker │                 │ Celery Worker  │
│   (Analysis)   │                 │    (Fixes)     │
└───────┬────────┘                 └────────┬───────┘
        │                                   │
        └─────────────────┬─────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│                    Message Broker                        │
│                    (Redis/RabbitMQ)                      │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│                     PostgreSQL                           │
│               (Users, Projects, Findings)                │
└─────────────────────────────────────────────────────────┘
```

**Scaling Considerations**:
- Horizontal scaling of API servers (stateless)
- Separate worker pools for analysis vs fixes
- Database read replicas for reports
- Object storage (S3) for CodeQL databases and results
- CDN for web dashboard static assets

### 17.4 Migration Path: CLI → SaaS

**Phase 1: CLI Only (v1.0)**
- File-based storage (`.patchsmith/` directory)
- Local execution
- Single-user

**Phase 2: Hybrid (v1.5)**
- CLI can optionally sync to cloud
- `patchsmith login` command for cloud sync
- Web dashboard shows results from CLI runs
- Database stores metadata, files stay local

**Phase 3: Full SaaS (v2.0)**
- Web-based project management
- API for programmatic access
- Background workers for analysis
- Team collaboration features
- Enterprise SSO

**Key Principle**: Service layer code remains **unchanged** across all phases.

---

## 18. Key Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Architecture** | Layered (Service Layer) | Enables CLI and SaaS from same codebase |
| **CLI Framework** | Click | Industry standard, excellent docs, composable |
| **Display** | Rich | Beautiful output with minimal code |
| **Logging** | structlog | Structured, performant, searchable |
| **CodeQL Integration** | Direct CLI | Maximum control, no dependencies |
| **LLM Integration** | Anthropic SDK | Official, well-maintained, streaming support |
| **Config Format** | JSON + Pydantic | Human-readable, type-safe, validatable |
| **Data Layer** | Repository Pattern | Easy swap: Files → Database |
| **Progress Updates** | Callback Pattern | Same service, different UI (CLI/WebSocket) |
| **Dependency Injection** | Constructor Injection | Testable, flexible, explicit |
| **Async** | asyncio (native) | No additional dependencies, Python standard |
| **Packaging** | Poetry | Modern, excellent dependency management |
| **Testing** | pytest | De facto standard, great plugins |
| **Future: API** | FastAPI | Async-native, automatic docs, type safety |
| **Future: Jobs** | Celery | Proven, scalable, Redis/RabbitMQ support |
| **Future: DB** | PostgreSQL | JSONB for flexibility, proven at scale |

---

## 19. Open Questions / Future Discussions

1. **Rate Limiting**: How to handle Claude API rate limits gracefully?
2. **Offline Mode**: Can we cache LLM responses for offline analysis?
3. **Multi-Repo**: Support for analyzing multiple repositories in one run?
4. **CI/CD Integration**: GitHub Action vs. generic Docker container?
5. **Custom Models**: Support for local LLMs (Ollama, LM Studio)?
6. **Query Sharing**: Community query repository?
7. **Telemetry**: Anonymous usage stats for improvement?
8. **Licensing**: MIT, Apache 2.0, or GPL?
9. **SaaS Pricing**: Usage-based (per analysis) vs. seat-based (per user)?
10. **Data Residency**: How to handle customer data in different regions?
11. **Enterprise Features**: On-premise deployment vs. cloud-only?
12. **CodeQL Database Storage**: Local vs. cloud object storage for SaaS?

---

## 20. Summary

This design document outlines a **layered architecture** for Patchsmith that:

1. **Separates concerns cleanly**: Presentation (CLI/API) → Services (business logic) → Adapters (integrations) → Infrastructure
2. **Enables SaaS evolution**: Same service layer powers both CLI and future HTTP API
3. **Maintains testability**: Each layer can be tested independently
4. **Provides flexibility**: Easy to swap implementations (file storage → database, console → WebSocket)
5. **Scales gracefully**: From single-user CLI to multi-tenant SaaS

**The key insight**: By designing the service layer to be **presentation-agnostic**, we can build v1.0 as a CLI tool and later add a SaaS offering with **minimal changes to core business logic**. Progress callbacks and dependency injection are the architectural patterns that make this possible.

This design provides a solid foundation for building Patchsmith with clear architectural decisions, extensibility in mind, and a practical path from CLI to SaaS.
