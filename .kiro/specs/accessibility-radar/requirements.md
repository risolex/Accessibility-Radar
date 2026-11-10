# Requirements Specification — Accessibility Radar

**Projeto:** Accessibility Radar (Autonomous Web Accessibility Auditor & Auto-Fixer)  
**Hackathon:** Kiroween  
**Metodologia:** Kiro Spec-Driven Development (`.kiro/specs/accessibility-radar/`)  
**Padrão de Referência:** W3C WCAG 2.1 / 2.2 (Níveis A e AA)  
**Versão:** 2.0.0

---

## 1. Visão Geral e Problema
Mais de 96% das páginas web globais apresentam falhas graves de acessibilidade detectáveis segundo o relatório WebAIM Million. Ferramentas tradicionais de linting estático analisam apenas o código-fonte bruto sem renderizar o DOM real, ignorando estilos CSS computados, estados dinâmicos de JavaScript, a **Árvore de Acessibilidade (Accessibility Tree)** do navegador e o contexto visual real das imagens.

Desenvolvido com a metodologia **Kiro Spec-Driven Development**, o **Accessibility Radar** resolve essa lacuna combinando **automação de navegador headless via Playwright**, **extração cirúrgica de DOM, coordenadas visuais e Accessibility Tree**, **IA Multimodal (Texto + Visão)** e uma **Interface Web Moderna e Minimalista (Web Studio)** para não apenas auditar páginas segundo a **WCAG 2.2**, mas também **gerar, visualizar e aplicar automaticamente patches de código (HTML/CSS/JSX)** prontos para produção.

---

## 2. Escopo dos 5 Pilares de Auditoria (WCAG 2.2 A & AA)

### Pilar 1: Contraste e Visibilidade (WCAG 1.4.3 Contrast Minimum - AA / 1.4.11 Non-text Contrast - AA)
- **Extração Real:** Coleta das propriedades CSS computadas (`color`, `backgroundColor`, `fontSize`, `fontWeight`, `opacity`) diretamente da árvore renderizada no navegador, subindo na hierarquia ancestral para resolver fundos transparentes.
- **Cálculo Matemático:** Cálculo exato de luminância relativa ($L$) e razão de contraste ($CR = \frac{L_1 + 0.05}{L_2 + 0.05}$), diferenciando texto normal (mínimo `4.5:1`) e texto grande ($\ge 18\text{pt}$ ou $\ge 14\text{pt}$ negrito, mínimo `3.0:1`).
- **Validação Multimodal:** Captura de screenshot de página inteira para confirmação visual de legibilidade e mapeamento de coordenadas (`rect`).

### Pilar 2: Elementos Interativos Mudos (WCAG 4.1.2 Name, Role, Value - A / 2.4.4 Link Purpose - A / 1.3.1 Info and Relationships - A)
- **Alvos:** Elementos `<button>`, `<a>`, `<input>`, `<select>`, `<textarea>` e elementos com `role="button"` ou `role="link"`.
- **Critério de Detecção:** Identificação de controles interativos que não possuem nome acessível calculado (sem texto visível interno, sem `aria-label`, sem `aria-labelledby` válido, sem `title` e, no caso de campos de formulário, sem `<label for="...">` associado).

### Pilar 3: Semântica de Mídia (WCAG 1.1.1 Non-text Content - A)
- **Alvos:** Elementos `<img>` e `<svg>` informativos ou funcionais.
- **Critério de Detecção:**
  - Imagens sem o atributo `alt`.
  - Imagens funcionais (ex.: dentro de `<a>` ou `<button>`) com `alt=""` vazio que tornam o controle mudo.
  - Descrições genéricas ou inúteis (`alt="imagem"`, `alt="foto"`, `alt="image"`, `alt="banner"`, `alt="icon"`, nomes de arquivos `.jpg`/`.png`).
  - Elementos `<svg>` significativos sem `role="img"`, `<title>` ou `aria-label`.
- **Correção com IA Vision / Contextual:** Geração de texto alternativo contextualizado considerando o screenshot, o contexto semântico ao redor do elemento (títulos de card, preços, seção da página) e o propósito da imagem.

