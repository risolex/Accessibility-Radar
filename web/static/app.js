/**
 * web/static/app.js — Lógica Principal da Interface Web do Accessibility Radar
 *
 * Controla:
 * - Execução assíncrona de Scan, Fix Seletivo e Ciclo Autônomo (Demo Kiroween)
 * - Renderização do Scorecard, 5 Pilares WCAG 2.2, Filtros e Diffs de Código
 * - Inspetor Visual com Hotspots (Bounding Boxes), Mapa de Ordem de Foco (Tab) e Simulador de Daltonismo
 * - Explorador da Accessibility Tree, Estrutura de Headings/Landmarks e Simulador de Leitor de Tela
 * - Calculadora Matemática de Contraste W3C em tempo real
 * - Histórico de Auditorias e Configurações de Provedores de IA (.env)
 */

const PILLARS_META = [
    {
        key: "contrast_visibility",
        label: "1. Contraste e Visibilidade",
        criteria: "WCAG 1.4.3 (AA) · 1.4.11 (AA)",
    },
    {
        key: "muted_interactives",
        label: "2. Elementos Interativos Mudos",
        criteria: "WCAG 4.1.2 (A) · 2.4.4 · 1.3.1",
    },
    {
        key: "media_semantics",
        label: "3. Semântica de Mídia (Vision)",
        criteria: "WCAG 1.1.1 Non-text Content (A)",
    },
    {
        key: "focus_keyboard",
        label: "4. Ordem de Foco e Teclado",
        criteria: "WCAG 2.4.3 · 2.4.7 (AA) · 2.1.1 · 2.1.2",
    },
    {
        key: "semantic_structure",
        label: "5. Estrutura e Semântica",
        criteria: "WCAG 3.1.1 · 2.4.2 · 1.3.1 · 2.4.6",
    },
];

const appState = {
    inputMode: "url", // 'url' | 'html'
    currentAnalysis: null,
    verifiedAnalysis: null,
    hasFixedPage: false,
    reportMarkdown: "",
    history: [],
    settings: {},
    selectedIssueIds: new Set(),
    customOverrides: {},
    pillarFilter: "all",
    severityFilter: "all",
    searchQuery: "",
    overlayMode: "issues", // 'issues' | 'taborder' | 'none'
    screenshotVersion: "before", // 'before' | 'after'
    activeHotspotId: null,
};

// =============================================================================
// Utilitários de UI e Formatação
// =============================================================================

function escapeHtml(str) {
    return String(str ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function showToast(message) {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.remove();
    }, 3600);
}

function setPipelineLoading(isLoading, stepText = "Processando no navegador headless Playwright...") {
    const bar = document.getElementById("pipeline-status-bar");
    const textEl = document.getElementById("pipeline-step-text");
    const btnScan = document.getElementById("btn-run-scan");
    const btnDemo = document.getElementById("btn-run-demo");
    const btnFix = document.getElementById("btn-apply-selected-fixes");

    if (textEl) textEl.textContent = stepText;
    if (bar) bar.classList.toggle("hidden", !isLoading);
    if (btnScan) btnScan.disabled = isLoading;
    if (btnDemo) btnDemo.disabled = isLoading;
    if (btnFix) btnFix.disabled = isLoading;
}

function switchTab(tabId) {
    document.querySelectorAll(".sidebar-nav .nav-item").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.tab === tabId);
    });
    document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === `tab-${tabId}`);
    });
    if (tabId === "visual") {
        renderVisualInspector();
    }
}

// =============================================================================
// Cálculos Matemáticos W3C (Contraste Client-Side Instantâneo)
// =============================================================================

