# Task: Bootstrap & Implement corp-project-extractor

## Overview

New repo in the Corporate OS agent ecosystem. Scans pre-sales project folders, classifies files, extracts text, and builds structured knowledge sheets per client opportunity.

**Decision source:** AI Council debate (3 models, 2 rounds) chose "Hybrid local extraction + manifest-driven deltas + section-scoped LLM synthesis + rendered Obsidian sheet." Full debate transcript available on request.

**Pilot:** Lenzing_Planning (~80 files, 559MB) at:
```
%USERPROFILE%\OneDrive - Blue Yonder\MyWork\10_Projects\Lenzing_Planning
```

**Related projects (same ecosystem, separate repos):**
- `corporate-os` — root orchestrator agent (will call this tool via CLI)
- `corporate-pdf-toolkit` — PDF→MD extraction + anonymization via local Ollama
- `ai-council` — multi-model architectural decision tool

---

## Phase 0: Project Setup

### 0.1 Repository Init
```powershell
cd C:\Users\1028120\Documents\Scripts
mkdir corp-project-extractor
cd corp-project-extractor
git init
git checkout -b feature/bootstrap
```

### 0.2 Target Directory Structure
```
corp-project-extractor/
├── CLAUDE.md                        # Engineering principles (provided, copy to root)
├── README.md                        # Comprehensive project docs
├── pyproject.toml                   # Package config, deps, entry points
├── .env.example                     # Template for environment-specific paths
├── .gitignore                       # Python + venv + .env exclusions
│
├── src/
│   └── corp_project_extractor/      # Python package (underscores per PEP 8)
│       ├── __init__.py
│       ├── cli.py                   # Click CLI, entry point "cpe"
│       ├── models.py                # All dataclasses (Classification, FileEntry, Manifest, ExtractionResult)
│       ├── config.py                # YAML config loader + Settings dataclass
│       ├── classifier.py            # Rules-first file classification
│       ├── extractors.py            # Per-filetype text extraction (PPTX, PDF, DOCX, XLSX, CSV)
│       ├── manifest.py              # Scan, hash, build/update manifest
│       └── renderer.py              # facts.yaml → knowledge-sheet.md (pure template, no LLM)
│
├── config/
│   └── default.yaml                 # Default pipeline configuration
│
├── schemas/
│   ├── facts_template.yaml          # Empty schema for per-project facts.yaml (provided)
│   └── tag_registry.yaml            # Controlled vocabulary for normalization (provided)
│
├── tests/
│   ├── conftest.py                  # Shared fixtures (temp dirs, sample files)
│   ├── fixtures/                    # Minimal test files (.pptx, .pdf, .docx, .xlsx)
│   ├── test_classifier.py           # Classification rules + edge cases
│   ├── test_extractors.py           # Extraction per filetype + error handling
│   ├── test_manifest.py             # Scan, hash, incremental detection
│   └── test_renderer.py             # facts.yaml → knowledge-sheet.md roundtrip
│
└── tasks/
    ├── todo.md                      # This file
    └── lessons.md                   # Post-correction learnings
```

### 0.3 pyproject.toml
```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "corp-project-extractor"
version = "0.1.0"
description = "Scan, classify, extract and structure knowledge from pre-sales project folders"
requires-python = ">=3.10"
dependencies = [
    "click>=8.0",
    "rich>=13.0",
    "pyyaml>=6.0",
    "python-pptx>=0.6.21",
    "pdfplumber>=0.10",
    "python-docx>=1.0",
    "openpyxl>=3.1",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov",
    "ruff",
]

[project.scripts]
cpe = "corp_project_extractor.cli:cli"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 120
target-version = "py310"
```

### 0.4 Virtual Environment
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

### 0.5 .env.example
```bash
# Pre-sales project folders (OneDrive-synced)
PROJECTS_ROOT=C:\Users\1028120\OneDrive - Blue Yonder\MyWork\10_Projects
ARCHIVE_ROOT=C:\Users\1028120\OneDrive - Blue Yonder\MyWork\80_Archive

# Optional: path to corporate-pdf-toolkit for enhanced PDF extraction
PDF_TOOLKIT_PATH=C:\Users\1028120\Documents\Scripts\corporate-pdf-toolkit
```

