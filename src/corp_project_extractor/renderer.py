"""Render project-level knowledge from CKE per-file extraction results.

Reads extract.json files from _knowledge/_cke_output/ and produces:
  - project-info.yaml  (corp-opportunity-manager compatible)
  - facts.yaml         (aggregated key points with sources)
  - index.md           (Obsidian project overview with frontmatter)
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import yaml

from corp_project_extractor.config import get_settings

logger = logging.getLogger(__name__)


def render_project(project_path: Path) -> dict:
    """Render project knowledge from CKE extraction results.

    Args:
        project_path: Root path of the project folder

    Returns:
        Summary dict with stats
    """
    settings = get_settings()
    knowledge_dir = project_path / settings.knowledge_dir
    cke_output = knowledge_dir / "_cke_output"

    if not cke_output.exists():
        raise FileNotFoundError(
            f"No CKE output found at {cke_output}. Run 'cpe extract-cke' first."
        )

    extractions = _load_extractions(cke_output)

    if not extractions:
        raise ValueError(f"No extract.json files found in {cke_output}")

    logger.info("Loaded %d extractions", len(extractions))

    project_name = project_path.name

    project_info = _build_project_info(project_name, extractions)
    facts = _build_facts(project_name, extractions)
    index_md = _build_index_md(project_name, project_info, facts)

    _write_yaml(knowledge_dir / "project-info.yaml", project_info)
    _write_yaml(knowledge_dir / "facts.yaml", facts)
    (knowledge_dir / "index.md").write_text(index_md, encoding="utf-8")

    logger.info("Rendered: project-info.yaml, facts.yaml, index.md")

    return {
        "extractions": len(extractions),
        "topics": len(project_info.get("topics", [])),
        "products": len(project_info.get("products", [])),
        "people": len(project_info.get("people", [])),
        "facts": facts["total_facts"],
    }


# -- Loading ------------------------------------------------------------------


def _load_extractions(cke_output: Path) -> list[dict]:
    """Load all extract.json files from CKE output directories."""
    extractions = []
    for extract_file in sorted(cke_output.rglob("extract.json")):
        try:
            with open(extract_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            extractions.append(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Failed to load %s: %s", extract_file, e)
    return extractions


# -- project-info.yaml --------------------------------------------------------


def _build_project_info(project_name: str, extractions: list[dict]) -> dict:
    """Build project-info.yaml compatible with corp-opportunity-manager."""
    all_topics: Counter[str] = Counter()
    all_products: Counter[str] = Counter()
    all_people: Counter[str] = Counter()
    doc_types: Counter[str] = Counter()

    for ext in extractions:
        for topic in ext.get("topics", []):
            all_topics[topic] += 1
        for product in ext.get("products", []):
            all_products[product] += 1
        for person in ext.get("people", []):
            all_people[person] += 1
        doc_types[ext.get("doc_type", "document")] += 1

    top_topics = [t for t, _ in all_topics.most_common(15)]
    top_products = [p for p, _ in all_products.most_common(8)]
    top_people = [p for p, _ in all_people.most_common(10)]

    return {
        "project": project_name,
        "status": "active",
        "rendered_at": datetime.now().isoformat(),
        "files_processed": len(extractions),
        "topics": top_topics,
        "products": top_products,
        "people": top_people,
        "doc_type_distribution": dict(doc_types.most_common()),
        "opportunity": {
            "name": project_name.replace("_", " "),
            "products": top_products[:4],
            "stage": "active",
            "key_topics": top_topics[:8],
        },
    }


# -- facts.yaml ---------------------------------------------------------------


def _build_facts(project_name: str, extractions: list[dict]) -> dict:
    """Build facts.yaml with aggregated key points from all files."""
    facts: list[dict] = []

    for ext in extractions:
        file_id = ext.get("id", "unknown")
        title = ext.get("title", file_id)
        topics = ext.get("topics", [])[:3]

        for point in ext.get("key_points", []):
            if isinstance(point, str) and len(point) > 20:
                facts.append({
                    "fact": point,
                    "source": file_id,
                    "source_title": title,
                    "topics": topics,
                })

        summary = ext.get("summary", "")
        if summary and len(summary) > 50:
            facts.append({
                "fact": summary,
                "source": file_id,
                "source_title": title,
                "type": "summary",
                "topics": topics,
            })

    # Group fact counts by topic
    topic_counts: Counter[str] = Counter()
    for fact in facts:
        for t in fact.get("topics", []):
            topic_counts[t] += 1

    return {
        "project": project_name,
        "total_facts": len(facts),
        "rendered_at": datetime.now().isoformat(),
        "facts_by_topic": dict(topic_counts.most_common()),
        "facts": facts,
    }


# -- index.md -----------------------------------------------------------------


def _build_index_md(
    project_name: str,
    project_info: dict,
    facts: dict,
) -> str:
    """Build index.md -- Obsidian-compatible project overview."""
    topics = project_info.get("topics", [])
    products = project_info.get("products", [])
    people = project_info.get("people", [])
    doc_dist = project_info.get("doc_type_distribution", {})
    display_name = project_name.replace("_", " ")
    today = str(date.today())

    # Frontmatter
    lines = [
        "---",
        f'title: "Project: {display_name}"',
        f"date: {today}",
        'type: "report"',
        'source_type: "opportunity"',
        'layer: "operational"',
        f"topics: {json.dumps(topics[:8])}",
        f"products: {json.dumps(products[:4])}",
        f"people: {json.dumps(people[:3])}",
        f'project: "{project_name}"',
        'confidentiality: "confidential"',
        'authority: "approved"',
        'source_tool: "project-extractor"',
        f'source_file: "{project_name}"',
        "schema_version: 2",
        "---",
        "",
        f"# {display_name}",
        "",
        f"**Files processed:** {project_info.get('files_processed', 0)}",
        f"**Last rendered:** {today}",
        "",
    ]

    # Links line
    link_parts = [f"[[{t}]]" for t in topics[:8]]
    link_parts += [f"[[{p}]]" for p in products[:4]]
    lines.append("**Links:** " + " . ".join(link_parts))
    lines.append("")

    # Topics by frequency
    lines.append("## Key Topics")
    lines.append("")
    for topic in topics[:12]:
        lines.append(f"- {topic}")
    lines.append("")

    # Products
    if products:
        lines.append("## Products")
        lines.append("")
        for product in products:
            lines.append(f"- {product}")
        lines.append("")

    # People
    if people:
        lines.append("## Key People")
        lines.append("")
        for person in people[:10]:
            lines.append(f"- {person}")
        lines.append("")

    # Facts by topic
    facts_by_topic = facts.get("facts_by_topic", {})
    if facts_by_topic:
        lines.append("## Knowledge by Topic")
        lines.append("")
        for topic, count in sorted(facts_by_topic.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"- **{topic}** -- {count} facts")
        lines.append("")

    # Document breakdown
    lines.append("## Documents Processed")
    lines.append("")
    for doc_type, count in sorted(doc_dist.items(), key=lambda x: -x[1]):
        lines.append(f"- **{doc_type}**: {count} files")
    lines.append("")

    # Dataview query for Obsidian
    lines.append("## All Extracted Notes")
    lines.append("")
    lines.append("```dataview")
    lines.append("TABLE source_type, topics")
    lines.append('FROM "02_sources"')
    lines.append(f'WHERE project = "{project_name}"')
    lines.append("SORT date DESC")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


# -- Utilities ----------------------------------------------------------------


def _write_yaml(path: Path, data: dict) -> None:
    """Write YAML file with clean formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            data, f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
