"""Generate a CKE-compatible manifest.json from CPE scan results.

Reads the CPE Manifest (YAML) and produces a JSON manifest that
corp-knowledge-extractor's process-manifest command can consume.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from corp_project_extractor.models import FileEntry, Manifest

logger = logging.getLogger(__name__)

# Map CPE categories to CKE doc_type values
# CKE supports: document, presentation, slides, spreadsheet, video, audio, note, transcript
CATEGORY_TO_DOC_TYPE: dict[str, str] = {
    "RFP_Original": "document",
    "RFP_Response": "document",
    "RFP_WIP": "document",
    "RFP_QA": "spreadsheet",
    "Meeting": "note",
    "Demo": "presentation",
    "Strategy": "document",
    "Commercial": "document",
    "Security": "document",
    "Proposal": "document",
    "Data": "spreadsheet",
    "Presentation": "presentation",
    "Document": "document",
    "Spreadsheet": "spreadsheet",
    "Junk": "document",
    "Unknown": "document",
}

# Extension-based overrides (more specific than category)
EXTENSION_TO_DOC_TYPE: dict[str, str] = {
    ".pptx": "presentation",
    ".ppt": "presentation",
    ".xlsx": "spreadsheet",
    ".xls": "spreadsheet",
    ".csv": "spreadsheet",
    ".mp4": "video",
    ".mkv": "video",
    ".avi": "video",
    ".mov": "video",
    ".mp3": "audio",
    ".wav": "audio",
    ".m4a": "audio",
}

# File extensions CKE can process
SUPPORTED_EXTENSIONS: set[str] = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md",
    ".mp4", ".mkv", ".avi", ".mov",
}


def generate_cke_manifest(
    manifest: Manifest,
    project_root: Path,
    output_dir: Path | None = None,
) -> Path:
    """Generate a CKE manifest.json from a CPE Manifest.

    Args:
        manifest: CPE Manifest with classified FileEntry items
        project_root: Absolute path to the project folder
        output_dir: Where CKE should write extraction output.
            Defaults to <project_root>/_knowledge/_cke_output

    Returns:
        Path to generated cke_manifest.json
    """
    project_root = project_root.resolve()
    output_dir = output_dir or (project_root / "_knowledge" / "_cke_output")

    files: list[dict] = []
    skipped: list[str] = []

    for entry in manifest.files:
        file_path = project_root / entry.rel_path

        # Skip junk / obsolete
        if entry.is_junk or entry.doc_role == "obsolete":
            skipped.append(f"{entry.filename} ({entry.category}/{'junk' if entry.is_junk else 'obsolete'})")
            continue

        # Skip unsupported extensions
        if entry.extension not in SUPPORTED_EXTENSIONS:
            skipped.append(f"{entry.filename} (unsupported: {entry.extension})")
            continue

        # Skip files that don't exist (cloud-only OneDrive placeholders)
        if not file_path.exists():
            skipped.append(f"{entry.filename} (not synced / cloud-only)")
            continue

        # Skip very small files (< 1KB, likely empty)
        if entry.size_kb < 1:
            skipped.append(f"{entry.filename} (< 1KB)")
            continue

        # Determine doc_type: extension override > category mapping
        doc_type = EXTENSION_TO_DOC_TYPE.get(
            entry.extension,
            CATEGORY_TO_DOC_TYPE.get(entry.category, "document"),
        )

        file_id = _slugify(file_path.stem)

        files.append({
            "id": file_id,
            "path": str(file_path.resolve()),
            "doc_type": doc_type,
            "name": entry.filename,
        })

    cke_manifest = {
        "schema_version": 1,
        "project": manifest.project_id,
        "output_dir": str(output_dir.resolve()),
        "generated_at": datetime.now().isoformat(),
        "generated_by": "corp-project-extractor",
        "files": files,
    }

    # Write manifest alongside the CPE manifest
    from corp_project_extractor.config import get_settings
    settings = get_settings()
    knowledge_dir = project_root / settings.knowledge_dir
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = knowledge_dir / "cke_manifest.json"

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(cke_manifest, f, indent=2, ensure_ascii=False)

    logger.info("CKE manifest: %d files, %d skipped", len(files), len(skipped))
    for s in skipped:
        logger.debug("  Skipped: %s", s)

    return manifest_path


def _slugify(name: str) -> str:
    """Convert filename to a URL-safe slug for use as ID."""
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = slug.strip("-")
    return slug
