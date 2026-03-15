"""YAML config loader + Settings dataclass. Expands ${ENV_VAR} from .env."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Try dotenv; gracefully degrade if not yet installed (bootstrap phase)
try:
    from dotenv import load_dotenv

    _HAS_DOTENV = True
except ImportError:  # pragma: no cover
    _HAS_DOTENV = False

_PACKAGE_ROOT = Path(__file__).parent  # src/corp_project_extractor/
_PROJECT_ROOT = _PACKAGE_ROOT.parent.parent  # repo root
CONFIG_DIR = _PROJECT_ROOT / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "default.yaml"

_QUESTIONNAIRE_DEFAULTS = [
    "Q&A",
    "Questionnaire",
    "Requirements",
    "Business",
    "Service and Technical",
    "Commercials",
    "Forecast",
    "Questions",
]
_SKIP_EXT_DEFAULTS = [
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".svg",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".zip",
    ".rar",
    ".7z",
    ".exe",
    ".msi",
    ".dll",
    ".lnk",
]


@dataclass
class ExtractionConfig:
    pptx_include_notes: bool = True
    pptx_include_slide_numbers: bool = True
    xlsx_questionnaire_markers: list[str] = field(default_factory=lambda: list(_QUESTIONNAIRE_DEFAULTS))
    xlsx_data_mode_max_rows: int = 10
    xlsx_questionnaire_max_rows: int = 500
    xlsx_cell_truncate_chars: int = 200
    max_file_size_mb: int = 100


@dataclass
class Settings:
    projects_root: str = ""
    archive_root: str = ""
    pdf_toolkit_path: str = ""
    knowledge_dir: str = "_knowledge"
    extracted_dir: str = "_extracted"
    junk_markers: list[str] = field(
        default_factory=lambda: [
            "DO NOT USE",
            "NOT USE!",
            "OLD!!",
            "~$",
            "Thumbs.db",
            ".DS_Store",
            "backup",
        ]
    )
    skip_extensions: list[str] = field(default_factory=lambda: list(_SKIP_EXT_DEFAULTS))
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)


_cached: Settings | None = None


def _expand_env(obj):
    """Recursively expand ${ENV_VAR} references."""
    if isinstance(obj, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), obj)
    if isinstance(obj, dict):
        return {k: _expand_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env(v) for v in obj]
    return obj


def get_settings(config_path: Path | None = None) -> Settings:
    global _cached
    if _cached is not None and config_path is None:
        return _cached

    # Load .env from repo root
    env_file = _PROJECT_ROOT / ".env"
    if _HAS_DOTENV and env_file.exists():
        load_dotenv(env_file)

    path = config_path or DEFAULT_CONFIG_PATH
    if path.exists():
        with open(path, encoding="utf-8") as f:
            raw = _expand_env(yaml.safe_load(f) or {})
    else:
        raw = {}

    paths = raw.get("paths", {})
    cls_cfg = raw.get("classification", {})
    ext_cfg = raw.get("extraction", {})
    xlsx_cfg = ext_cfg.get("xlsx", {})
    out_cfg = raw.get("output", {})

    extraction = ExtractionConfig(
        pptx_include_notes=ext_cfg.get("pptx", {}).get("include_notes", True),
        pptx_include_slide_numbers=ext_cfg.get("pptx", {}).get("include_slide_numbers", True),
        xlsx_questionnaire_markers=xlsx_cfg.get("questionnaire_markers", list(_QUESTIONNAIRE_DEFAULTS)),
        xlsx_data_mode_max_rows=xlsx_cfg.get("data_mode_max_rows", 10),
        xlsx_questionnaire_max_rows=xlsx_cfg.get("questionnaire_max_rows", 500),
        xlsx_cell_truncate_chars=xlsx_cfg.get("cell_truncate_chars", 200),
        max_file_size_mb=cls_cfg.get("max_file_size_mb", 100),
    )

    s = Settings(
        projects_root=paths.get("projects_root", ""),
        archive_root=paths.get("archive_root", ""),
        pdf_toolkit_path=paths.get("pdf_toolkit_path", ""),
        knowledge_dir=out_cfg.get("knowledge_dir", "_knowledge"),
        extracted_dir=out_cfg.get("extracted_dir", "_extracted"),
        junk_markers=cls_cfg.get("junk_markers", Settings.__dataclass_fields__["junk_markers"].default_factory()),
        skip_extensions=cls_cfg.get("skip_extensions", list(_SKIP_EXT_DEFAULTS)),
        extraction=extraction,
    )
    _cached = s
    return s


def reset_cache() -> None:
    """Force reload on next call (useful in tests)."""
    global _cached
    _cached = None
