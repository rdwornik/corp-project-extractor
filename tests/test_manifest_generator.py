"""Tests for CKE manifest generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from corp_project_extractor.manifest_generator import (
    CATEGORY_TO_DOC_TYPE,
    EXTENSION_TO_DOC_TYPE,
    _resolve_client,
    _slugify,
    generate_cke_manifest,
)
from corp_project_extractor.models import FileEntry, Manifest


def _make_manifest(entries: list[FileEntry]) -> Manifest:
    return Manifest(
        project_id="test-project",
        project_path="C:/fake/project",
        created_at="2026-03-06T00:00:00",
        last_scanned="2026-03-06T00:00:00",
        files=entries,
    )


def _make_entry(
    tmp_path: Path,
    filename: str = "test.pdf",
    category: str = "Document",
    size_kb: int = 100,
    is_junk: bool = False,
    doc_role: str = "supporting",
    create_file: bool = True,
    file_bytes: int = 2048,
) -> FileEntry:
    """Create a FileEntry and optionally the backing file."""
    ext = Path(filename).suffix.lower()
    if create_file:
        fp = tmp_path / filename
        fp.write_bytes(b"x" * file_bytes)
    return FileEntry(
        rel_path=filename,
        filename=filename,
        extension=ext,
        size_kb=size_kb,
        modified="2026-03-06T00:00:00",
        sha256="abc123",
        category=category,
        doc_role=doc_role,
        confidence=0.9,
        reason="test",
        is_junk=is_junk,
        extractable=True,
    )


def _load_cke_manifest(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestGenerateCkeManifest:
    def test_basic_generation(self, tmp_path: Path):
        entries = [
            _make_entry(tmp_path, "report.pdf", "Document"),
            _make_entry(tmp_path, "deck.pptx", "Presentation"),
        ]
        manifest = _make_manifest(entries)

        result_path = generate_cke_manifest(manifest, tmp_path)

        assert result_path.exists()
        data = _load_cke_manifest(result_path)
        assert data["schema_version"] == 1
        assert data["project"] == "test-project"
        assert len(data["files"]) == 2
        assert data["files"][0]["doc_type"] == "document"
        assert data["files"][1]["doc_type"] == "presentation"

    def test_skips_junk(self, tmp_path: Path):
        entries = [
            _make_entry(tmp_path, "good.pdf", "Document"),
            _make_entry(tmp_path, "trash.pdf", "Junk", is_junk=True),
        ]
        manifest = _make_manifest(entries)
        data = _load_cke_manifest(generate_cke_manifest(manifest, tmp_path))
        assert len(data["files"]) == 1

    def test_skips_obsolete(self, tmp_path: Path):
        entries = [
            _make_entry(tmp_path, "old.pdf", "Document", doc_role="obsolete"),
        ]
        manifest = _make_manifest(entries)
        data = _load_cke_manifest(generate_cke_manifest(manifest, tmp_path))
        assert len(data["files"]) == 0

    def test_skips_unsupported_extension(self, tmp_path: Path):
        entries = [
            _make_entry(tmp_path, "photo.jpg", "Unknown"),
        ]
        manifest = _make_manifest(entries)
        data = _load_cke_manifest(generate_cke_manifest(manifest, tmp_path))
        assert len(data["files"]) == 0

    def test_skips_missing_files(self, tmp_path: Path):
        entries = [
            _make_entry(tmp_path, "ghost.pdf", "Document", create_file=False),
        ]
        manifest = _make_manifest(entries)
        data = _load_cke_manifest(generate_cke_manifest(manifest, tmp_path))
        assert len(data["files"]) == 0

    def test_skips_tiny_files(self, tmp_path: Path):
        entries = [
            _make_entry(tmp_path, "empty.pdf", "Document", size_kb=0),
        ]
        manifest = _make_manifest(entries)
        data = _load_cke_manifest(generate_cke_manifest(manifest, tmp_path))
        assert len(data["files"]) == 0

    def test_extension_overrides_category(self, tmp_path: Path):
        """A .pptx file classified as 'Document' should still get doc_type 'presentation'."""
        entries = [
            _make_entry(tmp_path, "misclassified.pptx", "Document"),
        ]
        manifest = _make_manifest(entries)
        data = _load_cke_manifest(generate_cke_manifest(manifest, tmp_path))
        assert data["files"][0]["doc_type"] == "presentation"

    def test_xlsx_gets_spreadsheet(self, tmp_path: Path):
        entries = [
            _make_entry(tmp_path, "data.xlsx", "RFP_QA"),
        ]
        manifest = _make_manifest(entries)
        data = _load_cke_manifest(generate_cke_manifest(manifest, tmp_path))
        assert data["files"][0]["doc_type"] == "spreadsheet"

    def test_video_extension(self, tmp_path: Path):
        entries = [
            _make_entry(tmp_path, "demo.mp4", "Demo"),
        ]
        manifest = _make_manifest(entries)
        data = _load_cke_manifest(generate_cke_manifest(manifest, tmp_path))
        assert data["files"][0]["doc_type"] == "video"

    def test_output_dir_default(self, tmp_path: Path):
        entries = [_make_entry(tmp_path, "test.pdf")]
        manifest = _make_manifest(entries)
        data = _load_cke_manifest(generate_cke_manifest(manifest, tmp_path))
        assert "_cke_output" in data["output_dir"]

    def test_custom_output_dir(self, tmp_path: Path):
        entries = [_make_entry(tmp_path, "test.pdf")]
        manifest = _make_manifest(entries)
        custom_out = tmp_path / "my_output"
        data = _load_cke_manifest(generate_cke_manifest(manifest, tmp_path, output_dir=custom_out))
        assert str(custom_out.resolve()) in data["output_dir"]

    def test_file_paths_are_absolute(self, tmp_path: Path):
        entries = [_make_entry(tmp_path, "test.pdf")]
        manifest = _make_manifest(entries)
        data = _load_cke_manifest(generate_cke_manifest(manifest, tmp_path))
        file_path = data["files"][0]["path"]
        assert Path(file_path).is_absolute()


class TestSlugify:
    def test_basic(self):
        assert _slugify("Lenzing DPA SIOP Template") == "lenzing-dpa-siop-template"

    def test_underscores(self):
        assert _slugify("BY_WMS_Overview") == "by-wms-overview"

    def test_parens(self):
        assert _slugify("Overview (v2)") == "overview-v2"

    def test_strip_edges(self):
        assert _slugify("  spaces  ") == "spaces"

    def test_multiple_separators(self):
        assert _slugify("a___b   c") == "a-b-c"


class TestClientProject:
    def test_manifest_includes_client_and_project(self, tmp_path: Path):
        entries = [_make_entry(tmp_path, "test.pdf")]
        manifest = _make_manifest(entries)
        data = _load_cke_manifest(generate_cke_manifest(manifest, tmp_path, client_name="Lenzing AG"))
        assert data["files"][0]["client"] == "Lenzing AG"
        assert data["files"][0]["project"] == "test-project"

    def test_client_derived_from_folder_name(self, tmp_path: Path):
        """When no --client flag, derive from project root folder name."""
        # Simulate a project folder named "PepsiCo_Planning"
        project_dir = tmp_path / "PepsiCo_Planning"
        project_dir.mkdir()
        pdf = project_dir / "test.pdf"
        pdf.write_bytes(b"x" * 2048)

        entries = [
            FileEntry(
                rel_path="test.pdf",
                filename="test.pdf",
                extension=".pdf",
                size_kb=100,
                modified="2026-03-06T00:00:00",
                sha256="abc",
                category="Document",
                doc_role="supporting",
                confidence=0.9,
                reason="test",
                is_junk=False,
                extractable=True,
            )
        ]
        manifest = _make_manifest(entries)
        data = _load_cke_manifest(generate_cke_manifest(manifest, project_dir))
        assert data["files"][0]["client"] == "PepsiCo"
        assert data["files"][0]["project"] == "test-project"

    def test_explicit_client_overrides_derived(self, tmp_path: Path):
        entries = [_make_entry(tmp_path, "test.pdf")]
        manifest = _make_manifest(entries)
        data = _load_cke_manifest(generate_cke_manifest(manifest, tmp_path, client_name="Custom Client"))
        assert data["files"][0]["client"] == "Custom Client"

    def test_resolve_client_with_alias_file(self, tmp_path: Path):
        """Alias config should resolve folder-derived names."""
        alias_file = tmp_path / "clients.yaml"
        alias_file.write_text('aliases:\n  Lenzing: "Lenzing AG"\n')
        assert _resolve_client("Lenzing", alias_file) == "Lenzing AG"

    def test_resolve_client_no_alias_file(self):
        """Without alias file, return folder-derived name as-is."""
        assert _resolve_client("PepsiCo") == "PepsiCo"

    def test_resolve_client_unknown_alias(self, tmp_path: Path):
        """Unknown names pass through unchanged."""
        alias_file = tmp_path / "clients.yaml"
        alias_file.write_text('aliases:\n  Lenzing: "Lenzing AG"\n')
        assert _resolve_client("NewClient", alias_file) == "NewClient"


class TestCategoryMapping:
    """Ensure all CPE categories have a CKE mapping."""

    @pytest.mark.parametrize(
        "category,expected",
        [
            ("RFP_Original", "document"),
            ("RFP_Response", "document"),
            ("RFP_QA", "spreadsheet"),
            ("Meeting", "note"),
            ("Demo", "presentation"),
            ("Presentation", "presentation"),
            ("Security", "document"),
            ("Data", "spreadsheet"),
            ("Unknown", "document"),
        ],
    )
    def test_mapping(self, category: str, expected: str):
        assert CATEGORY_TO_DOC_TYPE[category] == expected
