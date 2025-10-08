# Patchsmith - Implementation Tasks

This document contains an exhaustive list of all implementation tasks for building Patchsmith v1.0 (CLI). Tasks are organized by phase and include acceptance criteria.

---

## Phase 1: Foundation & Project Setup ✅ **COMPLETED**

### 1.1 Project Structure & Configuration

- [x] **TASK-001: Initialize Poetry project** ✅
  - Create `pyproject.toml` with project metadata
  - Add core dependencies: click, rich, structlog, pydantic, anthropic, aiofiles
  - Add dev dependencies: pytest, pytest-asyncio, pytest-cov, black, mypy, ruff
  - Configure Poetry scripts for CLI entry point
  - Test: `poetry install` succeeds, `poetry run patchsmith --version` works

- [x] **TASK-002: Create project directory structure** ✅
  - Create all directories per design.md structure:
    - `src/patchsmith/` with subdirs: cli, services, adapters, core, models, repositories, presentation, utils
    - `tests/` with subdirs: unit, integration, fixtures
    - `documentation/`, `examples/`
  - Add `__init__.py` files to all Python packages
  - Test: Import structure works without errors

- [x] **TASK-003: Setup Git repository** ✅
  - Initialize git repository
  - Create `.gitignore` (Python, IDE, OS files, `.patchsmith/` directories)
  - Create initial README.md with project description
  - Test: Git is initialized, .gitignore works

- [x] **TASK-004: Configure code quality tools** ✅
  - Create `pyproject.toml` sections for black, mypy, ruff
  - Configure black: line length 100, target py39
  - Configure mypy: strict mode, ignore missing imports for external libs
  - Configure ruff: select rules, ignore specific patterns
  - Test: `black .`, `mypy src/`, `ruff check src/` all run successfully

### 1.2 Logging Infrastructure

- [x] **TASK-005: Implement structured logging setup** ✅
  - Create `src/patchsmith/utils/logging.py`
  - Implement `setup_logging(verbose: bool)` function
  - Configure structlog with processors: timestamp, log level, JSON formatting
  - Setup dual output: console (human-readable) + file (JSON)
  - Implement `get_logger()` helper function
  - Test: Logging to console and file works, JSON format is valid

- [x] **TASK-006: Create audit log system** ✅
  - Implement audit log writer that creates `.patchsmith/audit.log`
  - Add context binding for command name, timestamps
  - Create log rotation (max size 10MB, keep 5 files)
  - Test: Audit logs are created, rotation works

### 1.3 Configuration Management

- [x] **TASK-007: Create Pydantic configuration models** ✅
  - Create `src/patchsmith/models/config.py`
  - Implement `ProjectConfig`, `CodeQLConfig`, `AnalysisConfig`, `LLMConfig`, `GitConfig` models
  - Implement root `PatchsmithConfig` model with validators
  - Add `save()` and `load()` methods with JSON serialization
  - Add `create_default()` class method
  - Test: Config can be created, validated, saved, and loaded (18 tests passing)

- [x] **TASK-008: Implement configuration hierarchy** ✅
  - Create `src/patchsmith/core/config.py`
  - Implement config loading with priority: CLI args > env vars > file > defaults
  - Add environment variable parsing (`PATCHSMITH_*`)
  - Add config validation and error reporting
  - Test: Config hierarchy works correctly, env vars override file (15 tests passing)

### 1.4 Domain Models

- [x] **TASK-009: Create project models** ✅
  - Create `src/patchsmith/models/project.py`
  - Implement `ProjectInfo`, `LanguageDetection` models
  - Add validation for language names, confidence scores
  - Test: Models can be created and validated (8 tests passing)

- [x] **TASK-010: Create finding models** ✅
  - Create `src/patchsmith/models/finding.py`
  - Implement `Finding`, `Severity`, `CWE` models
  - Add `FalsePositiveScore` model with reasoning
  - Test: Findings can be created with all fields (12 tests passing)

- [x] **TASK-011: Create analysis models** ✅
  - Create `src/patchsmith/models/analysis.py`
  - Implement `AnalysisResult`, `AnalysisStatistics` models
  - Add methods for filtering, sorting, grouping findings
  - Test: Analysis results can aggregate findings correctly (16 tests passing)

- [x] **TASK-012: Create query models** ✅
  - Create `src/patchsmith/models/query.py`
  - Implement `Query`, `QuerySuite` models
  - Add validation for CodeQL query syntax (basic)
  - Test: Query models can be created (15 tests passing)

