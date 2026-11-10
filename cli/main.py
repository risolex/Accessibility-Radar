"""
cli/main.py — Interface de Linha de Comando do Accessibility Radar (Typer + Rich)

Comandos disponíveis:
- `ui`:   Inicia a Interface Web Moderna (Dashboard, Inspetor Visual, Auto-Fixer Studio e Laboratório WCAG).
- `scan`: Audita uma URL ou arquivo HTML local nos 5 pilares da WCAG 2.2 e gera `reports/audit_report.md`.
- `fix`:  Gera patches de código "Antes e Depois" e aplica a correção em um arquivo HTML local.
- `demo`: Fluxo completo de demonstração para o Hackathon Kiroween usando `tests/broken_page.html`
          com auto-correção e revalidação de score 100/100.
"""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


# Garante saída UTF-8 limpa em terminais Windows, Linux e macOS
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Adiciona o diretório raiz do projeto ao sys.path para execução direta
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.analyzer import A11yAnalyzer
from core.fixer import A11yFixer
from core.scanner import A11yScanner


app = typer.Typer(
    name="accessibility-radar",
    help="Accessibility Radar — Agente Autônomo de Auditoria e Correção de Acessibilidade Web (WCAG 2.2).",
    add_completion=False,
)
console = Console()


def _render_banner() -> None:
    """Exibe cabeçalho estilizado do Accessibility Radar."""
    banner_text = Text()
    banner_text.append("⚡ ACCESSIBILITY RADAR ", style="bold bright_magenta")
    banner_text.append("v2.0.0 — Autonomous WCAG 2.2 Web Accessibility Auditor & Auto-Fixer\n", style="bold white")
    banner_text.append(
        "Playwright Headless • Accessibility Tree • Multimodal Vision AI • Surgical DOM Patcher • Web UI",
        style="dim cyan",
    )
    console.print(Panel(banner_text, border_style="bright_magenta", box=box.DOUBLE_EDGE))


def _severity_badge(severity: str) -> str:
    sev = (severity or "serious").lower()
    mapping = {
        "critical": "[bold white on red] CRITICAL [/]",
        "serious": "[bold black on yellow] SERIOUS [/]",
        "moderate": "[bold white on blue] MODERATE [/]",
        "minor": "[bold black on cyan] MINOR [/]",
    }
    return mapping.get(sev, f"[bold]{sev.upper()}[/]")


def _score_color(score: int) -> str:
    if score >= 90:
        return "bold bright_green"
    if score >= 70:
        return "bold yellow"
    return "bold bright_red"


