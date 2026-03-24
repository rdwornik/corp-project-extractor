# Code Review Report -- Corp Project Extractor (CPE)

**Date:** 2026-03-15
**Branch:** `code-review-2026-03-15`
**Reviewer:** Claude Opus 4.6

---

## Summary

Professional code review of the CPE repository. The codebase is well-structured, mature, and follows good engineering practices. Changes were limited to lint cleanup and documentation improvements -- no functional changes were needed.

## Test Results

- **Before review:** 45 passed, 0 failed
- **After review:** 45 passed, 0 failed
- **Ruff:** All checks passed (clean)

## Changes Made

### 1. Ruff lint + format pass (`4390f01`)

**Lint fixes (14 total, 12 auto-fixed, 2 manual):**
- Removed unused variable `folder_str` in `classifier.py:78`
- Removed unused variable `settings` in `manifest.py:69` (call to `get_settings()` in `scan()` was assigned but never used; other functions still use it)
- 12 auto-fixed issues (import sorting, whitespace, trailing commas, etc.)

**Format:** All 12 source and test files reformatted to ruff standard (304 insertions, 201 deletions -- mostly whitespace/formatting).

### 2. CLAUDE.md restructure (`0bae6ec`)

- Restructured to lead with quick-start, architecture, and key commands
- Added test suite section with counts and fixture location
- Added full 20-rule classification priority table
- Documented test coverage gaps under Known Issues
- Streamlined workflow sections (removed redundant snippets)

### 3. README.md rewrite (`9beea43`)

- Professional structure: features, installation, usage, architecture, pipeline, output, configuration
- Complete CLI reference with all commands and flags
- Architecture table and pipeline diagram
- Related repos section

## Issues Found

### Hardcoding (pre-existing, documented)
| Issue | Location | Severity |
|-------|----------|----------|
| CKE directory path hardcoded | `cke_invoker.py:14` | Medium |
| CKE venv path Windows-only (`Scripts/python.exe`) | `cke_invoker.py:37` | Low |

### Code Quality (fixed)
| Issue | Location | Action |
|-------|----------|--------|
| Unused variable `folder_str` | `classifier.py:78` | Removed |
| Unused variable `settings` in `scan()` | `manifest.py:69` | Removed |
| 12 ruff lint violations | Various | Auto-fixed |
| Inconsistent formatting | All files | Reformatted |

### Test Coverage Gaps (documented, not fixed)
| Module | Coverage | Notes |
|--------|----------|-------|
| `manifest_generator.py` | 32 tests | Well covered |
| `renderer.py` | 13 tests | Well covered |
| `classifier.py` | 0 tests | Priority -- complex rule engine |
| `manifest.py` | 0 tests | Would need filesystem fixtures |
| `extractors.py` | 0 tests | Would need sample files |
| `cli.py` | 0 tests | Click testing with CliRunner |
| `models.py` | 0 tests | Dataclass serialization |
| `config.py` | 0 tests | Config loading + env expansion |
| `cke_invoker.py` | 0 tests | Subprocess mocking |

### Architecture Observations
- **Clean separation of concerns** -- each module has a single responsibility
- **Type safety** -- dataclasses throughout, all functions type-hinted
- **Config-driven** -- YAML + .env expansion, minimal hardcoding
- **Incremental processing** -- manifest merging preserves extraction status
- **Error resilience** -- graceful handling of cloud-only files, encoding issues
- **Process boundary** -- CKE invoked as subprocess, no shared library imports

## Environment

- No stale `requirements.txt` files (pyproject.toml is source of truth)
- `.venv/` properly in `.gitignore`
- All runtime imports resolve correctly
- mypy not installed (could add to dev dependencies)

## Final State

```
REPO: corp-project-extractor
TESTS: 45 passed, 0 failed
RUFF: clean (all checks passed)
COMMITS: 3 (lint, CLAUDE.md, README.md)
FILES CHANGED: 14
```

## Recommendations

1. **Add classifier tests** -- highest priority gap; complex rule engine with 20 rules deserves parametrized tests
2. **Move CKE path to config** -- `cke_invoker.py` hardcodes `C:/Users/1028120/Documents/Scripts/corp-knowledge-extractor`
3. **Add mypy to dev deps** -- code already has good type hints, mypy would catch regressions
4. **Consider `cpe run` pipeline** -- currently uses local `extract`, may want `extract-cke` instead
