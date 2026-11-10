# Contribuindo com o Accessibility Radar

Obrigado pelo interesse em contribuir! Este guia explica como colaborar de forma eficiente.

## Código de conduta

Seja respeitoso e construtivo. Discussões técnicas são bem-vindas; ataques pessoais não.

## Como contribuir

1. **Configure o ambiente** (veja o README):
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1   # Windows
   # source venv/bin/activate    # Linux/macOS
   pip install -r requirements.txt
   playwright install chromium
   ```
2. **Faça suas mudanças** seguindo os padrões abaixo.
3. **Valide** rodando o fluxo completo:
   ```bash
   python -m cli.main demo --mock
   ```

## Padrões de código

- **Python 3.10+**, com type hints onde fizer sentido.
- Siga o estilo já presente no projeto (docstrings em módulos e funções, nomes descritivos).
- Prefira funções puras e pequenas; isole efeitos colaterais (I/O, rede, disco).
- Mantenha a compatibilidade multiplataforma (use `pathlib.Path` e UTF-8 explícito).
- **Não** quebre o Smart Mock/Fallback: qualquer nova regra deve funcionar sem chave de API.

## Reportando bugs

Ao relatar um problema, inclua:
- Comando executado e saída (ou screenshot).
- Sistema operacional e versão do Python.
- URL ou trecho de HTML que reproduz o problema (quando possível).
- Comportamento esperado vs. observado.

## Sugerindo melhorias

Descreva o problema que a melhoria resolve, não apenas a solução. Isso ajuda a avaliar alternativas.

## Acessibilidade

Como este é um projeto de acessibilidade, mudanças que afetem detecção ou correção devem referenciar o **critério WCAG** correspondente e, idealmente, incluir um caso de teste em `tests/`.

## Licença das contribuições

Ao contribuir, você concorda que seu código será licenciado sob a licença **MIT** do projeto.