function hexToRgb(hexStr) {
    let h = String(hexStr || "#000000").trim().replace(/^#/, "");
    if (h.length === 3) {
        h = h.split("").map((c) => c + c).join("");
    }
    if (!/^[0-9a-fA-F]{6}$/.test(h)) return { r: 0, g: 0, b: 0 };
    return {
        r: parseInt(h.slice(0, 2), 16),
        g: parseInt(h.slice(2, 4), 16),
        b: parseInt(h.slice(4, 6), 16),
    };
}

function getRelativeLuminance(hexStr) {
    const { r, g, b } = hexToRgb(hexStr);
    const sRGB = [r / 255, g / 255, b / 255];
    const [R, G, B] = sRGB.map((c) =>
        c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
    );
    return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

function computeContrastRatio(fgHex, bgHex) {
    const l1 = getRelativeLuminance(fgHex);
    const l2 = getRelativeLuminance(bgHex);
    const lighter = Math.max(l1, l2);
    const darker = Math.min(l1, l2);
    return Number(((lighter + 0.05) / (darker + 0.05)).toFixed(2));
}

function suggestAccessibleColor(bgHex) {
    const bgLum = getRelativeLuminance(bgHex);
    const candidate = bgLum > 0.35 ? "#1a202c" : "#f8fafc";
    const ratio = computeContrastRatio(candidate, bgHex);
    return { color: candidate, ratio };
}

// =============================================================================
// Renderização Geral do Estado (Dashboard, Pilares, Violações)
// =============================================================================

function syncAnalysisState(analysis, verified = null, reportMd = "", history = null) {
    appState.currentAnalysis = analysis;
    appState.verifiedAnalysis = verified;
    if (reportMd) appState.reportMarkdown = reportMd;
    if (Array.isArray(history)) appState.history = history;

    // Seleciona todas as issues por padrão para o Auto-Fixer
    appState.selectedIssueIds = new Set((analysis?.issues || []).map((i) => i.id));
    appState.customOverrides = {};

    renderDashboard();
    renderIssuesList();
    renderVisualInspector();
    renderFixerStudio();
    renderA11yTreeAndScreenReader();
    renderDetectedContrastsList();
    renderReportsAndHistory();
}

function renderDashboard() {
    const analysis = appState.currentAnalysis;
    const verified = appState.verifiedAnalysis;
    if (!analysis) return;

    const summary = analysis.summary || {};
    const score = summary.score ?? 0;
    const totalIssues = summary.total_issues ?? 0;
    const byPillar = summary.by_pillar || {};
    const bySeverity = summary.by_severity || {};

    // Atualiza badge na sidebar
    const navBadge = document.getElementById("nav-badge-issues");
    if (navBadge) navBadge.textContent = String(totalIssues);

    // Atualiza status do motor na sidebar
    const engineText = document.getElementById("engine-status-text");
    if (engineText) {
        engineText.textContent = analysis.mode || "Smart Fallback";
    }

    // Banner de Verificação Pós-Correção (Ciclo Fechado)
    const vBanner = document.getElementById("verification-banner");
    if (vBanner) {
        if (verified && verified.summary) {
            vBanner.classList.remove("hidden");
            document.getElementById("v-score-before").textContent = `${score}`;
            document.getElementById("v-score-after").textContent = `${verified.summary.score}`;
            document.getElementById("v-issues-fixed").textContent = `${totalIssues} → ${verified.summary.total_issues}`;
        } else {
            vBanner.classList.add("hidden");
        }
    }

    // Gauge Radial do Score
    const scoreValEl = document.getElementById("metric-score-value");
    const ringEl = document.getElementById("score-ring-circle");
    const statusPill = document.getElementById("metric-wcag-status");
    const displayScore = verified?.summary ? verified.summary.score : score;
    const displayStatus = verified?.summary ? verified.summary.wcag_status : (summary.wcag_status || "N/A");

    if (scoreValEl) scoreValEl.textContent = String(score);
    if (ringEl) {
        const circumference = 314.16;
        const offset = circumference - (Math.max(0, Math.min(100, score)) / 100) * circumference;
        ringEl.style.strokeDashoffset = String(offset);
        if (score >= 90) ringEl.style.stroke = "var(--status-success)";
        else if (score >= 70) ringEl.style.stroke = "var(--status-warning)";
        else ringEl.style.stroke = "var(--status-danger)";
    }
    if (statusPill) {
        statusPill.textContent = summary.wcag_status || "Auditado";
        statusPill.style.color =
            score >= 90 ? "var(--status-success)" : score >= 70 ? "var(--status-warning)" : "var(--status-danger)";
    }

    document.getElementById("metric-target-label").textContent = analysis.target || "N/A";
    document.getElementById("metric-dom-info").textContent = `${analysis.total_dom_nodes || "--"} nós • lang: ${analysis.lang || "ausente"}`;
    const vpDims = analysis.viewport_dimensions || { width: 1280, height: 900 };
    document.getElementById("metric-viewport-info").textContent = `${analysis.viewport || "desktop"} (${vpDims.width}×${vpDims.height})`;
    document.getElementById("metric-total-issues-badge").textContent = `${totalIssues} violação(ões)`;

    // Lista dos 5 Pilares
    const pillarsContainer = document.getElementById("pillars-breakdown-list");
    if (pillarsContainer) {
        pillarsContainer.innerHTML = PILLARS_META.map((p) => {
            const count = byPillar[p.key] || 0;
            const badgeClass = count === 0 ? "pass" : "fail";
            const badgeText = count === 0 ? "✔ 0 falhas" : `✖ ${count} falha(s)`;
            return `
                <div class="pillar-row" data-pillar-jump="${p.key}" title="Clique para filtrar violações deste pilar">
                    <div class="pillar-row-left">
                        <span class="pillar-name">${escapeHtml(p.label)}</span>
                        <span class="pillar-criteria">${escapeHtml(p.criteria)}</span>
                    </div>
                    <span class="pillar-badge ${badgeClass}">${badgeText}</span>
                </div>
            `;
        }).join("");

        pillarsContainer.querySelectorAll(".pillar-row").forEach((row) => {
            row.addEventListener("click", () => {
                const key = row.dataset.pillarJump;
                setPillarFilter(key);
            });
        });
    }

    // Distribuição por Severidade
    const sevContainer = document.getElementById("severity-breakdown-list");
    if (sevContainer) {
        const items = [
            { key: "critical", label: "Crítico (Critical)", cls: "sev-critical" },
            { key: "serious", label: "Sério (Serious)", cls: "sev-serious" },
            { key: "moderate", label: "Moderado (Moderate)", cls: "sev-moderate" },
            { key: "minor", label: "Menor (Minor)", cls: "sev-minor" },
        ];
        sevContainer.innerHTML = items
            .map(
                (s) => `
            <div class="sev-stat-box ${s.cls}">
                <span class="sev-stat-label">${s.label}</span>
                <span class="sev-stat-count">${bySeverity[s.key] || 0}</span>
            </div>
        `
            )
            .join("");
    }
}

function setPillarFilter(pillarKey) {
    appState.pillarFilter = pillarKey;
    document.querySelectorAll("#pillar-filter-pills .filter-pill").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.pillarFilter === pillarKey);
    });
    renderIssuesList();
}

function getFilteredIssues() {
    const issues = appState.currentAnalysis?.issues || [];
    const q = appState.searchQuery.trim().toLowerCase();
    return issues.filter((iss) => {
        if (appState.pillarFilter !== "all" && iss.pillar !== appState.pillarFilter) return false;
        if (appState.severityFilter !== "all" && (iss.severity || "").toLowerCase() !== appState.severityFilter) {
            return false;
        }
        if (q) {
            const hay = `${iss.id} ${iss.title} ${iss.selector} ${iss.wcag_criterion} ${iss.description}`.toLowerCase();
            if (!hay.includes(q)) return false;
        }
        return true;
    });
}

function renderIssuesList() {
    const container = document.getElementById("issues-list-container");
    if (!container) return;

    if (!appState.currentAnalysis) {
        container.innerHTML = `<div class="text-muted">Clique em "Auditar (Scan)" ou "Ciclo Autônomo (Demo)" para iniciar o diagnóstico.</div>`;
        return;
    }

    const filtered = getFilteredIssues();
    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="card" style="text-align:center; padding:28px; border-color: rgba(16,185,129,0.35);">
                <strong style="color: var(--status-success); font-size: 15px;">✔ Nenhuma violação encontrada para os filtros selecionados!</strong>
                <p class="text-muted" style="margin-top:4px;">A página cumpre os critérios verificados da WCAG 2.2.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filtered
        .map((iss) => {
            const sev = (iss.severity || "serious").toLowerCase();
            return `
            <article class="issue-card" data-issue-id="${escapeHtml(iss.id)}">
                <div class="issue-card-top">
                    <div class="issue-meta-badges">
                        <span class="badge-id">${escapeHtml(iss.id)}</span>
                        <span class="badge-sev ${escapeHtml(sev)}">${escapeHtml(sev)}</span>
                        <span class="badge-wcag">${escapeHtml(iss.wcag_criterion)} (${escapeHtml(iss.wcag_level)})</span>
                        <code class="badge-selector">${escapeHtml(iss.selector)}</code>
                    </div>
                    <div style="display:flex; gap:6px;">
                        <button type="button" class="btn btn-xs btn-ghost btn-locate-hotspot" data-issue-id="${escapeHtml(iss.id)}">
                            ⌖ Ver no Screenshot
                        </button>
                        <button type="button" class="btn btn-xs btn-ghost btn-copy-patch" data-issue-id="${escapeHtml(iss.id)}">
                            📋 Copiar Patch
                        </button>
                    </div>
                </div>
                <h3 class="issue-title">${escapeHtml(iss.title)}</h3>
                <p class="issue-desc">${escapeHtml(iss.description)}</p>
                <p class="issue-impact"><strong>Impacto no usuário:</strong> ${escapeHtml(iss.impact)}</p>
                <div class="issue-code-compare">
                    <div class="code-box before">
                        <div class="code-box-header">
                            <span>❌ Antes (Violação DOM)</span>
                        </div>
                        <pre><code>${escapeHtml(iss.original_code)}</code></pre>
                    </div>
                    <div class="code-box after">
                        <div class="code-box-header">
                            <span>✅ Depois (Patch WCAG 2.2)</span>
                        </div>
                        <pre><code>${escapeHtml(iss.fixed_code)}</code></pre>
                    </div>
                </div>
            </article>
        `;
        })
        .join("");

    container.querySelectorAll(".btn-locate-hotspot").forEach((btn) => {
        btn.addEventListener("click", () => {
            appState.activeHotspotId = btn.dataset.issueId;
            appState.overlayMode = "issues";
            appState.screenshotVersion = "before";
            switchTab("visual");
        });
    });

    container.querySelectorAll(".btn-copy-patch").forEach((btn) => {
        btn.addEventListener("click", () => {
            const issue = (appState.currentAnalysis?.issues || []).find((i) => i.id === btn.dataset.issueId);
            if (issue && issue.fixed_code) {
                navigator.clipboard.writeText(issue.fixed_code);
                showToast(`Patch ${issue.id} copiado para a área de transferência!`);
            }
        });
    });
}

