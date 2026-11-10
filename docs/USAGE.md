# 📘 Manual Completo de Uso — Accessibility Radar (Interface Gráfica & Terminal)

Este manual ensina passo a passo como instalar, iniciar e utilizar todos os recursos do **Accessibility Radar**, tanto pela **Interface Gráfica Web (Web Studio)** quanto pelo **Terminal (CLI)**.

---

## 1. Instalação e Preparação do Ambiente (Do Zero)

Abra o **PowerShell** (ou terminal de sua preferência) e execute os comandos abaixo:

### Passo 1: Acessar a pasta do projeto
```powershell
cd "C:\Users\renan\projetosIA\accessibility radar"
```

### Passo 2: Criar e ativar o ambiente virtual Python (Recomendado)
```powershell
# Cria o ambiente virtual
python -m venv venv

# Ativa no Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# (No Linux/macOS use: source venv/bin/activate)
```

### Passo 3: Instalar as dependências e o navegador headless
```powershell
# Instala FastAPI, Uvicorn, Playwright, OpenAI, Typer, Rich, BeautifulSoup4, etc.
pip install -r requirements.txt

# Instala o navegador Chromium do Playwright
playwright install chromium
```
> **Dica:** Mesmo que você não execute `playwright install chromium`, o sistema possui fallback automático para usar o **Google Chrome** ou **Microsoft Edge** já instalados no seu computador.

---

## 2. Como Usar pela Interface Gráfica Web (Web Studio)

A Interface Gráfica oferece uma experiência visual completa com tema Claro/Escuro, mapas de calor sobre o screenshot, simulador de daltonismo e preview lado a lado.

### 2.1. Iniciando a Interface Gráfica
No terminal, execute:
```powershell
python -m cli.main ui
```
- O servidor iniciará automaticamente (em `http://127.0.0.1:8000` ou `http://127.0.0.1:8080` caso a porta 8000 esteja ocupada) e abrirá seu navegador.
- Outras opções úteis ao iniciar:
  ```powershell
  # Escolher uma porta específica
  python -m cli.main ui --port 8080

  # Iniciar o servidor sem abrir o navegador automaticamente
  python -m cli.main ui --no-browser
  ```

---

### 2.2. Barra de Comando Superior (Como Auditar Qualquer Página)
No topo da interface, você encontra os controles globais:
1. **Seletor de Modo de Entrada:**
   - **URL / Arquivo Local:** Digite o endereço de qualquer site (ex.: `https://example.com` ou apenas `meusite.com.br`), um servidor local (`localhost:3000`) ou o caminho de um arquivo no projeto (`tests/broken_page.html`) e pressione **Enter** ou clique em **Auditar (Scan)**.
   - **Colar HTML / Upload:** Abre o *Playground HTML ao Vivo*, onde você pode colar um código HTML diretamente ou enviar um arquivo `.html` do seu computador para testar na hora.
2. **Seletor de Viewport (Tamanho de Tela):**
   - Alterne entre **Desktop (`1280×900`)**, **Tablet (`768×1024`)** e **Mobile (`390×844`)** para auditar a responsividade da página.
3. **Chave `Smart Mock`:**
   - **Marcada:** Usa o motor determinístico local (100% gratuito, instantâneo e sem precisar de chave de API).
   - **Desmarcada:** Usa o modelo de IA Multimodal (Vision) configurado na aba de configurações (`.env`).
4. **Botão `🎃 Ciclo Autônomo (Demo)`:**
   - Executa em 1 clique todo o fluxo de demonstração na página `tests/broken_page.html`: escaneia as 18 falhas (Score `0/100`), aplica os patches automaticamente em `reports/fixed_page.html` e re-audita no navegador comprovando o **Score `100/100`**.
5. **Botão `◐` (Tema):**
   - Alterna instantaneamente entre **Dark Mode** e **Light Mode**.

---

### 2.3. Os 7 Módulos da Barra Lateral (Sidebar)