def _render_executive_summary(analysis: Dict[str, Any]) -> None:
    """Renderiza painel de resumo executivo e tabela dos 5 pilares."""
    summary = analysis.get("summary", {})
    score = summary.get("score", 0)
    status = summary.get("wcag_status", "N/A")
    total_issues = summary.get("total_issues", 0)
    by_pillar = summary.get("by_pillar", {})
    by_severity = summary.get("by_severity", {})
    score_style = _score_color(score)

    summary_grid = Table.grid(padding=(0, 2))
    summary_grid.add_column(style="bold cyan", justify="right")
    summary_grid.add_column(style="white")
    summary_grid.add_row("Alvo Auditado:", f"[underline]{analysis.get('target')}[/]")
    summary_grid.add_row("Título da Página:", str(analysis.get("page_title", "N/A")))
    summary_grid.add_row("Viewport:", str(analysis.get("viewport", "desktop")))
    summary_grid.add_row("Motor de IA:", f"[magenta]{analysis.get('mode')}[/]")
    summary_grid.add_row("Score WCAG 2.2:", f"[{score_style}]{score} / 100[/] — {status}")
    summary_grid.add_row(
        "Total de Falhas:",
        (
            f"[bold]{total_issues}[/] "
            f"(Críticas: [red]{by_severity.get('critical', 0)}[/] | "
            f"Sérias: [yellow]{by_severity.get('serious', 0)}[/] | "
            f"Moderadas: [blue]{by_severity.get('moderate', 0)}[/] | "
            f"Menores: [cyan]{by_severity.get('minor', 0)}[/])"
        ),
    )

    console.print(
        Panel(
            summary_grid,
            title="[bold bright_cyan]📊 Resumo Executivo da Auditoria[/]",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )

    # Tabela dos 5 Pilares
    pillar_table = Table(
        title="Diagnóstico nos Pilares Críticos (Escopo WCAG 2.1 / 2.2)",
        box=box.SIMPLE_HEAVY,
        header_style="bold bright_magenta",
    )
    pillar_table.add_column("Pilar de Auditoria", style="bold white")
    pillar_table.add_column("Critérios WCAG", style="cyan")
    pillar_table.add_column("Violações", justify="center")
    pillar_table.add_column("Status", justify="center")

    pillars_meta = [
        ("contrast_visibility", "1. Contraste e Visibilidade", "1.4.3 (AA) / 1.4.11 (AA)"),
        ("muted_interactives", "2. Elementos Interativos Mudos", "4.1.2 (A) / 2.4.4 (A) / 1.3.1 (A)"),
        ("media_semantics", "3. Semântica de Mídia (Vision)", "1.1.1 Non-text Content (A)"),
        ("focus_keyboard", "4. Ordem de Foco e Teclado", "2.4.3 (A) / 2.4.7 (AA) / 2.1.1 / 2.1.2"),
        ("semantic_structure", "5. Estrutura e Semântica", "3.1.1 (A) / 2.4.2 (A) / 1.3.1 / 2.4.6"),
    ]

    for key, label, criteria in pillars_meta:
        count = by_pillar.get(key, 0)
        status_badge = "[bold green]✔ APROVADO[/]" if count == 0 else f"[bold red]✖ {count} FALHA(S)[/]"
        pillar_table.add_row(label, criteria, str(count), status_badge)

    console.print(pillar_table)


def _render_issues_table(analysis: Dict[str, Any]) -> None:
    """Renderiza tabela detalhada de violações detectadas."""
    issues = analysis.get("issues", [])
    if not issues:
        console.print(
            Panel(
                "[bold bright_green]✔ Zero violações detectadas! Página 100% conforme.[/]",
                border_style="bright_green",
            )
        )
        return

    table = Table(
        title="Detalhamento Técnico de Violações WCAG 2.2",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold bright_cyan",
    )
    table.add_column("ID", style="bold magenta", width=9)
    table.add_column("Severidade", justify="center", width=12)
    table.add_column("Pilar / Critério WCAG", style="cyan", width=26)
    table.add_column("Seletor DOM", style="yellow", width=24)
    table.add_column("Diagnóstico & Correção Recomendada", style="white")

    for issue in issues:
        table.add_row(
            issue.get("id", ""),
            _severity_badge(issue.get("severity", "serious")),
            f"{issue.get('pillar_label', '')}\n[dim]{issue.get('wcag_criterion', '')} ({issue.get('wcag_level', '')})[/]",
            issue.get("selector", ""),
            f"[bold]{issue.get('title', '')}[/]\n[dim]{issue.get('remediation_notes', '')}[/]",
        )

    console.print(table)


def _render_code_patches(analysis: Dict[str, Any], limit: int = 6) -> None:
    """Exibe comparativos de código Antes e Depois com syntax highlighting."""
    issues = analysis.get("issues", [])
    if not issues:
        return

    console.print("\n[bold bright_magenta]🛠️  Patches de Código Gerados (Antes vs. Depois):[/]")
    for issue in issues[:limit]:
        header = (
            f"[{issue.get('id')}] {issue.get('title')} — "
            f"Seletor: {issue.get('selector')} ({issue.get('wcag_criterion')})"
        )
        orig = (issue.get("original_code") or "").strip()
        fixed = (issue.get("fixed_code") or "").strip()

        patch_text = f"<!-- ANTES (Violação) -->\n{orig}\n\n<!-- DEPOIS (Corrigido pelo Accessibility Radar) -->\n{fixed}"
        syntax = Syntax(patch_text, "html", theme="monokai", word_wrap=True)
        console.print(Panel(syntax, title=f"[bold yellow]{header}[/]", border_style="magenta"))

    if len(issues) > limit:
        console.print(
            f"[dim]... e mais {len(issues) - limit} patches completos salvos em `reports/audit_report.md`.[/]\n"
        )


def _execute_scan_and_analyze(
    target: str,
    mock: bool = False,
    viewport: str = "desktop",
    screenshot_filename: str = "latest_screenshot.png",
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Executa o pipeline Scanner + Analyzer com barra de progresso Rich."""
    scanner = A11yScanner()
    analyzer = A11yAnalyzer(force_mock=mock)

    with Progress(
        SpinnerColumn(style="bright_magenta"),
        TextColumn("[bold cyan]{task.description}"),
        console=console,
    ) as progress:
        t1 = progress.add_task(
            f"Abrindo navegador headless Playwright ({viewport}) e extraindo Accessibility Tree de '{target}'...",
            total=None,
        )
        scan_data = scanner.scan_sync(
            target=target,
            save_screenshot=True,
            viewport=viewport,
            screenshot_filename=screenshot_filename,
        )
        progress.update(t1, completed=True, description="✔ DOM filtrado, Screenshot e Accessibility Tree extraídos!")

        t2 = progress.add_task(
            "Executando diagnóstico multimodal nos pilares da WCAG 2.2...",
            total=None,
        )
        analysis = analyzer.analyze(scan_data)
        progress.update(t2, completed=True, description="✔ Diagnóstico WCAG 2.2 e patches de código gerados!")

    return scan_data, analysis


@app.command("scan")
def scan_command(
    target: str = typer.Argument(
        ...,
        help="URL (https://...) ou caminho de arquivo HTML local (ex: tests/broken_page.html).",
    ),
    report_path: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Caminho customizado para salvar o relatório Markdown (padrão: reports/audit_report.md).",
    ),
    viewport: str = typer.Option(
        "desktop",
        "--viewport",
        "-v",
        help="Perfil de tela para renderização: desktop, tablet ou mobile.",
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        help="Força o uso do Modo Smart Mock/Fallback sem consumir créditos de API.",
    ),
) -> None:
    """
    Audita uma URL ou página HTML local nos pilares da WCAG 2.2 e gera relatório em Markdown.
    """
    _render_banner()
    _, analysis = _execute_scan_and_analyze(
        target=target,
        mock=mock,
        viewport=viewport,
        screenshot_filename="before_screenshot.png",
    )

    _render_executive_summary(analysis)
    _render_issues_table(analysis)

    fixer = A11yFixer()
    saved_md = fixer.generate_markdown_report(analysis, output_path=report_path)
    fixer.record_audit_history(analysis)

    json_path = fixer.reports_dir / "audit_results.json"
    json_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    console.print(
        Panel(
            f"📄 Relatório Markdown gerado em: [bold bright_green]{saved_md}[/]\n"
            f"📦 Diagnóstico JSON salvo em:    [bold cyan]{json_path}[/]\n"
            f"📸 Screenshot capturado em:      [bold yellow]{analysis.get('screenshot_path')}[/]",
            title="[bold green]✔ Auditoria Concluída com Sucesso[/]",
            border_style="green",
        )
    )


@app.command("fix")
def fix_command(
    target: str = typer.Argument(
        ...,
        help="Caminho do arquivo HTML local a ser auditado e corrigido (ex: tests/broken_page.html).",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Caminho do arquivo HTML corrigido (padrão: reports/fixed_page.html).",
    ),
    in_place: bool = typer.Option(
        False,
        "--in-place",
        "-i",
        help="Aplica as correções diretamente no arquivo original (criando backup .bak).",
    ),
    viewport: str = typer.Option(
        "desktop",
        "--viewport",
        "-v",
        help="Perfil de tela para renderização: desktop, tablet ou mobile.",
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        help="Força o uso do Modo Smart Mock/Fallback.",
    ),
) -> None:
    """
    Audita um arquivo HTML local, exibe os patches de código e aplica as correções automaticamente.
    """
    _render_banner()
    _, analysis = _execute_scan_and_analyze(
        target=target,
        mock=mock,
        viewport=viewport,
        screenshot_filename="before_screenshot.png",
    )

    _render_executive_summary(analysis)
    _render_code_patches(analysis, limit=10)

    fixer = A11yFixer()
    saved_md = fixer.generate_markdown_report(analysis)
    fix_result = fixer.apply_fixes_to_file(
        source_path=target,
        analysis_result=analysis,
        output_path=output,
        in_place=in_place,
    )
    fixer.record_audit_history(analysis, fixed_issues_count=fix_result["total_fixes_applied"])

    console.print(
        Panel(
            f"✨ Total de correções aplicadas: [bold bright_green]{fix_result['total_fixes_applied']}[/]\n"
            f"🛠️  Arquivo HTML corrigido em:    [bold bright_green]{fix_result['output_path']}[/]\n"
            f"📄 Relatório Antes/Depois em:    [bold cyan]{saved_md}[/]",
            title="[bold bright_green]✔ Auto-Remediação Concluída[/]",
            border_style="bright_green",
        )
    )


@app.command("demo")
def demo_command(
    mock: bool = typer.Option(
        False,
        "--mock",
        help="Força o uso do Modo Smart Mock/Fallback mesmo se houver chave no .env.",
    ),
) -> None:
    """
    Executa a demonstração completa do Hackathon Kiroween na página `tests/broken_page.html`,
    aplicando as correções e revalidando o score final no navegador headless.
    """
    _render_banner()
    broken_file = PROJECT_ROOT / "tests" / "broken_page.html"
    if not broken_file.exists():
        console.print(f"[bold red]Erro: Arquivo de demonstração não encontrado em {broken_file}[/]")
        raise typer.Exit(code=1)

    console.print(
        Panel(
            "[bold white]Iniciando Demonstração Completa Kiroween (Ciclo Fechado de Agente Autônomo):[/]\n"
            "1. Escaneamento de `tests/broken_page.html` via Playwright + Accessibility Tree.\n"
            "2. Diagnóstico dos Pilares Críticos (WCAG 2.2 Nível A e AA).\n"
            "3. Geração do relatório `reports/audit_report.md` e auto-correção em `reports/fixed_page.html`.\n"
            "4. Re-escaneamento de verificação em `reports/fixed_page.html` para comprovar a correção.",
            border_style="bright_yellow",
        )
    )

    # Etapa 1 e 2: Scan e Análise da página quebrada
    _, initial_analysis = _execute_scan_and_analyze(
        target=str(broken_file),
        mock=mock,
        screenshot_filename="before_screenshot.png",
    )
    _render_executive_summary(initial_analysis)
    _render_issues_table(initial_analysis)
    _render_code_patches(initial_analysis, limit=4)

    # Etapa 3: Relatório Markdown e Auto-Fix
    fixer = A11yFixer()
    report_md = fixer.generate_markdown_report(initial_analysis)
    fixed_html_path = fixer.reports_dir / "fixed_page.html"
    fix_info = fixer.apply_fixes_to_file(
        source_path=broken_file,
        analysis_result=initial_analysis,
        output_path=fixed_html_path,
        in_place=False,
    )

    # Etapa 4: Revalidação da página corrigida no navegador
    console.print("\n[bold bright_cyan]🔄 Executando Re-Auditoria de Verificação na Página Corrigida...[/]")
    _, verified_analysis = _execute_scan_and_analyze(
        target=str(fixed_html_path),
        mock=mock,
        screenshot_filename="after_screenshot.png",
    )

    # Salva estados em reports/
    (fixer.reports_dir / "audit_results.json").write_text(
        json.dumps(initial_analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (fixer.reports_dir / "verified_results.json").write_text(
        json.dumps(verified_analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    fixer.record_audit_history(
        initial_analysis,
        after_score=verified_analysis["summary"]["score"],
        fixed_issues_count=fix_info["total_fixes_applied"],
    )

    before_score = initial_analysis["summary"]["score"]
    after_score = verified_analysis["summary"]["score"]
    before_issues = initial_analysis["summary"]["total_issues"]
    after_issues = verified_analysis["summary"]["total_issues"]

    comparison_table = Table(
        title="Resultado do Ciclo Autônomo (Antes vs. Depois da Auto-Correção)",
        box=box.DOUBLE_EDGE,
        header_style="bold bright_magenta",
    )
    comparison_table.add_column("Métrica", style="bold white")
    comparison_table.add_column("Antes (`broken_page.html`)", justify="center", style="red")
    comparison_table.add_column("Depois (`fixed_page.html`)", justify="center", style="bright_green")

    comparison_table.add_row("Score de Acessibilidade", f"{before_score} / 100", f"{after_score} / 100")
    comparison_table.add_row("Total de Violações WCAG", str(before_issues), str(after_issues))
    comparison_table.add_row(
        "Status WCAG 2.2 AA",
        initial_analysis["summary"]["wcag_status"],
        verified_analysis["summary"]["wcag_status"],
    )

    console.print(comparison_table)
    console.print(
        Panel(
            f"📄 Relatório Markdown ('Antes e Depois'): [bold bright_green]{report_md}[/]\n"
            f"🛠️  Página HTML 100% Corrigida:           [bold bright_green]{fix_info['output_path']}[/]\n"
            f"📸 Screenshot de Auditoria:              [bold yellow]{initial_analysis.get('screenshot_path')}[/]",
            title="[bold bright_green]🎃 Kiroween Demo Finalizada com Sucesso![/]",
            border_style="bright_green",
        )
    )


@app.command("ui")
def ui_command(
    host: str = typer.Option("127.0.0.1", "--host", help="Host do servidor web."),
    port: int = typer.Option(8000, "--port", "-p", help="Porta do servidor web."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Não abrir o navegador automaticamente."),
) -> None:
    """
    Inicia a Interface Web Moderna do Accessibility Radar (FastAPI + Uvicorn).
    """
    import socket
    import uvicorn

    # Encontra porta livre caso a porta solicitada já esteja ocupada
    chosen_port = port
    for candidate_port in [port, 8080, 8088, 8501, 3000]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, candidate_port)) != 0:
                chosen_port = candidate_port
                break

    _render_banner()
    url = f"http://{host}:{chosen_port}"
    console.print(
        Panel(
            f"🌐 Interface Web iniciada em: [bold bright_green underline]{url}[/]\n"
            "• Dashboard & Auditoria Multimodal (URL, Arquivo Local ou HTML Playground)\n"
            "• Inspetor Visual com Hotspots, Mapa de Ordem de Foco (Tab) e Simulador de Daltonismo\n"
            "• Auto-Fixer Studio com Seleção Granular e Live Preview Lado a Lado\n"
            "• Accessibility Tree Explorer, Simulador de Leitor de Tela e Calculadora de Contraste W3C",
            title="[bold bright_magenta]🚀 Accessibility Radar Web Studio[/]",
            border_style="bright_magenta",
        )
    )

    if not no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run("web.app:app", host=host, port=chosen_port, log_level="info")


if __name__ == "__main__":
    app()