### 0.6 .gitignore
```
.venv/
__pycache__/
*.pyc
*.pyo
.env
*.egg-info/
dist/
build/
.pytest_cache/
.ruff_cache/
*.swp
*~
```

### 0.7 Git Workflow
- `main` — stable, tested code only
- `feature/bootstrap` — initial project setup + all Phase 0
- `feature/classifier` — Phase 1 (models) + Phase 2 (classifier) + tests
- `feature/extractors` — Phase 3 (extractors) + tests
- `feature/pipeline` — Phase 4 (manifest) + Phase 5 (CLI) + Phase 6 (renderer) + Phase 7 (config)
- Merge to main after each feature branch passes tests
- Commit messages: imperative mood ("Add classifier module", "Fix XLSX questionnaire detection")

---

## Phase 1: Data Models (`src/corp_project_extractor/models.py`)

All data structures as frozen/typed dataclasses. No raw dicts anywhere.

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import datetime
import yaml


@dataclass
class Classification:
    """Result of classifying a single file."""
    category: str               # RFP_Original, Meeting, Strategy, Junk, etc.
    doc_role: str               # source_of_truth | supporting | obsolete
    confidence: float           # 0.0 - 1.0
    reason: str                 # Human-readable explanation
    is_junk: bool = False


@dataclass
class FileEntry:
    """Single file in the project manifest."""
    rel_path: str               # Relative to project root
    filename: str
    extension: str              # Lowercase with dot: ".pptx"
    size_kb: int
    modified: str               # ISO format timestamp
    sha256: str                 # Short hash (first 16 hex chars)
    category: str
    doc_role: str
    confidence: float
    reason: str
    is_junk: bool
    extracted: bool = False
    extracted_path: Optional[str] = None
    word_count: int = 0
    extraction_error: Optional[str] = None


@dataclass
class Manifest:
    """Project-level manifest tracking all files and their status."""
    project_id: str
    project_path: str
    created_at: str
    last_scanned: str
    schema_version: str = "1.0"
    files: list[FileEntry] = field(default_factory=list)

    def to_yaml(self) -> str:
        """Serialize manifest to YAML string."""
        ...

    @classmethod
    def from_yaml(cls, path: Path) -> "Manifest":
        """Deserialize manifest from YAML file."""
        ...

    def get_new_or_changed(self, other: "Manifest") -> list[FileEntry]:
        """Compare two manifests, return files that are new or have changed hash."""
        ...


@dataclass
class ExtractionResult:
    """Result of extracting text from a single file."""
    success: bool
    output_path: Optional[Path]
    word_count: int
    error: Optional[str] = None
