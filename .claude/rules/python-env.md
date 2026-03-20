# Python Environment — corp-project-extractor

- Python >=3.10, target 3.12
- Virtual env: .venv\Scripts\Activate.ps1
- Install: pip install -e ".[dev]"
- This is an ORCHESTRATOR — classifies files, delegates extraction to CKE via subprocess
- No shared library imports with CKE — clean process boundary
- CKE path currently hardcoded in cke_invoker.py (known issue)