### Pilar 4: Ordem de Foco e Navegação por Teclado (WCAG 2.4.3 Focus Order - A / 2.4.7 Focus Visible - AA / 2.1.1 Keyboard - A / 2.1.2 No Keyboard Trap - A)
- **Critério de Detecção:**
  - Uso de `tabindex` positivo (`tabindex > 0`), que altera e quebra a sequência lógica de navegação por teclado.
  - Supressão de indicador de foco visível via CSS (`outline: none` ou `outline: 0` sem `box-shadow` ou `border` compensatório em `:focus` / `:focus-visible`).
  - Elementos não-nativos interativos (`<div>` ou `<span>` com `onclick`) sem `tabindex="0"` e sem `role` semântico.
  - Armadilhas de teclado (*Keyboard Traps*) onde eventos `onkeydown`/`onkeypress` interceptam e bloqueiam `Tab` ou `Escape` (`event.preventDefault()`).

### Pilar 5: Estrutura e Semântica do Documento (WCAG 3.1.1 Language of Page - A / 2.4.2 Page Titled - A / 1.3.1 Info and Relationships - A / 2.4.6 Headings and Labels - AA)
- **Critério de Detecção:**
  - Ausência do atributo de idioma `lang` no elemento raiz `<html>`.
  - Ausência de elemento `<title>` descritivo no `<head>`.
  - Saltos na hierarquia lógica de cabeçalhos (`<h1>` a `<h6>`, ex.: pular de `<h1>` direto para `<h4>`).
  - Mapeamento do esqueleto semântico de **ARIA Landmarks** (`banner`, `navigation`, `main`, `contentinfo`, `region`, `form`).

---

## 3. Requisitos Funcionais (EARS Notation — Kiro Spec Standard)

### RF-01: Scanner de DOM, Estilos Computados, Coordenadas e Accessibility Tree (`core/scanner.py`)
- **WHEN** o usuário fornece uma URL (`http://`, `https://` ou domínio direto), caminho de arquivo local (`.html`) ou código HTML bruto (Playground), **THE SYSTEM SHALL** iniciar uma instância assíncrona do Playwright Chromium headless no perfil de viewport selecionado (`desktop`, `tablet` ou `mobile`).
- **WHEN** a página estiver carregada, **THE SYSTEM SHALL** capturar um screenshot de página inteira em formato PNG (codificado em Base64 e salvo em disco) e, para URLs remotas, salvar um snapshot local do DOM renderizado (`reports/remote_snapshot.html` com `<base href>`).
- **WHEN** a página estiver carregada, **THE SYSTEM SHALL** extrair o snapshot da Árvore de Acessibilidade (`page.accessibility.snapshot()` com fallback via protocolo CDP `Accessibility.getFullAXTree`).
- **WHEN** a extração do DOM iniciar, **THE SYSTEM SHALL** injetar um script JavaScript otimizado que filtra e retorna apenas os elementos relevantes aos 5 pilares com seus seletores CSS, snippets `outerHTML`, estilos computados, razão de contraste calculada, coordenadas visuais (`rect: {x, y, width, height}`), mapa da ordem real de foco (`focus_order_map`) e estrutura de cabeçalhos/landmarks (`document_outline`).

### RF-02: Motor de Análise Híbrido e Multimodal (`core/analyzer.py`)
- **WHEN** as variáveis `AI_API_KEY` e `AI_BASE_URL` estiverem configuradas no `.env`, **THE SYSTEM SHALL** enviar o payload filtrado do scanner e o screenshot em Base64 para o provedor compatível com o SDK `openai`, retornando um diagnóstico JSON estrito mapeado para critérios WCAG 2.1/2.2 (Níveis A e AA).
- **IF** a chave `AI_API_KEY` não estiver configurada, for inválida ou a flag `--mock` for acionada, **THEN THE SYSTEM SHALL** ativar automaticamente o **Modo Mock/Fallback Inteligente**, processando os dados reais extraídos pelo scanner com heurísticas determinísticas + síntese contextual de correções para garantir execução 100% funcional para avaliação no hackathon.

