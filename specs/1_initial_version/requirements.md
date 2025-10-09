# Patchsmith - Technical Requirements Document

## 1. Overview

Patchsmith is a CLI tool that leverages CodeQL and LLM capabilities to automatically detect security vulnerabilities in codebases, generate intelligent analysis reports, and create pull requests with fixes.

## 2. System Architecture

### 2.1 Technology Stack
- **Core Language**: Python 3.9+
- **Security Analysis Engine**: CodeQL
- **LLM Integration**: Claude Code Agent SDK
- **Version Control**: Git
- **Output Formats**: CSV (raw results), Markdown (reports)

### 2.2 Dependencies (Assumed Pre-installed)
- CodeQL CLI
- Git
- Python 3.9+
- Claude API credentials (configured via environment)

## 3. Core Commands

### 3.1 `patchsmith init`

**Purpose**: Initialize security analysis for a project

**Workflow**:
1. Detect project root and validate git repository
2. Use LLM to analyze project structure and detect programming languages
3. Create CodeQL database for detected languages
4. Inspect codebase to understand architecture, patterns, and potential vulnerability surfaces
5. Generate custom CodeQL security queries tailored to the specific codebase
6. Store configuration in `.patchsmith/config.json`
8. Store custom queries in `.patchsmith/queries/`

**Inputs**:
- Current working directory (implicit)
- Optional: `--languages <comma-separated>` to override auto-detection
- Optional: `--query-templates <path>` to use existing query templates

**Outputs**:
- `.patchsmith/` directory structure
- CodeQL database in `.patchsmith/db/`
- Custom queries in `.patchsmith/queries/`
- Configuration file `.patchsmith/config.json`
- Initialization report in `.patchsmith/init-report.md`

**Error Handling**:
- Verify CodeQL is installed and accessible
- Verify Git repository exists
- Handle unsupported languages gracefully
- Validate Claude API connectivity

### 3.2 `patchsmith analyze`

**Purpose**: Execute security analysis and generate intelligent report

**Workflow**:
1. Load configuration from `.patchsmith/config.json`
2. Execute CodeQL analysis:
   - Run standard language-specific security queries
   - Run custom queries from `.patchsmith/queries/`
3. Save raw results to `.patchsmith/results/results-<timestamp>.csv`
4. Process results with LLM code agent:
   - Review each finding with code context
   - Filter false positives using intelligent code analysis
   - Assess severity and exploitability
   - Generate detailed explanations
   - Prioritize issues
5. Generate comprehensive report: `.patchsmith/reports/report-<timestamp>.md`
6. Symlink latest report to `.patchsmith/reports/latest.md`

**Inputs**:
- Existing `.patchsmith/` configuration
- Optional: `--queries <path>` to run specific queries only
- Optional: `--format <csv|json|sarif>` for raw output format

**Outputs**:
- Raw results CSV: `.patchsmith/results/results-<timestamp>.csv`
- Detailed report: `.patchsmith/reports/report-<timestamp>.md`
- Summary statistics in console output

**Report Contents**:
- Executive summary
- Vulnerability statistics (by severity, category, language)
- Detailed findings with:
  - Issue ID
  - Title and description
  - Severity level (Critical, High, Medium, Low, Info)
  - CWE classification
  - Affected file(s) and line numbers
  - Code snippet with context
  - Explanation of the vulnerability
  - Recommended fix
  - False positive assessment
- Prioritized action items

### 3.3 `patchsmith fix <issue-id> [issue-id...]`

**Purpose**: Automatically fix one or more security issues and create pull request

**Workflow**:
1. Load latest analysis results
2. Validate issue IDs exist in results
3. For each issue:
   - Retrieve full context (code, surrounding functions, dependencies)
   - Use LLM code agent to generate fix
   - Apply fix to codebase
   - Verify fix doesn't break syntax
4. Create git branch: `patchsmith/fix-<issue-ids>`
5. Commit changes with descriptive message
6. Generate PR description with:
   - Issues addressed
   - Changes made
   - Testing recommendations
   - Security impact analysis
