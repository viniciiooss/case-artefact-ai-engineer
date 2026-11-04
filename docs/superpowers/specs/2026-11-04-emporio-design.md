# Agente de atendimento — especificação

## Contexto e escopo

O diretório estava vazio na retomada. O ZIP original contém o enunciado de três páginas,
o manual de oito páginas e seis CSVs. Os arquivos de dados foram preservados byte a byte,
com nomes simplificados. Python é a única tecnologia obrigatória; RAG, function calling,
ReAct e SQL são abordagens sugeridas, não frameworks obrigatórios.

Construir atendimento de instrumentos musicais em português, persona Mel: acolhedora,
informal e profissional. Responder sobre catálogo, estoque, preços, promoções, condições,
pedidos e políticas; reconhecer limites e oferecer contato humano. Não efetuar compras,
alterar estoque, cancelar pedidos nem afirmar que uma pessoa foi notificada.

## Arquitetura escolhida

LangGraph com ciclo modelo → ferramentas → modelo, limite de rodadas e ferramentas
tipadas pelo LangChain/Pydantic. OpenAI (gpt-4.1-mini configurável) e Ollama por integrações
dedicadas. Um provedor demo determinístico exercita o mesmo grafo e as mesmas ferramentas
sem rede: é um simulador, não uma LLM. A seleção é explícita, sem fallback silencioso.

SQL parametrizado sobre SQLite para dados operacionais. Preços e estoque são consultados
a cada turno, sem cache de respostas comerciais. Não expor SQL arbitrário à LLM.
Ingestão validada, idempotente por hash e transacional; valores monetários em centavos.
RAG BM25 com normalização em português sobre trechos por seção/página do PDF. O corpus é
curto: evitar embeddings remotos e infraestrutura vetorial que não acrescentem evidência.
Ferramentas retornam fontes estruturadas; não inventar citações a partir da resposta.

Histórico e contexto em outro SQLite, com sessões protegidas por tokens aleatórios cujo
hash é armazenado. Persistir apenas mensagens públicas finais e contexto mínimo; manter
traces de ferramentas sem raciocínio interno. Janela de histórico limitada. Pedidos só
podem ser acessados após validação explícita de número + e-mail no backend, com autorização
limitada ao pedido na sessão. Esse método demonstra isolamento, mas não substitui login/OTP.

FastAPI publica chat, criação/leitura/exclusão de sessão, verificação de pedido, health,
catálogo e documento de políticas. HTML/CSS/JS local, sem build Node, para chat responsivo
com fontes, histórico, sugestões e identificação de pedido. Typer oferece CLI equivalente.

## Regras e ambiguidades

- Disponível = status active E estoque > 0. coming_soon/discontinued nunca disponíveis.
- Aplicar somente a maior promoção ativa de um produto; nunca acumular PIX com promoção.
- PIX sem promoção = 5% sobre tabela. HALF_UP e divisão de parcelas preservam centavos.
- De 4 a 6 parcelas: mínimo R$ 80; de 7 a 12: mínimo R$ 100. Até 3: a exceção abaixo
  de R$ 50 é ambígua; pedir análise humana para parcela menor que R$ 50.
- Campo Grande: acima de R$ 500 gratuito; abaixo, R$ 35. Exatamente R$ 500 requer
  confirmação. Não inventar cidades da região metropolitana ou cotação de outras cidades.
- Arrependimento online: até sete dias corridos do recebimento; nunca usar a previsão de
  entrega do CSV como data real. Pedir canal/data faltantes e verificar condições do manual.
- Texto do manual é referência interna, não análise jurídica. Conflitos e exceções exigem
  equipe humana. Condições de venda final/personalização não resolvem direitos legais.
- Telefone geral: (67) 3341-4444; WhatsApp dedicado da seção 7: (67) 3321-4500.
  E-mails conflitantes no manual: não escolher silenciosamente; preferir os telefones.
- Totais históricos de pedidos são os registrados, sem recalcular com o catálogo atual.
- Os dados são um snapshot fornecido, não integração real com ERP/transportadoras.

## Contrato HTTP

`GET /api/health`: status, provider, model, counts {products, orders, policy_chunks}.
`POST /api/sessions`: {session_id, token} (token só retorna aqui).
Demais rotas de sessão exigem `Authorization: Bearer <token>`.
`POST /api/sessions/{id}/messages`, body {message}: resposta com
{message, sources, tools, provider, model, latency_ms, context}.
sources: [{id, kind, title, page?, reference?, excerpt?}].
tools: [{name, duration_ms, ok}].
`GET /api/sessions/{id}`: {session_id, messages: [{role, content, sources}], verified_orders}.
`POST /api/sessions/{id}/order-access`, body {order_id, email}: {verified, order_id}.
`DELETE /api/sessions/{id}`: 204, exclui histórico, grants e tickets locais.
`GET /api/products`: produtos públicos disponíveis; sem clientes ou pedidos.
`GET /api/policies/document`: PDF para abrir a página citada.
Erros têm {detail}; entradas vazias ou grandes geram 422. Sem CORS amplo.

## Segurança e confiabilidade

O modelo não recebe tabela de clientes, chave, token de sessão ou SQL. Ferramentas de
pedidos verificam autorização no backend mesmo diante de prompt injection. Limitar
mensagem, histórico, resultados, rodadas e tempo de LLM. Mensagens de erro não expõem
chaves nem argumentos sensíveis. Token ausente/incorreto não permite enumerar sessões.
Sem HTML dinâmico não sanitizado; UI usa textContent para mensagens. Persistência local e
exclusão explícita; produção demandaria autenticação forte, rate limit e retenção.

## Critérios de aceite

1. Rodar sem chave com uv e Docker; LLM real com configuração documentada.
2. Busca até R$ 1.000 retorna somente itens disponíveis e no orçamento.
3. Takamine GD20 exibe R$ 2.199,00; promoção inativa de 12% não é aplicada.
4. Promoção ativa + PIX não acumula; parcelas e limites têm testes de borda.
5. RAG recupera horário, endereço, devolução e pagamento com páginas corretas.
6. Pedido sem grant não vaza status/rastreio; grant não atravessa sessões.
7. Continuação de conversa lembra produto; preços são consultados novamente.
8. Falhas de provedor, chamadas inválidas e loops têm tratamento verificável.
9. Cinco conversas reproduzíveis, avaliação automática e README com decisões, limitações,
   execução, evidência de validação e uso de assistente de código.

## Direção visual

Uma loja de música independente: azul profundo #162f48, azul tinta #264c70, papel branco
#fafbfc, cinza azulado #e9eff4 e amarelo de etiqueta #f3c769. Tipografia de interface com
system UI, título com Georgia. A curva de um disco em SVG/CSS é a única ilustração marcante.
Chat é o centro; navegação lateral com contato e acesso ao pedido. Fontes aparecem sob a
resposta e abrem o manual. Sem métricas técnicas desnecessárias no fluxo do cliente.
