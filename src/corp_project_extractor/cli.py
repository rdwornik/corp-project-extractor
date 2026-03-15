"""Click CLI for corp-project-extractor. Entry point: cpe"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# ── Category colour map (Rich markup colours) ────────────────────────────────
CATEGORY_STYLE: dict[str, str] = {
    "RFP_Original": "green",
    "RFP_Response": "cyan",
    "RFP_WIP": "yellow",
    "RFP_QA": "blue",
    "Meeting": "magenta",
    "Demo": "bright_magenta",
    "Strategy": "bright_yellow",
    "Commercial": "bright_green",
    "Security": "dim",
    "Proposal": "bright_cyan",
    "Data": "bright_blue",
    "Presentation": "dim",
    "Document": "dim",
    "Spreadsheet": "dim",
    "Junk": "red",
    "Unknown": "dim red",
}

CONFIDENCE_STYLE: dict[str, str] = {
    "high": "green",
    "medium": "yellow",
    "low": "red",
}


def _conf_label(confidence: float) -> tuple[str, str]:
    if confidence >= 0.9:
        return "high", "green"
    elif confidence >= 0.6:
        return "medium", "yellow"
    else:
        return "low", "red"


def _fmt_size(kb: int) -> str:
    if kb < 1024:
        return f"{kb} KB"
    return f"{kb / 1024:.1f} MB"


# ── CLI group ─────────────────────────────────────────────────────────────────


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.option("--config", "config_path", type=click.Path(), default=None, help="Override config file path.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config_path: str | None) -> None:
    """Corp Project Extractor — scan, classify, extract, and render pre-sales knowledge."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["config_path"] = Path(config_path) if config_path else None
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    # Force config reload with custom path if provided
    if config_path:
        from corp_project_extractor.config import get_settings, reset_cache

        reset_cache()
        get_settings(Path(config_path))


# ── cpe scan ──────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False))
@click.pass_context
def scan(ctx: click.Context, project_path: str) -> None:
    """Classify all files in PROJECT_PATH and save _knowledge/manifest.yaml."""
    from corp_project_extractor import manifest as m

    path = Path(project_path)
    console.print("\n[bold]Corp Project Extractor — Scan[/bold]")
    console.print(f"Project: [cyan]{path.name}[/cyan]")
    console.print(f"Path:    [dim]{path}[/dim]\n")

    with console.status("[bold green]Scanning files…[/bold green]"):
        result, manifest_path = m.scan_and_save(path)

    _print_file_table(result.files)
    _print_summary_panel(result, manifest_path)


# ── cpe extract ───────────────────────────────────────────────────────────────


@cli.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False))
@click.option("--force", is_flag=True, help="Re-extract even if hash unchanged.")
@click.option("--skip-junk", "skip_junk", is_flag=True, default=True, help="Skip Junk and WIP files (default: True).")
@click.pass_context
def extract(ctx: click.Context, project_path: str, force: bool, skip_junk: bool) -> None:
    """Scan + extract text from all supported files in PROJECT_PATH."""
    from corp_project_extractor import manifest as m
    from corp_project_extractor import extractors

    path = Path(project_path)
    console.print("\n[bold]Corp Project Extractor — Extract[/bold]")
    console.print(f"Project: [cyan]{path.name}[/cyan]\n")

    with console.status("[bold green]Scanning files…[/bold green]"):
        result, _ = m.scan_and_save(path)

    to_extract = [
        f
        for f in result.files
        if f.extractable and (force or not f.extracted) and not (skip_junk and f.is_junk) and f.doc_role != "obsolete"
    ]

    console.print(f"Files to extract: [bold]{len(to_extract)}[/bold] (of {len(result.files)} total)\n")

    success = failed = skipped = 0
    for entry in to_extract:
        file_path = path / entry.rel_path
        try:
            res = extractors.extract(
                file_path,
                path,
                entry.category,
                entry.doc_role,
                entry.sha256,
            )
            if res.success and res.output_path:
                entry.extracted = True
                entry.extracted_path = str(res.output_path.relative_to(path)).replace("\\", "/")
                entry.word_count = res.word_count
                entry.extraction_error = None
                console.print(f"  [green]✓[/green] {entry.rel_path}  [dim]({res.word_count:,} words)[/dim]")
                success += 1
            else:
                entry.extraction_error = res.error
                console.print(f"  [dim]—[/dim] {entry.rel_path}  [dim]{res.error}[/dim]")
                skipped += 1
        except Exception as e:
            entry.extraction_error = str(e)
            console.print(f"  [red]✗[/red] {entry.rel_path}  [red]{e}[/red]")
            failed += 1

    m.save_manifest(path, result)
    console.print(
        f"\n[bold]Done.[/bold]  "
        f"Extracted: [green]{success}[/green]  "
        f"Skipped: [dim]{skipped}[/dim]  "
        f"Failed: [red]{failed}[/red]\n"
    )


