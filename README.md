# Corp Project Extractor (CPE)

Project-level orchestrator for the corp-by-os pre-sales ecosystem. CPE scans project folders, classifies files by type and role using 20-priority rules, generates manifests for CKE (corp-knowledge-extractor) batch processing, and renders aggregated project knowledge as structured YAML and Obsidian-compatible markdown.

## Features

- **File classification** -- 20-priority rule engine (Junk, Security, RFP, Meeting, Strategy, etc.)
- **Manifest generation** -- incremental hash-based tracking with extraction status
- **CKE integration** -- generates CKE-compatible manifests and invokes batch extraction via subprocess
- **Knowledge rendering** -- aggregates CKE results into project-info.yaml, facts.yaml, and index.md
- **Local extraction** -- PPTX, PDF, DOCX, XLSX, CSV text extraction with metadata
- **Client resolution** -- folder name to official client name via alias config
- **Rich CLI output** -- styled tables, panels, and progress indicators

## Installation

```bash
pip install -e .
```

Requires Python 3.10+. External dependency: [corp-knowledge-extractor](https://github.com/anthropics/corp-knowledge-extractor) (CKE) installed separately.

## Usage

```bash
# Classify files and save manifest
cpe scan <project_path>

# Generate CKE manifest and invoke batch extraction
cpe extract-cke <project_path> --client "Acme Corp" --max-rpm 100

# Preview without processing
cpe extract-cke <project_path> --dry-run

# Aggregate CKE results into project knowledge
cpe render <project_path>

# Copy rendered index to Obsidian vault
cpe render <project_path> --copy-to-vault <vault_path>

# Display existing manifest
cpe show <project_path>

# Full pipeline: scan -> extract -> render
cpe run <project_path>

# Local text extraction (without CKE)
cpe extract <project_path> --force
```

Global options: `--verbose` / `-v`, `--config PATH`

## Architecture

CPE is an **orchestrator** -- it classifies files and generates manifests, then delegates extraction to CKE via subprocess. No shared library imports between CPE and CKE.

| Module | Responsibility |
|--------|---------------|
| `cli.py` | Click CLI with Rich terminal output |
| `classifier.py` | 20-step priority classification (first match wins) |
| `manifest.py` | Scan filesystem, hash files, build/merge manifest |
| `manifest_generator.py` | Convert CPE manifest to CKE-compatible JSON |
| `cke_invoker.py` | Subprocess wrapper for CKE batch processing |
| `renderer.py` | Aggregate CKE extract.json into project knowledge |
| `extractors.py` | Local text extraction (PPTX/PDF/DOCX/XLSX/CSV) |
| `models.py` | Typed dataclasses for all data structures |
| `config.py` | YAML config loader with .env variable expansion |

### Pipeline

```
cpe scan       -> classify files -> _knowledge/manifest.yaml
cpe extract-cke -> cke_manifest.json -> CKE subprocess -> _cke_output/
cpe render     -> _cke_output/extract.json -> project-info.yaml + facts.yaml + index.md
```

### Output (`_knowledge/` per project)

| File | Purpose |
|------|---------|
| `manifest.yaml` | File inventory with classification and extraction status |
| `cke_manifest.json` | Manifest sent to CKE for batch processing |
| `project-info.yaml` | Project metadata (corp-opportunity-manager compatible) |
| `facts.yaml` | Aggregated facts with source attribution |
| `index.md` | Obsidian note with YAML frontmatter and Dataview query |

## Configuration

| File | Purpose |
|------|---------|
| `config/default.yaml` | Pipeline settings, junk markers, skip extensions |
| `config/clients.yaml` | Client name alias resolution |
| `.env` | Paths and secrets (not committed) |

## Testing

```bash
pytest
```

45 tests covering manifest generation and rendering. Test fixtures in `tests/fixtures/`.

## Dependencies

**Runtime:** click, rich, pyyaml, python-pptx, pdfplumber, python-docx, openpyxl, python-dotenv

**Dev:** pytest, pytest-cov, ruff

## Related repos

- **corp-by-os** -- root orchestrator that calls CPE via CLI
- **corp-knowledge-extractor (CKE)** -- extraction engine using Gemini LLM

## License

Internal use only -- Blue Yonder Pre-Sales Engineering