// =============================================================================
// TAB 2: Inspetor Visual, Hotspots e Mapa de Ordem de Foco (Tab)
// =============================================================================

function renderVisualInspector() {
    const analysis =
        appState.screenshotVersion === "after" && appState.verifiedAnalysis
            ? appState.verifiedAnalysis
            : appState.currentAnalysis;
    if (!analysis) return;

    const imgEl = document.getElementById("inspector-screenshot-img");
    const hotspotsLayer = document.getElementById("hotspots-layer");
    const svgLayer = document.getElementById("focus-path-svg");
    const sidebarList = document.getElementById("visual-sidebar-list");
    const sidebarTitle = document.getElementById("visual-sidebar-title");

    // Atualiza imagem do screenshot com cache-busting
    const ts = Date.now();
    const imgFile =
        appState.screenshotVersion === "after" && appState.verifiedAnalysis
            ? "after_screenshot.png"
            : analysis.screenshot_filename || "before_screenshot.png";
    if (imgEl) {
        imgEl.src = `/reports/${imgFile}?t=${ts}`;
    }

    // Atualiza botões segmentados
    document.querySelectorAll("[data-overlay-mode]").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.overlayMode === appState.overlayMode);
    });
    document.querySelectorAll("[data-screenshot-ver]").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.screenshotVer === appState.screenshotVersion);
    });

    const pageDims = analysis.page_dimensions || { width: 1280, height: 900 };
    const pageW = Math.max(1, pageDims.width || 1280);
    const pageH = Math.max(1, pageDims.height || 900);

    hotspotsLayer.innerHTML = "";
    svgLayer.innerHTML = "";

    if (appState.overlayMode === "none") {
        sidebarTitle.textContent = "Visualização Limpa";
        sidebarList.innerHTML = `<div class="text-muted">Selecione "Hotspots de Violações" ou "Mapa de Ordem de Foco" na barra superior para inspecionar os elementos sobre o screenshot.</div>`;
        return;
    }

    if (appState.overlayMode === "issues") {
        const issues = analysis.issues || [];
        sidebarTitle.textContent = `Hotspots de Violações (${issues.length})`;

        if (issues.length === 0) {
            sidebarList.innerHTML = `<div class="text-muted">✔ Zero violações nesta versão da página!</div>`;
            return;
        }

        hotspotsLayer.innerHTML = issues
            .map((iss, idx) => {
                const r = iss.rect || { x: 20, y: 20 + idx * 45, width: 140, height: 36 };
                const leftPct = Math.min(96, Math.max(0, (r.x / pageW) * 100));
                const topPct = Math.min(96, Math.max(0, (r.y / pageH) * 100));
                const widthPct = Math.min(100 - leftPct, Math.max(2.5, ((r.width || 80) / pageW) * 100));
                const heightPct = Math.min(100 - topPct, Math.max(2.2, ((r.height || 32) / pageH) * 100));
                const isActive = appState.activeHotspotId === iss.id;

                return `
                    <div
                        class="hotspot-box ${isActive ? "active" : ""}"
                        data-hotspot-id="${escapeHtml(iss.id)}"
                        style="left:${leftPct}%; top:${topPct}%; width:${widthPct}%; height:${heightPct}%;"
                        title="${escapeHtml(iss.id)}: ${escapeHtml(iss.title)}"
                    >
                        <span class="hotspot-pin">${escapeHtml(iss.id.replace("A11Y-", "#"))}</span>
                    </div>
                `;
            })
            .join("");

        sidebarList.innerHTML = issues
            .map((iss) => {
                const isActive = appState.activeHotspotId === iss.id;
                return `
                    <div class="visual-list-item ${isActive ? "active" : ""}" data-sidebar-issue="${escapeHtml(iss.id)}">
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <span class="badge-id">${escapeHtml(iss.id)}</span>
                            <code style="font-size:11px; color:var(--accent-text);">${escapeHtml(iss.selector)}</code>
                        </div>
                        <div style="font-weight:600; font-size:12.5px;">${escapeHtml(iss.title)}</div>
                        <div class="text-muted" style="font-size:11px; margin-top:3px;">${escapeHtml(iss.wcag_criterion)}</div>
                    </div>
                `;
            })
            .join("");

        const bindHotspotSelect = (id) => {
            appState.activeHotspotId = id;
            hotspotsLayer.querySelectorAll(".hotspot-box").forEach((el) => {
                el.classList.toggle("active", el.dataset.hotspotId === id);
                if (el.dataset.hotspotId === id) {
                    el.scrollIntoView({ behavior: "smooth", block: "center" });
                }
            });
            sidebarList.querySelectorAll(".visual-list-item").forEach((el) => {
                el.classList.toggle("active", el.dataset.sidebarIssue === id);
            });
        };

        hotspotsLayer.querySelectorAll(".hotspot-box").forEach((box) => {
            box.addEventListener("click", () => bindHotspotSelect(box.dataset.hotspotId));
        });
        sidebarList.querySelectorAll(".visual-list-item").forEach((item) => {
            item.addEventListener("click", () => bindHotspotSelect(item.dataset.sidebarIssue));
        });
        return;
    }

    // Modo: Mapa de Ordem de Foco (Tab Order)
    const focusMap = analysis.focus_order_map || [];
    sidebarTitle.textContent = `Sequência Real de Tab (${focusMap.length} paradas)`;

    svgLayer.setAttribute("viewBox", `0 0 ${pageW} ${pageH}`);
    svgLayer.setAttribute("preserveAspectRatio", "none");

    let polylinePoints = [];
    hotspotsLayer.innerHTML = focusMap
        .map((node) => {
            const r = node.rect || { x: 0, y: 0, width: 40, height: 28 };
            const cx = r.x + Math.max(16, r.width / 2);
            const cy = r.y + Math.max(14, r.height / 2);
            polylinePoints.push(`${cx},${cy}`);

            const leftPct = Math.min(96, Math.max(0, (r.x / pageW) * 100));
            const topPct = Math.min(96, Math.max(0, (r.y / pageH) * 100));
            const widthPct = Math.min(100 - leftPct, Math.max(2.2, ((r.width || 60) / pageW) * 100));
            const heightPct = Math.min(100 - topPct, Math.max(2.0, ((r.height || 28) / pageH) * 100));
            const hasAnomaly = node.has_positive_tabindex || node.missing_focus_ring || node.is_trap || node.is_muted;

            return `
                <div
                    class="hotspot-box tab-node ${hasAnomaly ? "anomaly" : ""}"
                    style="left:${leftPct}%; top:${topPct}%; width:${widthPct}%; height:${heightPct}%;"
                    title="Tab #${node.order}: ${escapeHtml(node.selector)} — ${escapeHtml(node.label)}"
                >
                    <span class="hotspot-pin">${node.order}</span>
                </div>
            `;
        })
        .join("");

    if (polylinePoints.length > 1) {
        svgLayer.innerHTML = `
            <polyline
                fill="none"
                stroke="#8b5cf6"
                stroke-width="3"
                stroke-dasharray="7 5"
                points="${polylinePoints.join(" ")}"
            />
        `;
    }

    sidebarList.innerHTML = focusMap
        .map((node) => {
            const badges = [];
            if (node.has_positive_tabindex) badges.push(`<span class="badge-sev serious">tabindex=${node.tabindex}</span>`);
            if (node.missing_focus_ring) badges.push(`<span class="badge-sev serious">sem foco visível</span>`);
            if (node.is_trap) badges.push(`<span class="badge-sev critical">keyboard trap</span>`);
            if (node.is_muted) badges.push(`<span class="badge-sev critical">mudo</span>`);

            return `
                <div class="visual-list-item">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span class="badge-id">Tab #${node.order}</span>
                        <code style="font-size:11px; color:var(--accent-text);">${escapeHtml(node.selector)}</code>
                    </div>
                    <div style="font-weight:600; font-size:12.5px;">${escapeHtml(node.label)}</div>
                    ${badges.length ? `<div style="display:flex; gap:4px; flex-wrap:wrap; margin-top:6px;">${badges.join("")}</div>` : ""}
                </div>
            `;
        })
        .join("");
}