# ── cpe extract-cke ──────────────────────────────────────────────────────────


@cli.command("extract-cke")
@click.argument("project_path", type=click.Path(exists=True, file_okay=False))
@click.option("--client", default=None, help="Client name (default: derived from folder name).")
@click.option("--resume/--no-resume", default=True, help="Skip already-extracted files.")
@click.option("--max-rpm", default=100, help="Max Gemini API requests per minute.")
@click.option("--dry-run", is_flag=True, help="Generate manifest only, don't invoke CKE.")
@click.pass_context
def extract_cke(
    ctx: click.Context, project_path: str, client: str | None, resume: bool, max_rpm: int, dry_run: bool
) -> None:
    """Extract knowledge via corp-knowledge-extractor (CKE) batch processing.

    Reads scan results, generates a CKE manifest, and invokes CKE's
    process-manifest command for LLM-powered extraction via Gemini.

    \b
    Examples:
        cpe extract-cke "C:\\path\\to\\Lenzing_Planning" --dry-run
        cpe extract-cke "C:\\path\\to\\Lenzing_Planning" --max-rpm 50
    """
    from corp_project_extractor.cke_invoker import invoke_cke_batch
    from corp_project_extractor.manifest import load_manifest, scan_and_save
    from corp_project_extractor.manifest_generator import generate_cke_manifest

    path = Path(project_path)
    console.print("\n[bold]Corp Project Extractor — Extract via CKE[/bold]")
    console.print(f"Project: [cyan]{path.name}[/cyan]\n")

    # Load existing manifest or run a fresh scan
    manifest = load_manifest(path)
    if manifest is None:
        console.print("[dim]No existing scan found, running scan...[/dim]")
        with console.status("[bold green]Scanning files...[/bold green]"):
            manifest, _ = scan_and_save(path)

    console.print(f"[bold]Scanned files:[/bold] {len(manifest.files)}")

    # Generate CKE manifest
    manifest_path = generate_cke_manifest(manifest, path, client_name=client)

    with open(manifest_path, "r", encoding="utf-8") as f:
        cke_data = json.load(f)

    n_files = len(cke_data["files"])
    console.print(f"[bold]CKE manifest:[/bold] {n_files} files to process")
    console.print(f"[bold]Output dir:[/bold] {cke_data['output_dir']}")

    if n_files == 0:
        console.print("\n[yellow]No processable files found.[/yellow]")
        return

    if dry_run:
        console.print(f"\n[yellow]Dry run — manifest saved to {manifest_path}[/yellow]")
        console.print("\nTo process manually:")
        console.print("  cd C:\\Users\\1028120\\Documents\\Scripts\\corp-knowledge-extractor")
        console.print(f'  python scripts/run.py process-manifest "{manifest_path}" --resume')
        return

    # Invoke CKE
    console.print("\n[bold]Starting extraction via CKE...[/bold]\n")
    result = invoke_cke_batch(
        manifest_path=manifest_path,
        resume=resume,
        max_rpm=max_rpm,
    )

    if result.returncode == 0:
        console.print("\n[bold green]Extraction complete.[/bold green]")
        console.print(f"Results in: {cke_data['output_dir']}")
    else:
        console.print(f"\n[bold red]CKE exited with errors (code {result.returncode}).[/bold red]")


