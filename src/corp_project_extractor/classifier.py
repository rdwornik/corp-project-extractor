"""Rules-first file classifier. Priority order: first match wins.

Priority (see CLAUDE.md for full table):
  1  Junk          — temp lock, DO NOT USE, NOT USE!, OLD!!, blank template
  2  Security      — SOC, ISO 27001, DPA, whitepaper, cloud services, ref architecture
  3  RFP_QA        — Q&A, questionnaire, offer questions in filename
  4  WIP path      — RFP_WIP (Security/Junk already handled above)
  5  Submission / Official Response path — RFP_Response
  6  RFP_Response filename — "Blue Yonder Responses"
  7  Data          — CSV, payload, data for forecast, fcst/forecast exercise
  8  Original + RFP ancestor path — RFP_Original
  9  Commercial filename — PSEstimator, effort estimation, deal alignment, T&M
 10  Implementation Services path — Commercial
 11  Proposal Presentation path — Proposal
 12  Dated folder / meeting folder — Meeting
 13  Demo folder — Demo
 14  Transformation Journey / Workshop folder — Strategy
 15  RFP folder catch-all — Q&A->RFP_QA, _old->RFP_WIP, strategy->Strategy, else->RFP_WIP
 16  Strategy filename — Briefing Book, Roadmap, Transformation, Strategy
 17  Meeting filename — meeting notes
 18  Proposal filename — Proposal Presentation
 19  Extension fallbacks — Presentation / Document / Spreadsheet / Data
 20  Unknown
"""

from __future__ import annotations

import re
from pathlib import Path

from corp_project_extractor.models import Classification

# Confidence levels
HIGH = 1.0
MEDIUM = 0.7
LOW = 0.4

DOC_ROLES: dict[str, str] = {
    "RFP_Original": "source_of_truth",
    "RFP_Response": "source_of_truth",
    "RFP_WIP": "obsolete",
    "RFP_QA": "source_of_truth",
    "Meeting": "source_of_truth",
    "Demo": "source_of_truth",
    "Strategy": "source_of_truth",
    "Commercial": "source_of_truth",
    "Security": "supporting",
    "Proposal": "source_of_truth",
    "Data": "supporting",
    "Presentation": "supporting",
    "Document": "supporting",
    "Spreadsheet": "supporting",
    "Junk": "obsolete",
    "Unknown": "supporting",
}

EXTRACTABLE_EXTENSIONS: set[str] = {".pptx", ".pdf", ".docx", ".xlsx", ".xls", ".csv"}


def _clf(category: str, confidence: float, reason: str) -> Classification:
    return Classification(
        category=category,
        doc_role=DOC_ROLES.get(category, "supporting"),
        confidence=confidence,
        reason=reason,
        is_junk=(category == "Junk"),
    )


