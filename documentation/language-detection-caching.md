# Language Detection Caching

## The Problem

Language detection was being performed every time, wasting time and API calls:

```bash
# First run
patchsmith finetune        # Detects languages (60 seconds)

# Second run
patchsmith analyze         # Re-detects languages (60 seconds) ← Wasteful!

# Third run
patchsmith analyze         # Re-detects languages (60 seconds) ← Still wasteful!
```

**Issues:**
- ❌ **Expensive**: Language detection uses AI (Claude API calls)
- ❌ **Slow**: Takes 30-60 seconds each time
- ❌ **Redundant**: Languages don't change between runs
- ❌ **Inconsistent**: Same project could get different results

## The Solution

Implemented language detection caching via `ProjectRepository`:

```
First run (any command):
  → Detect languages with AI
  → Save to .patchsmith/project-info.json

Subsequent runs:
  → Load from .patchsmith/project-info.json
  → Skip AI detection (instant!)
```

## Implementation

### 1. Created ProjectRepository

**File:** `src/patchsmith/repositories/project_repository.py`

```python
class ProjectRepository:
    @staticmethod
    def save(project_info: ProjectInfo) -> None:
        """Save to .patchsmith/project-info.json"""

    @staticmethod
    def load(project_root: Path) -> ProjectInfo | None:
        """Load from .patchsmith/project-info.json"""
```

### 2. Updated AnalysisService

**File:** `src/patchsmith/services/analysis_service.py`

```python
# Before: Always detect
languages = await language_agent.execute(project_path)

# After: Load from cache or detect
project_info = ProjectRepository.load(project_path)
if project_info and project_info.languages:
    languages = project_info.languages  # ← Cached! Instant!
else:
    languages = await language_agent.execute(project_path)
    # Save for next time
    ProjectRepository.save(ProjectInfo(...))
```

### 3. Updated QueryFinetuneService

**File:** `src/patchsmith/services/query_finetune_service.py`

Same pattern - load from cache first, detect only if needed.

## File Format

**Location:** `.patchsmith/project-info.json`

```json
{
  "name": "my-project",
  "root": "/path/to/project",
  "languages": [
    {
      "name": "typescript",
      "confidence": 0.95,
      "evidence": ["package.json", "tsconfig.json", "*.ts files"]
    },
    {
      "name": "javascript",
      "confidence": 0.90,
      "evidence": ["*.js files", "*.jsx files"]
    },
    {
      "name": "python",
      "confidence": 0.85,
      "evidence": ["requirements.txt", "*.py files"]
    }
  ],
  "description": null,
  "repository_url": null,
  "custom_queries": []
}
```

## Behavior

### First Time (No Cache)

```bash
$ patchsmith finetune

⠋ Detecting programming languages...    # AI detection (60s)
✓ Languages detected (typescript, javascript, python)
# Creates .patchsmith/project-info.json
```

### Second Time (With Cache)

```bash
$ patchsmith analyze

✓ Languages detected (typescript, javascript, python)  # Instant! (<1s)
# Loaded from .patchsmith/project-info.json
```

### Force Re-detection

If you want to force re-detection:

```bash
# Delete the cache
rm .patchsmith/project-info.json

# Next run will detect from scratch
patchsmith analyze
```

## Benefits

✅ **Faster**: Subsequent runs skip 30-60s AI call
✅ **Cheaper**: Saves Claude API calls
✅ **Consistent**: Same languages across commands
✅ **Shared**: Both `finetune` and `analyze` use same cache
✅ **Automatic**: No user action needed

## Performance Impact

**Before:**
```
patchsmith finetune:  60s language detection
patchsmith analyze:   60s language detection  (total: 120s wasted)
patchsmith analyze:   60s language detection  (total: 180s wasted)
```

**After:**
```
patchsmith finetune:  60s language detection  (cached)
patchsmith analyze:   <1s language loading    (cached!)
patchsmith analyze:   <1s language loading    (cached!)
```

**Savings:** ~60 seconds per command after first run!

## Edge Cases

### Project Languages Change

If you add a new language to your project:

```bash
# Option 1: Delete cache to re-detect
rm .patchsmith/project-info.json

# Option 2: Manually edit .patchsmith/project-info.json
# (Add new language entry)
```

### Multiple Projects

Each project has its own cache:

```
project-a/.patchsmith/project-info.json  # Project A languages
project-b/.patchsmith/project-info.json  # Project B languages
```

### Corrupted Cache

If cache is corrupted, it's automatically ignored:

```python
try:
    project_info = ProjectRepository.load(project_path)
except Exception:
    # Fallback: detect from scratch
    project_info = None
```

## Code Changes Summary

### Files Created
- `src/patchsmith/repositories/project_repository.py` (new)

### Files Modified
- `src/patchsmith/services/analysis_service.py` - Load/save cache
- `src/patchsmith/services/query_finetune_service.py` - Load/save cache

### No Breaking Changes
- ✅ Backward compatible
- ✅ Transparent to users
- ✅ No CLI changes needed
- ✅ Works automatically

## Testing

Test the caching:

```bash
# First run - detects languages
time patchsmith analyze
# Note the time

# Delete database to force fresh run
rm -rf .patchsmith/db

# Second run - uses cache!
time patchsmith analyze
# Should be ~60s faster!
```

## Future Enhancements

Possible improvements:
1. Add `--redetect` flag to force re-detection
2. Add timestamp to track when languages were detected
3. Auto-invalidate cache after N days
4. Show cache status in verbose mode