**Phase 1 Summary:**
- ✅ All 12 tasks completed
- ✅ 69 unit tests passing
- ✅ 62% code coverage
- ✅ Type checking clean (mypy)
- ✅ Linting clean (ruff)
- ✅ Complete domain model layer ready

---

## Phase 2: Core Integrations (Adapters) ✅ **COMPLETED**

### 2.1 CodeQL Adapter

- [x] **TASK-013: Implement CodeQL CLI wrapper** ✅
  - Create `src/patchsmith/adapters/codeql/cli.py`
  - Implement `CodeQLCLI` class with `_run()` method
  - Add `_verify_installation()` to check CodeQL version
  - Implement proper error handling and timeout management
  - Test: CodeQL CLI can be detected and version retrieved

- [x] **TASK-014: Implement database creation** ✅
  - Add `create_database()` method to CodeQLCLI
  - Support multiple languages (python, javascript, go, java, etc.)
  - Add progress tracking via logging
  - Handle compilation errors gracefully
  - Test: Database creation works for sample projects

- [x] **TASK-015: Implement query execution** ✅
  - Add `run_queries()` method to CodeQLCLI
  - Support SARIF output format
  - Handle query compilation errors
  - Add timeout handling for long-running queries
  - Test: Queries execute and return SARIF results

- [x] **TASK-016: Implement SARIF parser** ✅
  - Create `src/patchsmith/adapters/codeql/parsers.py`
  - Implement `SARIFParser` class
  - Parse SARIF to `Finding` models
  - Extract: file paths, line numbers, messages, rule IDs, severity
  - Test: SARIF files can be parsed to Finding objects

- [x] **TASK-017: Implement CSV result parser** ✅
  - Add `CSVParser` class to parsers.py
  - Parse CodeQL CSV output format
  - Convert to `Finding` models
  - Test: CSV results can be parsed

- [x] **TASK-018: Add database management utilities** ✅
  - Create `src/patchsmith/adapters/codeql/database.py`
  - Implement database cleanup, validation
  - Add methods to check database status
  - Test: Database utilities work correctly

### 2.2 Claude AI Adapter

- [x] **TASK-019: Implement base agent class** ✅
  - Create `src/patchsmith/adapters/claude/agent.py`
  - Implement `BaseAgent` with `query_claude()` method using Claude Code SDK
  - Add proper error handling with AgentError exception
  - Implement support for max_turns and allowed_tools
  - Add working directory context and logging
  - Test: Agent can make API calls with proper error handling

- [x] **TASK-020: Implement language detection agent** ✅
  - Create `src/patchsmith/adapters/claude/language_detection_agent.py`
  - Implement `LanguageDetectionAgent` class
  - Write system prompt for language detection
  - Implement `execute()` method with file tree analysis
  - Parse JSON response to `LanguageDetection` models
  - Test: Agent can detect languages from file tree (17 tests, 92% coverage)

- [x] **TASK-021: Implement query generator agent with validation and retry logic** ✅
  - Create `src/patchsmith/adapters/claude/query_generator_agent.py`
  - Implement `QueryGeneratorAgent` class
  - Write system prompt for CodeQL query generation
  - Implement `execute()` method with code analysis and validation
  - Validate generated queries using CodeQL CLI
  - Add retry logic (up to 3 attempts) for failed validations
  - Test: Agent generates valid CodeQL queries (20 tests, 91% coverage)

- [x] **TASK-022: Implement false positive filter agent** ✅
  - Create `src/patchsmith/adapters/claude/false_positive_filter_agent.py`
  - Implement `FalsePositiveFilterAgent` class
  - Write system prompt for false positive analysis
  - Implement `execute()` method to analyze findings with code context
  - Return FalsePositiveScore with score and reasoning
  - Test: Agent can identify false positives (16 tests, 92% coverage)

- [x] **TASK-023: Implement report generator agent** ✅
  - Create `src/patchsmith/adapters/claude/report_generator_agent.py`
  - Implement `ReportGeneratorAgent` class
  - Write system prompt for report generation
  - Implement `execute()` method supporting markdown, HTML, text formats
  - Generate reports with executive summary, findings, recommendations
  - Smart false positive filtering
  - Test: Agent generates well-formatted reports (11 tests, 100% coverage)