```

---

## Phase 2: File Classifier (`src/corp_project_extractor/classifier.py`)

Rules-first classification. Checked in priority order — first match wins.

### Category Table

| Priority | Category | doc_role | Matched by |
|---|---|---|---|
| 1 | Junk | obsolete | Filename contains "DO NOT USE", "OLD!!", "~$", "Thumbs.db", ".DS_Store", "backup", "template" |
| 2 | Security | supporting | Filename contains "SOC 1", "SOC 2", "SOC2", "ISO 27", "Security Whitepaper", "Cloud Services Standards", "DPA" |
| 3 | RFP_Original | source_of_truth | Path contains "Original" (not "Original Files" under WIP); filename matches "Global.*RFP", "BRC_RfP", "RFP Executive Summary" |
| 4 | RFP_Response | source_of_truth | Path contains "Submission", "Official Response"; filename matches "Blue.?Yonder.?Response", "RFP Response.*Blue Yonder" |
| 5 | RFP_WIP | supporting/obsolete | Path contains "WIP"; or filename contains "Revised", "draft", "old" |
| 6 | RFP_QA | source_of_truth | Filename matches "Q&A", "Q.and.A", "Questions", "Offer Questions" |
| 7 | Commercial | source_of_truth | Filename matches "PSEstimator", "Effort_Estimation", "Deal.?Alignment", "T&M", "FIXED.?FEE", "Commercials" |
| 8 | Proposal | source_of_truth | Path contains "Proposal Presentation"; filename matches "Proposal.?Presentation" |
| 9 | Meeting | source_of_truth | Path matches date pattern `\d{4}\.\d{2}\.\d{2}`; filename matches "meeting", "Working Session", "Prep Meeting" |
| 10 | Demo | source_of_truth | Path or filename contains "demo" (case-insensitive) |
| 11 | Strategy | source_of_truth | Filename matches "Strategy", "Roadmap", "Transformation", "Briefing.?Book" |
| 12 | Data | supporting | CSV files; filename matches "Data for Forecast", "payload", "sample", "Forecast.?Exercise" |
| 13 | Presentation | supporting | Fallback for unmatched .pptx |
| 14 | Document | supporting | Fallback for unmatched .pdf/.docx |
| 15 | Spreadsheet | supporting | Fallback for unmatched .xlsx |
| 16 | Unknown | supporting | Nothing matched |

### Rule Structure
Each rule is a dict with optional matchers — all present matchers must match:
- `path_contains_any: list[str]` — any substring in relative path (case-insensitive)
- `no_path_contains: list[str]` — exclusion filter
- `filename_contains_any: list[str]` — any substring in filename (case-insensitive)
- `filename_regex: str` — regex pattern on filename
- `path_regex: str` — regex pattern on relative path
- `extensions: list[str]` — file extension filter (lowercase with dot)

### Edge Cases (Lenzing-specific, must handle correctly)
| File | Expected | Why tricky |
|---|---|---|
| `Global IBP_SIOP_RFP Document.docx` in `Original/` | RFP_Original | Could match generic "Document" fallback |
| `Global IBP_SIOP_RFP Document.pdf` in `Original/` | RFP_Original | Same doc, different extension |
| `RFP Executive Summary.docx` in `Original/` | RFP_Original | Client's summary, NOT our response |
| `Blue_Yonder_Executive_Summary_Lenzing_RFP.pdf` in `Submission/` | RFP_Response | Our summary, not client's |
| `Q&A for Demand Planning-S&OP Tool.xlsx` in `Original/` | RFP_QA | In Original folder but Q&A takes priority |
| `Q&A...Published v2.xlsx` in `RFP/` root | RFP_QA | Not in any subfolder |
| `Lenzing_DPA_SIOP_Template.pdf` | Security | DPA = Data Processing Agreement |
| `SOC 2 Report.pdf` in `Submission/` | Security | In Submission folder but Security takes priority |
| WIP files with "NOT USE", "OLD!!" | Junk | Highest priority rule |
| `Lenzing ppt template.pptx` | Junk | Template = no content value |
| `.png` files | skip | Not text-extractable |
| `Stat Fcst Exercise Assessment BY.xlsx` | Data | Assessment/exercise data |
| `General Reference Architecture.pdf` in `Submission/` | Security | Architecture doc bundled with security supporting docs |

### Tests (test_classifier.py)
- One test per category with real Lenzing filenames
- Test priority ordering (Security wins over RFP_Response for SOC files in Submission)
- Test junk detection
- Test fallback behavior for unmatched files
- Test case insensitivity

---

## Phase 3: Text Extractors (`src/corp_project_extractor/extractors.py`)

Each extractor produces `_extracted/<safe_filename>.md` with YAML provenance header:

```yaml
---
source: "Lenzing & BY 24th of July.pptx"
source_hash: "a1b2c3d4e5f6g7h8"
category: "Meeting"
doc_role: "source_of_truth"
extracted_at: "2026-02-24T14:30:00"
word_count: 1234
---
```

### PPTX Extractor
- Library: `python-pptx`
- Output format:
  ```markdown
  # Lenzing & BY 24th of July
  
  ## Slide 1: Discovery Agenda
  - Introduction and objectives
  - Current state assessment
  - Blue Yonder capabilities overview
  
  > **Notes:** Focus on their pain with manual S&OP process
  
  ## Slide 2: Current Challenges
  ...
  ```
- Include slide numbers (for provenance references in facts)
- Include speaker notes (often contain the real insights)
- Preserve bullet indentation levels
- Skip empty slides (no text, no notes)

### PDF Extractor
- Library: `pdfplumber`
- Output format:
  ```markdown
  # RFP Response Lenzing - Blue Yonder
  
  ## Page 1
  
  Full text content of page...
  
  ## Page 2
  ...
  ```
- Enhancement: if `corporate-pdf-toolkit/pdf2md.py` is available (check PDF_TOOLKIT_PATH env var), use it instead — it has better TOC handling and chapter selection
- Skip pages with no extractable text

### DOCX Extractor
- Library: `python-docx`
- Preserve heading hierarchy: Heading 1 → `##`, Heading 2 → `###`, Heading 3 → `####`
- Lists as markdown bullets with indentation
- Skip empty paragraphs
- Handle tables: convert to markdown tables