7. Push branch and create pull request (if remote configured)

**Inputs**:
- `<issue-id>`: One or more issue IDs from latest report
- Optional: `--branch <name>` to specify custom branch name
- Optional: `--no-pr` to skip PR creation (just create branch)
- Optional: `--test-command <cmd>` to run tests after applying fixes

**Outputs**:
- Git branch with fixes
- Commit(s) with changes
- Pull request (if remote available)
- Fix summary in `.patchsmith/fixes/fix-<timestamp>.md`

**Safety Features**:
- Never commit directly to main/master
- Create backup of original files in `.patchsmith/backups/`
- Validate syntax after changes
- Optional: Run user-specified test command
- Dry-run mode available: `--dry-run`

### 3.4 `patchsmith report`

**Purpose**: Display the latest analysis report

**Workflow**:
1. Locate latest report: `.patchsmith/reports/latest.md`
2. Display in terminal with formatting
3. Optional: Open in default markdown viewer

**Inputs**:
- Optional: `--date <timestamp>` to view specific report
- Optional: `--format <terminal|browser|json>` for output format
- Optional: `--filter <severity>` to show only specific severity levels

**Outputs**:
- Formatted report display in terminal
- Optional: Open in browser or external viewer

## 4. Data Structures

### 4.1 Configuration File (`.patchsmith/config.json`)

```json
{
  "version": "1.0",
  "project": {
    "name": "project-name",
    "root": "/path/to/project",
    "languages": ["python", "javascript", "go"],
    "ignore_paths": ["tests/", "vendor/", "node_modules/"]
  },
  "codeql": {
    "database_path": ".patchsmith/db",
    "query_paths": [
      ".patchsmith/queries",
      "codeql-standard-libraries"
    ]
  },
  "analysis": {
    "filter_false_positives": true,
    "min_severity": "low",
    "max_results": 1000
  },
  "llm": {
    "model": "claude-sonnet-4",
    "temperature": 0.2
  },
  "git": {
    "remote": "origin",
    "base_branch": "main"
  },
  "initialized_at": "2025-10-07T10:30:00Z",
  "last_analysis": "2025-10-07T11:45:00Z"
}
```

### 4.2 Analysis Results (CSV)

Columns:
- `issue_id`: Unique identifier (hash of location + rule)
- `rule_id`: CodeQL rule/query ID
- `severity`: Critical/High/Medium/Low/Info
- `cwe`: CWE identifier (if applicable)
- `file`: Relative path to file
- `start_line`: Starting line number
- `end_line`: Ending line number
- `message`: Description from CodeQL
- `snippet`: Code snippet
- `false_positive_score`: 0.0-1.0 (from LLM analysis)
- `recommendation`: Fix recommendation

### 4.3 Report Structure (Markdown)

```markdown
# Security Analysis Report
Generated: <timestamp>

## Executive Summary
- Total issues found: X
- After false positive filtering: Y
- Critical: A | High: B | Medium: C | Low: D

## Statistics
[Charts/tables of findings by language, category, severity]

## Critical Issues
### [CRITICAL-001] SQL Injection in user_login
**File**: `src/auth/login.py:45-52`
**CWE**: CWE-89
**Severity**: Critical
...

## Recommended Actions
1. Fix CRITICAL-001: SQL Injection in user_login
2. Fix HIGH-003: Path Traversal in file_upload
...
```

## 5. LLM Integration Points

### 5.1 Language Detection (init)
**Task**: Analyze project structure to identify languages and frameworks
**Input**: Directory tree, file extensions, configuration files
**Output**: List of languages with confidence scores

### 5.2 Custom Query Generation (init)
**Task**: Create CodeQL queries tailored to codebase patterns
**Input**: Code samples, architecture analysis, common patterns
**Output**: CodeQL query files (.ql)

### 5.3 False Positive Filtering (analyze)
**Task**: Review findings with code context to identify false positives
**Input**: CodeQL result, code snippet, surrounding context
**Output**: False positive score (0.0-1.0), reasoning

