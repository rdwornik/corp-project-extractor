# Changelog — corp-project-extractor

## [0.1.0] — 2026-03-01

- Initial release: project folder classifier and orchestrator
- 20-priority classification rules (file-level before path-based)
- Click CLI: scan, extract, extract-cke, render, run, show
- CKE integration via subprocess (process-manifest)
- Local text extraction: PPTX, PDF, DOCX, XLSX, CSV
- Manifest generation with file hashing and merge support
- Renderer: aggregate CKE output to project-info.yaml, facts.yaml, index.md
- 45 tests passing
