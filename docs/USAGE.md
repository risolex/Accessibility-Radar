# Guia de Uso — Accessibility Radar

Este documento detalha os três comandos da CLI, suas opções e os artefatos gerados.

> Todos os comandos devem ser executados com o ambiente virtual **ativo** e a partir da raiz do projeto.

---

## Visão geral dos comandos

| Comando | O que faz | Alvo aceito |
| :--- | :--- | :--- |
| `scan` | Audita e gera relatório (não altera arquivos) | URL ou arquivo HTML local |
| `fix` | Audita e aplica correções no código | Arquivo HTML local |
| `demo` | Fluxo completo de ponta a ponta com revalidação | `tests/broken_page.html` (fixo) |

Flag comum a todos: `--mock` força o **Smart Mock/Fallback** (sem consumir créditos de API).

---

## `scan` — auditar sem alterar

Renderiza a página, diagnostica os 4 pilares, imprime um dashboard colorido no terminal e salva o relatório.

```bash
python -m cli.main scan <alvo> [--output CAMINHO] [--mock]
```

**Argumentos e opções**

| Nome | Descrição | Padrão |
| :--- | :--- | :--- |
| `<alvo>` | URL (`https://...`) ou caminho de arquivo HTML local | — (obrigatório) |
| `--output`, `-o` | Caminho do relatório Markdown | `reports/audit_report.md` |
| `--mock` | Força o modo determinístico | desligado |

**Exemplos**

```bash
# Arquivo local
python -m cli.main scan tests/broken_page.html

# URL remota
python -m cli.main scan https://example.com

# Relatório em caminho customizado, modo mock
python -m cli.main scan https://example.com -o relatorios/exemplo.md --mock
```

**Artefatos gerados**
- `reports/audit_report.md` — relatório executivo e técnico.
- `reports/audit_results.json` — diagnóstico estruturado (útil para CI/CD).
- `reports/latest_screenshot.png` — captura full-page.

---

## `fix` — corrigir o código

Executa a auditoria, exibe os diffs "Antes/Depois" e aplica as correções.

```bash
python -m cli.main fix <arquivo> [--output CAMINHO] [--in-place] [--mock]
```

**Argumentos e opções**

| Nome | Descrição | Padrão |
| :--- | :--- | :--- |
| `<arquivo>` | Caminho de arquivo HTML local | — (obrigatório) |
| `--output`, `-o` | Caminho do HTML corrigido | `reports/fixed_page.html` |
| `--in-place`, `-i` | Sobrescreve o arquivo original (cria backup `.bak`) | desligado |
| `--mock` | Força o modo determinístico | desligado |

**Exemplos**

```bash
# Gera a versão corrigida em reports/fixed_page.html
python -m cli.main fix tests/broken_page.html

# Salva em caminho específico
python -m cli.main fix pagina.html -o pagina.corrigida.html

# Aplica direto no original (backup pagina.html.bak é criado)
python -m cli.main fix pagina.html --in-place
```

> O modo `--in-place` **modifica o arquivo original**. O backup `.bak` permite reverter, mas trabalhe sempre com controle de versão.

---

## `demo` — demonstração completa

Fluxo autônomo de ciclo fechado sobre `tests/broken_page.html`:

1. Escaneia a página quebrada.
2. Gera `reports/audit_report.md`.
3. Cria `reports/fixed_page.html`.
4. **Re-audita** a página corrigida e compara o score antes/depois.

```bash
python -m cli.main demo [--mock]
```

---

## Entendendo o relatório

O `audit_report.md` contém:

- **Cabeçalho** — alvo, título da página, data/hora (UTC), motor de análise usado e score.
- **Resumo executivo** — distribuição de problemas por pilar e por severidade.
- **Diagnóstico detalhado** — para cada violação: ID, pilar, critério WCAG, nível, severidade, seletor, descrição técnica, impacto no usuário, recomendação e os blocos de código **Antes** vs. **Depois**.

**Severidades:** `critical`, `serious`, `moderate`, `minor`.

**Score:** 0 a 100, calculado por penalidade ponderada de severidade. `100` com zero violações = conforme WCAG 2.2 AA (nos critérios verificados).

---

## Modos de análise

- **`ai_multimodal`** — usado quando há `AI_API_KEY` válida. Envia DOM filtrado + screenshot ao provedor Vision.
- **`smart_fallback`** — usado quando não há chave, a chave é inválida, ou com `--mock`. Processa os dados reais do navegador com heurísticas determinísticas.

Se a chamada de IA falhar (rede/autenticação), o agente faz fallback automático para o modo determinístico sem interromper a execução.

---

## Dicas

- Use `--mock` em CI/CD para resultados reproduzíveis e sem custo.
- Para auditar várias páginas, chame `scan` em loop e use `--output` para separar os relatórios.
- O `audit_results.json` é ideal para integrar com pipelines (ex.: falhar o build se o score ficar abaixo de um limite).
