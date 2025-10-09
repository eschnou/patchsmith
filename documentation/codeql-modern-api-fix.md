# CodeQL Modern API Fix: Eliminating Deprecated Query Patterns

## The Problem

The CustomQueryGeneratorAgent was generating queries using **deprecated CodeQL APIs**, resulting in compilation warnings:

```
WARNING: module 'PathGraph' has been deprecated
WARNING: type 'Configuration' has been deprecated
WARNING: type 'PathNode' has been deprecated
```

### Example of Deprecated Query Pattern

```ql
import javascript
import semmle.javascript.security.dataflow.SqlInjectionQuery
import DataFlow::PathGraph  // ❌ DEPRECATED

from Configuration cfg, DataFlow::PathNode source, DataFlow::PathNode sink
where cfg.hasFlowPath(source, sink)
select sink.getNode(), source, sink, "..."
```

**Issues:**
- Uses deprecated `DataFlow::PathGraph` import
- Uses deprecated `Configuration` class type
- Uses deprecated `DataFlow::PathNode` type
- Will stop working when CodeQL removes these APIs (planned removal)

## Root Cause

The AI was trained on older CodeQL examples and documentation that used the class-based configuration API. CodeQL migrated to a modern modular API in version 2.13.0 (August 2023), but the AI continued generating old patterns.

## The CodeQL API Migration

### Timeline
- **August 2023**: New modular API introduced (CodeQL 2.13.0)
- **December 2023**: Deprecation warnings started
- **December 2024**: Old API scheduled for removal

### Key API Changes

#### 1. Configuration Pattern

**❌ Old (Deprecated):**
```ql
class MyConfig extends TaintTracking::Configuration {
  MyConfig() { this = "MyConfig" }

  override predicate isSource(DataFlow::Node source) { ... }
  override predicate isSink(DataFlow::Node sink) { ... }
  override predicate isSanitizer(DataFlow::Node node) { ... }
}
```

**✅ New (Modern):**
```ql
module MyConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) { ... }
  predicate isSink(DataFlow::Node sink) { ... }
  predicate isBarrier(DataFlow::Node node) { ... }  // Note: isBarrier, not isSanitizer
}

module MyFlow = TaintTracking::Global<MyConfig>;
```

#### 2. PathGraph Import

**❌ Old:**
```ql
import DataFlow::PathGraph
```

**✅ New:**
```ql
module MyFlow = TaintTracking::Global<MyConfig>;
import MyFlow::PathGraph  // Import from YOUR module
```

#### 3. PathNode Type

**❌ Old:**
```ql
from DataFlow::PathNode source, DataFlow::PathNode sink
```

**✅ New:**
```ql
from MyFlow::PathNode source, MyFlow::PathNode sink
```

#### 4. Flow Predicate

**❌ Old:**
```ql
where cfg.hasFlowPath(source, sink)
```

**✅ New:**
```ql
where MyFlow::flowPath(source, sink)
```

#### 5. Sanitizer → Barrier

**❌ Old:**
```ql
override predicate isSanitizer(DataFlow::Node node) { ... }
```

**✅ New:**
```ql
predicate isBarrier(DataFlow::Node node) { ... }
```

## The Solution

Updated the `CustomQueryGeneratorAgent` system prompt to teach it the modern API patterns.

### Key Changes to System Prompt

1. **Added explicit warning** about deprecated APIs
2. **Provided complete modern API examples** with proper syntax
3. **Created side-by-side comparison** of old vs new patterns
4. **Emphasized modern API usage** as a requirement
5. **Included both patterns**: path-problem and simple queries

### Updated System Prompt Structure

```python
return """You are a CodeQL query writing expert using MODERN CodeQL APIs.

CRITICAL: USE MODERN API (CodeQL 2.13.0+)
The old API using "class Configuration extends TaintTracking::Configuration" is DEPRECATED.

MODERN API PATTERN:
[Complete example showing module-based approach]

KEY DIFFERENCES FROM OLD API:
[Side-by-side comparison of deprecated vs modern]

REQUIREMENTS:
1. Use MODERN API (modules, not classes)
2. No deprecation warnings
3. Compile cleanly
"""
```

## Modern Query Template

Here's the complete modern template the agent now uses:

```ql
/**
 * @name SQL Injection Detection
 * @description Detects SQL injection vulnerabilities
 * @kind path-problem
 * @id custom/sql-injection
 * @problem.severity error
 * @tags security external/cwe/cwe-089
 */

import javascript

module SqlInjectionConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    // User-controlled input
    source instanceof RemoteFlowSource
  }

  predicate isSink(DataFlow::Node sink) {
    // SQL query execution
    sink = any(SqlExecution exec).getSql()
  }

  predicate isBarrier(DataFlow::Node node) {
    // Sanitizers/validators
    node = any(SqlSanitizer s).getOutput()
  }
}

module SqlInjectionFlow = TaintTracking::Global<SqlInjectionConfig>;
import SqlInjectionFlow::PathGraph

from SqlInjectionFlow::PathNode source, SqlInjectionFlow::PathNode sink
where SqlInjectionFlow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "SQL query depends on $@", source.getNode(), "user input"
```

## Benefits of Modern API

✅ **Future-proof**: Won't break when old API is removed
✅ **No warnings**: Compiles cleanly
✅ **Better performance**: Optimized for modern CodeQL
✅ **Clearer structure**: Module-based approach is more maintainable
✅ **Improved flexibility**: Easier to compose and reuse configurations

## Testing the Fix

### Before Fix
```bash
$ codeql query compile query.ql
WARNING: type 'Configuration' has been deprecated
WARNING: module 'PathGraph' has been deprecated
WARNING: type 'PathNode' has been deprecated
Done
```

### After Fix
```bash
$ codeql query compile query.ql
Compiling query plan for query.ql.
Done [1/1] query.ql.
```
✅ **No warnings!**

## Migration for Existing Queries

If you have existing queries generated with the old API:

### Option 1: Regenerate (Recommended)
```bash
# Delete old queries
rm -rf .patchsmith/queries/

# Generate with new API
patchsmith finetune
```

### Option 2: Manual Migration

1. Replace `class Config extends TaintTracking::Configuration` with module pattern
2. Change `import DataFlow::PathGraph` to `import MyFlow::PathGraph`
3. Update `DataFlow::PathNode` to `MyFlow::PathNode`
4. Replace `cfg.hasFlowPath` with `MyFlow::flowPath`
5. Change `isSanitizer` to `isBarrier`
6. Remove `override` keywords
7. Remove constructor: `MyConfig() { this = "MyConfig" }`

## References

- [CodeQL New Dataflow API Announcement](https://github.blog/changelog/2023-08-14-new-dataflow-api-for-writing-custom-codeql-queries/)
- [CodeQL Data Flow Cheat Sheet](https://codeql.github.com/docs/codeql-language-guides/data-flow-cheat-sheet-for-javascript/)
- [Creating Path Queries (Modern API)](https://codeql.github.com/docs/writing-codeql-queries/creating-path-queries/)

## Impact

With this fix:
- ✅ All generated queries use modern API
- ✅ No deprecation warnings
- ✅ Queries will continue working after December 2024
- ✅ Improved code quality and maintainability
- ✅ Better compilation performance
