# Product Overview — Accessibility Radar

- **Nome do Produto:** Accessibility Radar
- **Hackathon:** Kiroween (Submissão Oficial — Kiro Spec-Driven Development)
- **Propósito:** Agente autônomo de auditoria e auto-remediação de acessibilidade web segundo as diretrizes W3C WCAG 2.1 / 2.2 (Níveis A e AA).
- **Diferencial:** Renderiza páginas reais em navegador headless (Playwright), extrai a *Accessibility Tree* real e estilos CSS computados, mapeia coordenadas visuais (`rect`) e a ordem real de foco (`Tab`), analisa de forma multimodal (Texto + Visão ou Smart Mock determinístico) e aplica patches cirúrgicos de código com revalidação automática em ciclo fechado.
- **Interfaces:**
  - **Web Studio (`python -m cli.main ui`):** Interface gráfica web moderna e minimalista com Light/Dark Mode, Inspetor Visual de Hotspots, Mapa de Foco, Simulador de Daltonismo/Baixa Visão, Auto-Fixer Seletivo com Live Preview Lado a Lado, Simulador de Leitor de Tela e Calculadora de Contraste W3C.
  - **Rich CLI (`scan`, `fix`, `demo`, `ui`):** Linha de comando interativa para desenvolvedores e pipelines CI/CD.