### RF-03: Gerador de Patches Seletivo, Auto-Fixer e Histórico (`core/fixer.py`)
- **WHEN** o diagnóstico de acessibilidade for concluído, **THE SYSTEM SHALL** gerar snippets de código "Antes e Depois" (HTML/CSS/JSX) e diffs unificados para cada violação detectada.
- **WHEN** o usuário executar a correção (total ou seletiva via `selected_issue_ids` e `custom_overrides`), **THE SYSTEM SHALL** aplicar cirurgicamente as correções de atributos (`alt`, `aria-label`, `role`, `tabindex`, `lang`), associar rótulos, remover armadilhas de teclado e injetar/corrigir regras de contraste e foco visível `:focus-visible`.
- **WHEN** uma auditoria ou correção finalizar, **THE SYSTEM SHALL** salvar o relatório completo em Markdown (`reports/audit_report.md`) e registrar a execução no histórico persistente (`reports/history.json`).

### RF-04: Interface CLI Interativa (`cli/main.py`)
- **THE SYSTEM SHALL** disponibilizar uma CLI construída com `typer` e `rich` contendo os comandos:
  1. `ui`: Inicia a Interface Gráfica Web Moderna (FastAPI + Uvicorn) com detecção automática de porta livre.
  2. `scan <target>`: Audita uma URL ou arquivo HTML local (com suporte a `--viewport` e `--mock`), exibe tabelas coloridas no terminal e gera `reports/audit_report.md`.
  3. `fix <target>`: Audita um arquivo local, apresenta os diffs de correção no terminal e aplica os patches automaticamente.
  4. `demo`: Executa o fluxo completo de ponta a ponta sobre `tests/broken_page.html`, gera o relatório `reports/audit_report.md`, cria a versão corrigida `reports/fixed_page.html` e revalida o resultado comprovando a evolução do score de `0/100` para `100/100`.

### RF-05: Interface Gráfica Web Moderna e Minimalista (`web/app.py` + `web/static/`)
- **THE SYSTEM SHALL** disponibilizar uma aplicação web local com tema Claro/Escuro (Light/Dark Mode) organizada em 7 módulos:
  1. **Dashboard & Auditoria:** Entrada por URL, arquivo local ou Playground HTML, seletor de viewport, Scorecard radial e filtros rápidos por pilar e severidade.
  2. **Inspetor Visual & Mapa de Foco:** Screenshot interativo com hotspots clicáveis sobre as violações, Mapa Visual da Ordem de Foco (`Tab`), alternador de versão Antes/Depois e Simulador de Deficiências Visuais (Protanopia, Deuteranopia, Tritanopia, Acromatopsia e Baixa Visão).
  3. **Auto-Fixer & Diff Studio:** Seleção granular de correções via checkboxes, edição customizada de atributos sugeridos e **Live Preview Lado a Lado** em iframes comparando a página original e a corrigida.
  4. **Accessibility Tree & Leitor de Tela:** Simulador de anúncios de leitores de tela (NVDA / VoiceOver) Antes vs. Depois, visualizador de Landmarks/Headings e busca na árvore de acessibilidade.
  5. **Laboratório de Contraste W3C:** Calculadora interativa de luminância relativa em tempo real com sugestão automática de cores acessíveis.
  6. **Histórico & Relatórios:** Tabela de histórico de execuções e exportação em Markdown, JSON, HTML e Impressão/PDF.
  7. **Motor de IA & Config:** Configuração visual do arquivo `.env` com presets de 1 clique para OpenRouter, OpenAI, Ollama e Gemini.

---

## 4. Requisitos Não-Funcionais
- **RNF-01 (Performance e Economia de Tokens):** A filtragem no navegador deve limitar o payload JSON enviado à LLM apenas aos nós suspeitos e resumo da Accessibility Tree, reduzindo o consumo de tokens em mais de 80%.
- **RNF-02 (Interoperabilidade de IA):** Compatibilidade total com qualquer endpoint compatível com OpenAI (`OpenRouter`, `OpenAI`, `Grok`, `Gemini OpenAI-compat`, `Ollama`).
- **RNF-03 (Resiliência Zero-Config):** Os modos `demo` e `ui` devem funcionar imediatamente após a instalação, mesmo offline ou sem chaves de API externas.
- **RNF-04 (Portabilidade e Dogfooding WCAG):** Compatível com Python 3.10+ em Windows, macOS e Linux, sendo a própria interface web construída em conformidade com a WCAG 2.2 AA.
