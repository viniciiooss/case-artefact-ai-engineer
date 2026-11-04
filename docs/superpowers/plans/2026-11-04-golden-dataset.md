# Dataset golden e teste manual

Objetivo autorizado: adaptar o dataset de testes da Yaitec à Empório e entregar um
roteiro manual com resultados conferidos no snapshot. Execução na branch de trabalho
existente; sem modificar o checkout Yaitec ou copiar seu conteúdo comercial.

Desenho: preservar os quatro casos rápidos e as 12 regressões HTTP. Acrescentar JSONL
com 60 cenários, dez em cada grupo do banco Yaitec: qualidade, contexto, fontes,
alucinação, fora da base e prompt injection. Usar os mesmos dois critérios DeepEval
da Empório, acompanhados de verificações exatas de dinheiro, ferramentas e fontes.
Identificação prévia de pedidos é uma condição de teste explícita no backend.

- [x] Dataset e contratos: criar `eval_dataset.py` e testes de leitura JSON/JSONL,
  normalização input/mensagens, duplicatas, filtros e expectativas de respostas reais.
- [x] Runner: integrar pré-condição de identificação, verificações exatas e categorias;
  testar que uma nota alta do juiz não encobre falha objetiva nem identificação inválida.
  CLI ganha filtros e `--validate-only`, que não exige chave nem importa DeepEval.
- [x] Conteúdo: escrever 60 casos próprios em `evals/golden_emporio.jsonl`, com referências
  aos dados/PDF e perguntas positivas, negativas, ambíguas e em múltiplos turnos.
- [x] Entrega: documentar roteiro manual, dados fictícios de identificação e comandos;
  verificar o dataset offline, pytest, Ruff e regressões HTTP, revisar e registrar localmente.

Verificação prevista: pytest, Ruff, scripts/evaluate.py e scripts/evaluate_llm.py com
`--cases evals/golden_emporio.jsonl --validate-only --limit 60`. O lote ampliado pago fica
disponível por comando; esta adaptação será verificada offline, sem executar 60 casos pagos.
