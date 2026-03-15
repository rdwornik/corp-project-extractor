"""Tests for project renderer (CKE extract.json aggregation)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from corp_project_extractor.renderer import render_project


def _create_extraction(
    tmp_path: Path,
    file_id: str,
    title: str,
    topics: list[str],
    products: list[str] | None = None,
    people: list[str] | None = None,
    doc_type: str = "document",
    key_points: list[str] | None = None,
    summary: str | None = None,
) -> None:
    """Create a mock CKE output directory with extract.json."""
    extract_dir = tmp_path / "_knowledge" / "_cke_output" / file_id / "extract"
    extract_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "schema_version": 1,
        "id": file_id,
        "source_file": f"C:/fake/{file_id}.pdf",
        "doc_type": doc_type,
        "project": "test_project",
        "title": title,
        "summary": summary or f"Summary of {title} with enough length to be included as a fact entry.",
        "topics": topics,
        "products": products or ["Blue Yonder Platform"],
        "people": people or [],
        "key_points": key_points
        or [f"Key point from {title}: this is a detailed insight about the document contents."],
        "slides_count": 0,
        "links_line": "",
        "validation_result": "valid",
        "unknown_terms": [],
        "processed_at": "2026-03-06T12:00:00",
    }

    with open(extract_dir / "extract.json", "w", encoding="utf-8") as f:
        json.dump(data, f)


class TestRenderProject:
    def test_basic_render(self, tmp_path: Path):
        _create_extraction(tmp_path, "file-1", "RFP Response", ["SLA", "WMS"])
        _create_extraction(tmp_path, "file-2", "Meeting Notes", ["Demand Planning"])

        stats = render_project(tmp_path)

        assert stats["extractions"] == 2
        assert stats["topics"] >= 2
        assert stats["products"] >= 1
        assert stats["facts"] >= 2
        assert (tmp_path / "_knowledge" / "project-info.yaml").exists()
        assert (tmp_path / "_knowledge" / "facts.yaml").exists()
        assert (tmp_path / "_knowledge" / "index.md").exists()

    def test_project_info_structure(self, tmp_path: Path):
        _create_extraction(tmp_path, "file-1", "Test Doc", ["SLA"], products=["BY Platform"], people=["Alice (PM)"])
        render_project(tmp_path)

        with open(tmp_path / "_knowledge" / "project-info.yaml") as f:
            info = yaml.safe_load(f)

        assert info["project"] == tmp_path.name
        assert info["status"] == "active"
        assert info["files_processed"] == 1
        assert "SLA" in info["topics"]
        assert "BY Platform" in info["products"]
        assert "Alice (PM)" in info["people"]

    def test_project_info_has_opportunity(self, tmp_path: Path):
        _create_extraction(tmp_path, "file-1", "Test", ["SLA"], products=["BY Demand Planning"])
        render_project(tmp_path)

        with open(tmp_path / "_knowledge" / "project-info.yaml") as f:
            info = yaml.safe_load(f)

        assert "opportunity" in info
        assert "products" in info["opportunity"]
        assert "key_topics" in info["opportunity"]
        assert info["opportunity"]["stage"] == "active"

    def test_facts_yaml_structure(self, tmp_path: Path):
        _create_extraction(
            tmp_path,
            "file-1",
            "RFP",
            ["Demand Planning"],
            key_points=["This is a detailed key point about demand planning capabilities."],
        )
        render_project(tmp_path)

        with open(tmp_path / "_knowledge" / "facts.yaml") as f:
            facts = yaml.safe_load(f)

        assert facts["total_facts"] >= 1
        assert "facts_by_topic" in facts
        assert len(facts["facts"]) >= 1

        fact = facts["facts"][0]
        assert "fact" in fact
        assert "source" in fact
        assert "source_title" in fact
        assert "topics" in fact

    def test_facts_skips_short_key_points(self, tmp_path: Path):
        _create_extraction(
            tmp_path,
            "file-1",
            "Test",
            ["SLA"],
            key_points=["Too short", "This is a sufficiently long key point for extraction."],
            summary="Short",
        )  # < 50 chars, should skip
        render_project(tmp_path)

        with open(tmp_path / "_knowledge" / "facts.yaml") as f:
            facts = yaml.safe_load(f)

        fact_texts = [f["fact"] for f in facts["facts"]]
        assert "Too short" not in fact_texts
        assert any("sufficiently long" in f for f in fact_texts)

    def test_index_md_frontmatter(self, tmp_path: Path):
        _create_extraction(tmp_path, "file-1", "Test", ["SLA"], products=["BY Platform"])
        render_project(tmp_path)

        content = (tmp_path / "_knowledge" / "index.md").read_text()
        assert content.startswith("---")
        assert "schema_version: 2" in content
        assert 'source_tool: "project-extractor"' in content
        assert 'type: "report"' in content
        assert "## Key Topics" in content
        assert "## Products" in content
        assert "```dataview" in content

    def test_index_md_links_line(self, tmp_path: Path):
        _create_extraction(tmp_path, "file-1", "Test", ["Demand Planning"], products=["BY Platform"])
        render_project(tmp_path)

        content = (tmp_path / "_knowledge" / "index.md").read_text()
        assert "[[Demand Planning]]" in content
        assert "[[BY Platform]]" in content

    def test_topic_frequency_ranking(self, tmp_path: Path):
        """Topics appearing in more files should rank higher."""
        _create_extraction(tmp_path, "f1", "Doc 1", ["WMS", "SLA"])
        _create_extraction(tmp_path, "f2", "Doc 2", ["WMS", "Pricing"])
        _create_extraction(tmp_path, "f3", "Doc 3", ["WMS"])
        render_project(tmp_path)

        with open(tmp_path / "_knowledge" / "project-info.yaml") as f:
            info = yaml.safe_load(f)

        assert info["topics"][0] == "WMS"

    def test_doc_type_distribution(self, tmp_path: Path):
        _create_extraction(tmp_path, "f1", "Doc 1", ["A"], doc_type="document")
        _create_extraction(tmp_path, "f2", "Deck", ["B"], doc_type="presentation")
        _create_extraction(tmp_path, "f3", "Sheet", ["C"], doc_type="spreadsheet")
        render_project(tmp_path)

        with open(tmp_path / "_knowledge" / "project-info.yaml") as f:
            info = yaml.safe_load(f)

        dist = info["doc_type_distribution"]
        assert dist["document"] == 1
        assert dist["presentation"] == 1
        assert dist["spreadsheet"] == 1

    def test_no_cke_output_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="No CKE output"):
            render_project(tmp_path)

    def test_empty_cke_output_raises(self, tmp_path: Path):
        (tmp_path / "_knowledge" / "_cke_output").mkdir(parents=True)
        with pytest.raises(ValueError, match="No extract.json"):
            render_project(tmp_path)

    def test_people_section_in_index(self, tmp_path: Path):
        _create_extraction(tmp_path, "f1", "Test", ["SLA"], people=["Ernesto (VP Supply Chain)", "Christian (S&OP)"])
        render_project(tmp_path)

        content = (tmp_path / "_knowledge" / "index.md").read_text()
        assert "## Key People" in content
        assert "Ernesto (VP Supply Chain)" in content

    def test_no_people_section_when_empty(self, tmp_path: Path):
        _create_extraction(tmp_path, "f1", "Test", ["SLA"], people=[])
        render_project(tmp_path)

        content = (tmp_path / "_knowledge" / "index.md").read_text()
        assert "## Key People" not in content
