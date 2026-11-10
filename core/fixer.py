"""
core/fixer.py — Gerador de Patches WCAG 2.2, Auto-Fixer DOM e Exportador de Relatórios Markdown

Responsável por:
1. Receber o diagnóstico estruturado do `analyzer.py` e construir patches de código (HTML/CSS/JSX).
2. Aplicar correções cirúrgicas diretamente em arquivos HTML locais (ou gerar um novo arquivo corrigido),
   com suporte a seleção granular de issues (`selected_issue_ids`) e overrides customizados.
3. Gerar o relatório completo em Markdown (`reports/audit_report.md`) e gerenciar o histórico (`reports/history.json`).
"""

from __future__ import annotations

import difflib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag


class A11yFixer:
    """
    Motor de auto-remediação e geração de relatórios de acessibilidade WCAG 2.1/2.2.
    """

    def __init__(self, reports_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(__file__).resolve().parent.parent
        self.reports_dir = reports_dir or (self.base_dir / "reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.reports_dir / "history.json"

    @staticmethod
    def generate_unified_diff(original_code: str, fixed_code: str, selector: str = "element") -> str:
        """Gera um diff unificado legível entre o snippet original e o corrigido."""
        orig_lines = (original_code or "").splitlines(keepends=True)
        fixed_lines = (fixed_code or "").splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            fixed_lines,
            fromfile=f"a/{selector} (Antes)",
            tofile=f"b/{selector} (Depois)",
            lineterm="",
        )
        return "\n".join(diff)

    def apply_fixes_to_file(
        self,
        source_path: str | Path,
        analysis_result: Dict[str, Any],
        output_path: Optional[str | Path] = None,
        in_place: bool = False,
        selected_issue_ids: Optional[List[str]] = None,
        custom_overrides: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Aplica automaticamente os patches de acessibilidade sobre um arquivo HTML local.
        - Se `selected_issue_ids` for informado, aplica apenas as issues selecionadas.
        - Se `custom_overrides` for informado (mapa `issue_id -> texto customizado`), utiliza o valor
          informado pelo usuário para `alt`, `aria-label` ou cor hexadecimal.
        - Se `in_place=True`, cria um backup `.bak` e sobrescreve o próprio arquivo.
        """
        src = Path(source_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Arquivo local não encontrado para correção: {src}")

        raw_html = src.read_text(encoding="utf-8")
        soup = BeautifulSoup(raw_html, "html.parser")
        all_issues = analysis_result.get("issues", [])
        selected_set = set(selected_issue_ids) if selected_issue_ids is not None else None
        overrides = custom_overrides or {}

        issues = [
            iss for iss in all_issues if (selected_set is None or iss.get("id") in selected_set)
        ]
        apply_all = selected_set is None or len(issues) == len(all_issues)

        applied_fixes: List[Dict[str, str]] = []

        # Garante lang no elemento <html> se aplicando tudo ou se houver issue de lang
        html_tag = soup.find("html")
        if isinstance(html_tag, Tag) and not html_tag.get("lang") and apply_all:
            html_tag["lang"] = "pt-BR"

        css_contrast_overrides: List[str] = []

        # Processa cada issue selecionada
        for issue in issues:
            issue_id = issue.get("id", "")
            pillar = issue.get("pillar", "")
            selector = issue.get("selector", "")
            metrics = issue.get("computed_metrics", {})
            custom_val = (overrides.get(issue_id) or "").strip()

            target_el = self._select_first(soup, selector)

            if pillar == "contrast_visibility":
                new_fg = custom_val if custom_val.startswith("#") else metrics.get("suggested_foreground", "#1a202c")
                bg_hex = metrics.get("background", "#ffffff")
                if target_el is not None:
                    existing_style = target_el.get("style", "")
                    cleaned_style = re.sub(
                        r"(?<![-\w])color\s*:[^;]+;?", "", str(existing_style), flags=re.IGNORECASE
                    ).strip()
                    sep = "; " if cleaned_style and not cleaned_style.endswith(";") else " "
                    target_el["style"] = (
                        f"{cleaned_style}{sep}color: {new_fg} !important; background-color: {bg_hex};".strip()
                    )
                if selector:
                    css_contrast_overrides.append(
                        f"{selector} {{ color: {new_fg} !important; background-color: {bg_hex} !important; }}"
                    )
                applied_fixes.append(
                    {
                        "id": issue_id,
                        "pillar": pillar,
                        "selector": selector,
                        "action": f"Contraste corrigido para {new_fg} sobre {bg_hex}",
                    }
                )

            elif pillar == "muted_interactives":
                label = (
                    custom_val
                    or metrics.get("inferred_label")
                    or self._extract_attr_from_snippet(issue.get("fixed_code", ""), "aria-label")
                    or "Controle interativo"
                )
                if target_el is not None:
                    target_el["aria-label"] = label
                    if not target_el.get("title"):
                        target_el["title"] = label
                    inner_svg = target_el.find("svg")
                    if isinstance(inner_svg, Tag):
                        inner_svg["aria-hidden"] = "true"
                        inner_svg["focusable"] = "false"
                applied_fixes.append(
                    {
                        "id": issue_id,
                        "pillar": pillar,
                        "selector": selector,
                        "action": f'Adicionado aria-label="{label}"',
                    }
                )

            elif pillar == "media_semantics":
                suggested_alt = (
                    custom_val
                    or metrics.get("suggested_alt")
                    or self._extract_attr_from_snippet(issue.get("fixed_code", ""), "alt")
                    or self._extract_attr_from_snippet(issue.get("fixed_code", ""), "aria-label")
                    or "Imagem descritiva do conteúdo"
                )
                if target_el is not None:
                    if target_el.name == "svg":
                        target_el["role"] = "img"
                        target_el["aria-label"] = suggested_alt
                        if not target_el.find("title"):
                            title_tag = soup.new_tag("title")
                            title_tag.string = suggested_alt
                            target_el.insert(0, title_tag)
                    else:
                        target_el["alt"] = suggested_alt
                applied_fixes.append(
                    {
                        "id": issue_id,
                        "pillar": pillar,
                        "selector": selector,
                        "action": f'Definida semântica visual: "{suggested_alt[:55]}..."',
                    }
                )

            elif pillar == "focus_keyboard":
                issue_type = metrics.get("issue_type", "")
                if target_el is not None:
                    if issue_type == "positive_tabindex" or target_el.has_attr("tabindex"):
                        try:
                            if int(str(target_el.get("tabindex", "0"))) > 0:
                                target_el["tabindex"] = "0"
                        except ValueError:
                            target_el["tabindex"] = "0"

                    if issue_type == "missing_focus_indicator":
                        classes = list(target_el.get("class", []))
                        if "no-focus" in classes:
                            classes.remove("no-focus")
                        if "a11y-focus-ring" not in classes:
                            classes.append("a11y-focus-ring")
                        target_el["class"] = classes
                        if target_el.has_attr("style"):
                            target_el["style"] = re.sub(
                                r"outline\s*:\s*(none|0)[^;]*;?",
                                "",
                                str(target_el["style"]),
                                flags=re.IGNORECASE,
                            ).strip()

                    if issue_type == "non_keyboard_interactive":
                        target_el["role"] = "button"
                        target_el["tabindex"] = "0"
                        target_el["onkeydown"] = (
                            "if(event.key==='Enter'||event.key===' '){event.preventDefault();this.click();}"
                        )
                        if not target_el.get("aria-label") and not target_el.get_text(strip=True):
                            target_el["aria-label"] = "Acionar card interativo"

                    if issue_type == "keyboard_trap":
                        if target_el.has_attr("onkeydown"):
                            del target_el["onkeydown"]
                        if target_el.has_attr("onkeypress"):
                            del target_el["onkeypress"]

                applied_fixes.append(
                    {
                        "id": issue_id,
                        "pillar": pillar,
                        "selector": selector,
                        "action": f"Ordem de foco e navegação por teclado corrigidas ({issue_type or 'WCAG 2.4'})",
                    }
                )

            elif pillar == "semantic_structure":
                issue_type = metrics.get("issue_type", "")
                if issue_type == "missing_html_lang" and isinstance(html_tag, Tag):
                    html_tag["lang"] = custom_val or "pt-BR"
                elif issue_type == "missing_page_title":
                    head_el = soup.find("head")
                    if isinstance(head_el, Tag) and not head_el.find("title"):
                        t_tag = soup.new_tag("title")
                        t_tag.string = custom_val or "Página Acessível — Accessibility Radar"
                        head_el.insert(0, t_tag)
                elif issue_type == "heading_hierarchy_skip" and target_el is not None:
                    from_lvl = metrics.get("from_level") or 1
                    target_el.name = f"h{min(6, int(from_lvl) + 1)}"

                applied_fixes.append(
                    {
                        "id": issue_id,
                        "pillar": pillar,
                        "selector": selector,
                        "action": f"Estrutura semântica corrigida ({issue_type})",
                    }
                )

        # Varredura defensiva extra no DOM quando todas as correções estão habilitadas
        if apply_all:
            self._apply_comprehensive_dom_sweep(soup)

        # Injeta folha de estilos corretiva global para foco visível e contraste WCAG 2.2 AA
        self._inject_remediation_stylesheet(soup, css_contrast_overrides, include_focus_ring=apply_all or any(
            i.get("pillar") == "focus_keyboard" for i in issues
        ))

        # Determina destino do arquivo corrigido
        if in_place:
            backup_path = src.with_suffix(src.suffix + ".bak")
            backup_path.write_text(raw_html, encoding="utf-8")
            dest_path = src
        else:
            dest_path = Path(output_path).resolve() if output_path else (self.reports_dir / "fixed_page.html")
            dest_path.parent.mkdir(parents=True, exist_ok=True)

        fixed_html_str = str(soup)
        dest_path.write_text(fixed_html_str, encoding="utf-8")

        return {
            "source_path": str(src),
            "output_path": str(dest_path),
            "in_place": in_place,
            "total_fixes_applied": len(applied_fixes),
            "applied_fixes": applied_fixes,
            "fixed_html": fixed_html_str,
        }

    def record_audit_history(
        self,
        analysis_result: Dict[str, Any],
        after_score: Optional[int] = None,
        fixed_issues_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Registra uma entrada no histórico persistente `reports/history.json`."""
        history = self.get_audit_history()
        summary = analysis_result.get("summary", {})
        entry = {
            "id": f"RUN-{len(history) + 1:03d}-{int(datetime.now(timezone.utc).timestamp())}",
            "timestamp": analysis_result.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "target": analysis_result.get("target", "N/A"),
            "page_title": analysis_result.get("page_title", "Sem título"),
            "viewport": analysis_result.get("viewport", "desktop"),
            "mode": analysis_result.get("mode", "smart_fallback"),
            "score": summary.get("score", 0),
            "after_score": after_score,
            "wcag_status": summary.get("wcag_status", "N/A"),
            "total_issues": summary.get("total_issues", 0),
            "fixed_issues_count": fixed_issues_count,
            "by_pillar": summary.get("by_pillar", {}),
            "by_severity": summary.get("by_severity", {}),
        }
        history.insert(0, entry)
        history = history[:50]
        try:
            self.history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return entry

    def get_audit_history(self) -> List[Dict[str, Any]]:
        """Retorna a lista de auditorias realizadas salvas em `reports/history.json`."""
        if not self.history_file.exists():
            return []
        try:
            data = json.loads(self.history_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @staticmethod
    def _select_first(soup: BeautifulSoup, selector: str) -> Optional[Tag]:
        """Seleciona de forma resiliente o primeiro elemento correspondente ao seletor CSS."""
        if not selector:
            return None
        try:
            found = soup.select_one(selector)
            if isinstance(found, Tag):
                return found
        except Exception:
            pass
        if selector.startswith("#"):
            el = soup.find(id=selector[1:])
            if isinstance(el, Tag):
                return el
        return None

    @staticmethod
    def _extract_attr_from_snippet(snippet: str, attr_name: str) -> Optional[str]:
        match = re.search(rf'\b{re.escape(attr_name)}="([^"]+)"', snippet or "")
        return match.group(1) if match else None

    @staticmethod
    def _apply_comprehensive_dom_sweep(soup: BeautifulSoup) -> None:
        """
        Realiza uma varredura complementar na árvore BeautifulSoup para garantir que
        todos os elementos de `broken_page.html` ou páginas similares fiquem 100% conformes.
        """
        # 1. Remove qualquer tabindex > 0 remanescente
        for el in soup.find_all(attrs={"tabindex": True}):
            try:
                if int(str(el["tabindex"])) > 0:
                    el["tabindex"] = "0"
            except ValueError:
                pass

        # 2. Remove classes .no-focus e armadilhas de teclado em onkeydown
        for el in soup.find_all(True):
            classes = list(el.get("class", []))
            if "no-focus" in classes:
                classes.remove("no-focus")
                el["class"] = classes
            onkeydown = str(el.get("onkeydown", ""))
            if "preventDefault" in onkeydown and ("Tab" in onkeydown or "Escape" in onkeydown):
                del el["onkeydown"]

        # 3. Garante que divs/spans clicáveis tenham role="button", tabindex="0" e handler de Enter/Espaço
        for el in soup.find_all(["div", "span"], attrs={"onclick": True}):
            if not el.get("role"):
                el["role"] = "button"
            if not el.get("tabindex"):
                el["tabindex"] = "0"
            if not el.get("onkeydown"):
                el["onkeydown"] = (
                    "if(event.key==='Enter'||event.key===' '){event.preventDefault();this.click();}"
                )

    @staticmethod
    def _inject_remediation_stylesheet(
        soup: BeautifulSoup,
        contrast_rules: List[str],
        include_focus_ring: bool = True,
    ) -> None:
        """Injeta bloco <style id="accessibility-radar-remediation"> com foco visível WCAG 2.4.7 e correções de contraste."""
        existing = soup.find("style", id="accessibility-radar-remediation")
        if existing:
            existing.decompose()

        contrast_block = "\n        ".join(contrast_rules)
        focus_block = ""
        if include_focus_ring:
            focus_block = """
        a:focus, button:focus, input:focus, select:focus, textarea:focus, [tabindex]:focus,
        a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, [tabindex]:focus-visible {
            outline: 3px solid #7c3aed !important;
            outline-offset: 2px !important;
            box-shadow: 0 0 0 4px rgba(124, 58, 237, 0.25) !important;
        }"""

        style_content = f"""
        /* Accessibility Radar — Auto-Remediation Stylesheet (WCAG 2.2 Level AA) */
        .sr-only {{
            position: absolute !important;
            width: 1px !important;
            height: 1px !important;
            padding: 0 !important;
            margin: -1px !important;
            overflow: hidden !important;
            clip: rect(0, 0, 0, 0) !important;
            white-space: nowrap !important;
            border: 0 !important;
        }}
        {focus_block}
        {contrast_block}
        """

        style_tag = soup.new_tag("style", id="accessibility-radar-remediation")
        style_tag.string = style_content
        head = soup.find("head")
        if isinstance(head, Tag):
            head.append(style_tag)
        elif soup.body:
            soup.body.insert(0, style_tag)

    def generate_markdown_report(
        self,
        analysis_result: Dict[str, Any],
        output_path: Optional[str | Path] = None,
    ) -> Path:
        """
        Gera o relatório completo de auditoria e correção em Markdown (`reports/audit_report.md`)
        contendo resumo executivo, scorecard, tabela WCAG 2.1/2.2 e o "Antes e Depois" do código.
        """
        report_file = Path(output_path).resolve() if output_path else (self.reports_dir / "audit_report.md")
        report_file.parent.mkdir(parents=True, exist_ok=True)

        summary = analysis_result.get("summary", {})
        by_pillar = summary.get("by_pillar", {})
        by_severity = summary.get("by_severity", {})
        issues = analysis_result.get("issues", [])

        score = summary.get("score", 0)
        wcag_status = summary.get("wcag_status", "N/A")
        target = analysis_result.get("target", "N/A")
        page_title = analysis_result.get("page_title", "Sem título")
        timestamp = analysis_result.get("timestamp", "")
        mode = analysis_result.get("mode", "N/A")

        lines: List[str] = [
            "# Relatório de Auditoria e Auto-Correção WCAG 2.2 — Accessibility Radar",
            "",
            f"- **Alvo Auditado:** `{target}`",
            f"- **Título da Página:** {page_title}",
            f"- **Data/Hora (UTC):** `{timestamp}`",
            f"- **Motor de Análise:** `{mode}`",
            f"- **Score de Acessibilidade:** **{score} / 100**",
            f"- **Status de Conformidade:** **{wcag_status}**",
            "",
            "---",
            "",
            "## 1. Resumo Executivo",
            "",
            "### 1.1. Distribuição nos Pilares de Auditoria",
            "",
            "| Pilar de Auditoria | Critérios WCAG 2.1 / 2.2 | Problemas Detectados |",
            "| :--- | :--- | :---: |",
            f"| **1. Contraste e Visibilidade** | 1.4.3 Contrast (Minimum) (AA) / 1.4.11 | **{by_pillar.get('contrast_visibility', 0)}** |",
            f"| **2. Elementos Interativos Mudos** | 4.1.2 Name, Role, Value (A) / 2.4.4 / 1.3.1 | **{by_pillar.get('muted_interactives', 0)}** |",
            f"| **3. Semântica de Mídia** | 1.1.1 Non-text Content (A) | **{by_pillar.get('media_semantics', 0)}** |",
            f"| **4. Ordem de Foco e Teclado** | 2.4.3 Focus Order / 2.4.7 Focus Visible / 2.1.1 / 2.1.2 | **{by_pillar.get('focus_keyboard', 0)}** |",
            f"| **5. Estrutura e Semântica** | 3.1.1 Language / 2.4.2 Title / 1.3.1 Headings | **{by_pillar.get('semantic_structure', 0)}** |",
            f"| **TOTAL** | **WCAG 2.2 Nível A & AA** | **{summary.get('total_issues', 0)}** |",
            "",
            "### 1.2. Distribuição por Severidade",
            "",
            f"- **Crítico (`critical`):** {by_severity.get('critical', 0)}",
            f"- **Sério (`serious`):** {by_severity.get('serious', 0)}",
            f"- **Moderado (`moderate`):** {by_severity.get('moderate', 0)}",
            f"- **Menor (`minor`):** {by_severity.get('minor', 0)}",
            "",
            "---",
            "",
            "## 2. Diagnóstico Detalhado e Patches de Código (Antes vs. Depois)",
            "",
        ]

        if not issues:
            lines.extend(
                [
                    "> **Parabéns!** Nenhuma violação foi detectada nos pilares auditados. A página está 100% em conformidade com os critérios verificados da WCAG 2.2 Nível A e AA.",
                    "",
                ]
            )
        else:
            for issue in issues:
                lines.extend(
                    [
                        f"### [{issue.get('id')}] {issue.get('title')}",
                        "",
                        f"- **Pilar:** {issue.get('pillar_label', issue.get('pillar'))}",
                        f"- **Critério WCAG:** `{issue.get('wcag_criterion')}` (Nível **{issue.get('wcag_level')}**)",
                        f"- **Severidade:** `{issue.get('severity', 'serious').upper()}`",
                        f"- **Seletor DOM:** `{issue.get('selector')}`",
                        f"- **Diagnóstico Técnico:** {issue.get('description')}",
                        f"- **Impacto no Usuário:** {issue.get('impact')}",
                        f"- **Recomendação de Correção:** {issue.get('remediation_notes')}",
                        "",
                        "#### Antes (Código com Violação)",
                        "```html",
                        (issue.get("original_code") or "").strip(),
                        "```",
                        "",
                        "#### Depois (Patch Corrigido pelo Accessibility Radar)",
                        "```html",
                        (issue.get("fixed_code") or "").strip(),
                        "```",
                        "",
                        "---",
                        "",
                    ]
                )

        report_file.write_text("\n".join(lines), encoding="utf-8")
        return report_file
