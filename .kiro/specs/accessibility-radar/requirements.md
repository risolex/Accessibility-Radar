# Requirements Specification — Accessibility Radar

**Projeto:** Accessibility Radar (Autonomous Web Accessibility Auditor & Auto-Fixer)  
**Hackathon:** Kiroween  
**Padrão de Referência:** W3C WCAG 2.1 / 2.2 (Níveis A e AA)  
**Versão:** 1.0.0

---

## 1. Visão Geral e Problema
Mais de 96% das páginas web globais apresentam falhas graves de acessibilidade detectáveis segundo o relatório WebAIM Million. Ferramentas tradicionais de linting estático analisam apenas o código-fonte bruto sem renderizar o DOM real, ignorando estilos CSS computados, estados dinâmicos de JavaScript, a **Árvore de Acessibilidade (Accessibility Tree)** do navegador e o contexto visual real das imagens.

O **Accessibility Radar** resolve essa lacuna combinando **automação de navegador headless via Playwright**, **extração cirúrgica de DOM e Accessibility Tree** e **IA Multimodal (Texto + Visão)** para não apenas auditar páginas segundo a **WCAG 2.2**, mas também **gerar e aplicar automaticamente patches de código (HTML/CSS/JSX)** prontos para produção.

---

## 2. Escopo dos 4 Pilares de Auditoria (MVP)

### Pilar 1: Contraste e Visibilidade (WCAG 1.4.3 Contrast Minimum - AA / 1.4.11 Non-text Contrast - AA)
- **Extração Real:** Coleta das propriedades CSS computadas (`color`, `backgroundColor`, `fontSize`, `fontWeight`, `opacity`) diretamente da árvore renderizada no navegador.
- **Cálculo Matemático:** Cálculo exato de luminância relativa ($L$) e razão de contraste ($CR = \frac{L_1 + 0.05}{L_2 + 0.05}$), diferenciando texto normal (mínimo `4.5:1`) e texto grande ($\ge 18\text{pt}$ ou $\ge 14\text{pt}$ negrito, mínimo `3.0:1`).
- **Validação Multimodal:** Captura de screenshot de página inteira para confirmação visual de legibilidade sobre fundos complexos/gradientes.

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
- **Correção com IA Vision:** Geração de texto alternativo contextualizado considerando o screenshot, o contexto semântico ao redor do elemento (títulos de card, preços, seção da página) e o propósito da imagem.

### Pilar 4: Ordem de Foco e Navegação por Teclado (WCAG 2.4.3 Focus Order - A / 2.4.7 Focus Visible - AA / 2.1.1 Keyboard - A / 2.1.2 No Keyboard Trap - A)
- **Critério de Detecção:**
  - Uso de `tabindex` positivo (`tabindex > 0`), que altera e quebra a sequência lógica de navegação por teclado.
  - Supressão de indicador de foco visível via CSS (`outline: none` ou `outline: 0` sem `box-shadow` ou `border` compensatório em `:focus` / `:focus-visible`).
  - Elementos não-nativos interativos (`<div>` ou `<span>` com `onclick`) sem `tabindex="0"` e sem `role` semântico.
  - Armadilhas de teclado (*Keyboard Traps*) onde eventos `onkeydown`/`onkeypress` interceptam e bloqueiam `Tab` ou `Escape` (`event.preventDefault()`).

---

## 3. Requisitos Funcionais (EARS Notation)

### RF-01: Scanner de DOM, Estilos Computados e Accessibility Tree (`core/scanner.py`)
- **WHEN** o usuário fornece uma URL (`http://` / `https://`) ou caminho de arquivo local (`.html`), **THE SYSTEM SHALL** iniciar uma instância assíncrona do Playwright Chromium headless com `wait_until="networkidle"`.
- **WHEN** a página estiver carregada, **THE SYSTEM SHALL** capturar um screenshot de página inteira em formato PNG (codificado em Base64 e salvo em disco).
- **WHEN** a página estiver carregada, **THE SYSTEM SHALL** extrair o snapshot da Árvore de Acessibilidade (`page.accessibility.snapshot()` com fallback via protocolo CDP `Accessibility.getFullAXTree`).
- **WHEN** a extração do DOM iniciar, **THE SYSTEM SHALL** injetar um script JavaScript otimizado que filtra e retorna apenas os elementos relevantes aos 4 pilares com seus seletores CSS, snippets `outerHTML`, estilos computados, razão de contraste calculada e coordenadas visuais, reduzindo o consumo de tokens em mais de 80%.