- [x] **TASK-024: Implement fix generator agent** ✅
  - Create `src/patchsmith/adapters/claude/fix_generator_agent.py`
  - Implement `FixGeneratorAgent` class with Fix model
  - Write system prompt for fix generation
  - Implement `execute()` method with full code context via Read tool
  - Return Fix with original_code, fixed_code, explanation, confidence
  - Confidence-based filtering (returns None for confidence < 0.5)
  - Test: Agent generates reasonable fixes (17 tests, 92% coverage)

### 2.3 Git Adapter

- [x] **TASK-025: Implement Git repository wrapper** ✅
  - Create `src/patchsmith/adapters/git/repository.py`
  - Implement `GitRepository` class using subprocess
  - Add methods: `get_current_branch()`, `branch_exists()`, `create_branch()`, `checkout_branch()`
  - Add methods: `has_uncommitted_changes()`, `stage_file()`, `commit()`, `push_branch()`
  - Add methods: `get_diff()`, `get_file_content()`, `get_remote_url()`, `reset_hard()`
  - Add validation for Git installation and repository
  - Test: Git operations work correctly (23 tests, 91% coverage)

- [x] **TASK-026: Implement pull request creation** ✅
  - Create `src/patchsmith/adapters/git/pr.py`
  - Implement `PRCreator` class using GitHub CLI (`gh`)
  - Add `create_pr()` method with title, body, branch, base, draft support
  - Add `is_authenticated()`, `get_pr_url()`, `pr_exists()` helper methods
  - Handle cases where `gh` is not installed
  - Test: PR creation and checks work correctly (16 tests, 100% coverage)

- [x] **TASK-027: Add Git safety checks** ✅
  - Implement `is_clean()` check for dirty working directory
  - Implement `is_protected_branch()` to detect main/master/develop/production
  - Add protected branch validation in `commit()` method
  - Prevent commits to protected branches by default
  - Add `allow_protected` parameter to override safety check
  - Test: Safety checks work correctly (30 total tests, 91% coverage)

**Phase 2 Summary:**
- ✅ All 15 tasks completed (TASK-013 through TASK-027)
- ✅ CodeQL adapter: ~85-90% coverage across all components
- ✅ Claude AI agents: 90-100% coverage with robust error handling
- ✅ Git adapter: 46 tests passing, 91-100% coverage
- ✅ Type checking clean (mypy)
- ✅ Linting clean (ruff)
- ✅ All adapters ready for service layer integration

---

## Phase 3: Service Layer (Business Logic)

### 3.1 Base Service Infrastructure

- [ ] **TASK-028: Implement base service class**
  - Create `src/patchsmith/services/base_service.py`
  - Implement `BaseService` with config and progress callback
  - Add `_emit_progress()` method
  - Add logging setup with service context binding
  - Test: Service can emit progress events and log

- [ ] **TASK-029: Implement service factory**
  - Create `src/patchsmith/services/factory.py`
  - Implement `ServiceFactory` for dependency injection
  - Add methods to create all service types
  - Handle adapter instantiation
  - Test: Factory creates services with proper dependencies

### 3.2 Project Service

- [ ] **TASK-030: Implement project detection**
  - Create `src/patchsmith/core/project.py`
  - Implement `ProjectDetector` class
  - Add methods: detect project root, validate Git repo, scan file tree
  - Extract project name from directory/package files
  - Test: Detector works on sample projects

- [ ] **TASK-031: Implement ProjectService initialization**
  - Create `src/patchsmith/services/project_service.py`
  - Implement `ProjectService` class
  - Implement `initialize_project()` method (main workflow)
  - Add `_detect_languages()` helper using LanguageDetectorAgent
  - Add `_create_database()` helper using CodeQLCLI
  - Test: Service can initialize a project end-to-end

- [ ] **TASK-032: Implement custom query generation**
  - Add `_generate_custom_queries()` to ProjectService
  - Use QueryGeneratorAgent with code samples
  - Save queries to `.patchsmith/queries/`
  - Validate query syntax before saving
  - Test: Custom queries are generated and saved

- [ ] **TASK-033: Add project configuration persistence**
  - Implement config creation from ProjectInfo
  - Save config to `.patchsmith/config.json`
  - Create directory structure (`.patchsmith/db/`, `queries/`, etc.)
  - Test: Configuration is saved correctly

### 3.3 Analysis Service

- [ ] **TASK-034: Implement AnalysisService**
  - Create `src/patchsmith/services/analysis_service.py`
  - Implement `AnalysisService` class
  - Implement `run_analysis()` method (main workflow)
  - Execute standard and custom CodeQL queries
  - Parse SARIF results to Finding objects
  - Test: Service can run analysis and return findings

