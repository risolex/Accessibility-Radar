"""
web/app.py — Servidor FastAPI e API REST do Accessibility Radar

Fornece endpoints assíncronos para:
- Escaneamento de URLs remotas, arquivos HTML locais ou código HTML bruto (Playground)
- Ciclo completo de demonstração autônoma (`demo`) com comparação Antes vs. Depois
- Auto-remediação cirúrgica e seletiva (`selected_issue_ids` + `custom_overrides`) com revalidação
- Histórico de auditorias (`reports/history.json`)
- Configuração de provedores de IA (`.env`) e laboratório de contraste W3C
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv, set_key
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.analyzer import A11yAnalyzer
from core.fixer import A11yFixer
from core.scanner import A11yScanner


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
STATIC_DIR = Path(__file__).resolve().parent / "static"
TESTS_DIR = PROJECT_ROOT / "tests"
ENV_FILE = PROJECT_ROOT / ".env"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Accessibility Radar Web UI & API",
    description="Interface Web e API para Auditoria e Auto-Correção de Acessibilidade Web (WCAG 2.2)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_Methods=["*"],
    allow_headers=["*"],
) if False else app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# =============================================================================
# Schemas Pydantic
# =============================================================================

class ScanRequest(BaseModel):
    target: Optional[str] = Field(default="tests/broken_page.html", description="URL ou caminho de arquivo local")
    raw_html: Optional[str] = Field(default=None, description="Código HTML bruto colado ou enviado via upload")
    filename: Optional[str] = Field(default="playground_input.html", description="Nome do arquivo temporário")
    viewport: str = Field(default="desktop", description="desktop | tablet | mobile")
    mock: bool = Field(default=False, description="Forçar modo Smart Mock determinístico")


class FixRequest(BaseModel):
    target: Optional[str] = Field(default=None, description="Caminho do arquivo local a corrigir")
    selected_issue_ids: Optional[List[str]] = Field(default=None, description="IDs das issues selecionadas")
    custom_overrides: Optional[Dict[str, str]] = Field(default=None, description="Valores customizados por ID")
    in_place: bool = Field(default=False, description="Sobrescrever arquivo original criando .bak")
    reverify: bool = Field(default=True, description="Re-escanear página corrigida para comprovar o novo score")
    viewport: str = Field(default="desktop", description="desktop | tablet | mobile")
    mock: bool = Field(default=False, description="Forçar modo Smart Mock determinístico")


class DemoRequest(BaseModel):
    viewport: str = Field(default="desktop", description="desktop | tablet | mobile")
    mock: bool = Field(default=False, description="Forçar modo Smart Mock determinístico")


class SettingsUpdateRequest(BaseModel):
    ai_base_url: str = Field(default="https://openrouter.ai/api/v1")
    ai_api_key: Optional[str] = Field(default=None)
    ai_model_text: str = Field(default="openai/gpt-4o-mini")
    ai_model_vision: str = Field(default="openai/gpt-4o-mini")


class ContrastCheckRequest(BaseModel):
    foreground: str = Field(default="#b4b8c2")
    background: str = Field(default="#f8fafc")


# =============================================================================
# Utilitários Internos
# =============================================================================

def _enrich_issues_with_diffs(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Adiciona `unified_diff` em cada issue para exibição imediata no Diff Studio da UI."""
    fixer = A11yFixer(reports_dir=REPORTS_DIR)
    for issue in analysis.get("issues", []):
        if not issue.get("unified_diff"):
            issue["unified_diff"] = fixer.generate_unified_diff(
                original_code=issue.get("original_code", ""),
                fixed_code=issue.get("fixed_code", ""),
                selector=issue.get("selector", "element"),
            )
    return analysis