### RF-02: Motor de Análise Híbrido e Multimodal (`core/analyzer.py`)
- **WHEN** as variáveis `AI_API_KEY` e `AI_BASE_URL` estiverem configuradas no `.env`, **THE SYSTEM SHALL** enviar o payload filtrado do scanner e o screenshot em Base64 para o provedor compatível com o SDK `openai`, retornando um diagnóstico JSON estrito mapeado para critérios WCAG 2.1/2.2 (Níveis A e AA).
- **IF** a chave `AI_API_KEY` não estiver configurada, for inválida ou a flag `--mock` for acionada, **THEN THE SYSTEM SHALL** ativar automaticamente o **Modo Mock/Fallback Inteligente**, processando os dados reais extraídos pelo scanner com heurísticas determinísticas + síntese contextual de correções para garantir execução 100% funcional para avaliação no hackathon.

### RF-03: Gerador de Patches e Auto-Fixer (`core/fixer.py`)
- **WHEN** o diagnóstico de acessibilidade for concluído, **THE SYSTEM SHALL** gerar snippets de código "Antes e Depois" (HTML/CSS/JSX) para cada violação detectada.
- **WHEN** o usuário executar o comando `fix` em um arquivo local com `--apply` (ou salvar em arquivo de saída), **THE SYSTEM SHALL** aplicar cirurgicamente as correções de atributos (`alt`, `aria-label`, `role`, `tabindex`), associar rótulos, remover armadilhas de teclado e injetar/corrigir regras de contraste e foco visível `:focus-visible`.
- **WHEN** uma auditoria ou correção finalizar, **THE SYSTEM SHALL** salvar um relatório completo em Markdown (`reports/audit_report.md`) contendo score de acessibilidade (0–100), resumo executivo por pilar e severidade, explicação WCAG e diffs de código prontos para uso.

### RF-04: Interface CLI Interativa (`cli/main.py`)
- **THE SYSTEM SHALL** disponibilizar uma CLI construída com `typer` e `rich` contendo os comandos:
  1. `scan <target>`: Audita uma URL ou arquivo HTML local, exibe tabelas coloridas no terminal e gera `reports/audit_report.md`.
  2. `fix <target>`: Audita um arquivo local, apresenta os diffs de correção no terminal e aplica os patches automaticamente.
  3. `demo`: Executa o fluxo completo de ponta a ponta sobre `tests/broken_page.html`, gera o relatório `reports/audit_report.md`, cria a versão corrigida `reports/fixed_page.html` e revalida o resultado comprovando a evolução do score de acessibilidade.

---

## 4. Requisitos Não-Funcionais
- **RNF-01 (Performance e Economia de Tokens):** A filtragem no navegador deve limitar o payload JSON enviado à LLM apenas aos nós suspeitos e resumo da Accessibility Tree.
- **RNF-02 (Interoperabilidade de IA):** Compatibilidade total com qualquer endpoint compatível com OpenAI (`OpenRouter`, `OpenAI`, `Anthropic via proxy`, `Grok`, `Gemini OpenAI-compat`, `Ollama`).
- **RNF-03 (Resiliência Zero-Config):** O modo `demo` deve funcionar imediatamente após a instalação, mesmo offline ou sem chaves de API externas.
- **RNF-04 (Portabilidade):** Compatível com Python 3.10+ em Windows, macOS e Linux usando `pathlib.Path` e codificação UTF-8 explícita.