def classify_file(file_path: Path, project_root: Path) -> Classification:
    """Classify *file_path* relative to *project_root*. First rule match wins."""
    try:
        rel = file_path.relative_to(project_root)
    except ValueError:
        rel = Path(file_path.name)

    # Folder parts as lowercase strings (excludes filename itself)
    folder_parts: list[str] = [p.lower() for p in rel.parts[:-1]]

    name: str = file_path.name
    name_lower: str = name.lower()
    stem_lower: str = file_path.stem.lower()
    ext: str = file_path.suffix.lower()

    # ── 1. JUNK ──────────────────────────────────────────────────────────────
    if name.startswith("~$"):
        return _clf("Junk", HIGH, "temp lock file (~$)")
    if re.search(r"do\s*not\s*use|not\s+use\s*!|old!!+", name_lower):
        return _clf("Junk", HIGH, "obsolete marker in filename")
    # Blank template: only pptx/docx; ignore if it also looks like a content doc
    if re.search(r"\btemplate\b", name_lower) and ext in (".pptx", ".docx"):
        if not re.search(r"dpa|rfp|proposal|strategy|commercial|response", name_lower):
            return _clf("Junk", MEDIUM, "blank slide/doc template")

    # ── 2. SECURITY ──────────────────────────────────────────────────────────
    if re.search(r"\bsoc\s*[12]\b|soc2|soc 2|soc1|soc 1", name_lower):
        return _clf("Security", HIGH, "SOC audit report")
    if re.search(r"iso\s*27001", name_lower):
        return _clf("Security", HIGH, "ISO 27001 certificate")
    if re.search(r"white\s*paper|whitepaper", name_lower):
        return _clf("Security", HIGH, "security whitepaper")
    if "cloud services standards" in name_lower:
        return _clf("Security", HIGH, "cloud services standards")
    if "general reference architecture" in name_lower:
        return _clf("Security", HIGH, "reference architecture doc")
    # \b doesn't work across underscores, so use negative letter lookaround for DPA
    if re.search(r"(?<![a-z])dpa(?![a-z])|data processing a(?:greement|ddendum)", name_lower):
        return _clf("Security", HIGH, "DPA document")

    # ── 3. RFP_QA — filename ─────────────────────────────────────────────────
    if re.search(r"q\s*&\s*a|q\s+and\s+a|\bqa\b|questionnaire|offer\s+questions", name_lower):
        return _clf("RFP_QA", HIGH, "Q&A or questionnaire in filename")

    # ── 4. PATH: WIP ─────────────────────────────────────────────────────────
    if "wip" in folder_parts:
        return _clf("RFP_WIP", HIGH, "inside WIP/ folder")

    # ── 5. PATH: Submission / Official Response ───────────────────────────────
    if any("official response" in p or "submission" in p for p in folder_parts):
        return _clf("RFP_Response", HIGH, "inside Official Response / Submission folder")

    # ── 6. RFP_Response — filename ────────────────────────────────────────────
    if re.search(r"blue\s*yonder\s*responses?|by\s+responses?", name_lower):
        return _clf("RFP_Response", HIGH, "Blue Yonder Responses in filename")

    # ── 7. DATA — filename / extension ───────────────────────────────────────
    if ext == ".csv":
        return _clf("Data", HIGH, "CSV file")
    if re.search(r"\bpayload\b", name_lower):
        return _clf("Data", HIGH, "payload data file")
    if re.search(r"data\s+for\s+forecast|data\s*for\s+fcst", name_lower):
        return _clf("Data", HIGH, "forecast data file")
    if re.search(r"(?:forecast|fcst).{0,3}exercise|stat.{0,5}fcst", name_lower):
        return _clf("Data", MEDIUM, "statistical forecast exercise data")

    # ── 8. PATH: Original/ within RFP subtree ────────────────────────────────
    if "original" in folder_parts and any("rfp" in p for p in folder_parts):
        # "Original Files" under WIP/ already caught by rule 4
        return _clf("RFP_Original", HIGH, "inside RFP/Original folder")

    # ── 9. COMMERCIAL — filename ──────────────────────────────────────────────
    if re.search(r"psestimator|ps.?estimator|effort.?estimation", name_lower):
        return _clf("Commercial", HIGH, "PS estimator / effort estimation")
    if re.search(r"deal.?alignment", name_lower):
        return _clf("Commercial", HIGH, "deal alignment document")
    if re.search(r"\bt\s*&\s*m\b|time.?and.?material", name_lower):
        return _clf("Commercial", MEDIUM, "T&M pricing document")

    # ── 10. PATH: Implementation Services ────────────────────────────────────
    if any("implementation services" in p for p in folder_parts):
        return _clf("Commercial", HIGH, "inside Implementation Services folder")

    # ── 11. PATH: Proposal Presentation ──────────────────────────────────────
    if any("proposal presentation" in p for p in folder_parts):
        return _clf("Proposal", HIGH, "inside Proposal Presentation folder")

    # ── 12. PATH: dated folder (YYYY.MM.DD) or meeting/prep folder ───────────
    _meeting_folder = any(
        re.search(r"\d{4}\.\d{2}\.\d{2}", p) or "meeting" in p or "prep meeting" in p for p in folder_parts
    )
    if _meeting_folder:
        return _clf("Meeting", HIGH, "inside dated meeting / meeting folder")

    # ── 13. PATH: Demo folder ─────────────────────────────────────────────────
    if any(re.search(r"\bdemo\b", p) for p in folder_parts):
        return _clf("Demo", HIGH, "inside demo folder")

    # ── 14. PATH: Transformation Journey / Workshop ───────────────────────────
    if any("transformation journey" in p or "workshop" in p for p in folder_parts):
        return _clf("Strategy", HIGH, "inside Transformation Journey / Workshop folder")

    # ── 15. PATH: RFP folder catch-all ────────────────────────────────────────
    if any("rfp" in p for p in folder_parts):
        if re.search(r"q\s*&\s*a|questionnaire|offer\s+questions", name_lower):
            return _clf("RFP_QA", HIGH, "Q&A filename inside RFP folder")
        if re.search(r"_old\b|_old\.", name_lower) or stem_lower.endswith("_old"):
            return _clf("RFP_WIP", HIGH, "_old suffix inside RFP folder")
        if re.search(r"\bstrategy\b", stem_lower):
            return _clf("Strategy", MEDIUM, "strategy filename inside RFP folder")
        # Everything else in RFP root that hasn't matched yet
        return _clf("RFP_WIP", MEDIUM, "inside RFP folder, no specific rule matched")

    # ── 16. STRATEGY — filename ───────────────────────────────────────────────
    if re.search(r"briefing\s*book", name_lower):
        return _clf("Strategy", HIGH, "briefing book")
    if re.search(r"\broadmap\b", name_lower):
        return _clf("Strategy", HIGH, "roadmap document")
    if re.search(r"transformation\s+journey", name_lower):
        return _clf("Strategy", HIGH, "transformation journey document")
    if re.search(r"\bstrategy\b", name_lower):
        return _clf("Strategy", MEDIUM, "strategy in filename")

    # ── 17. MEETING — filename ────────────────────────────────────────────────
    if re.search(r"meeting\s*notes?|notes?\s+\d+", name_lower):
        return _clf("Meeting", MEDIUM, "meeting notes in filename")

    # ── 18. PROPOSAL — filename ───────────────────────────────────────────────
    if re.search(r"proposal\s+presentation", name_lower):
        return _clf("Proposal", MEDIUM, "proposal presentation in filename")

    # ── 19. EXTENSION FALLBACKS ───────────────────────────────────────────────
    if ext == ".pptx":
        return _clf("Presentation", LOW, "unmatched .pptx fallback")
    if ext in (".pdf", ".docx", ".doc"):
        return _clf("Document", LOW, "unmatched document fallback")
    if ext in (".xlsx", ".xls"):
        return _clf("Spreadsheet", LOW, "unmatched spreadsheet fallback")
    if ext == ".csv":
        return _clf("Data", LOW, "CSV extension fallback")

    # ── 20. UNKNOWN ───────────────────────────────────────────────────────────
    return _clf("Unknown", LOW, f"no rule matched (ext: {ext or 'none'})")