# ── cpe render ────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False))
@click.option("--copy-to-vault", type=click.Path(), default=None, help="Copy index.md to Obsidian vault path.")
@click.pass_context
def render(ctx: click.Context, project_path: str, copy_to_vault: str | None) -> None:
    """Render project knowledge from CKE extraction results.

    Generates project-info.yaml (com compatible), facts.yaml,
    and index.md (Obsidian) from CKE extract.json files.
    """
    from corp_project_extractor.renderer import render_project

    path = Path(project_path)
    console.print("\n[bold]Corp Project Extractor — Render[/bold]")
    console.print(f"Project: [cyan]{path.name}[/cyan]\n")

    try:
        stats = render_project(path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    console.print("[green]Done.[/green]")
    console.print(f"  Extractions: {stats['extractions']}")
    console.print(f"  Topics:      {stats['topics']}")
    console.print(f"  Products:    {stats['products']}")
    console.print(f"  People:      {stats['people']}")
    console.print(f"  Facts:       {stats['facts']}")

    from corp_project_extractor.config import get_settings

    knowledge_dir = path / get_settings().knowledge_dir
    console.print(f"\n  [dim]{knowledge_dir / 'project-info.yaml'}[/dim]")
    console.print(f"  [dim]{knowledge_dir / 'facts.yaml'}[/dim]")
    console.print(f"  [dim]{knowledge_dir / 'index.md'}[/dim]")

    if copy_to_vault:
        import shutil

        vault_dir = Path(copy_to_vault) / path.name
        vault_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(knowledge_dir / "index.md", vault_dir / "index.md")
        console.print(f"\n  Copied to vault: [cyan]{vault_dir / 'index.md'}[/cyan]")


# ── cpe show ──────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False))
@click.pass_context
def show(ctx: click.Context, project_path: str) -> None:
    """Display existing manifest as a Rich table (no rescan)."""
    from corp_project_extractor import manifest as m
    from corp_project_extractor.config import get_settings

    path = Path(project_path)
    settings = get_settings()
    manifest_path = path / settings.knowledge_dir / "manifest.yaml"
    if not manifest_path.exists():
        console.print(f"[red]No manifest found.[/red] Run [bold]cpe scan {project_path}[/bold] first.")
        sys.exit(1)
    result = m.load_manifest(path)
    if result is None:
        console.print("[red]Failed to load manifest.[/red]")
        sys.exit(1)
    _print_file_table(result.files)
    _print_summary_panel(result, manifest_path)


# ── cpe run ───────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False))
@click.pass_context
def run(ctx: click.Context, project_path: str) -> None:
    """Full pipeline: scan -> extract -> render."""
    ctx.invoke(scan, project_path=project_path)
    ctx.invoke(extract, project_path=project_path, force=False, skip_junk=True)
    ctx.invoke(render, project_path=project_path)


# ── Rich output helpers ───────────────────────────────────────────────────────


def _print_file_table(files: list) -> None:
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold", expand=False, highlight=False)
    table.add_column("Category", min_width=14, no_wrap=True)
    table.add_column("Role", min_width=14, no_wrap=True)
    table.add_column("Ext", min_width=5, no_wrap=True)
    table.add_column("KB", min_width=7, justify="right", no_wrap=True)
    table.add_column("Words", min_width=6, justify="right", no_wrap=True)
    table.add_column("File", min_width=30)
    table.add_column("Status", min_width=8, no_wrap=True)

    for f in files:
        cat_style = CATEGORY_STYLE.get(f.category, "")
        conf_label, conf_style = _conf_label(f.confidence)

        # File column: dim folder prefix, bold filename
        parts = f.rel_path.split("/")
        if len(parts) > 1:
            file_text = Text()
            file_text.append("/".join(parts[:-1]) + "/", style="dim")
            file_text.append(parts[-1])
        else:
            file_text = Text(f.rel_path)

        # Status
        if f.is_junk:
            status = Text("🔴 JUNK", style="red")
        elif f.category == "Security":
            status = Text("— skip", style="dim")
        elif f.doc_role == "obsolete":
            status = Text("— skip", style="dim")
        elif f.extracted:
            status = Text("✅", style="green")
        elif f.extraction_error:
            status = Text("⚠ err", style="red")
        elif not f.extractable:
            status = Text("— n/a", style="dim")
        else:
            status = Text("⬜ pending", style="dim")

        words = f"{f.word_count:,}" if f.word_count else "—"

        table.add_row(
            Text(f.category, style=cat_style),
            Text(f.doc_role, style="dim"),
            Text(f.extension, style="dim"),
            _fmt_size(f.size_kb),
            words,
            file_text,
            status,
        )

    console.print(table)


def _print_summary_panel(result, manifest_path: Path) -> None:
    counts: Counter = Counter(f.category for f in result.files)
    extracted_counts: Counter = Counter(f.category for f in result.files if f.extracted)
    word_totals: dict[str, int] = {}
    for f in result.files:
        word_totals[f.category] = word_totals.get(f.category, 0) + f.word_count

    rows: list[str] = []
    for cat, count in sorted(counts.items(), key=lambda x: -x[1]):
        style = CATEGORY_STYLE.get(cat, "")
        extr = extracted_counts.get(cat, 0)
        words = word_totals.get(cat, 0)
        extr_str = f"{extr} extracted" if extr else "— pending"
        word_str = f"   {words:,} words" if words else ""
        rows.append(f"[{style}]{cat:<16}[/{style}]  {count:>3} file(s)  {extr_str:<14}{word_str}")

    rows.append("")
    rows.append(f"[dim]Total: {len(result.files)} files  |  Scanned: {result.last_scanned}[/dim]")
    rows.append(f"[dim]Manifest: {manifest_path}[/dim]")

    console.print(
        Panel(
            "\n".join(rows),
            title=f"[bold]{result.project_id}[/bold]",
            border_style="dim",
            padding=(0, 1),
        )
    )
    console.print()
