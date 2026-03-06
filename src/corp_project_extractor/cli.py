"""Click CLI for corp-project-extractor. Entry point: cpe"""
from __future__ import annotations

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
    "RFP_Original":  "green",
    "RFP_Response":  "cyan",
    "RFP_WIP":       "yellow",
    "RFP_QA":        "blue",
    "Meeting":       "magenta",
    "Demo":          "bright_magenta",
    "Strategy":      "bright_yellow",
    "Commercial":    "bright_green",
    "Security":      "dim",
    "Proposal":      "bright_cyan",
    "Data":          "bright_blue",
    "Presentation":  "dim",
    "Document":      "dim",
    "Spreadsheet":   "dim",
    "Junk":          "red",
    "Unknown":       "dim red",
}

CONFIDENCE_STYLE: dict[str, str] = {
    "high":   "green",
    "medium": "yellow",
    "low":    "red",
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
@click.option("--config", "config_path", type=click.Path(), default=None,
              help="Override config file path.")
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
    console.print(f"\n[bold]Corp Project Extractor — Scan[/bold]")
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
@click.option("--skip-junk", "skip_junk", is_flag=True, default=True,
              help="Skip Junk and WIP files (default: True).")
@click.pass_context
def extract(ctx: click.Context, project_path: str, force: bool, skip_junk: bool) -> None:
    """Scan + extract text from all supported files in PROJECT_PATH."""
    from corp_project_extractor import manifest as m
    from corp_project_extractor import extractors

    path = Path(project_path)
    console.print(f"\n[bold]Corp Project Extractor — Extract[/bold]")
    console.print(f"Project: [cyan]{path.name}[/cyan]\n")

    with console.status("[bold green]Scanning files…[/bold green]"):
        result, _ = m.scan_and_save(path)

    to_extract = [
        f for f in result.files
        if f.extractable
        and (force or not f.extracted)
        and not (skip_junk and f.is_junk)
        and f.doc_role != "obsolete"
    ]

    console.print(f"Files to extract: [bold]{len(to_extract)}[/bold] "
                  f"(of {len(result.files)} total)\n")

    success = failed = skipped = 0
    for entry in to_extract:
        file_path = path / entry.rel_path
        try:
            res = extractors.extract(
                file_path, path, entry.category, entry.doc_role, entry.sha256,
            )
            if res.success and res.output_path:
                entry.extracted = True
                entry.extracted_path = str(res.output_path.relative_to(path)).replace("\\", "/")
                entry.word_count = res.word_count
                entry.extraction_error = None
                console.print(f"  [green]✓[/green] {entry.rel_path}  "
                              f"[dim]({res.word_count:,} words)[/dim]")
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


# ── cpe render ────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False))
@click.pass_context
def render(ctx: click.Context, project_path: str) -> None:
    """Generate _knowledge/knowledge-sheet.md from _knowledge/facts.yaml."""
    from corp_project_extractor import renderer

    path = Path(project_path)
    console.print(f"\n[bold]Corp Project Extractor — Render[/bold]")
    console.print(f"Project: [cyan]{path.name}[/cyan]\n")
    try:
        out_path = renderer.render(path)
        console.print(f"[green]✓[/green] Written: [cyan]{out_path}[/cyan]\n")
    except FileNotFoundError as e:
        console.print(f"[red]✗[/red] {e}\n")
        sys.exit(1)


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
    """Full pipeline: scan → extract → render."""
    ctx.invoke(scan, project_path=project_path)
    ctx.invoke(extract, project_path=project_path, force=False, skip_junk=True)
    ctx.invoke(render, project_path=project_path)


# ── Rich output helpers ───────────────────────────────────────────────────────

def _print_file_table(files: list) -> None:
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold",
                  expand=False, highlight=False)
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
    extracted_counts: Counter = Counter(
        f.category for f in result.files if f.extracted
    )
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
        rows.append(
            f"[{style}]{cat:<16}[/{style}]  {count:>3} file(s)  {extr_str:<14}{word_str}"
        )

    rows.append("")
    rows.append(f"[dim]Total: {len(result.files)} files  |  Scanned: {result.last_scanned}[/dim]")
    rows.append(f"[dim]Manifest: {manifest_path}[/dim]")

    console.print(Panel(
        "\n".join(rows),
        title=f"[bold]{result.project_id}[/bold]",
        border_style="dim",
        padding=(0, 1),
    ))
    console.print()
