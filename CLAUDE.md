# CLAUDE.md — Corp Project Extractor (CPE)

> **Purpose:** Project-specific context for Claude Code sessions + engineering principles.
>
> Last updated: 2026-03-12.

---

## Project Overview

**CPE is an orchestrator, not an extractor.** It scans pre-sales project folders, classifies files, generates manifests, and delegates extraction to CKE (corp-knowledge-extractor) via subprocess.

### Key Commands
```
cpe scan <path>         -- classify files, save _knowledge/manifest.yaml
cpe extract-cke <path>  -- generate CKE manifest, invoke CKE batch
cpe render <path>       -- aggregate CKE results -> project-info.yaml + facts.yaml + index.md
cpe show <path>         -- display manifest table
cpe run <path>          -- full pipeline: scan -> extract -> render
```

### Module Map
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

### Config Files
- `config/default.yaml` -- pipeline settings, junk markers, skip extensions
- `config/clients.yaml` -- client name alias resolution
- `.env` -- paths and secrets (not committed)

### Integration Points
- **CKE** -- invoked via subprocess (`cke_invoker.py`). CKE has its own venv.
- **corp-by-os** -- calls CPE via CLI (e.g., `cpe scan`, `cpe extract-cke`)
- No shared library imports between CPE and CKE -- clean process boundary.

### Classification Priority (abbreviated)
Junk -> Security -> RFP_QA (file) -> RFP_Original (file) -> WIP path -> RFP_Response (file) -> Submission path -> RFP path catch-all -> Strategy/Meeting/Proposal (file) -> Unknown

### Known Issues
- CKE path hardcoded in `cke_invoker.py` (should move to config/env)
- `cpe run` uses local `extract`, not `extract-cke` -- may need updating
- Windows cp1252 encoding: avoid Unicode arrows/special chars in Click help strings

---

## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes — don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests — then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

---

## Task Management

1. **Plan First:** Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan:** Check in before starting implementation
3. **Track Progress:** Mark items complete as you go
4. **Explain Changes:** High-level summary at each step
5. **Document Results:** Add review section to `tasks/todo.md`
6. **Capture Lessons:** Update `tasks/lessons.md` after corrections

---

## Core Principles

- **Simplicity First:** Make every change as simple as possible. Impact minimal code.
- **No Laziness:** Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact:** Changes should only touch what's necessary. Avoid introducing bugs.

---

## Architecture & Code Standards

### Structure
- **Clean architecture** — single-responsibility modules, clear separation of concerns
- **Config over hardcoding** — all paths, URLs, credentials, environment-specific values go in YAML config files (never hardcoded)
- **Dataclasses over dicts** — typed data structures, not loose dictionaries
- **`.env` files** for secrets and dynamic paths — never commit these
- **README.md** in every project root — purpose, setup, usage, architecture overview

### Code Quality
- **Logging, not print** — use Python `logging` module with appropriate levels
- **Comments** — explain *why*, not *what*. Document non-obvious decisions
- **Type hints** everywhere in Python
- **Error handling** — explicit, meaningful error messages. No bare `except:`

### CLI & Output
- **Click** for CLI interfaces
- **Rich** for terminal output (tables, progress bars, panels)

### Testing & Verification
- **pytest** as test framework
- Write tests before marking anything done
- Test edge cases, not just happy paths
- If you can't test it, you can't ship it

### Git Workflow
- **Feature branches** — never commit directly to main
- Meaningful commit messages (imperative mood: "Add X", "Fix Y")
- Small, focused commits — one logical change per commit

---

## Knowledge Management (Obsidian)

- YAML frontmatter on all notes
- Sparse `[[wikilinks]]` in text — max 2-3 per paragraph
- Source/extract separation: source notes are immutable, extracts are regenerable
- `_meta.yaml` for versioning metadata

---

## Communication Style

- **Insight-first** — lead with the "so what", not a description of what you did
- **Bold-first paragraphs** for scanning
- **No corporate filler** — cut fluff words, be direct
- **Critical thinking** — challenge assumptions, flag risks, present tradeoffs
- **ADHD-optimized** — scannable, structured, front-loaded with the important bits

---

## Anti-Patterns (Never Do These)

| Anti-Pattern | Do Instead |
|---|---|
| Hardcoded paths/URLs | YAML config + `.env` |
| `print()` debugging | `logging.debug()` / `logging.info()` |
| Raw dicts for data | Dataclasses with type hints |
| Committing to main | Feature branch -> PR |
| "It works on my machine" | Tests + CI verification |
| Asking "should I fix it?" | Just fix it, show the diff |
| Vague commit messages | "Fix rate limiter edge case in retry logic" |
| Temporary workarounds | Root cause analysis -> proper fix |
| Over-engineering simple tasks | Proportional effort to problem size |
| Losing context mid-task | `tasks/todo.md` + `tasks/lessons.md` |

---

## Quick-Paste Snippets

### Session Start Reminder
```
Before starting: read tasks/lessons.md and tasks/todo.md. Plan mode for anything non-trivial. Feature branch. Tests. Logging. Config in YAML. Go.
```

### Mid-Session Course Correction
```
STOP. You're drifting. Re-read CLAUDE.md core principles: simplicity first, no laziness, minimal impact. Re-plan in plan mode before continuing.
```

### Pre-Commit Checklist
```
Before marking done: tests pass? Logs clean? Diff reviewed? Staff engineer would approve? Config externalized? README updated if needed?
```

---

*This document is a living reference. Update it as patterns evolve.*