// =============================================================================
// TAB 3: Auto-Fixer Studio & Live Split Iframe Preview
// =============================================================================

function renderFixerStudio() {
    const container = document.getElementById("fixer-patches-container");
    const countEl = document.getElementById("fixer-selected-count");
    const selectAllCheckbox = document.getElementById("fixer-select-all");
    if (!container) return;

    const issues = appState.currentAnalysis?.issues || [];
    if (countEl) countEl.textContent = String(appState.selectedIssueIds.size);
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = issues.length > 0 && appState.selectedIssueIds.size === issues.length;
    }

    // Atualiza iframes de Live Preview Antes vs Depois
    const iframeBefore = document.getElementById("iframe-preview-before");
    const iframeAfter = document.getElementById("iframe-preview-after");
    const beforeLabel = document.getElementById("preview-before-label");
    const ts = Date.now();

    if (iframeBefore && appState.currentAnalysis) {
        const localPath = appState.currentAnalysis.local_path;
        if (localPath) {
            iframeBefore.src = `/preview/local?path=${encodeURIComponent(localPath)}&t=${ts}`;
            if (beforeLabel) beforeLabel.textContent = appState.currentAnalysis.target || "original.html";
        } else {
            iframeBefore.src = "/preview/broken";
        }
    }
    if (iframeAfter) {
        iframeAfter.src = `/reports/fixed_page.html?t=${ts}`;
    }

    if (issues.length === 0) {
        container.innerHTML = `<div class="card text-muted">Nenhuma violação pendente para remediação.</div>`;
        return;
    }

    container.innerHTML = issues
        .map((iss) => {
            const isChecked = appState.selectedIssueIds.has(iss.id);
            const metrics = iss.computed_metrics || {};
            let defaultEditableValue = "";
            let overrideLabel = "Valor customizado (opcional):";

            if (iss.pillar === "contrast_visibility") {
                defaultEditableValue = metrics.suggested_foreground || "#1a202c";
                overrideLabel = "Cor de texto sugerida (Hex):";
            } else if (iss.pillar === "muted_interactives") {
                defaultEditableValue = metrics.inferred_label || "";
                overrideLabel = "Rótulo acessível (aria-label):";
            } else if (iss.pillar === "media_semantics") {
                defaultEditableValue = metrics.suggested_alt || "";
                overrideLabel = "Descrição visual (alt / title):";
            }

            const currentOverride = appState.customOverrides[iss.id] ?? defaultEditableValue;
            const showOverrideInput = ["contrast_visibility", "muted_interactives", "media_semantics"].includes(
                iss.pillar
            );

            return `
            <div class="patch-item-card">
                <div class="patch-item-header">
                    <label class="patch-checkbox-label">
                        <input
                            type="checkbox"
                            class="patch-issue-checkbox"
                            data-issue-id="${escapeHtml(iss.id)}"
                            ${isChecked ? "checked" : ""}
                        />
                        <span class="badge-id">${escapeHtml(iss.id)}</span>
                        <span>${escapeHtml(iss.title)}</span>
                    </label>
                    <div style="display:flex; gap:8px; align-items:center;">
                        <span class="badge-wcag">${escapeHtml(iss.wcag_criterion)}</span>
                        <code class="badge-selector">${escapeHtml(iss.selector)}</code>
                    </div>
                </div>

                <p class="issue-desc">${escapeHtml(iss.remediation_notes)}</p>

                <div class="issue-code-compare">
                    <div class="code-box before">
                        <div class="code-box-header"><span>Antes (Original)</span></div>
                        <pre><code>${escapeHtml(iss.original_code)}</code></pre>
                    </div>
                    <div class="code-box after">
                        <div class="code-box-header"><span>Depois (Patch Gerado)</span></div>
                        <pre><code>${escapeHtml(iss.fixed_code)}</code></pre>
                    </div>
                </div>

                ${
                    showOverrideInput
                        ? `
                    <div class="patch-override-row">
                        <label for="override-${escapeHtml(iss.id)}">${escapeHtml(overrideLabel)}</label>
                        <input
                            type="text"
                            id="override-${escapeHtml(iss.id)}"
                            class="target-input patch-override-input"
                            style="background:var(--bg-surface-elevated); padding:6px 10px; border-radius:6px; border:1px solid var(--border-subtle);"
                            data-issue-id="${escapeHtml(iss.id)}"
                            value="${escapeHtml(currentOverride)}"
                        />
                    </div>
                `
                        : ""
                }
            </div>
        `;
        })
        .join("");

    container.querySelectorAll(".patch-issue-checkbox").forEach((cb) => {
        cb.addEventListener("change", () => {
            const id = cb.dataset.issueId;
            if (cb.checked) appState.selectedIssueIds.add(id);
            else appState.selectedIssueIds.delete(id);
            if (countEl) countEl.textContent = String(appState.selectedIssueIds.size);
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = appState.selectedIssueIds.size === issues.length;
            }
        });
    });

    container.querySelectorAll(".patch-override-input").forEach((inp) => {
        inp.addEventListener("input", () => {
            appState.customOverrides[inp.dataset.issueId] = inp.value;
        });
    });
}