| Aba na Interface | Para que serve e como usar |
| :--- | :--- |
| **1. Dashboard & Auditoria** | Exibe o **Score WCAG 2.2 (0 a 100)**, o resumo dos **5 Pilares de Auditoria**, a contagem por severidade (`Critical`, `Serious`, `Moderate`, `Minor`) e a lista completa de falhas. Você pode clicar em qualquer pilar para filtrar, pesquisar por seletor CSS e copiar o patch de código individual. |
| **2. Inspetor Visual & Foco** | Mostra o screenshot real da página com: <br>• **Hotspots de Violações:** Caixas vermelhas numeradas exatamente sobre os elementos com erro.<br>• **Mapa de Ordem de Foco (Tab):** Desenha a linha pontilhada numerada (`1 → 2 → 3...`) mostrando a sequência real da tecla `Tab`.<br>• **Versão Antes / Depois:** Alterna entre o screenshot original e o corrigido.<br>• **Simulador de Visão:** Aplica filtros matemáticos de **Protanopia**, **Deuteranopia**, **Tritanopia**, **Acromatopsia (P&B)** e **Baixa Visão / Catarata**. |
| **3. Auto-Fixer & Diff Studio** | Permite **marcar/desmarcar** quais correções você quer aplicar, **editar o texto sugerido** (`alt`, `aria-label` ou cor hexadecimal) antes de corrigir, aplicar tudo com 1 clique e ver o **Live Preview Comparativo Lado a Lado** (página original vs. página corrigida rodando ao vivo). |
| **4. A11y Tree & Leitor de Tela** | Exibe o **Simulador de Leitor de Tela (NVDA / VoiceOver)** comparando como cada elemento era lido antes e como passa a ser anunciado depois da correção, além das **Landmarks ARIA**, **Hierarquia de Cabeçalhos (`H1–H6`)** e busca na **Accessibility Tree** do Chromium. |
| **5. Laboratório de Contraste** | Calculadora interativa da fórmula oficial de luminância da W3C. Escolha qualquer cor de texto e fundo para testar conformidade **AA (`4.5:1`)** e **AAA (`7.0:1`)**, ou clique em uma falha detectada na página para carregá-la na calculadora. |
| **6. Histórico & Relatórios** | Lista todas as auditorias já executadas (com evolução do Score Inicial $\rightarrow$ Pós-Fix) e permite visualizar, copiar, imprimir/salvar em PDF ou baixar `audit_report.md`, `audit_results.json` e `fixed_page.html`. |
| **7. Motor de IA & Config** | Permite configurar sua chave de API e escolher com 1 clique presets para **OpenRouter**, **OpenAI Oficial**, **Ollama (Local)** ou **Google Gemini**, salvando diretamente no arquivo `.env`. |

---

## 3. Como Usar pelo Terminal (CLI)

Se preferir automatizar tarefas, integrar em pipelines CI/CD ou rodar tudo pelo terminal, a CLI oferece 4 comandos principais:

| Comando | Descrição |
| :--- | :--- |
| `python -m cli.main ui` | Inicia o servidor da Interface Gráfica Web. |
| `python -m cli.main demo` | Executa a demonstração completa (`broken_page.html` $\rightarrow$ `fixed_page.html` $\rightarrow$ revalidação `100/100`). |
| `python -m cli.main scan <alvo>` | Audita uma URL ou arquivo HTML local e gera os relatórios em `reports/`. |
| `python -m cli.main fix <arquivo>` | Audita um arquivo HTML local, exibe os diffs no terminal e aplica as correções. |

### 3.1. Comando `demo` (Ciclo Completo no Terminal)
```powershell
# Executa no modo Smart Mock (sem consumir API externa)
python -m cli.main demo --mock

# Executa utilizando a chave de IA configurada no .env
python -m cli.main demo
```

### 3.2. Comando `scan` (Auditar Sites ou Arquivos Locais)
```powershell
# Auditar um arquivo HTML local
python -m cli.main scan tests/broken_page.html --mock

# Auditar qualquer site da internet
python -m cli.main scan https://example.com --mock

# Auditar um site simulando visualização Mobile (390x844) ou Tablet (768x1024)
python -m cli.main scan https://example.com --viewport mobile --mock

# Salvar o relatório Markdown em um caminho personalizado
python -m cli.main scan https://example.com --output meu_relatorio.md
```

### 3.3. Comando `fix` (Corrigir Código Automaticamente)
```powershell
# Gera o arquivo corrigido em reports/fixed_page.html (mantendo o original intacto)
python -m cli.main fix tests/broken_page.html --mock

# Salva o HTML corrigido em um caminho específico
python -m cli.main fix tests/broken_page.html --output pagina_pronta.html --mock

# Corrige o próprio arquivo original (cria automaticamente um backup .html.bak antes)
python -m cli.main fix tests/broken_page.html --in-place --mock
```

---

## 4. Arquivos Gerados Automaticamente (`reports/`)

Sempre que você roda uma auditoria ou correção (seja pela Interface Gráfica ou pelo Terminal), os seguintes arquivos são salvos na pasta `reports/`:

- **`reports/audit_report.md`** — Relatório completo em Markdown com Scorecard, tabelas por pilar/severidade e blocos de código **Antes vs. Depois**.
- **`reports/audit_results.json`** — Diagnóstico estruturado em JSON contendo todas as métricas, coordenadas visuais (`rect`), mapa de foco e árvore de acessibilidade.
- **`reports/fixed_page.html`** — Código HTML com todas as correções aplicadas pelo Auto-Fixer.
- **`reports/before_screenshot.png` / `after_screenshot.png`** — Capturas de tela de página inteira antes e depois da remediação.
- **`reports/history.json`** — Histórico local de todas as auditorias executadas.