def _mask_api_key(key: str) -> str:
    cleaned = (key or "").strip()
    placeholders = {"", "your_api_key_here", "sua_chave_aqui", "sk-xxx", "none", "mock"}
    if cleaned.lower() in placeholders:
        return ""
    if len(cleaned) <= 8:
        return "••••••••"
    return f"{cleaned[:4]}••••••••{cleaned[-4:]}"


# =============================================================================
# Rotas de Páginas e Arquivos Estáticos / Relatórios
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_index() -> HTMLResponse:
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Accessibility Radar UI não encontrada em web/static/index.html</h1>", status_code=404)
    return HTMLResponse(index_file.read_text(encoding="utf-8"))


@app.get("/reports/{filename}")
async def serve_report_file(filename: str) -> FileResponse:
    """Serve arquivos do diretório `reports/` com cabeçalhos sem cache para atualizar screenshots ao vivo."""
    safe_path = (REPORTS_DIR / filename).resolve()
    if not str(safe_path).startswith(str(REPORTS_DIR.resolve())) or not safe_path.exists():
        raise HTTPException(status_code=404, detail=f"Arquivo '{filename}' não encontrado em reports/.")
    return FileResponse(
        path=str(safe_path),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/preview/broken", response_class=HTMLResponse)
async def serve_broken_demo_page() -> HTMLResponse:
    broken_path = TESTS_DIR / "broken_page.html"
    if not broken_path.exists():
        raise HTTPException(status_code=404, detail="tests/broken_page.html não encontrado.")
    return HTMLResponse(
        broken_path.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/preview/local", response_class=HTMLResponse)
async def serve_local_preview(path: str = Query(..., description="Caminho do arquivo HTML local")) -> HTMLResponse:
    """Serve um arquivo HTML local dentro do projeto para visualização no iframe Antes/Depois."""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if not candidate.exists() or candidate.suffix.lower() not in (".html", ".htm"):
        raise HTTPException(status_code=404, detail=f"Arquivo HTML local não encontrado: {path}")

    return HTMLResponse(
        candidate.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store"},
    )


# =============================================================================
# Endpoints Principais da API REST
# =============================================================================

@app.get("/api/state")
async def get_initial_state() -> JSONResponse:
    """Retorna o estado atual do projeto, último diagnóstico salvo, histórico e status da IA."""
    fixer = A11yFixer(reports_dir=REPORTS_DIR)
    analyzer = A11yAnalyzer()

    latest_analysis = None
    audit_json_path = REPORTS_DIR / "audit_results.json"
    if audit_json_path.exists():
        try:
            latest_analysis = json.loads(audit_json_path.read_text(encoding="utf-8"))
            latest_analysis = _enrich_issues_with_diffs(latest_analysis)
        except Exception:
            latest_analysis = None

    verified_analysis = None
    verified_json_path = REPORTS_DIR / "verified_results.json"
    if verified_json_path.exists():
        try:
            verified_analysis = json.loads(verified_json_path.read_text(encoding="utf-8"))
        except Exception:
            verified_analysis = None

    report_md = ""
    report_md_path = REPORTS_DIR / "audit_report.md"
    if report_md_path.exists():
        try:
            report_md = report_md_path.read_text(encoding="utf-8")
        except Exception:
            report_md = ""

    return JSONResponse(
        {
            "latest_analysis": latest_analysis,
            "verified_analysis": verified_analysis,
            "has_fixed_page": (REPORTS_DIR / "fixed_page.html").exists(),
            "report_markdown": report_md,
            "history": fixer.get_audit_history(),
            "settings": {
                "ai_configured": analyzer.is_api_configured,
                "ai_base_url": analyzer.base_url,
                "ai_api_key_masked": _mask_api_key(analyzer.api_key),
                "ai_model_text": analyzer.model_text,
                "ai_model_vision": analyzer.model_vision,
            },
        }
    )


@app.post("/api/scan")
async def api_scan(req: ScanRequest) -> JSONResponse:
    """Executa o pipeline completo de escaneamento Playwright + análise WCAG 2.2."""
    scanner = A11yScanner(reports_dir=REPORTS_DIR)
    analyzer = A11yAnalyzer(force_mock=req.mock)
    fixer = A11yFixer(reports_dir=REPORTS_DIR)

    try:
        if req.raw_html and req.raw_html.strip():
            scan_data = await scanner.scan_raw_html(
                html_content=req.raw_html,
                filename=req.filename or "playground_input.html",
                viewport=req.viewport,
            )
        else:
            target = (req.target or "tests/broken_page.html").strip()
            scan_data = await scanner.scan(
                target=target,
                save_screenshot=True,
                viewport=req.viewport,
                screenshot_filename="before_screenshot.png",
            )

        analysis = analyzer.analyze(scan_data)
        analysis = _enrich_issues_with_diffs(analysis)

        # Salva artefatos em reports/
        report_md_path = fixer.generate_markdown_report(analysis)
        (REPORTS_DIR / "audit_results.json").write_text(
            json.dumps(analysis, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # Remove verificação anterior se existir para não confundir com o novo scan
        verified_json_path = REPORTS_DIR / "verified_results.json"
        if verified_json_path.exists():
            try:
                verified_json_path.unlink()
            except Exception:
                pass

        fixer.record_audit_history(analysis)

        source_html = None
        if analysis.get("local_path") and Path(analysis["local_path"]).exists():
            try:
                source_html = Path(analysis["local_path"]).read_text(encoding="utf-8")
            except Exception:
                source_html = None

        return JSONResponse(
            {
                "status": "ok",
                "analysis": analysis,
                "source_html": source_html,
                "report_markdown": report_md_path.read_text(encoding="utf-8"),
                "history": fixer.get_audit_history(),
            }
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao escanear alvo: {exc}")


@app.post("/api/fix")
async def api_fix(req: FixRequest) -> JSONResponse:
    """
    Aplica correções (todas ou apenas `selected_issue_ids` com `custom_overrides`) sobre um arquivo HTML local
    e opcionalmente re-executa o scanner no arquivo gerado (`reports/fixed_page.html`) para comprovar a evolução.
    """
    scanner = A11yScanner(reports_dir=REPORTS_DIR)
    analyzer = A11yAnalyzer(force_mock=req.mock)
    fixer = A11yFixer(reports_dir=REPORTS_DIR)

    audit_json_path = REPORTS_DIR / "audit_results.json"
    analysis: Optional[Dict[str, Any]] = None
    if audit_json_path.exists():
        try:
            analysis = json.loads(audit_json_path.read_text(encoding="utf-8"))
        except Exception:
            analysis = None

    target_path = req.target or (analysis.get("local_path") if analysis else None) or (analysis.get("target") if analysis else None)
    if not target_path:
        target_path = str(TESTS_DIR / "broken_page.html")

    # Se não houver análise prévia ou o alvo for diferente, escaneia primeiro
    try:
        _, resolved_local = scanner.resolve_target_url(target_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"A auto-correção requer um arquivo HTML local válido: {exc}")

    if resolved_local is None or not resolved_local.exists():
        raise HTTPException(
            status_code=400,
            detail="A aplicação direta de patches requer um arquivo HTML local (ou código colado no Playground). Para URLs remotas, copie os snippets corrigidos.",
        )

    if not analysis or (analysis.get("local_path") and Path(analysis["local_path"]).resolve() != resolved_local.resolve()):
        scan_data = await scanner.scan(
            target=str(resolved_local),
            save_screenshot=True,
            viewport=req.viewport,
            screenshot_filename="before_screenshot.png",
        )
        analysis = analyzer.analyze(scan_data)
        analysis = _enrich_issues_with_diffs(analysis)
        (REPORTS_DIR / "audit_results.json").write_text(
            json.dumps(analysis, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    fix_result = fixer.apply_fixes_to_file(
        source_path=resolved_local,
        analysis_result=analysis,
        output_path=REPORTS_DIR / "fixed_page.html",
        in_place=req.in_place,
        selected_issue_ids=req.selected_issue_ids,
        custom_overrides=req.custom_overrides,
    )

    verified_analysis = None
    if req.reverify:
        after_scan = await scanner.scan(
            target=fix_result["output_path"],
            save_screenshot=True,
            viewport=req.viewport,
            screenshot_filename="after_screenshot.png",
        )
        verified_analysis = analyzer.analyze(after_scan)
        verified_analysis = _enrich_issues_with_diffs(verified_analysis)
        (REPORTS_DIR / "verified_results.json").write_text(
            json.dumps(verified_analysis, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        fixer.record_audit_history(
            analysis,
            after_score=verified_analysis["summary"]["score"],
            fixed_issues_count=fix_result["total_fixes_applied"],
        )

    report_md_path = fixer.generate_markdown_report(analysis)

    return JSONResponse(
        {
            "status": "ok",
            "initial_analysis": analysis,
            "fix_result": fix_result,
            "verified_analysis": verified_analysis,
            "report_markdown": report_md_path.read_text(encoding="utf-8"),
            "history": fixer.get_audit_history(),
        }
    )


@app.post("/api/demo")
async def api_demo(req: DemoRequest) -> JSONResponse:
    """
    Executa o ciclo autônomo completo de demonstração em `tests/broken_page.html`:
    1. Escaneia `tests/broken_page.html` e salva `before_screenshot.png`
    2. Analisa os pilares WCAG 2.2
    3. Gera relatório Markdown e corrige o DOM em `reports/fixed_page.html`
    4. Re-escaneia `reports/fixed_page.html` e salva `after_screenshot.png` comprovando Score 100/100
    """
    broken_file = TESTS_DIR / "broken_page.html"
    if not broken_file.exists():
        raise HTTPException(status_code=404, detail=f"Arquivo demo não encontrado: {broken_file}")

    scanner = A11yScanner(reports_dir=REPORTS_DIR)
    analyzer = A11yAnalyzer(force_mock=req.mock)
    fixer = A11yFixer(reports_dir=REPORTS_DIR)

    # 1 & 2: Scan e Análise da página original com falhas
    before_scan = await scanner.scan(
        target=str(broken_file),
        save_screenshot=True,
        viewport=req.viewport,
        screenshot_filename="before_screenshot.png",
    )
    initial_analysis = analyzer.analyze(before_scan)
    initial_analysis = _enrich_issues_with_diffs(initial_analysis)

    # 3: Relatório e Auto-Fix
    report_md_path = fixer.generate_markdown_report(initial_analysis)
    fixed_html_path = REPORTS_DIR / "fixed_page.html"
    fix_result = fixer.apply_fixes_to_file(
        source_path=broken_file,
        analysis_result=initial_analysis,
        output_path=fixed_html_path,
        in_place=False,
    )

    # 4: Revalidação no navegador real
    after_scan = await scanner.scan(
        target=str(fixed_html_path),
        save_screenshot=True,
        viewport=req.viewport,
        screenshot_filename="after_screenshot.png",
    )
    verified_analysis = analyzer.analyze(after_scan)
    verified_analysis = _enrich_issues_with_diffs(verified_analysis)

    # Persiste estados
    (REPORTS_DIR / "audit_results.json").write_text(
        json.dumps(initial_analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (REPORTS_DIR / "verified_results.json").write_text(
        json.dumps(verified_analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    fixer.record_audit_history(
        initial_analysis,
        after_score=verified_analysis["summary"]["score"],
        fixed_issues_count=fix_result["total_fixes_applied"],
    )

    return JSONResponse(
        {
            "status": "ok",
            "initial_analysis": initial_analysis,
            "fix_result": fix_result,
            "verified_analysis": verified_analysis,
            "source_html": broken_file.read_text(encoding="utf-8"),
            "report_markdown": report_md_path.read_text(encoding="utf-8"),
            "history": fixer.get_audit_history(),
        }
    )


@app.post("/api/contrast-check")
async def api_contrast_check(req: ContrastCheckRequest) -> JSONResponse:
    """Calcula a razão de contraste W3C WCAG 2.x entre duas cores hexadecimais e sugere alternativas acessíveis."""
    try:
        fg_lum = A11yAnalyzer._relative_luminance(req.foreground)
        bg_lum = A11yAnalyzer._relative_luminance(req.background)
        lighter = max(fg_lum, bg_lum)
        darker = min(fg_lum, bg_lum)
        ratio = round((lighter + 0.05) / (darker + 0.05), 2)
        suggested_fg, suggested_ratio = A11yAnalyzer._suggest_accessible_foreground(req.background)

        return JSONResponse(
            {
                "foreground": req.foreground,
                "background": req.background,
                "contrast_ratio": ratio,
                "passes": {
                    "aa_normal": ratio >= 4.5,
                    "aa_large": ratio >= 3.0,
                    "aaa_normal": ratio >= 7.0,
                    "aaa_large": ratio >= 4.5,
                    "non_text_ui": ratio >= 3.0,
                },
                "suggested_foreground": suggested_fg,
                "suggested_ratio": suggested_ratio,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Formato de cor inválido: {exc}")


@app.get("/api/settings")
async def api_get_settings() -> JSONResponse:
    load_dotenv(dotenv_path=ENV_FILE, override=True)
    analyzer = A11yAnalyzer()
    return JSONResponse(
        {
            "ai_configured": analyzer.is_api_configured,
            "ai_base_url": analyzer.base_url,
            "ai_api_key_masked": _mask_api_key(analyzer.api_key),
            "ai_model_text": analyzer.model_text,
            "ai_model_vision": analyzer.model_vision,
        }
    )


@app.post("/api/settings")
async def api_update_settings(req: SettingsUpdateRequest) -> JSONResponse:
    """Salva configurações de provedor de IA no arquivo `.env` e atualiza o ambiente em execução."""
    if not ENV_FILE.exists():
        example_env = PROJECT_ROOT / ".env.example"
        if example_env.exists():
            ENV_FILE.write_text(example_env.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            ENV_FILE.write_text("", encoding="utf-8")

    set_key(str(ENV_FILE), "AI_BASE_URL", req.ai_base_url.strip())
    os.environ["AI_BASE_URL"] = req.ai_base_url.strip()

    if req.ai_api_key is not None and "••••" not in req.ai_api_key:
        set_key(str(ENV_FILE), "AI_API_KEY", req.ai_api_key.strip())
        os.environ["AI_API_KEY"] = req.ai_api_key.strip()

    set_key(str(ENV_FILE), "AI_MODEL_TEXT", req.ai_model_text.strip())
    os.environ["AI_MODEL_TEXT"] = req.ai_model_text.strip()

    set_key(str(ENV_FILE), "AI_MODEL_VISION", req.ai_model_vision.strip())
    os.environ["AI_MODEL_VISION"] = req.ai_model_vision.strip()

    analyzer = A11yAnalyzer()
    return JSONResponse(
        {
            "status": "ok",
            "settings": {
                "ai_configured": analyzer.is_api_configured,
                "ai_base_url": analyzer.base_url,
                "ai_api_key_masked": _mask_api_key(analyzer.api_key),
                "ai_model_text": analyzer.model_text,
                "ai_model_vision": analyzer.model_vision,
            },
        }
    )


@app.delete("/api/history")
async def api_clear_history() -> JSONResponse:
    fixer = A11yFixer(reports_dir=REPORTS_DIR)
    if fixer.history_file.exists():
        fixer.history_file.write_text("[]", encoding="utf-8")
    return JSONResponse({"status": "ok", "history": []})