### XLSX Extractor — Two Modes

**Questionnaire mode** (for Q&A, Requirements, Commercials sheets):
- Triggered when filename matches any of: "Q&A", "Questionnaire", "Requirements", "Business_Requirements", "Service and Technical", "Commercials", "Forecast"
- Full row extraction as markdown table (up to 500 rows safety limit)
- Truncate cell content at 200 chars to prevent bloat
- All sheets extracted

**Data mode** (everything else):
- Per sheet: name, column headers, row count
- Sample: first 10 rows as markdown table
- Truncate cells at 100 chars
- Note: `*... N more rows*` at end

### CSV Extractor
- Headers + first 10 sample rows as markdown table
- Stats: total rows, total columns

### Skip List
Do not attempt extraction on:
- `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.svg` — images
- `.mp4`, `.mov`, `.avi`, `.mkv` — video
- `.zip`, `.rar`, `.7z` — archives
- `.exe`, `.msi`, `.dll` — binaries
- Files > 100MB — flag in manifest as `extraction_error: "File too large"`

### Error Handling
- Every extractor wraps in try/except
- Returns `ExtractionResult(success=False, error="descriptive message")`
- Never crash the pipeline on one bad file
- Log at WARNING level with full file path
- Cloud-only files (OneDrive not synced): catch OSError, log "File not available locally (cloud-only?)"

### Tests (test_extractors.py)
- Create minimal fixture files in `tests/fixtures/` (1-2 slides, 1 page, 3 rows)
- Test provenance header generation (correct source, hash, category)
- Test XLSX questionnaire vs data mode selection
- Test error handling: corrupt file, missing file, oversized file
- Test empty file handling (no crash)

---

## Phase 4: Manifest Builder (`src/corp_project_extractor/manifest.py`)

### Scan Logic
1. Walk project folder recursively with `Path.rglob("*")`
2. Skip directories: `_knowledge`, `_extracted`, `.git`, `__pycache__`, `node_modules`, `.venv`
3. For each file:
   a. Compute short SHA256 (first 16 hex chars) — skip files >100MB (set hash to `"skipped_too_large"`)
   b. Get modified time as ISO string
   c. Classify via `classifier.classify_file(filepath, project_root)`
   d. Build `FileEntry` dataclass
4. Wrap in `Manifest` dataclass
5. Save to `<project>/_knowledge/manifest.yaml`

### Incremental Logic (for re-runs)
- If `_knowledge/manifest.yaml` exists, load previous manifest
- Compare by file path + sha256 hash:
  - **New files**: path not in previous manifest → classify + extract
  - **Changed files**: same path, different hash → re-classify + re-extract
  - **Deleted files**: path in previous but not in current → mark as removed
  - **Unchanged files**: same path + same hash → skip, keep previous classification + extraction status
- Log summary: "3 new, 1 changed, 0 deleted, 76 unchanged"

### Output Directories
- Create `<project>/_knowledge/` if not exists
- Create `<project>/_extracted/` if not exists
- Never overwrite `<project>/_knowledge/notes.md` (human-only)
- If `notes.md` doesn't exist, create with header: `# Notes — {project_name}\n\nAdd your observations here. This file is never touched by the pipeline.\n`

### Tests (test_manifest.py)
- Test scan produces correct file count on a temp directory with known files
- Test YAML serialization + deserialization roundtrip (`to_yaml` → `from_yaml`)
- Test incremental detection: mock adding/changing/removing files between scans
- Test skip logic for `_knowledge`, `_extracted` directories
- Test hash computation consistency

