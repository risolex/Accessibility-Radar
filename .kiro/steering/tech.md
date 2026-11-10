# Technology Stack — Accessibility Radar

- **Linguagem:** Python 3.10+
- **Automação de Navegador & Extração Real:** `playwright` (Async API + Chrome DevTools Protocol `Accessibility.getFullAXTree`)
- **IA Multimodal:** `openai` Python SDK (compatível com OpenRouter, OpenAI, Grok, Gemini e Ollama via `AI_BASE_URL`) + Motor **Smart Mock/Fallback** determinístico zero-config
- **Manipulação e Patching DOM:** `beautifulsoup4` (`html.parser`) + `difflib`
- **Backend Web & API REST:** `fastapi` + `uvicorn` + `pydantic`
- **Frontend Web Studio:** HTML5 Semântico + CSS3 Design System Minimalista (Light/Dark Mode, Filtros SVG de Daltonismo) + Vanilla JavaScript ES6+
- **CLI Interativa:** `typer` + `rich`
- **Metodologia de Engenharia:** Kiro Spec-Driven Development (`.kiro/specs/accessibility-radar/`)