- [ ] **TASK-035: Implement false positive filtering**
  - Add `_filter_false_positives()` to AnalysisService
  - Use FalsePositiveFilterAgent for each finding
  - Process findings concurrently (batched)
  - Update findings with false positive scores
  - Test: False positives are filtered correctly

- [ ] **TASK-036: Implement analysis result aggregation**
  - Add `_aggregate_results()` to AnalysisService
  - Calculate statistics (counts by severity, language, CWE)
  - Sort and prioritize findings
  - Create AnalysisResult model
  - Test: Results are aggregated correctly

- [ ] **TASK-037: Implement result persistence**
  - Save raw SARIF to `.patchsmith/results/results-<timestamp>.sarif`
  - Save CSV summary to `.patchsmith/results/results-<timestamp>.csv`
  - Create symlink to latest results
  - Test: Results are saved correctly

### 3.4 Query Service

- [ ] **TASK-038: Implement QueryService**
  - Create `src/patchsmith/services/query_service.py`
  - Implement `QueryService` class
  - Add methods: `list_queries()`, `validate_query()`, `compile_query()`
  - Support loading standard and custom queries
  - Test: Service can list and validate queries

- [ ] **TASK-039: Implement query template system**
  - Add query template loading from files
  - Support parameterized queries (substitute values)
  - Add query metadata (name, description, severity)
  - Test: Templates can be loaded and parameterized

### 3.5 Report Service

- [ ] **TASK-040: Implement ReportService**
  - Create `src/patchsmith/services/report_service.py`
  - Implement `ReportService` class
  - Implement `generate_report()` method using ReportGeneratorAgent
  - Add markdown formatting utilities
  - Test: Service generates markdown reports

- [ ] **TASK-041: Implement report templates**
  - Create report sections: executive summary, statistics, findings
  - Add code snippet extraction with context
  - Format findings by severity with proper styling
  - Add prioritized recommendations section
  - Test: Reports are well-formatted and complete

- [ ] **TASK-042: Implement report persistence**
  - Save report to `.patchsmith/reports/report-<timestamp>.md`
  - Create symlink to `latest.md`
  - Add metadata header to reports
  - Test: Reports are saved with correct structure

### 3.6 Fix Service

- [ ] **TASK-043: Implement FixService**
  - Create `src/patchsmith/services/fix_service.py`
  - Implement `FixService` class
  - Implement `fix_issues()` method (main workflow)
  - Load findings by issue IDs
  - Test: Service can load and process fix requests

- [ ] **TASK-044: Implement fix generation**
  - Add `_generate_fix()` using FixGeneratorAgent
  - Extract full code context for each finding
  - Get fix code and explanation from agent
  - Test: Fixes are generated with proper context

- [ ] **TASK-045: Implement fix application**
  - Add `_apply_fix()` to modify source files
  - Create backups in `.patchsmith/backups/`
  - Validate syntax after changes (basic check)
  - Support rollback on errors
  - Test: Fixes are applied correctly and can be rolled back

- [ ] **TASK-046: Implement Git workflow for fixes**
  - Create branch `patchsmith/fix-<issue-ids>`
  - Commit changes with descriptive message
  - Generate PR description
  - Push branch and create PR using GitRepository
  - Test: Git workflow completes successfully

- [ ] **TASK-047: Implement fix documentation**
  - Save fix summary to `.patchsmith/fixes/fix-<timestamp>.md`
  - Document issues addressed, changes made, testing recommendations
  - Test: Fix documentation is created

---

## Phase 4: Orchestration & Error Handling

### 4.1 Workflow Orchestration

- [ ] **TASK-048: Implement workflow orchestrator**
  - Create `src/patchsmith/core/orchestrator.py`
  - Implement `WorkflowOrchestrator` class
  - Add `WorkflowStep` dataclass with status tracking
  - Implement `add_step()` and `execute()` methods
  - Support required vs optional steps
  - Test: Orchestrator can execute multi-step workflows

- [ ] **TASK-049: Implement progress tracking integration**
  - Add progress tracking to orchestrator
  - Emit events for step start/complete/fail
  - Support progress callbacks from services
  - Test: Progress is tracked correctly through workflows

- [ ] **TASK-050: Implement error recovery**
  - Add error handling for partial failures
  - Implement step skipping after required step fails
  - Add rollback support for failed operations
  - Test: Errors are handled gracefully

### 4.2 Event System