---

## Phase 5: CLI (`src/corp_project_extractor/cli.py`)

Click-based CLI. Installed entry point: `cpe`

### Commands

```
cpe scan <project_path>       Scan + classify all files. Save manifest. Show Rich results table.
cpe extract <project_path>    Scan + classify + extract text from all non-junk files. Save manifest + _extracted/*.md
cpe render <project_path>     Read _knowledge/facts.yaml → generate _knowledge/knowledge-sheet.md
cpe run <project_path>        Full pipeline: scan + extract + render (synthesis is separate LLM step)
cpe show <project_path>       Display existing manifest as Rich table (no rescan)
```

### Rich Output for `scan` and `extract`

**Summary Panel:**
```
╭─── Lenzing_Planning — 80 files ────────────────────╮
│ 🟢 RFP_Original:  10 files    8 extracted   12,340 words │
│ 🟢 RFP_Response:   8 files    8 extracted   18,200 words │
│ 🟡 RFP_WIP:        6 files    — skipped —                │
│ 🟢 RFP_QA:         5 files    5 extracted    8,100 words │
│ 🟢 Meeting:        6 files    6 extracted   15,600 words │
│ 🟢 Demo:           1 file     1 extracted    3,200 words │
│ 🟢 Strategy:       5 files    5 extracted    9,800 words │
│ 🟢 Commercial:     8 files    8 extracted    4,500 words │
│ 🔵 Security:       8 files    — supporting —              │
│ 🟢 Proposal:       1 file     1 extracted    5,100 words │
│ 🟢 Data:           5 files    5 extracted    2,300 words │
│ 🔴 Junk:           4 files    — skipped —                │
│ ⚪ Other:          13 files    — fallback —               │
╰───────────────────────────────────────────────────────────╯
```

**File Table:**
```
Category        │ Role            │ Ext   │    KB │ Words │ Filename                              │ Status
────────────────┼─────────────────┼───────┼───────┼───────┼───────────────────────────────────────┼────────
RFP_Original    │ source_of_truth │ .docx │ 2,200 │ 8,400 │ Global IBP_SIOP_RFP Document.docx    │ ✅
RFP_Original    │ source_of_truth │ .xlsx │   180 │ 1,200 │ BRC_RfP SIOP_Business Requirements…  │ ✅
Meeting         │ source_of_truth │ .pptx │72,000 │ 3,100 │ Lenzing & BY 24th of July.pptx       │ ✅
Junk            │ obsolete        │ .xlsx │   340 │     — │ DO NOT USE!! old requirements.xlsx    │ 🔴 JUNK
Security        │ supporting      │ .pdf  │ 1,800 │     — │ SOC 2 Report.pdf                     │ — skip
```

### Color Coding
| Category | Color |
|---|---|
| RFP_Original | green |
| RFP_Response | cyan |
| RFP_WIP | yellow |
| RFP_QA | blue |
| Meeting | magenta |
| Demo | bright_magenta |
| Strategy | bright_yellow |
| Commercial | bright_green |
| Security | dim |
| Proposal | bright_cyan |
| Data | bright_blue |
| Junk | red |

### Global Options
- `--verbose` / `-v` — show debug logging
- `--config <path>` — override config file path

---

## Phase 6: Knowledge Sheet Renderer (`src/corp_project_extractor/renderer.py`)

Pure template step. No LLM. Reads `_knowledge/facts.yaml` → writes `_knowledge/knowledge-sheet.md`.

### YAML Frontmatter (for Obsidian search + cross-project queries)
```yaml
---
project_id: lenzing-planning
client: Lenzing AG
stage: rfp
industry: manufacturing
region: EMEA
by_solution: [DSP, IBP]
integrations: [SAP S/4HANA]
last_updated: "2026-02-24"
sources_count: 80
generated: true
---
```

