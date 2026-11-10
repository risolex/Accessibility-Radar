"""
core/scanner.py — Motor Assíncrono de Escaneamento de Acessibilidade Web (Playwright)

Responsável por:
1. Abrir URLs remotas ou arquivos HTML locais via navegador Chromium headless (`wait_until="networkidle"`).
2. Capturar screenshot de página inteira em Base64 para análise visual multimodal e mapeamento de hotspots.
3. Extrair a Árvore de Acessibilidade (Accessibility Tree) real do navegador (`page.accessibility.snapshot()`
   com fallback automático via protocolo CDP `Accessibility.getFullAXTree` para Playwright >= 1.49).
4. Injetar JavaScript cirúrgico no DOM para filtrar e retornar os elementos violadores ou suspeitos
   nos 5 pilares da WCAG 2.1/2.2 (incluindo coordenadas visuais `rect`, mapa de ordem de foco e estrutura semântica).
"""

from __future__ import annotations

import asyncio
import base64
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from playwright.async_api import Page, async_playwright


VIEWPORT_PRESETS: Dict[str, Dict[str, int]] = {
    "desktop": {"width": 1280, "height": 900},
    "tablet": {"width": 768, "height": 1024},
    "mobile": {"width": 390, "height": 844},
}


# Script JavaScript injetado no navegador para extrair e filtrar os elementos dos 5 pilares + mapa visual
A11Y_DOM_FILTER_JS = r"""
() => {
    // Utilitário: Converte string rgb/rgba para objeto {r, g, b, a}
    function parseRgba(colorStr) {
        if (!colorStr) return { r: 255, g: 255, b: 255, a: 0 };
        const match = colorStr.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)/i);
        if (!match) return { r: 255, g: 255, b: 255, a: 1 };
        return {
            r: parseInt(match[1], 10),
            g: parseInt(match[2], 10),
            b: parseInt(match[3], 10),
            a: match[4] !== undefined ? parseFloat(match[4]) : 1.0
        };
    }

    // Utilitário: Converte RGB para Hexadecimal (#rrggbb)
    function rgbToHex(r, g, b) {
        const toHex = (n) => Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, '0');
        return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
    }

    // Utilitário: Calcula luminância relativa segundo fórmula oficial W3C WCAG 2.x
    function getRelativeLuminance(r, g, b) {
        const sRGB = [r / 255, g / 255, b / 255];
        const [R, G, B] = sRGB.map((c) =>
            c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
        );
        return 0.2126 * R + 0.7152 * G + 0.0722 * B;
    }

    // Utilitário: Calcula razão de contraste entre duas cores RGB
    function getContrastRatio(fg, bg) {
        const l1 = getRelativeLuminance(fg.r, fg.g, fg.b);
        const l2 = getRelativeLuminance(bg.r, bg.g, bg.b);
        const lighter = Math.max(l1, l2);
        const darker = Math.min(l1, l2);
        return Number(((lighter + 0.05) / (darker + 0.05)).toFixed(2));
    }

    // Resolve cor de fundo efetiva subindo na árvore ancestral quando transparente
    function getEffectiveBackgroundColor(el) {
        let current = el;
        while (current && current !== document.documentElement) {
            const style = window.getComputedStyle(current);
            const parsed = parseRgba(style.backgroundColor);
            if (parsed.a > 0.05) {
                return parsed;
            }
            current = current.parentElement;
        }
        const bodyStyle = window.getComputedStyle(document.body || document.documentElement);
        const bodyBg = parseRgba(bodyStyle.backgroundColor);
        return bodyBg.a > 0.05 ? bodyBg : { r: 255, g: 255, b: 255, a: 1 };
    }

    // Extrai coordenadas visuais absolutas em relação à página inteira (para overlay no screenshot)
    function getElementRect(el) {
        if (!el || typeof el.getBoundingClientRect !== 'function') {
            return { x: 0, y: 0, width: 0, height: 0 };
        }
        const r = el.getBoundingClientRect();
        return {
            x: Math.max(0, Math.round(r.left + window.scrollX)),
            y: Math.max(0, Math.round(r.top + window.scrollY)),
            width: Math.max(0, Math.round(r.width)),
            height: Math.max(0, Math.round(r.height))
        };
    }

    // Gera seletor CSS único e legível para um elemento
    function getCssSelector(el) {
        if (!el || el.nodeType !== 1) return '';
        if (el.id) return `#${el.id}`;
        const tag = el.tagName.toLowerCase();
        const classes = Array.from(el.classList || []).filter(Boolean).slice(0, 2);
        if (classes.length > 0) {
            const classSelector = `${tag}.${classes.join('.')}`;
            if (document.querySelectorAll(classSelector).length === 1) {
                return classSelector;
            }
        }
        if (el.getAttribute('name')) {
            return `${tag}[name="${el.getAttribute('name')}"]`;
        }
        if (el.getAttribute('data-testid')) {
            return `${tag}[data-testid="${el.getAttribute('data-testid')}"]`;
        }
        const parent = el.parentElement;
        if (!parent) return tag;
        const siblings = Array.from(parent.children).filter((c) => c.tagName === el.tagName);
        const idx = siblings.indexOf(el) + 1;
        const parentSel = parent.id ? `#${parent.id}` : parent.tagName.toLowerCase();
        return siblings.length > 1
            ? `${parentSel} > ${tag}:nth-of-type(${idx})`
            : `${parentSel} > ${tag}`;
    }

    // Extrai contexto textual próximo (título do card, seção pai, etc.)
    function getSurroundingContext(el) {
        const container = el.closest('article, section, .product-card, .card, .hero, .promo-box, form, header, footer, div') || el.parentElement;
        if (!container) return '';
        const heading = container.querySelector('h1, h2, h3, h4, strong, .product-title');
        if (heading && heading.innerText) {
            return heading.innerText.trim().slice(0, 120);
        }
        return (container.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120);
    }

    // Verifica se o elemento possui texto direto (não apenas em filhos profundos já auditados)
    function getDirectText(el) {
        let text = '';
        for (const node of el.childNodes) {
            if (node.nodeType === Node.TEXT_NODE) {
                text += node.textContent;
            }
        }
        return text.replace(/\s+/g, ' ').trim();
    }

    // Calcula nome acessível simplificado de um elemento interativo
    function computeAccessibleName(el) {
        if (!el || el.nodeType !== 1) return '';
        const tag = el.tagName.toLowerCase();
        const ariaLabel = (el.getAttribute('aria-label') || '').trim();
        if (ariaLabel) return ariaLabel;

        const ariaLabelledBy = (el.getAttribute('aria-labelledby') || '').trim();
        if (ariaLabelledBy) {
            const txt = ariaLabelledBy
                .split(/\s+/)
                .map((id) => {
                    const ref = document.getElementById(id);
                    return ref ? ref.innerText.trim() : '';
                })
                .join(' ')
                .trim();
            if (txt) return txt;
        }

        if (['input', 'select', 'textarea'].includes(tag)) {
            if (el.id) {
                const labelEl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
                if (labelEl && labelEl.innerText.trim()) {
                    return labelEl.innerText.trim();
                }
            }
            const parentLabel = el.closest('label');
            if (parentLabel && parentLabel.innerText.trim()) {
                return parentLabel.innerText.trim();
            }
        }

        const visibleText = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
        if (visibleText) return visibleText.slice(0, 80);

        const childImg = el.querySelector('img[alt]');
        if (childImg && (childImg.getAttribute('alt') || '').trim()) {
            return childImg.getAttribute('alt').trim();
        }

        const childSvgTitle = el.querySelector('svg title');
        if (childSvgTitle && childSvgTitle.textContent.trim()) {
            return childSvgTitle.textContent.trim();
        }

        const titleAttr = (el.getAttribute('title') || '').trim();
        if (titleAttr) return titleAttr;

        const inputType = (el.getAttribute('type') || '').toLowerCase();
        if (['submit', 'button', 'reset'].includes(inputType)) {
            return (el.getAttribute('value') || '').trim();
        }
        return '';
    }

    // =========================================================================
    // PILAR 1: Contraste e Visibilidade (WCAG 1.4.3 / 1.4.11)
    // =========================================================================
    const contrastViolations = [];
    const textCandidates = document.querySelectorAll(
        'h1, h2, h3, h4, h5, h6, p, span, a, button, label, li, small, strong, div, td, th'
    );

    for (const el of textCandidates) {
        const directText = getDirectText(el);
        if (!directText || directText.length < 2) continue;

        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) {
            continue;
        }

        const fg = parseRgba(style.color);
        const bg = getEffectiveBackgroundColor(el);
        const ratio = getContrastRatio(fg, bg);

        const fontSizePx = parseFloat(style.fontSize) || 16;
        const fontWeight = parseInt(style.fontWeight, 10) || (style.fontWeight === 'bold' ? 700 : 400);
        const isLargeText = fontSizePx >= 24 || (fontSizePx >= 18.66 && fontWeight >= 700);
        const requiredRatio = isLargeText ? 3.0 : 4.5;

        if (ratio < requiredRatio) {
            contrastViolations.push({
                selector: getCssSelector(el),
                tag: el.tagName.toLowerCase(),
                text: directText.slice(0, 100),
                foreground_hex: rgbToHex(fg.r, fg.g, fg.b),
                background_hex: rgbToHex(bg.r, bg.g, bg.b),
                contrast_ratio: ratio,
                required_ratio: requiredRatio,
                is_large_text: isLargeText,
                font_size: `${Math.round(fontSizePx)}px`,
                font_weight: String(fontWeight),
                rect: getElementRect(el),
                outer_html: el.outerHTML.slice(0, 350)
            });
        }
    }

    // =========================================================================
    // PILAR 2: Elementos Interativos Mudos (WCAG 4.1.2 / 2.4.4 / 1.3.1)
    // =========================================================================
    const mutedInteractives = [];
    const interactiveEls = document.querySelectorAll(
        'button, a[href], input:not([type="hidden"]), select, textarea, [role="button"], [role="link"]'
    );

    for (const el of interactiveEls) {
        const tag = el.tagName.toLowerCase();
        const accessibleName = computeAccessibleName(el);

        if (!accessibleName) {
            mutedInteractives.push({
                selector: getCssSelector(el),
                tag: tag,
                type: el.getAttribute('type') || null,
                id: el.id || null,
                name: el.getAttribute('name') || null,
                placeholder: el.getAttribute('placeholder') || null,
                href: el.getAttribute('href') || null,
                context: getSurroundingContext(el),
                rect: getElementRect(el),
                outer_html: el.outerHTML.slice(0, 350)
            });
        }
    }

    // =========================================================================
    // PILAR 3: Semântica de Mídia (WCAG 1.1.1 Non-text Content)
    // =========================================================================
    const mediaViolations = [];
    const GENERIC_ALT_TERMS = new Set([
        'imagem', 'foto', 'image', 'photo', 'picture', 'pic', 'banner',
        'icon', 'icone', 'ícone', 'grafico', 'gráfico', 'placeholder',
        'img', 'produto', 'product', 'thumbnail', 'thumb', 'logo'
    ]);

    for (const img of document.querySelectorAll('img')) {
        const hasAltAttr = img.hasAttribute('alt');
        const altVal = (img.getAttribute('alt') || '').trim();
        const role = (img.getAttribute('role') || '').toLowerCase();
        const ariaHidden = img.getAttribute('aria-hidden') === 'true';
        const isInsideInteractive = Boolean(img.closest('a, button'));

        if (ariaHidden || role === 'presentation' || role === 'none') {
            continue;
        }

        const normalizedAlt = altVal.toLowerCase();
        const isFilenameAlt = /\.(jpg|jpeg|png|webp|gif|svg)$/i.test(normalizedAlt);
        const isGenericAlt = GENERIC_ALT_TERMS.has(normalizedAlt) || isFilenameAlt;
        const isUnjustifiedEmptyAlt = hasAltAttr && altVal === '' && (isInsideInteractive || Boolean(img.closest('.product-card, article, figure, .hero')));

        if (!hasAltAttr || isGenericAlt || isUnjustifiedEmptyAlt) {
            let issueType = 'missing_alt';
            if (isUnjustifiedEmptyAlt) issueType = 'empty_alt_informative';
            else if (isGenericAlt) issueType = 'generic_alt';

            mediaViolations.push({
                selector: getCssSelector(img),
                tag: 'img',
                issue_type: issueType,
                current_alt: hasAltAttr ? altVal : null,
                src: img.getAttribute('src') || '',
                context: getSurroundingContext(img),
                rect: getElementRect(img),
                outer_html: img.outerHTML.slice(0, 350)
            });
        }
    }

    for (const svg of document.querySelectorAll('svg')) {
        if (svg.closest('button, a')) continue;
        if (svg.getAttribute('aria-hidden') === 'true') continue;

        const ariaLabel = (svg.getAttribute('aria-label') || '').trim();
        const titleEl = svg.querySelector('title');
        const titleText = titleEl ? titleEl.textContent.trim() : '';
        const role = (svg.getAttribute('role') || '').trim();

        if (!ariaLabel && !titleText) {
            mediaViolations.push({
                selector: getCssSelector(svg),
                tag: 'svg',
                issue_type: 'svg_missing_accessible_name',
                current_alt: null,
                role: role || null,
                context: getSurroundingContext(svg),
                rect: getElementRect(svg),
                outer_html: svg.outerHTML.slice(0, 350)
            });
        }
    }

    // =========================================================================
    // PILAR 4: Ordem de Foco e Navegação por Teclado (WCAG 2.4.3 / 2.4.7 / 2.1.1 / 2.1.2)
    // =========================================================================
    const focusKeyboardViolations = [];

    // 4.1 Tabindex positivo (> 0)
    for (const el of document.querySelectorAll('[tabindex]')) {
        const rawTab = el.getAttribute('tabindex');
        const tabVal = parseInt(rawTab, 10);
        if (!isNaN(tabVal) && tabVal > 0) {
            focusKeyboardViolations.push({
                selector: getCssSelector(el),
                tag: el.tagName.toLowerCase(),
                issue_type: 'positive_tabindex',
                tabindex: tabVal,
                context: getSurroundingContext(el),
                rect: getElementRect(el),
                outer_html: el.outerHTML.slice(0, 350)
            });
        }
    }

    // 4.2 Elementos interativos com foco suprimido (outline: none / 0 sem substituto)
    const sheets = Array.from(document.styleSheets || []);
    const suppressedFocusSelectors = [];
    for (const sheet of sheets) {
        try {
            for (const rule of Array.from(sheet.cssRules || [])) {
                if (rule.selectorText && rule.style) {
                    const outStyle = rule.style.outlineStyle || rule.style.outline;
                    const outWidth = rule.style.outlineWidth;
                    const boxShad = rule.style.boxShadow;
                    if (
                        (outStyle === 'none' || outStyle === '0' || outStyle === '0px' || outWidth === '0px') &&
                        (!boxShad || boxShad === 'none')
                    ) {
                        suppressedFocusSelectors.push(rule.selectorText.replace(/:focus(-visible)?/g, '').trim());
                    }
                }
            }
        } catch (e) {
            // Ignora stylesheets cross-origin
        }
    }

    const focusableCheckEls = document.querySelectorAll('a[href], button, input, select, textarea, [tabindex]');
    const flaggedNoFocus = new Set();

    for (const el of focusableCheckEls) {
        const inlineOutline = el.style && (el.style.outline === 'none' || el.style.outline === '0' || el.style.outlineStyle === 'none');
        let matchedRule = false;
        for (const sel of suppressedFocusSelectors) {
            if (!sel) continue;
            try {
                if (el.matches(sel)) {
                    matchedRule = true;
                    break;
                }
            } catch (e) {}
        }

        if (inlineOutline || matchedRule || el.classList.contains('no-focus')) {
            const selector = getCssSelector(el);
            if (!flaggedNoFocus.has(selector)) {
                flaggedNoFocus.add(selector);
                focusKeyboardViolations.push({
                    selector: selector,
                    tag: el.tagName.toLowerCase(),
                    issue_type: 'missing_focus_indicator',
                    context: getSurroundingContext(el),
                    rect: getElementRect(el),
                    outer_html: el.outerHTML.slice(0, 350)
                });
            }
        }
    }

    // 4.3 Elementos não-nativos clicáveis (div/span com onclick) sem suporte de teclado
    for (const el of document.querySelectorAll('div[onclick], span[onclick], li[onclick]')) {
        const hasTabindex = el.hasAttribute('tabindex') && parseInt(el.getAttribute('tabindex'), 10) >= 0;
        const hasRole = Boolean(el.getAttribute('role'));
        const hasKeyHandler = el.hasAttribute('onkeydown') || el.hasAttribute('onkeyup') || el.hasAttribute('onkeypress');
        if (!hasTabindex || !hasRole || !hasKeyHandler) {
            focusKeyboardViolations.push({
                selector: getCssSelector(el),
                tag: el.tagName.toLowerCase(),
                issue_type: 'non_keyboard_interactive',
                context: getSurroundingContext(el),
                rect: getElementRect(el),
                outer_html: el.outerHTML.slice(0, 350)
            });
        }
    }

    // 4.4 Armadilhas de teclado (Keyboard Traps em onkeydown/onkeypress)
    const trappedSelectors = new Set();
    for (const el of document.querySelectorAll('[onkeydown], [onkeypress]')) {
        const handlerCode = (el.getAttribute('onkeydown') || el.getAttribute('onkeypress') || '');
        if (/Tab|Escape|keyCode\s*===?\s*(9|27)/i.test(handlerCode) && /preventDefault|return\s+false/i.test(handlerCode)) {
            const sel = getCssSelector(el);
            trappedSelectors.add(sel);
            focusKeyboardViolations.push({
                selector: sel,
                tag: el.tagName.toLowerCase(),
                issue_type: 'keyboard_trap',
                handler: handlerCode,
                context: getSurroundingContext(el),
                rect: getElementRect(el),
                outer_html: el.outerHTML.slice(0, 350)
            });
        }
    }

    // =========================================================================
    // PILAR 5: Estrutura Semântica, Landmarks & Alvos de Toque (WCAG 3.1.1 / 2.4.1 / 1.3.1 / 2.5.8)
    // =========================================================================
    const semanticStructureViolations = [];
    const htmlLang = (document.documentElement.getAttribute('lang') || '').trim();
    if (!htmlLang) {
        semanticStructureViolations.push({
            selector: 'html',
            tag: 'html',
            issue_type: 'missing_html_lang',
            context: document.title || 'Documento raiz',
            rect: { x: 0, y: 0, width: window.innerWidth, height: 60 },
            outer_html: '<html>'
        });
    }

    if (!(document.title || '').trim()) {
        semanticStructureViolations.push({
            selector: 'head',
            tag: 'head',
            issue_type: 'missing_page_title',
            context: 'Cabeçalho do documento',
            rect: { x: 0, y: 0, width: window.innerWidth, height: 40 },
            outer_html: '<head>...</head>'
        });
    }

    // Extrai árvore de Headings (H1-H6) e verifica saltos de nível (ex: H1 -> H4)
    const headingsOutline = [];
    let prevLevel = 0;
    for (const h of document.querySelectorAll('h1, h2, h3, h4, h5, h6')) {
        const level = parseInt(h.tagName.substring(1), 10);
        const text = (h.innerText || h.textContent || '').replace(/\s+/g, ' ').trim();
        const sel = getCssSelector(h);
        const rect = getElementRect(h);
        const skipped = prevLevel > 0 && level > prevLevel + 1;
        headingsOutline.push({
            level: level,
            tag: h.tagName.toLowerCase(),
            text: text.slice(0, 100),
            selector: sel,
            skipped: skipped,
            rect: rect
        });
        if (skipped) {
            semanticStructureViolations.push({
                selector: sel,
                tag: h.tagName.toLowerCase(),
                issue_type: 'heading_hierarchy_skip',
                from_level: prevLevel,
                to_level: level,
                context: text.slice(0, 80),
                rect: rect,
                outer_html: h.outerHTML.slice(0, 350)
            });
        }
        prevLevel = level;
    }

    // Extrai Landmarks semânticas da página
    const landmarksList = [];
    const landmarkMap = {
        header: 'banner',
        nav: 'navigation',
        main: 'main',
        footer: 'contentinfo',
        aside: 'complementary',
        section: 'region',
        form: 'form'
    };
    for (const el of document.querySelectorAll('header, nav, main, footer, aside, section[aria-label], section[aria-labelledby], form, [role]')) {
        const tag = el.tagName.toLowerCase();
        const explicitRole = (el.getAttribute('role') || '').toLowerCase();
        const role = explicitRole || landmarkMap[tag];
        if (!role) continue;
        landmarksList.push({
            role: role,
            tag: tag,
            selector: getCssSelector(el),
            label: (el.getAttribute('aria-label') || '').trim() || getSurroundingContext(el).slice(0, 60),
            rect: getElementRect(el)
        });
    }

    // Mapa da Ordem Real de Foco por Teclado (Tab Order Map)
    const allFocusable = Array.from(
        document.querySelectorAll(
            'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
    ).filter((el) => {
        const s = window.getComputedStyle(el);
        return s.display !== 'none' && s.visibility !== 'hidden' && parseFloat(s.opacity) !== 0;
    });

    const positiveTabEls = [];
    const normalTabEls = [];
    allFocusable.forEach((el, domIdx) => {
        const rawTab = el.getAttribute('tabindex');
        const tabVal = rawTab !== null ? parseInt(rawTab, 10) : 0;
        const item = { el, tabVal: isNaN(tabVal) ? 0 : tabVal, domIdx };
        if (item.tabVal > 0) {
            positiveTabEls.push(item);
        } else {
            normalTabEls.push(item);
        }
    });

    positiveTabEls.sort((a, b) => (a.tabVal !== b.tabVal ? a.tabVal - b.tabVal : a.domIdx - b.domIdx));
    const orderedFocusItems = [...positiveTabEls, ...normalTabEls];

    const focusOrderMap = orderedFocusItems.map((item, idx) => {
        const el = item.el;
        const sel = getCssSelector(el);
        const name = computeAccessibleName(el);
        return {
            order: idx + 1,
            selector: sel,
            tag: el.tagName.toLowerCase(),
            label: name || '(Sem nome acessível / Mudo)',
            is_muted: !name,
            tabindex: item.tabVal,
            has_positive_tabindex: item.tabVal > 0,
            missing_focus_ring: flaggedNoFocus.has(sel),
            is_trap: trappedSelectors.has(sel),
            rect: getElementRect(el)
        };
    });

    const docWidth = Math.max(
        document.documentElement.scrollWidth || 0,
        document.body ? document.body.scrollWidth : 0,
        window.innerWidth || 1280
    );
    const docHeight = Math.max(
        document.documentElement.scrollHeight || 0,
        document.body ? document.body.scrollHeight : 0,
        window.innerHeight || 900
    );

    return {
        page_title: document.title || 'Sem título',
        lang: htmlLang || null,
        total_dom_nodes: document.querySelectorAll('*').length,
        page_dimensions: {
            width: docWidth,
            height: docHeight,
            viewport_width: window.innerWidth || 1280,
            viewport_height: window.innerHeight || 900
        },
        document_outline: {
            headings: headingsOutline,
            landmarks: landmarksList
        },
        focus_order_map: focusOrderMap,
        pillars: {
            contrast_visibility: contrastViolations,
            muted_interactives: mutedInteractives,
            media_semantics: mediaViolations,
            focus_keyboard: focusKeyboardViolations,
            semantic_structure: semanticStructureViolations
        }
    };
}
"""