- [ ] **TASK-051: Implement event system**
  - Create `src/patchsmith/core/events.py`
  - Implement `EventEmitter` class
  - Support event listeners and handlers
  - Add standard events: progress, error, warning
  - Test: Events can be emitted and handled

### 4.3 Retry Logic

- [ ] **TASK-052: Implement retry decorator**
  - Create `src/patchsmith/utils/retry.py`
  - Implement `retry_with_backoff()` decorator
  - Support exponential backoff with jitter
  - Handle both sync and async functions
  - Add configurable retry exceptions
  - Test: Retry logic works with transient failures

---

## Phase 5: Data Layer (Repositories)

### 5.1 File Repository

- [ ] **TASK-053: Implement base repository interface**
  - Create `src/patchsmith/repositories/base.py`
  - Define abstract base class with standard methods
  - Document repository contract
  - Test: Interface is well-defined

- [ ] **TASK-054: Implement FileRepository**
  - Create `src/patchsmith/repositories/file_repository.py`
  - Implement `FileRepository` class
  - Add methods: `save_config()`, `load_config()`, `save_analysis()`, `load_analysis()`
  - Handle file I/O errors gracefully
  - Test: Files can be saved and loaded

- [ ] **TASK-055: Implement file-based query storage**
  - Add methods for saving/loading queries
  - Support query metadata
  - Test: Queries can be persisted

- [ ] **TASK-056: Implement result history management**
  - Add methods to list historical analyses
  - Support loading analysis by timestamp
  - Implement cleanup of old results (retention policy)
  - Test: Historical data can be accessed

---

## Phase 6: Presentation Layer (CLI)

### 6.1 CLI Framework

- [ ] **TASK-057: Implement main CLI entry point**
  - Create `src/patchsmith/cli/main.py`
  - Implement Click command group
  - Add global options: `--verbose`, `--no-color`, `--config`
  - Setup logging based on verbose flag
  - Test: CLI starts and shows help

- [ ] **TASK-058: Implement version command**
  - Add `--version` flag
  - Display Patchsmith version, Python version, platform
  - Test: Version command works

### 6.2 Console Output

- [ ] **TASK-059: Implement console utilities**
  - Create `src/patchsmith/presentation/console.py`
  - Setup Rich Console singleton
  - Add utility functions for common output patterns
  - Test: Console can print styled output

- [ ] **TASK-060: Implement progress display**
  - Create `src/patchsmith/presentation/progress.py`
  - Implement progress bar for long operations
  - Add spinners for indeterminate tasks
  - Create progress callback handlers for services
  - Test: Progress displays correctly

- [ ] **TASK-061: Implement formatters**
  - Create `src/patchsmith/presentation/formatters.py`
  - Implement markdown formatter (for terminal display)
  - Add table formatter for findings
  - Add syntax highlighting for code snippets
  - Test: Formatting works correctly

### 6.3 Init Command

- [ ] **TASK-062: Implement init command**
  - Create `src/patchsmith/cli/init.py`
  - Implement `init()` Click command with options
  - Add `run_init()` async function
  - Integrate with ProjectService via ServiceFactory
  - Setup progress callback for Rich output
  - Test: Init command works end-to-end

- [ ] **TASK-063: Add init command validations**
  - Check if already initialized (`.patchsmith/` exists)
  - Validate Git repository exists
  - Check for required dependencies (CodeQL, Git)
  - Test: Validations work correctly

- [ ] **TASK-064: Add init command output**
  - Display detected languages with confidence
  - Show CodeQL database creation progress
  - Display generated custom queries count
  - Show success message with summary
  - Test: Output is user-friendly

### 6.4 Analyze Command

- [ ] **TASK-065: Implement analyze command**
  - Create `src/patchsmith/cli/analyze.py`
  - Implement `analyze()` Click command with options
  - Add `run_analyze()` async function
  - Integrate with AnalysisService via ServiceFactory
  - Setup progress callback
  - Test: Analyze command works end-to-end

- [ ] **TASK-066: Add analyze command options**
  - Add `--queries` option to specify custom queries
  - Add `--format` option for output format (sarif, csv, json)
  - Add `--skip-false-positive-filter` flag
  - Test: Options work correctly

- [ ] **TASK-067: Implement analyze command output**
  - Display analysis progress (query execution, filtering)
  - Show summary statistics table
  - Display top critical findings
  - Show report location
  - Test: Output is clear and actionable

### 6.5 Fix Command

