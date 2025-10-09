# Custom Queries Progress Display Fix

## The Issue

During analysis, the custom queries progress bar displayed differently from other steps:

```
✓ Languages detected                     ━━━━━━━━━━━━━━━━━━━ 100% 0:01:09
✓ CodeQL database created                ━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
✓ Security queries completed             ━━━━━━━━━━━━━━━━━━━ 100% 0:00:34
custom_queries_completed                 ━━━━━━━━━━━━━━━━━━━ 100% 0:01:36  ← Missing ✓
✓ Results parsed                         ━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
```

**Problems:**
- ❌ No checkmark (✓) for custom queries
- ❌ Raw event name instead of user-friendly label
- ❌ Inconsistent with other progress indicators

## Root Cause

The custom queries events were missing from the progress descriptions dictionary in `cli/progress.py`.

**Event flow:**
1. Analysis service emits: `custom_queries_started`
2. Analysis service emits: `custom_queries_completed`
3. Progress tracker has no mapping for these events
4. Falls back to displaying raw event name

## The Fix

Added custom query events to the progress descriptions dictionary:

```python
descriptions = {
    # ... existing events ...
    "codeql_queries_started": "Running security queries...",
    "codeql_queries_completed": "✓ Security queries completed",
    "custom_queries_started": "Running custom queries...",      # ← NEW
    "custom_queries_completed": "✓ Custom queries completed",   # ← NEW
    "custom_queries_failed": "⚠ Custom queries failed",         # ← NEW
    "sarif_parsing_started": "Parsing results...",
    # ... more events ...
}
```

## Expected Output After Fix

```
✓ Languages detected                     ━━━━━━━━━━━━━━━━━━━ 100% 0:01:09
✓ CodeQL database created                ━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
✓ Security queries completed             ━━━━━━━━━━━━━━━━━━━ 100% 0:00:34
✓ Custom queries completed               ━━━━━━━━━━━━━━━━━━━ 100% 0:01:36  ← Fixed!
✓ Results parsed                         ━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
```

**Improvements:**
- ✅ Checkmark (✓) displayed
- ✅ User-friendly label
- ✅ Consistent with other steps
- ✅ Warning symbol (⚠) for failures

## Events Added

### Custom Queries Events

| Event | Label | Symbol |
|-------|-------|--------|
| `custom_queries_started` | "Running custom queries..." | (spinner) |
| `custom_queries_completed` | "Custom queries completed" | ✓ |
| `custom_queries_failed` | "Custom queries failed" | ⚠ |

### Behavior

**When custom queries exist:**
```
⠋ Running custom queries...              ━━━━━━━━━━━━━━━━━━━  45% 0:00:23
```

**On success:**
```
✓ Custom queries completed               ━━━━━━━━━━━━━━━━━━━ 100% 0:01:36
```

**On failure (graceful):**
```
⚠ Custom queries failed                  ━━━━━━━━━━━━━━━━━━━ 100% 0:00:05
```
(Analysis continues with standard queries)

## Code Changes

**File:** `src/patchsmith/cli/progress.py`

**Lines added:** 121-123

**Change:** Added three new event mappings to the descriptions dictionary

**Impact:**
- No breaking changes
- No API changes
- Pure UI improvement
- Backward compatible

## Testing

The fix can be verified by running:

```bash
# Run analysis on a project with custom queries
patchsmith analyze

# Expected: "✓ Custom queries completed" appears in progress
```

## Related Files

- `src/patchsmith/services/analysis_service.py` - Emits the custom query events
- `src/patchsmith/cli/progress.py` - Maps events to UI labels
- `src/patchsmith/cli/commands/analyze.py` - Uses ProgressTracker

## Benefits

✅ **Consistency**: All progress steps have the same visual style
✅ **Clarity**: Users see exactly what's happening
✅ **Professional**: Polished UI experience
✅ **Informative**: Success/failure states clearly indicated

## Additional Notes

The progress tracker automatically handles:
- Event lifecycle (started → completed)
- Progress bar updates
- Checkmark display on completion
- Warning symbol on failure
- Time tracking

No additional code needed beyond adding the event mappings!
