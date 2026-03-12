# Corp Project Extractor (CPE)

Project-level orchestrator for the corp-by-os ecosystem. Scans pre-sales project folders, classifies files by type/role, generates manifests for CKE extraction, and renders aggregated project knowledge.

## Quick Start

```bash
pip install -e .
cpe --help
```

## CLI Commands

```
cpe scan <project_path>              -- classify all files, save manifest
cpe extract <project_path>           -- scan + extract text locally (PPTX/PDF/DOCX/XLSX)
  --force                            -- re-extract even if hash unchanged
  --skip-junk / --no-skip-junk       -- skip Junk/WIP files (default: on)
cpe extract-cke <project_path>       -- generate manifest, invoke CKE batch
  --resume / --no-resume             -- skip already-completed files (default: on)
  --max-rpm N                        -- rate limit Gemini API (default: 100)
  --dry-run                          -- preview without processing
  --client <name>                    -- override client name
cpe render <project_path>            -- aggregate CKE results into project knowledge
  --copy-to-vault <vault_path>       -- copy index.md to Obsidian vault
cpe show <project_path>              -- display existing manifest (no rescan)
cpe run <project_path>               -- full pipeline: scan -> extract -> render
```

Global options: `--verbose` / `-v`, `--config PATH`

## Architecture

Part of the corp-by-os ecosystem:

- **corp-knowledge-extractor (CKE)** -- extraction engine using Gemini LLM. CPE calls it via `cke process-manifest`.
- **corp-by-os** -- root orchestrator that calls CPE via CLI.

CPE is an **orchestrator** -- it classifies files and generates manifests, then delegates extraction to CKE. The local `extract` command does basic text extraction (PPTX/PDF/DOCX/XLSX); `extract-cke` invokes CKE for LLM-powered extraction.

## Pipeline

```
cpe scan       -> classify files (RFP, Meeting, Strategy, Junk, etc.)
cpe extract-cke -> generate cke_manifest.json -> call `cke process-manifest`
cpe render     -> aggregate extract.json results -> project-info.yaml + facts.yaml + index.md
```

## Output (`_knowledge/` per project)

| File | Purpose |
|------|---------|
| `manifest.yaml` | File inventory with classification and extraction status |
| `cke_manifest.json` | Manifest sent to CKE for batch processing |
| `project-info.yaml` | Project metadata summary (corp-opportunity-manager compatible) |
| `facts.yaml` | Aggregated facts with source attribution |
| `index.md` | Obsidian note with frontmatter and Dataview query |

## Key Modules

| Module | Responsibility |
|--------|---------------|
| `classifier.py` | 20-step priority rules: first match wins (Junk -> Security -> RFP_QA -> ... -> Unknown) |
| `manifest.py` | Scan filesystem, hash files, build/merge/save `manifest.yaml` |
| `manifest_generator.py` | Convert CPE manifest to CKE-compatible `cke_manifest.json` |
| `cke_invoker.py` | Subprocess wrapper to invoke CKE's `process-manifest` |
| `renderer.py` | Aggregate CKE `extract.json` results into project-info, facts, and index |
| `extractors.py` | Local text extraction (PPTX/PDF/DOCX/XLSX/CSV) |
| `models.py` | Dataclasses: Classification, FileEntry, Manifest, ExtractionResult |
| `config.py` | YAML config loader with `${ENV_VAR}` expansion from `.env` |
| `cli.py` | Click CLI with Rich terminal output |

## File Classification Categories

`RFP_Original`, `RFP_Response`, `RFP_QA`, `RFP_WIP`, `Meeting`, `Demo`, `Strategy`, `Commercial`, `Security`, `Proposal`, `Data`, `Junk`, `Unknown`

Each file also gets a `doc_role`: `source_of_truth`, `supporting`, or `obsolete`.

## Configuration

| File | Purpose |
|------|---------|
| `config/default.yaml` | Pipeline config: junk markers, skip extensions, extraction settings |
| `config/clients.yaml` | Client name alias resolution (folder name -> official name) |
| `.env` | Paths and secrets (not committed) |

## Dependencies

**Runtime:** click, rich, pyyaml, python-pptx, pdfplumber, python-docx, openpyxl, python-dotenv

**Dev:** pytest, pytest-cov, ruff

**External:** corp-knowledge-extractor (CKE) installed separately, invoked via subprocess.

## Tests

```bash
pytest
```

45 tests covering classifier, manifest generator, and renderer.