- [ ] **TASK-068: Implement fix command**
  - Create `src/patchsmith/cli/fix.py`
  - Implement `fix()` Click command with issue IDs
  - Add `run_fix()` async function
  - Integrate with FixService via ServiceFactory
  - Test: Fix command works end-to-end

- [ ] **TASK-069: Add fix command options**
  - Add `--branch` option for custom branch name
  - Add `--no-pr` flag to skip PR creation
  - Add `--dry-run` flag for testing
  - Add `--test-command` option to run tests after fix
  - Test: Options work correctly

- [ ] **TASK-070: Implement fix command safety**
  - Check for dirty working directory
  - Prompt user for confirmation before applying fixes
  - Display diff before committing
  - Show backup locations
  - Test: Safety checks work

- [ ] **TASK-071: Implement fix command output**
  - Show fix generation progress
  - Display code changes with diff
  - Show commit and branch information
  - Display PR URL if created
  - Test: Output is informative

### 6.6 Report Command

- [ ] **TASK-072: Implement report command**
  - Create `src/patchsmith/cli/report.py`
  - Implement `report()` Click command
  - Add `run_report()` function to load and display latest report
  - Test: Report command works

- [ ] **TASK-073: Add report command options**
  - Add `--date` option to view specific report
  - Add `--format` option (terminal, browser, json)
  - Add `--filter` option for severity filtering
  - Test: Options work correctly

- [ ] **TASK-074: Implement report display**
  - Display markdown in terminal with Rich
  - Support opening in browser (convert MD to HTML)
  - Support JSON output for scripting
  - Test: Different formats work correctly

---

## Phase 7: Utilities & Helpers

### 7.1 Filesystem Utilities

- [ ] **TASK-075: Implement safe file operations**
  - Create `src/patchsmith/utils/filesystem.py`
  - Implement safe read/write with error handling
  - Add directory creation with proper permissions
  - Implement file backup/restore functions
  - Add path validation (prevent directory traversal)
  - Test: File operations are safe

- [ ] **TASK-076: Implement file tree scanner**
  - Add function to generate file tree string
  - Add function to get file samples (stratified by extension)
  - Support ignore patterns (node_modules, .git, etc.)
  - Test: Scanner works on sample projects

### 7.2 Validation Utilities

- [ ] **TASK-077: Implement input validation**
  - Create `src/patchsmith/utils/validation.py`
  - Add validators for: language names, issue IDs, branch names
  - Add CodeQL query syntax validation (basic)
  - Add path validation functions
  - Test: Validators work correctly

### 7.3 Context Management

- [ ] **TASK-078: Implement code context extraction**
  - Add function to extract code snippet with context lines
  - Add function to find function/class containing line
  - Support multiple languages (basic AST parsing)
  - Test: Context extraction works for common cases

---

## Phase 8: Testing

### 8.1 Unit Tests - Models

- [ ] **TASK-079: Write tests for config models**
  - Test config creation, validation, save/load
  - Test config hierarchy (env vars, defaults)
  - Test validation errors
  - Coverage: >90%

- [ ] **TASK-080: Write tests for domain models**
  - Test Finding, ProjectInfo, AnalysisResult models
  - Test model validation and edge cases
  - Coverage: >90%

### 8.2 Unit Tests - Adapters

- [ ] **TASK-081: Write tests for CodeQL adapter**
  - Mock subprocess calls
  - Test database creation, query execution
  - Test error handling (CodeQL not found, timeout)
  - Coverage: >85%

- [ ] **TASK-082: Write tests for Claude adapter**
  - Mock Anthropic API calls
  - Test all agents with various responses
  - Test retry logic and error handling
  - Coverage: >85%

- [ ] **TASK-083: Write tests for Git adapter**
  - Mock git subprocess calls
  - Test all git operations
  - Test error handling
  - Coverage: >85%

### 8.3 Unit Tests - Services

- [ ] **TASK-084: Write tests for ProjectService**
  - Mock all adapters
  - Test initialization workflow
  - Test error handling at each step
  - Coverage: >90%

- [ ] **TASK-085: Write tests for AnalysisService**
  - Mock adapters and test analysis workflow
  - Test false positive filtering
  - Test result aggregation
  - Coverage: >90%

- [ ] **TASK-086: Write tests for FixService**
  - Mock adapters and test fix workflow
  - Test fix application and rollback
  - Test Git operations
  - Coverage: >90%

- [ ] **TASK-087: Write tests for other services**
  - Test QueryService, ReportService
  - Coverage: >85%