class A11yScanner:
    """
    Scanner assíncrono que utiliza Playwright para renderizar a página alvo,
    capturar screenshot em página inteira, extrair a Árvore de Acessibilidade
    e filtrar cirurgicamente os elementos dos 5 pilares no DOM.
    """

    def __init__(self, reports_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(__file__).resolve().parent.parent
        self.reports_dir = reports_dir or (self.base_dir / "reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def resolve_target_url(target: str) -> tuple[str, Optional[Path]]:
        """
        Converte o alvo informado (URL HTTP/HTTPS, domínio sem esquema como 'example.com'
        ou caminho de arquivo local) em uma URL navegável pelo Playwright e retorna também o `Path` local se aplicável.
        """
        cleaned = (target or "").strip()
        parsed = urlparse(cleaned)
        if parsed.scheme in ("http", "https"):
            return cleaned, None
        if parsed.scheme == "file":
            local_path = Path(parsed.path.lstrip("/")) if re.match(r"^/[A-Za-z]:", parsed.path) else Path(parsed.path)
            return cleaned, local_path

        local_file = Path(cleaned)
        if not local_file.is_absolute():
            local_file = Path.cwd() / local_file
        local_file = local_file.resolve()

        if local_file.exists():
            return local_file.as_uri(), local_file

        # Se não é um arquivo local existente e parece um domínio web (ex: google.com, localhost:3000)
        if re.match(r"^localhost(:\d+)?(/.*)?$", cleaned, flags=re.IGNORECASE) or re.match(
            r"^127\.0\.0\.1(:\d+)?(/.*)?$", cleaned
        ):
            return f"http://{cleaned}", None

        if (
            not cleaned.endswith((".html", ".htm"))
            and re.match(r"^[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+(:?\d+)?(/.*)?$", cleaned)
        ):
            return f"https://{cleaned}", None

        raise FileNotFoundError(f"Arquivo local ou URL inválida: {cleaned}")

    async def _extract_accessibility_tree(self, page: Page) -> Dict[str, Any]:
        """
        Extrai a Árvore de Acessibilidade real do navegador.
        1. Tenta `await page.accessibility.snapshot()` (API clássica do Playwright).
        2. Caso `page.accessibility` tenha sido removida na versão instalada do Playwright (>= 1.49),
           utiliza automaticamente uma sessão CDP (`Accessibility.getFullAXTree`) para obter a árvore real.
        """
        try:
            accessibility_api = getattr(page, "accessibility", None)
            if accessibility_api is not None and hasattr(accessibility_api, "snapshot"):
                snapshot = await accessibility_api.snapshot()
                if snapshot:
                    return snapshot
        except Exception:
            pass

        # Fallback via Chrome DevTools Protocol (CDP) Accessibility.getFullAXTree
        try:
            cdp_session = await page.context.new_cdp_session(page)
            ax_tree_raw = await cdp_session.send("Accessibility.getFullAXTree")
            await cdp_session.detach()
            nodes = ax_tree_raw.get("nodes", [])
            simplified_nodes: List[Dict[str, Any]] = []
            for node in nodes:
                if node.get("ignored"):
                    continue
                role = node.get("role", {}).get("value", "")
                name = node.get("name", {}).get("value", "")
                if role in ("none", "generic", "InlineTextBox", "StaticText") and not name:
                    continue
                simplified_nodes.append(
                    {
                        "role": role,
                        "name": name,
                        "description": node.get("description", {}).get("value", ""),
                        "focusable": any(
                            p.get("name") == "focusable" and p.get("value", {}).get("value") is True
                            for p in node.get("properties", [])
                        ),
                    }
                )
            return {
                "role": "WebArea",
                "name": await page.title(),
                "total_ax_nodes": len(nodes),
                "children": simplified_nodes[:120],
            }
        except Exception as exc:
            return {
                "role": "WebArea",
                "name": await page.title(),
                "note": f"AXTree fallback info: {exc}",
                "children": [],
            }

    async def _launch_browser(self, p: Any) -> Any:
        """
        Inicia o navegador Chromium headless do Playwright.
        Caso o binário dedicado do Playwright ainda não tenha sido baixado (`playwright install chromium`),
        realiza fallback automático para o Google Chrome ou Microsoft Edge instalados no sistema.
        """
        for channel in (None, "chrome", "msedge"):
            try:
                if channel is None:
                    return await p.chromium.launch(headless=True)
                return await p.chromium.launch(headless=True, channel=channel)
            except Exception:
                continue
        raise RuntimeError(
            "Não foi possível iniciar o Chromium headless. Execute `playwright install chromium` no terminal."
        )

    async def scan(
        self,
        target: str,
        save_screenshot: bool = True,
        viewport: str = "desktop",
        screenshot_filename: str = "latest_screenshot.png",
    ) -> Dict[str, Any]:
        """
        Executa o escaneamento completo da página alvo via Playwright assíncrono.
        Retorna um dicionário contendo:
        - `target`: URL ou caminho original
        - `resolved_url`: URL aberta no navegador
        - `local_path`: caminho em disco (se arquivo local)
        - `viewport`: perfil de viewport utilizado (`desktop`, `tablet`, `mobile`)
        - `screenshot_base64`: imagem PNG de página inteira codificada em Base64
        - `screenshot_path`: caminho do screenshot salvo em `reports/`
        - `accessibility_tree`: snapshot da Árvore de Acessibilidade
        - `dom_filtered`: elementos filtrados nos pilares, dimensões, outline e mapa de foco
        """
        resolved_url, local_path = self.resolve_target_url(target)
        screenshot_path = self.reports_dir / screenshot_filename
        vp_dims = VIEWPORT_PRESETS.get(viewport.lower(), VIEWPORT_PRESETS["desktop"])

        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            context = await browser.new_context(
                viewport=vp_dims,
                device_scale_factor=1,
            )
            page = await context.new_page()

            try:
                try:
                    await page.goto(resolved_url, wait_until="networkidle", timeout=20000)
                except Exception:
                    # Fallback para sites pesados com conexões contínuas (analytics/websockets)
                    await page.goto(resolved_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(1500)

                # Se for uma URL remota, salva um snapshot local do DOM renderizado com <base href>
                # para permitir que o Auto-Fixer e o Live Preview também funcionem em sites externos!
                if local_path is None:
                    try:
                        rendered_html = await page.content()
                        if "<base " not in rendered_html.lower() and "<head" in rendered_html.lower():
                            rendered_html = re.sub(
                                r"(<head[^>]*>)",
                                rf'\1<base href="{resolved_url}">',
                                rendered_html,
                                count=1,
                                flags=re.IGNORECASE,
                            )
                        snapshot_file = self.reports_dir / "remote_snapshot.html"
                        snapshot_file.write_text(rendered_html, encoding="utf-8")
                        local_path = snapshot_file
                    except Exception:
                        pass

                # Captura de screenshot de página inteira
                screenshot_bytes = await page.screenshot(full_page=True, type="png")
                if save_screenshot:
                    screenshot_path.write_bytes(screenshot_bytes)
                    # Mantém também latest_screenshot.png atualizado
                    latest_default = self.reports_dir / "latest_screenshot.png"
                    if screenshot_path != latest_default:
                        latest_default.write_bytes(screenshot_bytes)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

                # Extração da Árvore de Acessibilidade (Accessibility Tree)
                ax_tree = await self._extract_accessibility_tree(page)

                # Injeção de JS para filtragem cirúrgica no DOM + coordenadas + mapa de foco
                dom_filtered = await page.evaluate(A11Y_DOM_FILTER_JS)

                return {
                    "target": target,
                    "resolved_url": resolved_url,
                    "local_path": str(local_path) if local_path else None,
                    "viewport": viewport.lower(),
                    "viewport_dimensions": vp_dims,
                    "screenshot_base64": screenshot_b64,
                    "screenshot_path": str(screenshot_path) if save_screenshot else None,
                    "screenshot_filename": screenshot_filename if save_screenshot else None,
                    "accessibility_tree": ax_tree,
                    "dom_filtered": dom_filtered,
                }
            finally:
                await context.close()
                await browser.close()

    async def scan_raw_html(
        self,
        html_content: str,
        filename: str = "playground_input.html",
        viewport: str = "desktop",
    ) -> Dict[str, Any]:
        """Salva um snippet/documento HTML bruto em `reports/` e executa o scan completo."""
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
        if not safe_name.endswith(".html"):
            safe_name += ".html"
        temp_path = self.reports_dir / safe_name
        temp_path.write_text(html_content, encoding="utf-8")
        return await self.scan(target=str(temp_path), save_screenshot=True, viewport=viewport)

    def scan_sync(
        self,
        target: str,
        save_screenshot: bool = True,
        viewport: str = "desktop",
        screenshot_filename: str = "latest_screenshot.png",
    ) -> Dict[str, Any]:
        """Wrapper síncrono conveniente para chamadas diretas via CLI (Typer)."""
        return asyncio.run(
            self.scan(
                target=target,
                save_screenshot=save_screenshot,
                viewport=viewport,
                screenshot_filename=screenshot_filename,
            )
        )