### Body Sections (fixed headings — predictable for updates)
1. **Overview** — client problem, proposed outcome, BY solutions, engagement type
2. **Timeline** — key dates, events in chronological order
3. **Key Requirements** — with priority icons: 🔴 must_have, 🟡 nice_to_have, ⚪ unclear. Each with source reference.
4. **Integrations & Constraints** — system name, type (ERP/CRM/BI), direction, notes
5. **Competitors** — name, known strengths, known weaknesses
6. **Commercial** — pricing model, deal value, contract term, key assumptions
7. **Security & Compliance** — questions client asked, certifications we provided, data residency requirements
8. **Risks & Open Questions** — probability/impact rating, mitigation if known
9. **Decision Log** — chronological, with rationale and source
10. **Team** — BY team members + roles, client contacts + roles
11. **Key Files** — top files with category and why they matter

### Rules
- `knowledge-sheet.md` is ALWAYS fully regenerated from `facts.yaml` — never hand-edit
- `notes.md` is NEVER touched by the pipeline — human-only annotations
- Auto-generated header: `> **Auto-generated** from project files on {date}. Do not edit — use notes.md for annotations.`
- Empty sections are omitted (no empty "## Competitors" with nothing under it)

### Tests (test_renderer.py)
- Create a sample facts.yaml, render, verify output has correct frontmatter and section headers
- Test empty sections are omitted
- Test special characters in client names
- Test YAML frontmatter is valid YAML

---

## Phase 7: Configuration (`src/corp_project_extractor/config.py` + `config/default.yaml`)

### config/default.yaml
```yaml
# corp-project-extractor pipeline configuration

paths:
  projects_root: "${PROJECTS_ROOT}"       # from .env
  archive_root: "${ARCHIVE_ROOT}"         # from .env
  pdf_toolkit_path: "${PDF_TOOLKIT_PATH}" # optional

classification:
  junk_markers:
    - "DO NOT USE"
    - "OLD!!"
    - "~$"
    - "Thumbs.db"
    - ".DS_Store"
    - "backup"
    - "template"
  skip_extensions:
    - ".png"
    - ".jpg"
    - ".jpeg"
    - ".gif"
    - ".bmp"
    - ".svg"
    - ".mp4"
    - ".mov"
    - ".avi"
    - ".mkv"
    - ".zip"
    - ".rar"
    - ".7z"
    - ".exe"
    - ".msi"
    - ".dll"
  max_file_size_mb: 100

extraction:
  pptx:
    include_notes: true
    include_slide_numbers: true
  xlsx:
    questionnaire_markers:
      - "Q&A"
      - "Questionnaire"
      - "Requirements"
      - "Business_Requirements"
      - "Service and Technical"
      - "Commercials"
      - "Forecast"
    data_mode_max_rows: 10
    questionnaire_max_rows: 500
    cell_truncate_chars: 200

output:
  knowledge_dir: "_knowledge"
  extracted_dir: "_extracted"
```

### config.py
- Load YAML config from `config/default.yaml`
- Expand `${ENV_VAR}` references from `.env` (via `python-dotenv`)
- Provide typed `Settings` dataclass with all config values
- Allow override via `--config` CLI flag

---

## Implementation Checklist

### Phase 0: Project Setup
- [ ] Create repo, `git init`, `feature/bootstrap` branch
- [ ] Write `pyproject.toml`
- [ ] Create `.env.example`, `.gitignore`
- [ ] Set up `python -m venv .venv` + `pip install -e ".[dev]"`
- [ ] Create directory structure (`src/`, `tests/`, `config/`, `schemas/`, `tasks/`)
- [ ] Copy provided `schemas/facts_template.yaml` and `schemas/tag_registry.yaml`
- [ ] Copy CLAUDE.md to root
- [ ] Initial commit: "Bootstrap project structure"
- [ ] Merge `feature/bootstrap` → main

### Phase 1-2: Models + Classifier
- [ ] Branch: `feature/classifier`
- [ ] Implement `models.py` — all dataclasses
- [ ] Implement `classifier.py` — rules + classify_file()
- [ ] Write `test_classifier.py` — all categories + edge cases
- [ ] Run tests, verify all pass
- [ ] Commit: "Add data models and file classifier"
- [ ] Merge → main