### 8.4 Unit Tests - Utilities

- [ ] **TASK-088: Write tests for utilities**
  - Test retry logic, validation, filesystem operations
  - Test logging setup
  - Coverage: >85%

### 8.5 Integration Tests

- [ ] **TASK-089: Create fixture projects**
  - Create `tests/fixtures/vulnerable_python/` with known vulnerabilities
  - Create `tests/fixtures/vulnerable_javascript/`
  - Add README documenting vulnerabilities
  - Test: Fixtures are valid projects

- [ ] **TASK-090: Write integration test for init workflow**
  - Test full init on fixture project
  - Verify directory structure, config, databases
  - Test: Init works end-to-end

- [ ] **TASK-091: Write integration test for analyze workflow**
  - Run analyze on initialized fixture project
  - Verify findings are detected
  - Verify report is generated
  - Test: Analyze works end-to-end

- [ ] **TASK-092: Write integration test for fix workflow**
  - Run fix on known vulnerability
  - Verify code is changed correctly
  - Verify Git operations
  - Test: Fix works end-to-end

- [ ] **TASK-093: Write integration test for full workflow**
  - Run init → analyze → fix in sequence
  - Verify complete workflow
  - Test: Full workflow works

### 8.6 Test Infrastructure

- [ ] **TASK-094: Setup pytest configuration**
  - Configure pytest.ini with test paths, markers
  - Setup pytest-asyncio
  - Configure coverage reporting
  - Test: Pytest runs all tests

- [ ] **TASK-095: Create test fixtures and mocks**
  - Create reusable fixtures for configs, findings, etc.
  - Create mock factories for adapters
  - Test: Fixtures work correctly

- [ ] **TASK-096: Setup CI/CD testing**
  - Create GitHub Actions workflow
  - Run tests on push and PR
  - Test on multiple Python versions (3.9, 3.10, 3.11, 3.12)
  - Test on multiple platforms (Ubuntu, macOS, Windows)
  - Upload coverage reports
  - Test: CI/CD works

---

## Phase 9: Documentation

### 9.1 Code Documentation

- [ ] **TASK-097: Add docstrings to all public APIs**
  - Add Google-style docstrings to all classes and methods
  - Include type hints everywhere
  - Add usage examples in docstrings
  - Test: Docstrings are complete and accurate

- [ ] **TASK-098: Add inline comments**
  - Add comments for complex logic
  - Document non-obvious design decisions
  - Test: Code is well-commented

### 9.2 User Documentation

- [ ] **TASK-099: Write comprehensive README.md**
  - Add project description and features
  - Add installation instructions
  - Add quick start guide
  - Add prerequisites (CodeQL, Git, API key)
  - Add link to full documentation
  - Test: README is clear and complete

- [ ] **TASK-100: Write user guide**
  - Create `documentation/user-guide.md`
  - Document each command with examples
  - Add common workflows and troubleshooting
  - Add FAQ section
  - Test: User guide covers common scenarios

- [ ] **TASK-101: Write configuration reference**
  - Create `documentation/configuration.md`
  - Document all config options with defaults
  - Add examples of common configurations
  - Test: Configuration is documented

- [ ] **TASK-102: Write query writing guide**
  - Create `documentation/custom-queries.md`
  - Explain how to write custom CodeQL queries
  - Add examples for common patterns
  - Test: Guide is helpful for query authors

### 9.3 Developer Documentation

- [ ] **TASK-103: Write contributing guide**
  - Create `CONTRIBUTING.md`
  - Document development setup
  - Add code style guidelines
  - Document PR process
  - Test: Contributing guide is clear

- [ ] **TASK-104: Write architecture documentation**
  - Create `documentation/architecture.md` (summary of design.md)
  - Add architecture diagrams
  - Document key design patterns
  - Test: Architecture is well-documented

### 9.4 API Documentation

- [ ] **TASK-105: Generate API documentation**
  - Setup Sphinx for API docs generation
  - Configure autodoc to extract docstrings
  - Generate HTML documentation
  - Test: API docs are generated and accurate

---

## Phase 10: Polish & Release Preparation

### 10.1 Error Messages & UX

- [ ] **TASK-106: Improve error messages**
  - Review all error messages for clarity
  - Add actionable suggestions to errors
  - Add links to documentation where relevant
  - Test: Error messages are helpful

- [ ] **TASK-107: Add help text and examples**
  - Improve Click command help text
  - Add usage examples to `--help` output
  - Test: Help text is clear

