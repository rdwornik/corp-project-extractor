# CLAUDE.md -- Corp Project Extractor (CPE)

## What this repo does

CPE is an orchestrator for pre-sales project folders. It scans directories, classifies files by type/role using 20-priority rules, generates manifests, delegates extraction to CKE (corp-knowledge-extractor) via subprocess, and renders aggregated project knowledge as YAML + Obsidian markdown.

## Quick start

```bash
pip install -e .          # install in dev mode
cpe --help                # see all commands
pytest                    # run tests (45 tests)
ruff check src/ --fix     # lint
ruff format src/ tests/   # format
```

## Architecture

**CPE is an orchestrator, not an extractor.** It classifies files and generates manifests, then delegates extraction to CKE.

### Module map

| Module | Responsibility |
|--------|---------------|
| `cli.py` | Click CLI + Rich output |
| `classifier.py` | 20-step priority rules (first match wins) |
| `manifest.py` | Scan, hash, build/merge manifest.yaml |
| `manifest_generator.py` | CPE manifest -> CKE cke_manifest.json |
| `cke_invoker.py` | Subprocess call to CKE process-manifest |
| `renderer.py` | Aggregate CKE extract.json -> project-info, facts, index |
| `extractors.py` | Local text extraction (PPTX/PDF/DOCX/XLSX/CSV) |
| `models.py` | Dataclasses: Classification, FileEntry, Manifest, ExtractionResult |
| `config.py` | YAML config + .env expansion |

### Data flow

```
cpe scan       -> classify files -> _knowledge/manifest.yaml
cpe extract-cke -> manifest -> cke_manifest.json -> CKE subprocess -> _cke_output/
cpe render     -> _cke_output/extract.json -> project-info.yaml + facts.yaml + index.md
cpe run        -> scan -> extract -> render (full pipeline)
```

### Integration points

- **CKE** -- invoked via subprocess (`cke_invoker.py`). CKE has its own venv.
- **corp-by-os** -- calls CPE via CLI (e.g., `cpe scan`, `cpe extract-cke`)
- No shared library imports between CPE and CKE -- clean process boundary.

## Dev standards

- Python 3.10+, Windows-first (pathlib, `py -m`)
- `pyproject.toml` as single source of truth for deps and config
- `ruff` for linting + formatting, `pytest` for testing
- Feature branches, never commit directly to main
- Logging not print, dataclasses not dicts, type hints everywhere
- Config in YAML (`config/default.yaml`), secrets in `.env` (not committed)
- Click CLI, Rich output (tables, panels, progress bars)
- Meaningful commit messages (imperative mood: "Add X", "Fix Y")

## Key commands

```
cpe scan <path>              -- classify all files, save manifest
cpe extract <path>           -- scan + extract text locally (PPTX/PDF/DOCX/XLSX)
  --force                    -- re-extract even if hash unchanged
  --skip-junk / --no-skip-junk
cpe extract-cke <path>       -- generate manifest, invoke CKE batch
  --resume / --no-resume     -- skip already-completed files (default: on)
  --max-rpm N                -- rate limit Gemini API (default: 100)
  --dry-run                  -- preview without processing
  --client <name>            -- override client name
cpe render <path>            -- aggregate CKE results into project knowledge
  --copy-to-vault <path>     -- copy index.md to Obsidian vault
cpe show <path>              -- display existing manifest (no rescan)
cpe run <path>               -- full pipeline: scan -> extract -> render
```

Global options: `--verbose` / `-v`, `--config PATH`

## Config files

| File | Purpose |
|------|---------|
| `config/default.yaml` | Pipeline settings: junk markers, skip extensions, extraction params |
| `config/clients.yaml` | Client name alias resolution (folder name -> official name) |
| `.env` | Paths and secrets (not committed) |

## Test suite

```bash
pytest                    # 45 tests, ~0.6s
pytest --tb=long          # full tracebacks
pytest -k test_renderer   # run specific test file
```

**Coverage:** `test_manifest_generator.py` (32 tests), `test_renderer.py` (13 tests).
Test fixtures in `tests/fixtures/`.

## Dependencies

**Runtime:** click, rich, pyyaml, python-pptx, pdfplumber, python-docx, openpyxl, python-dotenv

**Dev:** pytest, pytest-cov, ruff

**External:** corp-knowledge-extractor (CKE) -- installed separately, invoked via subprocess

## Classification priority

```
 1  Junk (temp/lock/obsolete markers)
 2  Security (SOC, ISO, DPA)
 3  RFP_QA filename (Q&A, questionnaire)
 4  RFP_Original filename
 5  WIP path
 6  Submission/Official Response path
 7  RFP_Response filename
 8  Data (CSV, payload, forecast)
 9  Original path within RFP
10  Commercial filename (PS estimator, deal alignment)
11  Implementation Services path
12  Proposal Presentation path
13  Dated/meeting folder (YYYY.MM.DD)
14  Demo folder
15  Transformation/Workshop folder
16  RFP folder catch-all
17  Strategy filename
18  Meeting filename
19  Proposal filename
20  Extension fallbacks / Unknown
```

File-level rules come BEFORE path-based rules. Security wins over Submission path.

## Known issues

- CKE path hardcoded in `cke_invoker.py` (should move to config/env)
- `cpe run` uses local `extract`, not `extract-cke` -- may need updating
- Windows cp1252: avoid Unicode arrows/special chars in Click help strings
- Emoji status indicators render as `?` in cmd.exe (works in Windows Terminal/VSCode)
- No test coverage for: `cli.py`, `classifier.py`, `extractors.py`, `manifest.py`, `cke_invoker.py`, `config.py`, `models.py`

---

## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction: update `tasks/lessons.md` with the pattern
- Write rules that prevent the same mistake
- Review lessons at session start

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Run tests, check logs, demonstrate correctness
- Ask: "Would a staff engineer approve this?"

### 5. Autonomous Bug Fixing
- Just fix it. No hand-holding. Point at logs, errors, failing tests -- then resolve.

## Task Management

1. Write plan to `tasks/todo.md` with checkable items
2. Check in before starting implementation
3. Mark items complete as you go
4. Update `tasks/lessons.md` after corrections

## Core Principles

- **Simplicity First:** Minimal code, minimal impact
- **No Laziness:** Root causes, not temporary fixes
- **Minimal Impact:** Only touch what's necessary

## Anti-Patterns

| Don't | Do Instead |
|---|---|
| Hardcoded paths/URLs | YAML config + `.env` |
| `print()` debugging | `logging.debug()` / `logging.info()` |
| Raw dicts for data | Dataclasses with type hints |
| Committing to main | Feature branch -> PR |
| Asking "should I fix it?" | Just fix it, show the diff |
| Vague commit messages | "Fix rate limiter edge case in retry logic" |
| Over-engineering | Proportional effort to problem size |