### 5.4 Report Generation (analyze)
**Task**: Transform technical findings into human-readable report
**Input**: Filtered results, code context, project metadata
**Output**: Markdown report with explanations and recommendations

### 5.5 Fix Generation (fix)
**Task**: Generate secure code fix for vulnerability
**Input**: Vulnerability details, affected code, project context
**Output**: Code changes, explanation, test recommendations

## 6. File System Structure

```
project-root/
├── .patchsmith/
│   ├── config.json
│   ├── db/                    # CodeQL databases
│   │   ├── python/
│   │   └── javascript/
│   ├── queries/               # Custom CodeQL queries
│   │   ├── sql-injection.ql
│   │   └── custom-*.ql
│   ├── results/               # Raw analysis results
│   │   ├── results-20251007-114500.csv
│   │   └── results-*.csv
│   ├── reports/               # Generated reports
│   │   ├── latest.md -> report-20251007-114500.md
│   │   ├── report-20251007-114500.md
│   │   └── report-*.md
│   ├── fixes/                 # Fix documentation
│   │   └── fix-20251007-120000.md
│   ├── backups/               # Original file backups
│   └── init-report.md
└── [project files]
```

## 7. Non-Functional Requirements

### 7.1 Performance
- `init` command: < 5 minutes for typical project (< 100k LOC)
- `analyze` command: < 10 minutes for typical project
- `fix` command: < 2 minutes per issue
- LLM calls should have timeout (120s default)

### 7.2 Security
- Never expose sensitive code in LLM prompts without user awareness
- Store credentials securely (environment variables, not config files)
- Validate all file operations stay within project boundaries
- No automatic push to remote without explicit confirmation

### 7.3 Reliability
- Handle LLM API failures gracefully (retry with backoff)
- Validate CodeQL output before processing
- Atomic operations for file modifications
- Maintain audit log of all operations in `.patchsmith/audit.log`

### 7.4 Usability
- Clear progress indicators for long operations
- Helpful error messages with actionable suggestions
- Support for `--help` on all commands
- Colored output for terminal (with `--no-color` option)
- Verbose mode: `--verbose` or `-v`

## 8. Error Scenarios

### 8.1 Missing Dependencies
- Detect and report missing CodeQL, Git, Python packages
- Provide installation instructions

### 8.2 CodeQL Database Creation Failures
- Handle unsupported languages
- Report compilation errors clearly
- Suggest workarounds

### 8.3 LLM API Issues
- Handle rate limits (exponential backoff)
- Handle timeouts (retry or skip with warning)
- Handle quota exhaustion (clear error message)

### 8.4 Git Issues
- No remote configured (skip PR creation)
- Merge conflicts (detect and warn)
- Dirty working directory (warn before init/fix)

### 8.5 Invalid Configurations
- Validate config.json on load
- Provide schema validation
- Offer repair/reset options

## 9. Future Enhancements (Out of Scope for v1)

- Web dashboard for report visualization
- Integration with CI/CD pipelines
- Support for custom LLM providers
- Incremental analysis (only changed files)
- Team collaboration features
- Historical trend analysis
- Integration with issue tracking systems (Jira, GitHub Issues)
- Support for multiple LLM providers (OpenAI, local models)
- Auto-fix mode with automatic PR creation
- Configurable rule sets and severity levels

## 10. Testing Requirements

### 10.1 Unit Tests
- Configuration parsing and validation
- CSV/report parsing and generation
- Git operations (mocked)
- CodeQL wrapper functions

### 10.2 Integration Tests
- Full workflow: init → analyze → fix
- Test with sample vulnerable projects
- Test with multiple language projects

### 10.3 Test Coverage
- Minimum 80% code coverage
- Critical paths: 100% coverage (fix generation, file operations)

## 11. Documentation Requirements

- README.md: Quick start guide
- User guide: Detailed command documentation
- Development guide: Architecture and contribution guidelines
- Example projects: Sample vulnerable code for testing
- Query writing guide: How to write custom CodeQL queries
