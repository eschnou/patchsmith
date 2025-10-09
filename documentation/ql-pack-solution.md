# CodeQL QL Pack Solution for Custom Queries

## The Problem

When generating custom CodeQL queries, compilation failed with:
```
ERROR: Could not locate a dbscheme to compile against.
There should probably be a qlpack.yml file declaring dependencies
```

## Root Cause

CodeQL queries cannot be compiled in isolation. They require:
1. A **qlpack.yml** file that declares dependencies
2. Dependencies on **standard libraries** (e.g., `codeql/python-all`)
3. The **dbscheme** (database schema) for the target language
4. Dependencies must be **downloaded** via `codeql pack install`

## Solution Overview

We implement proper **QL pack management** with three key additions:

### 1. QL Pack Creation (`create_ql_pack`)
**File**: `src/patchsmith/adapters/codeql/cli.py`

Creates a proper QL pack structure:
```yaml
name: patchsmith/patchsmith-custom-queries-python
version: 0.0.1
dependencies:
  codeql/python-all: "*"
```

Maps languages to their standard library packs:
- `python` → `codeql/python-all`
- `javascript` → `codeql/javascript-all`
- `java` → `codeql/java-all`
- `go` → `codeql/go-all`
- `cpp` → `codeql/cpp-all`
- `csharp` → `codeql/csharp-all`
- `ruby` → `codeql/ruby-all`

### 2. Dependency Installation (`install_pack_dependencies`)
**File**: `src/patchsmith/adapters/codeql/cli.py`

Runs `codeql pack install` to:
- Download standard library packs from GitHub Container Registry
- Create `codeql-pack.lock.yml` tracking precise versions
- Set up the compilation environment

### 3. Service Integration
**File**: `src/patchsmith/services/query_finetune_service.py`

Before generating queries, the service:
1. Creates QL pack structure for each detected language
2. Installs dependencies for each pack
3. Passes `pack_dir` to the agent for query generation
4. Queries are saved directly into the pack directory

### 4. Agent Updates
**File**: `src/patchsmith/adapters/claude/custom_query_generator_agent.py`

The agent now:
- Accepts a `pack_dir` parameter
- Saves queries directly into the pack directory (not temp files)
- Compiles queries within the proper QL pack context
- Falls back to creating a temp QL pack for testing

## Implementation Flow

```
1. User runs: patchsmith finetune
                    ↓
2. Service detects languages (e.g., python)
                    ↓
3. For each language:
   - Create .patchsmith/queries/python/
   - Create qlpack.yml with dependencies
   - Run codeql pack install
                    ↓
4. Generate queries:
   - Save to .patchsmith/queries/python/query.ql
   - Compile with: codeql query compile --check-only
   - Now succeeds because qlpack.yml exists!
                    ↓
5. On compilation errors:
   - Feed errors back to AI
   - Regenerate improved query
   - Retry (max 3 attempts)
```

## Directory Structure

```
.patchsmith/
  └── queries/
      ├── python/
      │   ├── qlpack.yml           # ← Declares dependencies
      │   ├── codeql-pack.lock.yml # ← Downloaded versions
      │   ├── .codeql/             # ← Downloaded standard libs
      │   ├── sql_injection.ql     # ← Custom queries
      │   └── command_injection.ql
      ├── javascript/
      │   ├── qlpack.yml
      │   └── ...
      └── metadata.json
```

## Benefits

✅ **Proper Compilation**: Queries compile successfully with access to standard libraries

✅ **Language Support**: Works for all CodeQL-supported languages

✅ **Offline Capability**: Dependencies cached locally after first download

✅ **Version Control**: `codeql-pack.lock.yml` ensures reproducible builds

✅ **Standard Compliance**: Follows CodeQL's official pack management system

## Commands Added

### create_ql_pack
```python
codeql_cli.create_ql_pack(
    pack_dir=Path(".patchsmith/queries/python"),
    language="python"
)
```

### install_pack_dependencies
```python
codeql_cli.install_pack_dependencies(
    pack_dir=Path(".patchsmith/queries/python")
)
```

## Testing

All existing tests pass with the new implementation. The solution:
- Maintains backward compatibility
- Gracefully handles failures (continues with other languages)
- Provides clear error messages
- Falls back to temp pack creation for testing

## Resources

- [Creating CodeQL Packs - GitHub Docs](https://docs.github.com/en/code-security/codeql-cli/using-the-advanced-functionality-of-the-codeql-cli/creating-and-working-with-codeql-packs)
- [CodeQL Standard Libraries](https://github.com/github/codeql)
- [qlpack.yml Format](https://docs.github.com/en/code-security/codeql-cli/using-the-advanced-functionality-of-the-codeql-cli/creating-and-working-with-codeql-packs#qlpackyml-properties)
