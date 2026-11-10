# Configuração de IA — Accessibility Radar

O agente funciona **sem nenhuma configuração** graças ao Smart Mock/Fallback. Esta página é para quem quer habilitar a análise por **IA multimodal (Vision)**.

---

## Variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto (copie de `.env.example`):

```bash
# Windows
copy .env.example .env
# Linux/macOS
cp .env.example .env
```

| Variável | Descrição | Exemplo |
| :--- | :--- | :--- |
| `AI_BASE_URL` | Endpoint compatível com o SDK da OpenAI | `https://openrouter.ai/api/v1` |
| `AI_API_KEY` | Sua chave de API (deixe vazio para modo mock) | `sk-...` |
| `AI_MODEL_TEXT` | Modelo de texto | `openai/gpt-4o-mini` |
| `AI_MODEL_VISION` | Modelo com suporte a imagem | `openai/gpt-4o-mini` |

> ⚠️ **Segurança:** Nunca compartilhe chaves de API publicamente. Se uma chave vazar, revogue-a imediatamente no painel do provedor.

---

## Provedores compatíveis

Qualquer endpoint no padrão OpenAI funciona. Exemplos de configuração:

### OpenRouter (padrão)
```env
AI_BASE_URL=https://openrouter.ai/api/v1
AI_API_KEY=sk-or-...
AI_MODEL_TEXT=openai/gpt-4o-mini
AI_MODEL_VISION=openai/gpt-4o-mini
```

### OpenAI
```env
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=sk-...
AI_MODEL_TEXT=gpt-4o-mini
AI_MODEL_VISION=gpt-4o
```

### xAI (Grok)
```env
AI_BASE_URL=https://api.x.ai/v1
AI_API_KEY=xai-...
AI_MODEL_TEXT=grok-2-latest
AI_MODEL_VISION=grok-2-vision-latest
```

### Google Gemini (compatível com OpenAI)
```env
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
AI_API_KEY=...
AI_MODEL_TEXT=gemini-1.5-flash
AI_MODEL_VISION=gemini-1.5-flash
```

### Ollama (local, offline)
```env
AI_BASE_URL=http://localhost:11434/v1
AI_API_KEY=ollama
AI_MODEL_TEXT=llama3.1
AI_MODEL_VISION=llava
```

---

## Como o agente decide o modo

1. Se `AI_API_KEY` estiver preenchida com um valor real → **modo IA multimodal**.
2. Se estiver vazia, for um placeholder (`your_api_key_here`, `sua_chave_aqui`, `sk-xxx`, `none`, `mock`) ou a flag `--mock` for usada → **Smart Mock/Fallback**.
3. Se a chamada de IA falhar em tempo de execução → **fallback automático** para o modo determinístico.

---

## Recomendações de modelo

- Para análise visual (descrições `alt` contextuais), prefira um modelo com **suporte a Vision** em `AI_MODEL_VISION`.
- Para auditorias puramente estruturais, o modelo de texto já cobre a maior parte dos casos.
- Em CI/CD, prefira `--mock` para resultados reproduzíveis e custo zero.