### 10.2 Performance Optimization

- [ ] **TASK-108: Optimize LLM calls**
  - Implement caching for language detection
  - Batch false positive filtering
  - Add token usage optimization
  - Test: Performance is acceptable

- [ ] **TASK-109: Optimize file operations**
  - Profile file I/O operations
  - Add caching where appropriate
  - Test: File operations are efficient

### 10.3 Security Hardening

- [ ] **TASK-110: Audit for security issues**
  - Review path handling for traversal vulnerabilities
  - Ensure API keys are never logged
  - Validate all user inputs
  - Test: Security checks pass

- [ ] **TASK-111: Add security best practices**
  - Document sensitive data handling
  - Add warnings for security-sensitive operations
  - Test: Security documentation is clear

### 10.4 Platform Compatibility

- [ ] **TASK-112: Test on Windows**
  - Test all commands on Windows
  - Fix path separator issues
  - Test: Works on Windows

- [ ] **TASK-113: Test on macOS**
  - Test all commands on macOS
  - Test: Works on macOS

- [ ] **TASK-114: Test on Linux**
  - Test on Ubuntu and other distros
  - Test: Works on Linux

### 10.5 Packaging & Distribution

- [ ] **TASK-115: Finalize Poetry configuration**
  - Set correct version number
  - Add classifiers and keywords
  - Add license file
  - Test: Package metadata is correct

- [ ] **TASK-116: Test installation from source**
  - Test `poetry install` on fresh system
  - Test CLI works after installation
  - Test: Installation works

- [ ] **TASK-117: Create distribution packages**
  - Build wheel and source distributions
  - Test installation from wheel
  - Test: Distributions work

- [ ] **TASK-118: Prepare for PyPI upload**
  - Register on PyPI (test.pypi.org first)
  - Configure Poetry for PyPI upload
  - Test: Can upload to test.pypi.org

### 10.6 Release

- [ ] **TASK-119: Create release checklist**
  - Document release process
  - Add version bumping procedure
  - Add changelog generation
  - Test: Release process is documented

- [ ] **TASK-120: Prepare v1.0 release**
  - Bump version to 1.0.0
  - Generate CHANGELOG.md
  - Tag release in Git
  - Upload to PyPI
  - Create GitHub release with notes
  - Test: Release is complete

---

## Phase 11: Examples & Demo

### 11.1 Example Projects

- [ ] **TASK-121: Create Python example**
  - Create `examples/vulnerable_python/` with Flask app
  - Add SQL injection, XSS, path traversal vulnerabilities
  - Add README explaining vulnerabilities
  - Test: Patchsmith detects vulnerabilities

- [ ] **TASK-122: Create JavaScript example**
  - Create `examples/vulnerable_javascript/` with Express app
  - Add common Node.js vulnerabilities
  - Add README
  - Test: Patchsmith detects vulnerabilities

### 11.2 Demo Materials

- [ ] **TASK-123: Create demo script**
  - Write step-by-step demo script
  - Add expected outputs
  - Record demo GIF/video
  - Test: Demo is reproducible

- [ ] **TASK-124: Create tutorial**
  - Write beginner-friendly tutorial
  - Add screenshots
  - Test: Tutorial is followable

---

## Summary Statistics

**Total Tasks: 124**

**By Phase:**
- Phase 1 (Foundation): 12 tasks
- Phase 2 (Adapters): 15 tasks
- Phase 3 (Services): 20 tasks
- Phase 4 (Orchestration): 5 tasks
- Phase 5 (Repositories): 4 tasks
- Phase 6 (CLI): 18 tasks
- Phase 7 (Utilities): 4 tasks
- Phase 8 (Testing): 18 tasks
- Phase 9 (Documentation): 9 tasks
- Phase 10 (Polish): 15 tasks
- Phase 11 (Examples): 4 tasks

**By Category:**
- Infrastructure/Setup: 15 tasks
- Core Implementation: 62 tasks
- Testing: 18 tasks
- Documentation: 14 tasks
- Polish/Release: 15 tasks

---

## Notes

- Tasks are designed to be implemented sequentially within each phase
- Some tasks can be parallelized across phases (e.g., tests can be written alongside implementation)
- Each task includes test criteria for acceptance
- Code coverage targets: >85% overall, >90% for critical paths
- All tasks should follow the architecture defined in design.md
- Service layer must remain presentation-agnostic for future SaaS evolution
