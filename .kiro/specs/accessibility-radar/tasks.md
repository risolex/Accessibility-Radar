# Implementation Task List — Accessibility Radar

**Projeto:** Accessibility Radar  
**Hackathon:** Kiroween  
**Metodologia:** Kiro Spec-Driven Development (`.kiro/specs/accessibility-radar/`)  
**Status Geral:** Completo (v2.0.0)

---

## Fase 1: Planejamento e Especificação (Kiro Spec-Driven Development)
- [x] **Task 1.1:** Elaborar `requirements.md` detalhando os pilares de auditoria WCAG 2.1/2.2 e requisitos funcionais no formato EARS.
- [x] **Task 1.2:** Elaborar `design.md` com arquitetura modular, fluxo de dados multimodal, cálculo de luminância e schema JSON de diagnóstico.
- [x] **Task 1.3:** Estruturar `tasks.md` com o roteiro completo de implementação e verificação.

## Fase 2: Configuração Base e Ambiente
- [x] **Task 2.1:** Criar estrutura de diretórios (`core/`, `cli/`, `web/`, `tests/`, `reports/`, `.kiro/specs/accessibility-radar/`).
- [x] **Task 2.2:** Criar `requirements.txt` com `playwright`, `openai`, `typer`, `rich`, `python-dotenv`, `beautifulsoup4`, `pydantic`, `fastapi` e `uvicorn`.
- [x] **Task 2.3:** Criar `.env.example` documentando `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL_TEXT` e `AI_MODEL_VISION`.

## Fase 3: Implementação do Core Engine (`core/`)
- [x] **Task 3.1:** Implementar `core/scanner.py`:
  - [x] Suporte assíncrono via `playwright.async_api` para URLs (com ou sem protocolo), arquivos locais e HTML bruto (`scan_raw_html`).
  - [x] Captura de screenshot de página inteira em Base64 + arquivos PNG (`before_screenshot.png`, `after_screenshot.png`, `latest_screenshot.png`) e snapshot DOM local para URLs remotas (`remote_snapshot.html`).
  - [x] Extração de `page.accessibility.snapshot()` com fallback automático via protocolo CDP (`Accessibility.getFullAXTree`).
  - [x] Injeção de JS no DOM para cálculo de contraste real (luminância W3C), coordenadas visuais (`rect`), mapa da ordem real de foco (`focus_order_map`), outline de cabeçalhos/landmarks e filtragem cirúrgica dos 5 pilares.
- [x] **Task 3.2:** Implementar `core/analyzer.py`:
  - [x] Cliente `openai` compatível com qualquer `AI_BASE_URL` customizada e suporte multimodal (JSON filtrado + Screenshot Base64).
  - [x] Prompt especialista WCAG 2.2 Nível A/AA com retorno JSON estruturado nos 5 pilares.
  - [x] Motor **Smart Mock/Fallback** determinístico e contextual para execução imediata sem necessidade de chave de API.
- [x] **Task 3.3:** Implementar `core/fixer.py`:
  - [x] Geração de patches "Antes e Depois" e diffs unificados em HTML/CSS/JSX.
  - [x] Auto-remediação cirúrgica e seletiva (`selected_issue_ids` + `custom_overrides`) em arquivos HTML locais (correção de contraste, `aria-label`, `alt` contextual, `tabindex`, `:focus-visible`, remoção de keyboard traps e estrutura semântica).
  - [x] Gerador de relatório executivo e técnico em Markdown (`reports/audit_report.md`) e histórico persistente (`reports/history.json`).

## Fase 4: Interface CLI e Ambiente de Testes (`cli/` e `tests/`)
- [x] **Task 4.1:** Implementar `cli/main.py` com `typer` e `rich`:
  - [x] Comando `ui`: Inicialização da Interface Gráfica Web Moderna com detecção automática de porta livre.
  - [x] Comando `scan`: Auditoria completa com spinners, scorecard colorido, tabela dos 5 pilares WCAG e geração de relatório Markdown.
  - [x] Comando `fix`: Exibição de diffs "Antes e Depois" e aplicação automática de correções em arquivo local.
  - [x] Comando `demo`: Execução de ponta a ponta em `tests/broken_page.html` com verificação pós-correção em `reports/fixed_page.html` (Score `0/100` $\rightarrow$ `100/100`).
- [x] **Task 4.2:** Criar `tests/broken_page.html` simulando um mini e-commerce moderno ("KiroGear Store") com falhas intencionais reais.

## Fase 5: Interface Gráfica Web Moderna (`web/`)
- [x] **Task 5.1:** Implementar backend FastAPI (`web/app.py`) com endpoints `/api/state`, `/api/scan`, `/api/fix`, `/api/demo`, `/api/contrast-check`, `/api/settings` e `/api/history`.
- [x] **Task 5.2:** Implementar SPA Minimalista (`web/static/index.html`, `styles.css`, `app.js`) com Light/Dark Mode e 7 módulos integrados:
  - [x] Dashboard & Central de Auditoria (URL, Arquivo Local, Playground HTML, Multi-Viewport).
  - [x] Inspetor Visual com Hotspots clicáveis, Mapa de Ordem de Foco (`Tab`) e Simulador de Daltonismo/Baixa Visão.
  - [x] Auto-Fixer & Diff Studio com seleção granular, edição de atributos e Live Preview Lado a Lado (`<iframe>`).
  - [x] Accessibility Tree Explorer, Esqueleto de Headings/Landmarks e Simulador de Leitor de Tela (NVDA / VoiceOver).
  - [x] Calculadora Matemática de Contraste W3C em tempo real.
  - [x] Histórico de Auditorias, Exportação de Relatórios e Gerenciador visual de IA (`.env`).

## Fase 6: Documentação e Validação End-to-End
- [x] **Task 6.1:** Criar e atualizar `README.md`, `MANUAL.md` e `docs/USAGE.md` com instruções completas para Interface Gráfica e Terminal.
- [x] **Task 6.2:** Validar ciclo completo da CLI (`scan`, `fix`, `demo`, `ui`) e endpoints da Interface Web.