// =============================================================================
// TAB 4: Accessibility Tree, Document Outline & Screen Reader Simulator
// =============================================================================

function renderA11yTreeAndScreenReader() {
    const analysis = appState.currentAnalysis;
    if (!analysis) return;

    // 1. Simulador de Leitor de Tela (NVDA / VoiceOver) Antes vs Depois
    const srContainer = document.getElementById("sr-simulator-list");
    if (srContainer) {
        const issues = analysis.issues || [];
        const relevantIssues = issues.filter((i) =>
            ["muted_interactives", "media_semantics", "focus_keyboard"].includes(i.pillar)
        );

        if (relevantIssues.length === 0) {
            srContainer.innerHTML = `<div class="text-muted">Todos os controles e mídias possuem anúncios semânticos claros para leitores de tela.</div>`;
        } else {
            srContainer.innerHTML = relevantIssues
                .map((iss) => {
                    const m = iss.computed_metrics || {};
                    let beforeSpeech = `"elemento sem rótulo"`;
                    let afterSpeech = `"elemento rotulado"`;

                    if (iss.pillar === "muted_interactives") {
                        beforeSpeech = `🔊 NVDA Antes: "botão, em branco (sem nome acessível)"`;
                        afterSpeech = `🔊 NVDA Depois: "botão, ${m.inferred_label || "Controle acessível"}"`;
                    } else if (iss.pillar === "media_semantics") {
                        const cur = m.current_alt;
                        beforeSpeech = cur
                            ? `🔊 NVDA Antes: "gráfico, ${cur}" (genérico/inútil)`
                            : `🔊 NVDA Antes: "gráfico, data_image_svg_xml_utf8 (ou ignorado)"`;
                        afterSpeech = `🔊 NVDA Depois: "gráfico, ${m.suggested_alt || "Descrição rica"}"`;
                    } else if (iss.pillar === "focus_keyboard") {
                        if (m.issue_type === "non_keyboard_interactive") {
                            beforeSpeech = `🔊 Teclado Antes: (Inalcançável via tecla Tab — ignorado pelo foco)`;
                            afterSpeech = `🔊 NVDA Depois: "botão, focável via Tab e acionável com Enter/Espaço"`;
                        } else if (m.issue_type === "keyboard_trap") {
                            beforeSpeech = `🔊 Teclado Antes: (ARMADILHA DE TECLADO — Tab e Escape bloqueados!)`;
                            afterSpeech = `🔊 Teclado Depois: "Navegação Tab livre desbloqueada"`;
                        } else {
                            beforeSpeech = `🔊 Teclado Antes: "Ordem de foco quebrada ou indicador visual invisível"`;
                            afterSpeech = `🔊 Teclado Depois: "Sequência lógica DOM + anel :focus-visible ativo"`;
                        }
                    }

                    return `
                        <div class="sr-utterance-card">
                            <div style="display:flex; justify-content:space-between;">
                                <span class="badge-id">${escapeHtml(iss.id)}</span>
                                <code style="font-size:11px; color:var(--accent-text);">${escapeHtml(iss.selector)}</code>
                            </div>
                            <div class="sr-line before">❌ ${escapeHtml(beforeSpeech)}</div>
                            <div class="sr-line after">✅ ${escapeHtml(afterSpeech)}</div>
                        </div>
                    `;
                })
                .join("");
        }
    }

    // 2. Document Outline: Landmarks & Headings
    const outline = analysis.document_outline || { headings: [], landmarks: [] };
    const landmarksEl = document.getElementById("outline-landmarks-list");
    if (landmarksEl) {
        const landmarks = outline.landmarks || [];
        landmarksEl.innerHTML = landmarks.length
            ? landmarks
                  .map(
                      (lm) => `
                <div class="landmark-chip">
                    <strong style="color:var(--accent-text);">${escapeHtml(lm.role)}</strong>
                    <span class="text-muted">&lt;${escapeHtml(lm.tag)}&gt;</span>
                </div>
            `
                  )
                  .join("")
            : `<span class="text-muted">Nenhuma landmark semântica detectada.</span>`;
    }

    const headingsEl = document.getElementById("outline-headings-list");
    if (headingsEl) {
        const headings = outline.headings || [];
        headingsEl.innerHTML = headings.length
            ? headings
                  .map(
                      (h) => `
                <div class="heading-node" style="margin-left:${(h.level - 1) * 14}px;">
                    <span class="badge-id">H${h.level}</span>
                    <span>${escapeHtml(h.text)}</span>
                    ${h.skipped ? `<span class="badge-sev serious">Salto de nível</span>` : ""}
                </div>
            `
                  )
                  .join("")
            : `<span class="text-muted">Nenhum cabeçalho H1–H6 encontrado.</span>`;
    }

    // 3. Accessibility Tree Nodes
    renderAxTreeNodes("");
}

