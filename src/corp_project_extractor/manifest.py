"""Scan, hash, build and incrementally update the project manifest.

Output: <project>/_knowledge/manifest.yaml
Incremental: unchanged files (same path + hash) keep their extraction status.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from corp_project_extractor.classifier import EXTRACTABLE_EXTENSIONS, classify_file
from corp_project_extractor.config import get_settings
from corp_project_extractor.models import FileEntry, Manifest

log = logging.getLogger(__name__)

SKIP_DIRS: set[str] = {"_knowledge", "_extracted", ".git", "__pycache__", "node_modules", ".venv"}


def _short_hash(file_path: Path, length: int = 16) -> str:
    """SHA-256, first *length* hex chars."""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:length]
    except OSError:
        return "error_reading"


def _build_entry(file_path: Path, project_root: Path) -> FileEntry:
    rel = file_path.relative_to(project_root)
    rel_str = str(rel).replace("\\", "/")
    stat = file_path.stat()
    size_kb = max(1, stat.st_size // 1024)
    modified = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
    sha = _short_hash(file_path)
    clf = classify_file(file_path, project_root)
    ext = file_path.suffix.lower()
    settings = get_settings()
    extractable = ext in EXTRACTABLE_EXTENSIONS and ext not in settings.skip_extensions

    return FileEntry(
        rel_path=rel_str,
        filename=file_path.name,
        extension=ext,
        size_kb=size_kb,
        modified=modified,
        sha256=sha,
        category=clf.category,
        doc_role=clf.doc_role,
        confidence=clf.confidence,
        reason=clf.reason,
        is_junk=clf.is_junk,
        extractable=extractable,
    )


def scan(
    project_path: Path,
    progress_callback: Optional[Callable[[FileEntry], None]] = None,
) -> Manifest:
    """Walk *project_path*, classify every file, return a fresh Manifest."""
    project_path = project_path.resolve()
    settings = get_settings()

    entries: list[FileEntry] = []

    for item in sorted(project_path.rglob("*")):
        if not item.is_file():
            continue
        # Skip output dirs and hidden dirs
        rel_parts = item.parts[len(project_path.parts):]
        if any(p in SKIP_DIRS for p in rel_parts):
            continue
        if any(p.startswith(".") for p in rel_parts):
            continue
        # Skip files too large even to hash? No — we hash them, just flag extraction
        try:
            entry = _build_entry(item, project_path)
        except OSError as e:
            log.warning("Cannot read %s: %s (cloud-only?)", item, e)
            entry = FileEntry(
                rel_path=str(item.relative_to(project_path)).replace("\\", "/"),
                filename=item.name,
                extension=item.suffix.lower(),
                size_kb=0,
                modified="",
                sha256="",
                category="Unknown",
                doc_role="supporting",
                confidence=0.0,
                reason=f"OSError: {e}",
                is_junk=False,
                extractable=False,
                extraction_error=str(e),
            )
        entries.append(entry)
        if progress_callback:
            progress_callback(entry)

    now = datetime.now().isoformat(timespec="seconds")
    return Manifest(
        project_id=project_path.name.lower().replace(" ", "-"),
        project_path=str(project_path).replace("\\", "/"),
        created_at=now,
        last_scanned=now,
        files=entries,
    )


def load_manifest(project_path: Path) -> Optional[Manifest]:
    settings = get_settings()
    path = project_path / settings.knowledge_dir / "manifest.yaml"
    if not path.exists():
        return None
    try:
        return Manifest.from_yaml(path)
    except Exception as e:
        log.warning("Could not load existing manifest: %s", e)
        return None


def save_manifest(project_path: Path, manifest: Manifest) -> Path:
    settings = get_settings()
    manifest_path = project_path / settings.knowledge_dir / "manifest.yaml"
    manifest.save(manifest_path)
    return manifest_path


def _merge(new: Manifest, old: Optional[Manifest]) -> Manifest:
    """Preserve extraction status for files whose hash hasn't changed."""
    if old is None:
        return new
    old_index: dict[str, FileEntry] = {e.rel_path: e for e in old.files}
    for entry in new.files:
        prev = old_index.get(entry.rel_path)
        if prev and prev.sha256 == entry.sha256:
            entry.extracted = prev.extracted
            entry.extracted_path = prev.extracted_path
            entry.word_count = prev.word_count
            entry.extraction_error = prev.extraction_error
    # Preserve created_at from original manifest
    new.created_at = old.created_at
    return new


def scan_and_save(
    project_path: Path,
    progress_callback: Optional[Callable[[FileEntry], None]] = None,
) -> tuple[Manifest, Path]:
    """Full scan with incremental merge. Returns (manifest, manifest_path)."""
    old = load_manifest(project_path)
    new = scan(project_path, progress_callback)
    merged = _merge(new, old)

    # Ensure _knowledge/notes.md exists (human-only — never overwrite)
    settings = get_settings()
    notes_path = project_path / settings.knowledge_dir / "notes.md"
    if not notes_path.exists():
        notes_path.parent.mkdir(parents=True, exist_ok=True)
        notes_path.write_text(
            f"# Notes — {project_path.name}\n\n"
            "Add your observations here. This file is never touched by the pipeline.\n",
            encoding="utf-8",
        )

    manifest_path = save_manifest(project_path, merged)

    # Delta summary
    if old:
        old_index = {e.rel_path: e.sha256 for e in old.files}
        old_paths = set(old_index)
        new_paths = {e.rel_path for e in merged.files}
        added = len(new_paths - old_paths)
        changed = sum(1 for e in merged.files
                      if e.rel_path in old_paths and old_index[e.rel_path] != e.sha256)
        removed = len(old_paths - new_paths)
        unchanged = len(merged.files) - added - changed
        log.info("Scan delta: %d new, %d changed, %d removed, %d unchanged",
                 added, changed, removed, unchanged)

    return merged, manifest_path
