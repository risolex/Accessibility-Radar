# Project Structure — Accessibility Radar

```text
accessibility-radar/
├── .kiro/
│   ├── specs/accessibility-radar/
│   │   ├── requirements.md       # Requisitos EARS e escopo dos 5 pilares WCAG 2.2
│   │   ├── design.md             # Arquitetura modular, API REST, Web Studio e JSON Schema
│   │   └── tasks.md              # Checklist de implementação Kiro Spec-Driven Development
│   └── steering/
│       ├── product.md            # Visão do produto e diferenciais Kiroween
│       ├── tech.md               # Stack tecnológica e padrões
│       └── structure.md          # Organização de diretórios do repositório
├── core/
│   ├── scanner.py                # Async Playwright + Screenshot + A11y Tree + JS DOM & Focus Map
│   ├── analyzer.py               # Cliente OpenAI SDK Multimodal + Motor Smart Mock/Fallback
│   └── fixer.py                  # Diffs Unificados, Auto-Fixer Seletivo DOM, Relatórios e Histórico
├── web/
│   ├── app.py                    # Servidor FastAPI e endpoints REST (/api/scan, /api/fix, /api/demo, etc.)
│   └── static/
│       ├── index.html            # SPA Minimalista (7 módulos + filtros SVG de visão)
│       ├── styles.css            # Design System (Dark & Light Mode, WCAG 2.2 AAA)
│       └── app.js                # Estado reativo, hotspots, mapa de foco, diffs e calculadora W3C
├── cli/
│   └── main.py                   # CLI Typer + Rich (comandos: ui, scan, fix, demo)
├── tests/
│   └── broken_page.html          # Página de demonstração ("KiroGear Store") com falhas intencionais
├── docs/
│   ├── USAGE.md                  # Manual completo de uso (Interface Gráfica & Terminal)
│   ├── CONFIGURATION.md          # Configuração de provedores de IA (.env)
│   └── TROUBLESHOOTING.md        # Guia de resolução de problemas
├── reports/                      # Saídas geradas (audit_report.md, fixed_page.html, screenshots, history.json)
├── MANUAL.md                     # Manual rápido de uso na raiz do projeto
├── requirements.md               # Espelho da especificação de requisitos na raiz
├── design.md                     # Espelho do documento de arquitetura na raiz
├── tasks.md                      # Espelho do plano de tarefas na raiz
├── requirements.txt              # Dependências Python
└── README.md                     # Documentação principal do repositório
```