function renderAxTreeNodes(filterText = "") {
    const container = document.getElementById("ax-nodes-container");
    if (!container) return;
    const axTree = appState.currentAnalysis?.accessibility_tree || {};
    const children = axTree.children || [];
    const q = filterText.trim().toLowerCase();

    const filtered = children.filter((n) => {
        if (!q) return true;
        return `${n.role} ${n.name} ${n.description || ""}`.toLowerCase().includes(q);
    });

    if (filtered.length === 0) {
        container.innerHTML = `<div class="text-muted">Nenhum nó da Accessibility Tree corresponde ao filtro.</div>`;
        return;
    }

    container.innerHTML = filtered
        .map(
            (n) => `
        <div class="ax-node-item">
            <div style="display:flex; justify-content:space-between; margin-bottom:3px;">
                <strong style="color:var(--accent-text); font-family:var(--font-mono);">${escapeHtml(n.role || "node")}</strong>
                ${n.focusable ? `<span class="wcag-tag">focusable</span>` : ""}
            </div>
            <div>${escapeHtml(n.name || "(sem nome acessível)")}</div>
        </div>
    `
        )
        .join("");
}

// =============================================================================
// TAB 5: Laboratório de Contraste W3C
// =============================================================================

function updateContrastCalculator(fgHex, bgHex) {
    const fgPicker = document.getElementById("lab-fg-picker");
    const bgPicker = document.getElementById("lab-bg-picker");
    const fgInput = document.getElementById("lab-fg-hex");
    const bgInput = document.getElementById("lab-bg-hex");

    if (fgInput) fgInput.value = fgHex;
    if (bgInput) bgInput.value = bgHex;
    if (fgPicker && /^#[0-9a-fA-F]{6}$/.test(fgHex)) fgPicker.value = fgHex;
    if (bgPicker && /^#[0-9a-fA-F]{6}$/.test(bgHex)) bgPicker.value = bgHex;

    const previewBox = document.getElementById("lab-preview-box");
    if (previewBox) {
        previewBox.style.color = fgHex;
        previewBox.style.backgroundColor = bgHex;
    }

    const ratio = computeContrastRatio(fgHex, bgHex);
    const ratioEl = document.getElementById("lab-ratio-value");
    if (ratioEl) {
        ratioEl.textContent = `${ratio}:1`;
        ratioEl.style.color =
            ratio >= 4.5 ? "var(--status-success)" : ratio >= 3.0 ? "var(--status-warning)" : "var(--status-danger)";
    }

    const updateBadge = (id, passes) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.className = `matrix-item ${passes ? "pass" : "fail"}`;
        el.querySelector("strong").textContent = passes ? "✔ APROVADO" : "✖ FALHA";
    };

    updateBadge("badge-aa-normal", ratio >= 4.5);
    updateBadge("badge-aa-large", ratio >= 3.0);
    updateBadge("badge-aaa-normal", ratio >= 7.0);
    updateBadge("badge-ui-comp", ratio >= 3.0);

    const suggestion = suggestAccessibleColor(bgHex);
    const sugText = document.getElementById("lab-suggested-text");
    const btnApplySug = document.getElementById("btn-apply-suggested-color");
    if (sugText) {
        sugText.textContent = `Usar ${suggestion.color} sobre ${bgHex} (Contraste ${suggestion.ratio}:1)`;
    }
    if (btnApplySug) {
        btnApplySug.onclick = () => updateContrastCalculator(suggestion.color, bgHex);
    }
}

function renderDetectedContrastsList() {
    const container = document.getElementById("detected-contrasts-list");
    if (!container) return;

    const contrastIssues = (appState.currentAnalysis?.issues || []).filter(
        (i) => i.pillar === "contrast_visibility"
    );

    if (contrastIssues.length === 0) {
        container.innerHTML = `<div class="text-muted">Nenhuma falha de contraste detectada na última auditoria.</div>`;
        return;
    }

    container.innerHTML = contrastIssues
        .map((iss) => {
            const m = iss.computed_metrics || {};
            const fg = m.foreground || "#999999";
            const bg = m.background || "#ffffff";
            const ratio = m.current_ratio || 1.5;

            return `
                <div class="detected-contrast-item" data-fg="${escapeHtml(fg)}" data-bg="${escapeHtml(bg)}">
                    <div>
                        <code style="font-size:12px; color:var(--accent-text);">${escapeHtml(iss.selector)}</code>
                        <div class="text-muted" style="font-size:11.5px;">${escapeHtml(fg)} sobre ${escapeHtml(bg)}</div>
                    </div>
                    <div class="swatch-pair">
                        <span class="color-swatch" style="background:${escapeHtml(fg)};" title="Texto: ${escapeHtml(fg)}"></span>
                        <span class="color-swatch" style="background:${escapeHtml(bg)};" title="Fundo: ${escapeHtml(bg)}"></span>
                        <span class="pillar-badge fail">${ratio}:1</span>
                    </div>
                </div>
            `;
        })
        .join("");

    container.querySelectorAll(".detected-contrast-item").forEach((el) => {
        el.addEventListener("click", () => {
            updateContrastCalculator(el.dataset.fg, el.dataset.bg);
            showToast(`Cores de ${el.dataset.fg} / ${el.dataset.bg} carregadas na calculadora!`);
        });
    });
}

// =============================================================================
// TAB 6 & TAB 7: Histórico, Relatórios e Configurações de IA
// =============================================================================

function renderReportsAndHistory() {
    const viewer = document.getElementById("markdown-report-viewer");
    if (viewer && appState.reportMarkdown) {
        viewer.textContent = appState.reportMarkdown;
    }

    const tbody = document.getElementById("history-table-body");
    if (!tbody) return;

    if (!appState.history || appState.history.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-muted">Nenhuma execução registrada no histórico ainda.</td></tr>`;
        return;
    }

    tbody.innerHTML = appState.history
        .map((item) => {
            const dt = item.timestamp ? new Date(item.timestamp).toLocaleString("pt-BR") : "--";
            const afterBadge =
                item.after_score !== null && item.after_score !== undefined
                    ? `<strong style="color:var(--status-success); font-family:var(--font-mono);">${item.after_score}/100</strong>`
                    : `<span class="text-muted">--</span>`;
            return `
                <tr>
                    <td class="mono" style="font-size:11.5px;">${escapeHtml(dt)}</td>
                    <td><code>${escapeHtml(item.target)}</code></td>
                    <td>${escapeHtml(item.viewport || "desktop")}</td>
                    <td><strong class="mono">${item.score}/100</strong></td>
                    <td>${afterBadge}</td>
                    <td>${item.total_issues}</td>
                    <td class="text-muted" style="font-size:11.5px;">${escapeHtml(item.mode)}</td>
                </tr>
            `;
        })
        .join("");
}

function populateSettingsForm(settings) {
    if (!settings) return;
    appState.settings = settings;
    const baseUrlEl = document.getElementById("setting-base-url");
    const modelTextEl = document.getElementById("setting-model-text");
    const modelVisEl = document.getElementById("setting-model-vision");
    const keyStatusEl = document.getElementById("setting-key-status");

    if (baseUrlEl && settings.ai_base_url) baseUrlEl.value = settings.ai_base_url;
    if (modelTextEl && settings.ai_model_text) modelTextEl.value = settings.ai_model_text;
    if (modelVisEl && settings.ai_model_vision) modelVisEl.value = settings.ai_model_vision;
    if (keyStatusEl) {
        keyStatusEl.textContent = settings.ai_configured
            ? `✔ Chave configurada (${settings.ai_api_key_masked}) — Desmarque 'Smart Mock' no topo para usar IA Multimodal.`
            : "Nenhuma chave configurada — Modo Smart Fallback determinístico ativo.";
    }
}

// =============================================================================
// Chamadas à API Backend (Scan, Fix, Demo, Settings)
// =============================================================================

async function executeScan() {
    const target = document.getElementById("scan-target-input").value.trim();
    const rawHtml = document.getElementById("raw-html-textarea").value;
    const viewport = document.getElementById("viewport-select").value;
    const mock = document.getElementById("force-mock-checkbox").checked;

    setPipelineLoading(true, `Escaneando '${appState.inputMode === "html" ? "HTML Playground" : target}' via Playwright Headless...`);
    try {
        const payload = {
            target: target || "tests/broken_page.html",
            raw_html: appState.inputMode === "html" ? rawHtml : null,
            viewport,
            mock,
        };
        const res = await fetch("/api/scan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Erro ao executar scan.");

        appState.screenshotVersion = "before";
        syncAnalysisState(data.analysis, null, data.report_markdown, data.history);
        showToast(`Auditoria concluída! Score: ${data.analysis.summary.score}/100 (${data.analysis.summary.total_issues} violações)`);
    } catch (err) {
        showToast(`Erro: ${err.message}`);
    } finally {
        setPipelineLoading(false);
    }
}

async function executeAutonomousDemo() {
    const viewport = document.getElementById("viewport-select").value;
    const mock = document.getElementById("force-mock-checkbox").checked;

    setPipelineLoading(
        true,
        "Executando Ciclo Autônomo Kiroween: 1. Scan broken_page.html → 2. Diagnóstico WCAG 2.2 → 3. Auto-Fix DOM → 4. Revalidação..."
    );
    try {
        const res = await fetch("/api/demo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ viewport, mock }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Erro ao executar demo.");

        syncAnalysisState(
            data.initial_analysis,
            data.verified_analysis,
            data.report_markdown,
            data.history
        );
        showToast(
            `🎃 Demo Completa! Score evoluiu de ${data.initial_analysis.summary.score}/100 para ${data.verified_analysis.summary.score}/100!`
        );
    } catch (err) {
        showToast(`Erro na Demo: ${err.message}`);
    } finally {
        setPipelineLoading(false);
    }
}

async function executeFixSelected() {
    if (!appState.currentAnalysis) {
        showToast("Execute uma auditoria antes de aplicar correções.");
        return;
    }
    const viewport = document.getElementById("viewport-select").value;
    const mock = document.getElementById("force-mock-checkbox").checked;
    const inPlace = document.getElementById("fixer-inplace-checkbox").checked;
    const selectedIds = Array.from(appState.selectedIssueIds);

    setPipelineLoading(true, `Aplicando ${selectedIds.length} correção(ões) no DOM e revalidando no navegador...`);
    try {
        const res = await fetch("/api/fix", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                target: appState.currentAnalysis.local_path || appState.currentAnalysis.target,
                selected_issue_ids: selectedIds,
                custom_overrides: appState.customOverrides,
                in_place: inPlace,
                reverify: true,
                viewport,
                mock,
            }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Falha ao aplicar correções.");

        syncAnalysisState(
            data.initial_analysis,
            data.verified_analysis,
            data.report_markdown,
            data.history
        );
        showToast(
            `✔ ${data.fix_result.total_fixes_applied} correções aplicadas! Novo Score verificado: ${data.verified_analysis.summary.score}/100`
        );
    } catch (err) {
        showToast(`Erro ao corrigir: ${err.message}`);
    } finally {
        setPipelineLoading(false);
    }
}

// =============================================================================
// Inicialização e Event Listeners
// =============================================================================

document.addEventListener("DOMContentLoaded", async () => {
    // Navegação da Sidebar
    document.querySelectorAll(".sidebar-nav .nav-item").forEach((btn) => {
        btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    // Alternância de Tema Claro / Escuro
    document.getElementById("btn-theme-toggle")?.addEventListener("click", () => {
        const html = document.documentElement;
        const next = html.getAttribute("data-theme") === "light" ? "dark" : "light";
        html.setAttribute("data-theme", next);
    });

    // Modo de entrada: URL/Arquivo vs Colar HTML
    document.querySelectorAll("[data-input-mode]").forEach((btn) => {
        btn.addEventListener("click", () => {
            appState.inputMode = btn.dataset.inputMode;
            document.querySelectorAll("[data-input-mode]").forEach((b) =>
                b.classList.toggle("active", b.dataset.inputMode === appState.inputMode)
            );
            document
                .getElementById("raw-html-drawer")
                ?.classList.toggle("hidden", appState.inputMode !== "html");
        });
    });

    // Upload de arquivo .html para o Playground
    document.getElementById("html-file-upload")?.addEventListener("change", (ev) => {
        const file = ev.target.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
            document.getElementById("raw-html-textarea").value = String(reader.result || "");
            showToast(`Arquivo '${file.name}' carregado no Playground!`);
        };
        reader.readAsText(file);
    });

    // Inserir snippet de exemplo com falhas no Playground
    document.getElementById("btn-load-sample-broken")?.addEventListener("click", () => {
        document.getElementById("raw-html-textarea").value = `<!DOCTYPE html>
<html>
<head><title>Snippet Teste A11y</title></head>
<body style="background:#f8fafc; font-family:sans-serif; padding:24px;">
  <p style="color:#b4b8c2; background:#f8fafc;">Cupom secreto com baixo contraste</p>
  <button type="button"><svg width="18" height="18"><circle cx="9" cy="9" r="8"/></svg></button>
  <img src="produto.png" alt="imagem" />
  <div onclick="alert('ok')">Card clicável sem suporte a teclado</div>
</body>
</html>`;
    });

    // Presets de caminho rápido
    document.querySelectorAll("[data-preset-target]").forEach((chip) => {
        chip.addEventListener("click", () => {
            document.getElementById("scan-target-input").value = chip.dataset.presetTarget;
            executeScan();
        });
    });

    // Botões principais de Scan, Demo e Fix
    document.getElementById("btn-run-scan")?.addEventListener("click", executeScan);
    document.getElementById("btn-run-demo")?.addEventListener("click", executeAutonomousDemo);
    document.getElementById("btn-quick-autofix")?.addEventListener("click", async () => {
        await executeFixSelected();
        switchTab("fixer");
    });
    document.getElementById("btn-apply-selected-fixes")?.addEventListener("click", executeFixSelected);

    document.getElementById("btn-jump-to-preview")?.addEventListener("click", () => {
        switchTab("fixer");
        document.querySelector('[data-fixer-view="live-preview"]')?.click();
    });

    document.getElementById("btn-open-visual-hotspot")?.addEventListener("click", () => {
        switchTab("visual");
    });

    document.getElementById("btn-export-md")?.addEventListener("click", () => {
        switchTab("reports");
    });

    // Filtros da Lista de Violações
    document.querySelectorAll("#pillar-filter-pills .filter-pill").forEach((btn) => {
        btn.addEventListener("click", () => setPillarFilter(btn.dataset.pillarFilter));
    });
    document.getElementById("severity-filter-select")?.addEventListener("change", (e) => {
        appState.severityFilter = e.target.value;
        renderIssuesList();
    });
    document.getElementById("issue-search-input")?.addEventListener("input", (e) => {
        appState.searchQuery = e.target.value;
        renderIssuesList();
    });

    // Controles do Inspetor Visual
    document.querySelectorAll("[data-overlay-mode]").forEach((btn) => {
        btn.addEventListener("click", () => {
            appState.overlayMode = btn.dataset.overlayMode;
            renderVisualInspector();
        });
    });
    document.querySelectorAll("[data-screenshot-ver]").forEach((btn) => {
        btn.addEventListener("click", () => {
            appState.screenshotVersion = btn.dataset.screenshotVer;
            renderVisualInspector();
        });
    });
    document.getElementById("vision-sim-select")?.addEventListener("change", (e) => {
        const canvas = document.getElementById("screenshot-canvas");
        if (!canvas) return;
        canvas.className = "screenshot-canvas";
        if (e.target.value !== "normal") {
            canvas.classList.add(`vision-${e.target.value}`);
        }
    });

    // Sub-abas do Auto-Fixer Studio
    document.querySelectorAll("[data-fixer-view]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const view = btn.dataset.fixerView;
            document.querySelectorAll("[data-fixer-view]").forEach((b) =>
                b.classList.toggle("active", b.dataset.fixerView === view)
            );
            document
                .getElementById("fixer-view-patches")
                ?.classList.toggle("hidden", view !== "patches");
            document
                .getElementById("fixer-view-live-preview")
                ?.classList.toggle("hidden", view !== "live-preview");
        });
    });

    document.getElementById("fixer-select-all")?.addEventListener("change", (e) => {
        const issues = appState.currentAnalysis?.issues || [];
        if (e.target.checked) {
            appState.selectedIssueIds = new Set(issues.map((i) => i.id));
        } else {
            appState.selectedIssueIds.clear();
        }
        renderFixerStudio();
    });

    // Busca na Accessibility Tree
    document.getElementById("ax-tree-search")?.addEventListener("input", (e) => {
        renderAxTreeNodes(e.target.value);
    });

    // Calculadora de Contraste W3C
    const fgPicker = document.getElementById("lab-fg-picker");
    const bgPicker = document.getElementById("lab-bg-picker");
    const fgInput = document.getElementById("lab-fg-hex");
    const bgInput = document.getElementById("lab-bg-hex");

    fgPicker?.addEventListener("input", (e) => updateContrastCalculator(e.target.value, bgInput.value));
    bgPicker?.addEventListener("input", (e) => updateContrastCalculator(fgInput.value, e.target.value));
    fgInput?.addEventListener("input", (e) => {
        if (/^#[0-9a-fA-F]{6}$/.test(e.target.value)) updateContrastCalculator(e.target.value, bgInput.value);
    });
    bgInput?.addEventListener("input", (e) => {
        if (/^#[0-9a-fA-F]{6}$/.test(e.target.value)) updateContrastCalculator(fgInput.value, e.target.value);
    });
    document.getElementById("btn-swap-colors")?.addEventListener("click", () => {
        updateContrastCalculator(bgInput.value, fgInput.value);
    });
    updateContrastCalculator("#b4b8c2", "#f8fafc");

    // Relatórios e Histórico
    document.getElementById("btn-copy-markdown")?.addEventListener("click", () => {
        if (appState.reportMarkdown) {
            navigator.clipboard.writeText(appState.reportMarkdown);
            showToast("Relatório Markdown copiado!");
        }
    });
    document.getElementById("btn-print-report")?.addEventListener("click", () => {
        window.print();
    });
    document.getElementById("btn-clear-history")?.addEventListener("click", async () => {
        await fetch("/api/history", { method: "DELETE" });
        appState.history = [];
        renderReportsAndHistory();
        showToast("Histórico limpo.");
    });

    // Presets e Formulário de Configurações de IA
    const providerPresets = {
        openrouter: {
            url: "https://openrouter.ai/api/v1",
            text: "openai/gpt-4o-mini",
            vision: "openai/gpt-4o-mini",
        },
        openai: {
            url: "https://api.openai.com/v1",
            text: "gpt-4o-mini",
            vision: "gpt-4o-mini",
        },
        ollama: {
            url: "http://localhost:11434/v1",
            text: "llama3.2",
            vision: "llava",
        },
        gemini: {
            url: "https://generativelanguage.googleapis.com/v1beta/openai/",
            text: "gemini-2.0-flash",
            vision: "gemini-2.0-flash",
        },
    };
    document.querySelectorAll("[data-provider-preset]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const p = providerPresets[btn.dataset.providerPreset];
            if (!p) return;
            document.getElementById("setting-base-url").value = p.url;
            document.getElementById("setting-model-text").value = p.text;
            document.getElementById("setting-model-vision").value = p.vision;
            showToast(`Preset ${btn.dataset.providerPreset.toUpperCase()} preenchido!`);
        });
    });

    document.getElementById("settings-form")?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const payload = {
            ai_base_url: document.getElementById("setting-base-url").value,
            ai_api_key: document.getElementById("setting-api-key").value,
            ai_model_text: document.getElementById("setting-model-text").value,
            ai_model_vision: document.getElementById("setting-model-vision").value,
        };
        const res = await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (res.ok) {
            populateSettingsForm(data.settings);
            showToast("Configurações de IA salvas em .env!");
        }
    });

    // Carrega estado inicial do servidor; se não houver auditoria prévia, executa o ciclo Demo inicial
    try {
        const res = await fetch("/api/state");
        const state = await res.json();
        populateSettingsForm(state.settings);
        appState.history = state.history || [];
        if (state.latest_analysis) {
            syncAnalysisState(
                state.latest_analysis,
                state.verified_analysis,
                state.report_markdown,
                state.history
            );
        } else {
            await executeAutonomousDemo();
        }
    } catch (e) {
        console.error(e);
    }
});
