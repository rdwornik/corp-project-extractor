"""Invoke corp-knowledge-extractor's batch CLI.

Runs CKE as a subprocess -- maintains CLI boundary per orchestrator pattern.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# CKE location -- configurable via config, default for this workstation
CKE_DIR = Path("C:/Users/1028120/Documents/Scripts/corp-knowledge-extractor")


def invoke_cke_batch(
    manifest_path: Path,
    resume: bool = True,
    max_rpm: int = 100,
    cke_dir: Path | None = None,
) -> subprocess.CompletedProcess:
    """Invoke CKE's process-manifest command.

    Args:
        manifest_path: Path to cke_manifest.json
        resume: Skip already-completed files
        max_rpm: Max Gemini API requests per minute
        cke_dir: Override CKE installation directory

    Returns:
        CompletedProcess with return code
    """
    cke = cke_dir or CKE_DIR

    # CKE has its own venv -- use its Python
    cke_python = cke / "venv" / "Scripts" / "python.exe"
    if not cke_python.exists():
        raise FileNotFoundError(
            f"CKE Python not found at {cke_python}. Ensure corp-knowledge-extractor is installed at {cke}"
        )

    run_script = cke / "scripts" / "run.py"
    if not run_script.exists():
        raise FileNotFoundError(f"CKE run script not found at {run_script}")

    cmd = [
        str(cke_python),
        str(run_script),
        "process-manifest",
        str(manifest_path.resolve()),
        "--max-rpm",
        str(max_rpm),
    ]

    if resume:
        cmd.append("--resume")

    logger.info("Invoking CKE: %s", " ".join(cmd))

    # Stream output to terminal in real-time
    result = subprocess.run(
        cmd,
        cwd=str(cke),
        capture_output=False,
        text=True,
    )

    if result.returncode != 0:
        logger.error("CKE exited with code %d", result.returncode)
    else:
        logger.info("CKE batch processing completed successfully")

    return result
