"""Pure template step: facts.yaml → knowledge-sheet.md (no LLM).

Rules:
- knowledge-sheet.md is ALWAYS fully regenerated — never hand-edit it
- notes.md is NEVER touched — human-only
- Empty sections are omitted
- YAML frontmatter for Obsidian
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from corp_project_extractor.config import get_settings

_PRIORITY_ICONS = {"must_have": "🔴", "nice_to_have": "🟡", "unclear": "⚪"}


def _section(title: str, lines: list[str]) -> list[str]:
    """Return section lines only if there's content."""
    if not lines:
        return []
    return ["", f"## {title}", ""] + lines


def render(project_path: Path) -> Path:
    """Read _knowledge/facts.yaml and write _knowledge/knowledge-sheet.md."""
    settings = get_settings()
    knowledge_dir = project_path / settings.knowledge_dir
    facts_path = knowledge_dir / "facts.yaml"
    output_path = knowledge_dir / "knowledge-sheet.md"

    if not facts_path.exists():
        raise FileNotFoundError(
            f"facts.yaml not found at {facts_path}. "
            "Populate it first (cpe synthesize or manually from _extracted/)."
        )

    with open(facts_path, encoding="utf-8") as f:
        facts: dict = yaml.safe_load(f) or {}

    today = datetime.now().strftime("%Y-%m-%d")
    client = facts.get("client", "Unknown Client")
    stage = facts.get("stage", "")
    industry = facts.get("industry", "")
    region = facts.get("region", "")
    last_updated = facts.get("last_updated", today)
    project_id = facts.get("project_id", client.lower().replace(" ", "-"))
    sources_count = facts.get("sources_count", 0)
    by_solutions = facts.get("overview", {}).get("by_solution", [])

    # ── YAML frontmatter ──────────────────────────────────────────────────────
    fm_lines = [
        "---",
        f"project_id: {project_id}",
        f"client: {client}",
        f"stage: {stage}",
        f"industry: {industry}",
        f"region: {region}",
        f"by_solution: {by_solutions!r}",
        f"last_updated: \"{last_updated}\"",
        f"sources_count: {sources_count}",
        "generated: true",
        "---",
    ]

    body: list[str] = [
        f"# {client} — Knowledge Sheet",
        "",
        f"> **Auto-generated** from project files on {today}. "
        "Do not edit — use `_knowledge/notes.md` for annotations.",
    ]

    # ── 1. Overview ───────────────────────────────────────────────────────────
    ov = facts.get("overview", {})
    ov_lines: list[str] = []
    if ov.get("client_problem"):
        ov_lines += [f"**Problem:** {ov['client_problem']}", ""]
    if ov.get("proposed_outcome"):
        ov_lines += [f"**Proposed Outcome:** {ov['proposed_outcome']}", ""]
    if ov.get("by_solution"):
        ov_lines += [f"**BY Solutions:** {', '.join(ov['by_solution'])}", ""]
    if ov.get("engagement_type"):
        ov_lines += [f"**Engagement Type:** {ov['engagement_type']}"]
    body += _section("Overview", ov_lines)

    # ── 2. Timeline ───────────────────────────────────────────────────────────
    tl = facts.get("timeline", {})
    tl_lines: list[str] = []
    _date_fields = [
        ("first_contact", "First Contact"),
        ("discovery",     "Discovery"),
        ("demo",          "Demo"),
        ("rfp_received",  "RFP Received"),
        ("rfp_submitted", "RFP Submitted"),
        ("decision_expected", "Decision Expected"),
    ]
    for key, label in _date_fields:
        if tl.get(key):
            tl_lines.append(f"- **{label}:** {tl[key]}")
    events = tl.get("events", [])
    if events:
        tl_lines.append("")
        tl_lines.append("**Event Log:**")
        for ev in sorted(events, key=lambda e: e.get("date", "")):
            src = f" _(source: {ev['source']})_" if ev.get("source") else ""
            tl_lines.append(f"- **{ev.get('date', '')}** — {ev.get('event', '')}{src}")
    body += _section("Timeline", tl_lines)

    # ── 3. Key Requirements ───────────────────────────────────────────────────
    reqs = facts.get("requirements", [])
    req_lines: list[str] = []
    for req in reqs:
        prio = req.get("priority", "unclear")
        icon = _PRIORITY_ICONS.get(prio, "⚪")
        topic = req.get("topic", "")
        text = req.get("requirement", "")
        src = req.get("source", {})
        src_str = ""
        if src:
            parts = []
            if src.get("file"):
                parts.append(src["file"])
            if src.get("page"):
                parts.append(f"p.{src['page']}")
            if parts:
                src_str = f" _({', '.join(parts)})_"
        req_lines.append(f"{icon} **{topic}:** {text}{src_str}")
    body += _section("Key Requirements", req_lines)

    # ── 4. Integrations & Constraints ─────────────────────────────────────────
    intgs = facts.get("integrations", [])
    intg_lines: list[str] = []
    for intg in intgs:
        system = intg.get("system", "")
        typ = intg.get("type", "")
        direction = intg.get("direction", "")
        notes = intg.get("notes", "")
        meta = ", ".join(x for x in [typ, direction] if x)
        note_str = f": {notes}" if notes else ""
        intg_lines.append(f"- **{system}** ({meta}){note_str}")
    body += _section("Integrations & Constraints", intg_lines)

    # ── 5. Competitors ────────────────────────────────────────────────────────
    comps = facts.get("competitors", [])
    comp_lines: list[str] = []
    for comp in comps:
        name = comp.get("name", "")
        comp_lines.append(f"### {name}")
        if comp.get("strengths"):
            comp_lines.append(f"- **Strengths:** {comp['strengths']}")
        if comp.get("weaknesses"):
            comp_lines.append(f"- **Weaknesses:** {comp['weaknesses']}")
    body += _section("Competitors", comp_lines)

    # ── 6. Commercial ─────────────────────────────────────────────────────────
    comm = facts.get("commercial", {})
    comm_lines: list[str] = []
    if comm.get("pricing_model"):
        comm_lines.append(f"- **Pricing Model:** {comm['pricing_model']}")
    if comm.get("deal_value"):
        comm_lines.append(f"- **Deal Value:** {comm['deal_value']}")
    if comm.get("contract_term"):
        comm_lines.append(f"- **Contract Term:** {comm['contract_term']}")
    for assumption in comm.get("key_assumptions", []):
        comm_lines.append(f"  - {assumption}")
    body += _section("Commercial", comm_lines)

    # ── 7. Security & Compliance ──────────────────────────────────────────────
    sec = facts.get("security", {})
    sec_lines: list[str] = []
    certs = sec.get("certifications_provided", [])
    if certs:
        sec_lines.append(f"- **Certifications Provided:** {', '.join(certs)}")
    if sec.get("data_residency"):
        sec_lines.append(f"- **Data Residency:** {sec['data_residency']}")
    for q in sec.get("questions_asked", []):
        sec_lines.append(f"- Q: {q}")
    for sr in sec.get("special_requirements", []):
        sec_lines.append(f"- ⚠ {sr}")
    body += _section("Security & Compliance", sec_lines)

    # ── 8. Risks & Open Questions ─────────────────────────────────────────────
    risks = facts.get("risks", [])
    risk_lines: list[str] = []
    for risk in risks:
        prob = risk.get("probability", "").upper()
        impact = risk.get("impact", "").upper()
        badge = f"[{prob}/{impact}]" if prob or impact else ""
        mitigation = risk.get("mitigation", "")
        src = risk.get("source", {})
        src_str = f" _({src['file']})_" if src and src.get("file") else ""
        risk_lines.append(f"- {badge} {risk.get('risk', '')}{src_str}")
        if mitigation:
            risk_lines.append(f"  - Mitigation: {mitigation}")
    body += _section("Risks & Open Questions", risk_lines)

    # ── 9. Decision Log ───────────────────────────────────────────────────────
    decisions = facts.get("decisions", [])
    dec_lines: list[str] = []
    for dec in sorted(decisions, key=lambda d: d.get("date", "")):
        src = dec.get("source", {})
        src_str = f" _({src['file']})_" if src and src.get("file") else ""
        dec_lines.append(f"- **{dec.get('date', '')}** — {dec.get('decision', '')}{src_str}")
        if dec.get("rationale"):
            dec_lines.append(f"  - {dec['rationale']}")
    body += _section("Decision Log", dec_lines)

    # ── 10. Team ──────────────────────────────────────────────────────────────
    team = facts.get("team", {})
    team_lines: list[str] = []
    by_team = team.get("by_team", [])
    client_contacts = team.get("client_contacts", [])
    if by_team:
        team_lines.append("**Blue Yonder Team:**")
        for m in by_team:
            team_lines.append(f"- {m.get('name', '')} — {m.get('role', '')}")
    if client_contacts:
        if by_team:
            team_lines.append("")
        team_lines.append("**Client Contacts:**")
        for m in client_contacts:
            team_lines.append(f"- {m.get('name', '')} — {m.get('role', '')}")
    body += _section("Team", team_lines)

    # ── 11. Key Files ─────────────────────────────────────────────────────────
    kf_items = facts.get("key_files", [])
    kf_lines: list[str] = []
    for kf in kf_items:
        kf_lines.append(
            f"- **{kf.get('file', '')}** ({kf.get('category', '')}): {kf.get('why_important', '')}"
        )
    body += _section("Key Files", kf_lines)

    # ── Write ─────────────────────────────────────────────────────────────────
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    content = "\n".join(fm_lines) + "\n\n" + "\n".join(body) + "\n"
    output_path.write_text(content, encoding="utf-8")
    return output_path
