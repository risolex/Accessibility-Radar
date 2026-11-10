# Solução de Problemas — Accessibility Radar

Erros comuns e como resolvê-los.

---

## Instalação e ambiente

### `ModuleNotFoundError: No module named 'typer'` (ou outro módulo)
O ambiente virtual provavelmente não está ativo ou as dependências não foram instaladas.

```bash
# Ative o venv
.\venv\Scripts\Activate.ps1   # Windows
# source venv/bin/activate    # Linux/macOS

pip install -r requirements.txt
```

### `playwright: command not found`
O Playwright não foi instalado no ambiente ativo. Rode `pip install -r requirements.txt` com o venv ativo.

---

## Navegador / Playwright

### Erro ao iniciar o Chromium headless
Instale o binário do navegador:

```bash
playwright install chromium
```

Se mesmo assim falhar, o agente tenta automaticamente usar o **Google Chrome** ou **Microsoft Edge** instalados no sistema. Garanta que ao menos um deles esteja presente.

### Timeout ao carregar uma URL
Páginas pesadas podem exceder o tempo de espera (`networkidle`, 30s). Verifique sua conexão e se a URL é acessível. Para arquivos locais, isso raramente ocorre.

---

## Execução

### Caracteres estranhos / caixas quebradas no terminal (Windows)
É apenas a renderização de caracteres de caixa da biblioteca Rich no console legado. **Não afeta** os resultados nem os arquivos gerados. Para uma exibição melhor, use o **Windows Terminal** em vez do console clássico `cmd.exe`.

### A saída não mostra acentuação correta
O projeto força UTF-8 na saída, mas terminais muito antigos podem não suportar. Prefira Windows Terminal, PowerShell 7+ ou um terminal Unix.

### `FileNotFoundError` ao rodar `scan`/`fix`
O caminho do arquivo HTML está incorreto ou relativo ao diretório errado. Rode os comandos a partir da raiz do projeto e confira o caminho.

---

## IA / API

### A análise cai sempre no modo mock mesmo com chave configurada
- Confirme que o arquivo se chama exatamente `.env` (não `.env.txt`) e está na raiz do projeto.
- Verifique se `AI_API_KEY` não é um placeholder (`your_api_key_here`, `sua_chave_aqui`, `sk-xxx`, `none`, `mock`).
- Reinicie o terminal após editar o `.env`.

### Erro de autenticação / 401 do provedor
A chave é inválida ou expirou. Gere uma nova no painel do provedor. O agente faz fallback automático para o modo determinístico quando a API falha, então a execução continua.

### Erro 404 de modelo
O nome em `AI_MODEL_TEXT`/`AI_MODEL_VISION` não existe no provedor escolhido. Consulte [`CONFIGURATION.md`](./CONFIGURATION.md) para os exemplos corretos por provedor.