### Phase 3: Extractors
- [ ] Branch: `feature/extractors`
- [ ] Implement `extractors.py` — all five extractors + dispatcher
- [ ] Create `tests/fixtures/` with minimal sample files
- [ ] Write `test_extractors.py` — per-type + error handling
- [ ] Run tests, verify all pass
- [ ] Commit: "Add text extractors for PPTX/PDF/DOCX/XLSX/CSV"
- [ ] Merge → main

### Phase 4-7: Pipeline
- [ ] Branch: `feature/pipeline`
- [ ] Implement `config.py` + `config/default.yaml`
- [ ] Implement `manifest.py` — scan + hash + incremental
- [ ] Implement `renderer.py` — facts.yaml → knowledge-sheet.md
- [ ] Implement `cli.py` — all commands with Rich output
- [ ] Write remaining tests
- [ ] Run full test suite
- [ ] Commit: "Add manifest builder, renderer, CLI, and config"
- [ ] Merge → main

### Pilot: Lenzing
- [ ] Run `cpe scan` on Lenzing_Planning — verify all 80 files classified correctly
- [ ] Review classifications — fix any misses in rules
- [ ] Run `cpe extract` on Lenzing — verify extracted text quality
- [ ] Manually synthesize `facts.yaml` (user reads extracted text + LLM assistance)
- [ ] Run `cpe render` on Lenzing — verify knowledge-sheet.md output
- [ ] Tag: `v0.1.0`

---

## Per-Project Output Structure (what `cpe extract` creates inside a project folder)

```
Lenzing_Planning/
├── ... (existing project files, untouched) ...
├── _knowledge/
│   ├── manifest.yaml              # File inventory with hashes and classifications
│   ├── facts.yaml                 # Structured knowledge (GENERATED by LLM synthesis step)
│   ├── knowledge-sheet.md         # Rendered from facts.yaml (GENERATED, never hand-edit)
│   └── notes.md                   # Human annotations (NEVER touched by pipeline)
└── _extracted/
    ├── Briefing_Book_Lenzing_April_2025.docx.md
    ├── Global_IBP_SIOP_RFP_Document.docx.md
    ├── Lenzing_&_BY_24th_of_July.pptx.md
    ├── BRC_RfP_SIOP_Business_Requirements.xlsx.md
    ├── Q&A_for_Demand_Planning-S&OP_Tool.xlsx.md
    ├── RFP_Response_Lenzing_-_Blue_Yonder.pdf.md
    └── ... (one .md per extracted source file)
```

---

## Lenzing File Tree with Expected Classifications

