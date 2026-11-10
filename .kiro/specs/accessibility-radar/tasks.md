# Implementation Task List — Accessibility Radar

**Projeto:** Accessibility Radar  
**Hackathon:** Kiroween  
**Status Geral:** Em Execução / Completo

---

## Fase 1: Planejamento e Especificação (Kiro Spec-Driven Development)
- [x] **Task 1.1:** Elaborar `requirements.md` detalhando os 4 pilares de auditoria WCAG 2.1/2.2 e requisitos funcionais no formato EARS.
- [x] **Task 1.2:** Elaborar `design.md` com arquitetura modular, fluxo de dados multimodal, cálculo de luminância e schema JSON de diagnóstico.
- [x] **Task 1.3:** Estruturar `tasks.md` com o roteiro completo de implementação e verificação.

## Fase 2: Configuração Base e Ambiente
- [x] **Task 2.1:** Criar estrutura de diretórios (`core/`, `cli/`, `tests/`, `reports/`, `.kiro/specs/accessibility-radar/`).
- [x] **Task 2.2:** Criar `requirements.txt` com `playwright`, `openai`, `typer`, `rich`, `python-dotenv`, `beautifulsoup4` e `pydantic`.
- [x] **Task 2.3:** Criar `.env.example` documentando `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL_TEXT` e `AI_MODEL_VISION`.

## Fase 3: Implementação do Core Engine (`core/`)
- [x] **Task 3.1:** Implementar `core/scanner.py`:
  - [x] Suporte assíncrono via `playwright.async_api` para URLs e arquivos locais (`wait_until="networkidle"`).
  - [x] Captura de screenshot de página inteira em Base64 + arquivo PNG em `reports/`.
  - [x] Extração de `page.accessibility.snapshot()` com fallback automático via protocolo CDP (`Accessibility.getFullAXTree`).
  - [x] Injeção de JS no DOM para cálculo de contraste real (luminância W3C) e filtragem cirúrgica dos 4 pilares para economia de tokens.
- [x] **Task 3.2:** Implementar `core/analyzer.py`:
  - [x] Cliente `openai` compatível com qualquer `AI_BASE_URL` customizada e suporte multimodal (JSON filtrado + Screenshot Base64).
  - [x] Prompt especialista WCAG 2.2 Nível A/AA com retorno JSON estruturado.
  - [x] Motor **Smart Mock/Fallback** determinístico e contextual para execução imediata sem necessidade de chave de API.
- [x] **Task 3.3:** Implementar `core/fixer.py`:
  - [x] Geração de patches "Antes e Depois" em HTML/CSS/JSX.
  - [x] Auto-remediação cirúrgica em arquivos HTML locais (correção de contraste, `aria-label`, `alt` contextual, `tabindex`, `:focus-visible` e remoção de keyboard traps).
  - [x] Gerador de relatório executivo e técnico em Markdown (`reports/audit_report.md`).

## Fase 4: Interface CLI e Ambiente de Testes (`cli/` e `tests/`)
- [x] **Task 4.1:** Implementar `cli/main.py` com `typer` e `rich`:
  - [x] Comando `scan`: Auditoria completa com spinners, scorecard colorido, tabela de falhas WCAG e geração de relatório Markdown.
  - [x] Comando `fix`: Exibição de diffs "Antes e Depois" e aplicação automática de correções em arquivo local.
  - [x] Comando `demo`: Execução de ponta a ponta em `tests/broken_page.html` com verificação pós-correção em `reports/fixed_page.html`.
- [x] **Task 4.2:** Criar `tests/broken_page.html` simulando um mini e-commerce moderno ("KiroGear Store") com falhas intencionais reais nos 4 pilares.

## Fase 5: Documentação e Validação End-to-End
- [x] **Task 5.1:** Criar `README.md` profissional formatado para submissão no Devpost (arquitetura, diferencial, instalação, uso e exemplos).
- [x] **Task 5.2:** Executar testes reais da CLI (`scan`, `fix` e `demo`) validando a geração de `reports/audit_report.md` e `reports/fixed_page.html`.
