"""All dataclasses for corp-project-extractor. No raw dicts anywhere in the pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class Classification:
    """Result of classifying a single file."""

    category: str  # RFP_Original, Meeting, Strategy, Junk, etc.
    doc_role: str  # source_of_truth | supporting | obsolete
    confidence: float  # 0.0 – 1.0
    reason: str  # Human-readable explanation
    is_junk: bool = False


@dataclass
class FileEntry:
    """Single file recorded in the project manifest."""

    rel_path: str  # Relative to project root, forward slashes
    filename: str
    extension: str  # Lowercase with dot: ".pptx"
    size_kb: int
    modified: str  # ISO format timestamp
    sha256: str  # Short hash (first 16 hex chars)
    category: str
    doc_role: str
    confidence: float
    reason: str
    is_junk: bool
    extractable: bool = True
    extracted: bool = False
    extracted_path: Optional[str] = None
    word_count: int = 0
    extraction_error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FileEntry":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


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
        data = {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "project_path": self.project_path,
            "created_at": self.created_at,
            "last_scanned": self.last_scanned,
            "files": [f.to_dict() for f in self.files],
        }
        return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_yaml(), encoding="utf-8")

    @classmethod
    def from_yaml(cls, path: Path) -> "Manifest":
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        files = [FileEntry.from_dict(d) for d in data.get("files", [])]
        return cls(
            project_id=data.get("project_id", ""),
            project_path=data.get("project_path", ""),
            created_at=data.get("created_at", ""),
            last_scanned=data.get("last_scanned", ""),
            schema_version=data.get("schema_version", "1.0"),
            files=files,
        )

    def get_new_or_changed(self, other: "Manifest") -> list[FileEntry]:
        """Return entries from self that are new or have a different hash in other."""
        other_index = {e.rel_path: e.sha256 for e in other.files}
        return [e for e in self.files if other_index.get(e.rel_path) != e.sha256]


@dataclass
class ExtractionResult:
    """Result of extracting text from a single file."""

    success: bool
    output_path: Optional[Path]
    word_count: int
    error: Optional[str] = None