```
Lenzing_Planning/
├── Lenzing Platform Use Case.docx                    → Document (supporting)
├── Lenzing_Platform_UseCase.pptx                     → Presentation (supporting)
├── Lenzing_UseCase_Presentation.pptx                 → Presentation (supporting)
├── Lenzing_payload.csv                               → Data (supporting)
├── payload_Lenzing2.csv                              → Data (supporting)
│
└── _Lenzing 2023 - 2025 Oppty/
    ├── Briefing Book_Lenzing_April 2025.docx         → Strategy (source_of_truth)
    ├── Lenzing AG - IBP Presentation.pdf             → Document (supporting)
    ├── Lenzing Roadmap.pptx                          → Strategy (source_of_truth)
    ├── Lenzing ppt template.pptx                     → Junk (template, no content)
    │
    ├── 2025.07.24 - meeting/
    │   └── Lenzing & BY 24th of July.pptx            → Meeting (source_of_truth)
    │
    ├── 2025.08.08 - meeting tech QA.../
    │   ├── ...tech QA and follow up.pdf              → Meeting (source_of_truth)
    │   └── ...tech QA and follow up.pptx             → Meeting (source_of_truth)
    │
    ├── 2025.08.28 - Prep Meeting/
    │   ├── ...Working Session.pptx                   → Meeting (source_of_truth)
    │   └── Meeting notes 21st Aug.docx               → Meeting (source_of_truth)
    │
    ├── 2025.09.24 demo/
    │   └── Lenzing & BY - 24th Sept.pptx             → Demo (source_of_truth)
    │
    ├── Transformation Journey Workshop 15-Oct-2025/
    │   ├── Agenda proposal.docx                      → Strategy (supporting)
    │   └── Transformation Journey...v1.pptx          → Strategy (source_of_truth)
    │
    └── RFP/
        ├── Strategy Lenzing.pptx                     → Strategy (source_of_truth)
        ├── Lenzing RFP Presentation...old.pptx       → RFP_WIP (obsolete)
        ├── Q&A...Published v2.xlsx                   → RFP_QA (source_of_truth)
        ├── Q&A...Published.xlsx                      → RFP_QA (supporting)
        │
        ├── Original/
        │   ├── Global IBP_SIOP_RFP Document.docx     → RFP_Original (source_of_truth)
        │   ├── Global IBP_SIOP_RFP Document.pdf      → RFP_Original (source_of_truth)
        │   ├── BRC_RfP SIOP_Business Requirements.xlsx → RFP_Original (source_of_truth)
        │   ├── BRC_RfP SIOP_Commercials.xlsx         → RFP_Original (source_of_truth)
        │   ├── BRC_RfP SIOP_Service and Technical.xlsx → RFP_Original (source_of_truth)
        │   ├── LENZING AG - Data for Forecast.xlsx   → Data (source_of_truth)
        │   ├── Lenzing_DPA_SIOP_Template.pdf         → Security (supporting)
        │   ├── Q&A for Demand Planning...xlsx        → RFP_QA (source_of_truth)
        │   ├── Global IBP_SIOP_RFP Acronyms 1.pdf   → RFP_Original (supporting)
        │   └── RFP Executive Summary.docx            → RFP_Original (source_of_truth)
        │
        ├── Official Response Documents/Submission/
        │   ├── RFP Response Lenzing - Blue Yonder.pdf → RFP_Response (source_of_truth)
        │   ├── Blue_Yonder_Executive_Summary...pdf   → RFP_Response (source_of_truth)
        │   ├── Blue Yonder Responses_BRC...xlsx ×3   → RFP_Response (source_of_truth)
        │   ├── Forecast_Exercise.xlsx                → RFP_Response (source_of_truth)
        │   ├── SOC 2 Report.pdf                      → Security (supporting)
        │   ├── SOC 1 Report.pdf                      → Security (supporting)
        │   ├── ISO 27001 Certificate.pdf             → Security (supporting)
        │   ├── Cloud Services Standards.pdf          → Security (supporting)
        │   ├── General Reference Architecture.pdf    → Security (supporting)
        │   └── Security Whitepaper.pdf               → Security (supporting)
        │
        ├── Implementation Services/
        │   ├── DSP_Base_Effort_Estimation...xlsx ×2  → Commercial (source_of_truth)
        │   ├── PSEstimator_T&M...xlsx ×4             → Commercial (source_of_truth)
        │   └── Deal Alignment Review...pptx          → Commercial (source_of_truth)
        │
        ├── Proposal Presentation 19th Feb/
        │   └── Proposal Presentation...pptx          → Proposal (source_of_truth)
        │
        ├── Questions 19th of Feb/
        │   ├── Offer Questions Blue Yonder.xlsx      → RFP_QA (source_of_truth)
        │   ├── Stat Fcst Exercise Assessment...xlsx  → Data (source_of_truth)
        │   └── Generated_chart...png                 → skip (image)
        │
        └── WIP/
            ├── Exec Summary.pptx                     → RFP_WIP (supporting)
            ├── RFP Response Lenzing Revised...×3     → RFP_WIP (supporting)
            ├── LENZING AG - Data for Forecast.xlsx   → Data (supporting)
            ├── Lenzing_DPA_SIOP_Template.pdf         → Security (supporting)
            ├── Blue Yonder Responses/
            │   ├── BRC_RfP...Responses.xlsx ×4       → RFP_WIP (supporting)
            │   ├── LENZING AG - Forecasts...Copy.xlsx → Data (supporting)
            │   ├── NOT USE!...docx                   → Junk (obsolete)
            │   └── OLD!!...xlsx                      → Junk (obsolete)
            ├── Supporting Documents/                 → Security (supporting)
            └── Original Files/
                ├── DO NOT USE!!...xlsx ×2             → Junk (obsolete)
                ├── BRC_RfP...Responses.xlsx          → RFP_WIP (supporting)
                └── Q&A...xlsx                        → RFP_QA (supporting)
```
