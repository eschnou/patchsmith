# TypeScript Support Fix

## The Issue

When running `patchsmith finetune`, only 1 query was generated instead of the expected 5:

```
WARNING ql_pack_setup_failed error=Unsupported language for QL pack: typescript
WARNING skipping_query_no_pack language=typescript (x4 queries skipped)
INFO custom_query_generated language=javascript (only 1 query succeeded)
```

## Root Cause

**TypeScript was treated as a separate CodeQL language**, but it isn't!

In CodeQL:
- TypeScript uses the **same standard library** as JavaScript
- TypeScript code is analyzed by the **JavaScript extractor**
- TypeScript queries depend on `codeql/javascript-all`

The vulnerability targeting logic created 5 queries:
- **Queries 1-4**: TypeScript (all skipped because no QL pack)
- **Query 5**: JavaScript (succeeded)

## The Fix

Added TypeScript → JavaScript mapping in QL pack creation:

```python
standard_libs = {
    "python": "codeql/python-all",
    "javascript": "codeql/javascript-all",
    "typescript": "codeql/javascript-all",  # ← TypeScript uses JS pack!
    "java": "codeql/java-all",
    "go": "codeql/go-all",
    "cpp": "codeql/cpp-all",
    "c": "codeql/cpp-all",  # C also uses C++ pack
    "csharp": "codeql/csharp-all",
    "ruby": "codeql/ruby-all",
}
```

## Directory Structure After Fix

```
.patchsmith/
  └── queries/
      ├── typescript/
      │   ├── qlpack.yml                    # depends on codeql/javascript-all
      │   ├── sql_injection.ql              # TypeScript-specific queries
      │   └── xss_dom.ql
      ├── javascript/
      │   ├── qlpack.yml                    # depends on codeql/javascript-all
      │   ├── sql_injection.ql              # JavaScript-specific queries
      │   └── command_injection.ql
      └── python/
          ├── qlpack.yml                    # depends on codeql/python-all
          └── sql_injection_orm.ql
```

## Behavior After Fix

✅ **TypeScript QL pack** created successfully (uses `codeql/javascript-all`)
✅ **TypeScript queries** generate and compile correctly
✅ **Separate directories** for TypeScript and JavaScript queries
✅ **Both use the same CodeQL standard library** (JavaScript)

This is correct because:
- TypeScript and JavaScript may have different vulnerability patterns
- TypeScript has type-specific issues (e.g., "Type assertion bypasses")
- Keeping them separate allows language-specific query customization

## Expected Output After Fix

```
QL pack setup: ✓ typescript, ✓ javascript, ✓ python
Generated 5 queries:
  - typescript: 4 queries
  - javascript: 1 query
```

## Additional Languages Supported

Also added support for:
- **C** → uses `codeql/cpp-all` (C and C++ share the same pack)

## Testing

The fix ensures:
- All detected languages get proper QL packs
- TypeScript queries compile successfully
- No queries are skipped due to missing packs
- Language-specific vulnerabilities are targeted correctly
