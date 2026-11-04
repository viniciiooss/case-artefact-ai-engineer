# Horário, endereço e políticas com fontes

Gerado por `uv run --no-sync python scripts/evaluate.py --write-examples`; execução real do serviço HTTP local, sem LLM.

- provider: `demo`
- model: `deterministic-v1`
- dataset_sha256: `4f4078fee1ec8fa8b660cfbc1b3de67d3b97da4ba5505800fc0dbacb8eb84c7c`
- policy_sha256: `b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7`

Os e-mails deste snapshot são fictícios; a identificação abaixo é exclusiva deste exemplo.

**Cliente:** Qual o horário de funcionamento aos sábados?

**Mel:** Encontrei estas orientações no manual da loja:

Horário de funcionamento (página 2):
2. Horário de Funcionamento O atendimento presencial na loja segue os horários abaixo. O atendimento via WhatsApp segue o mesmo horário, com respostas automáticas fora do expediente. Dia Horário Segunda a Sexta-feira 09:00 às 18:00 Sábado 09:00 às 13:00 Domingo e Feriados Fechado Em datas especiais (Black Friday, Aniversário da Loja, Natal), o horário pode ser estendido. Alterações serão comunicadas com antecedência nas redes sociais e no atendimento via WhatsApp.

Diretrizes de atendimento (página 6):
7.1 Diretrizes de Atendimento Tom de voz: informal mas profissional. O cliente deve se sentir acolhido, como se estivesse conversando com um amigo que entende de música. Evitar linguagem excessivamente formal ou robotizada. Tempo de resposta: máximo de 5 minutos durante o horário de funcionamento. Fora do expediente, o assistente virtual deve informar o horário de retorno. Informações precisas: nunca fornecer informações sobre preços, estoque ou prazos sem consultar o sistema. Informações incorretas geram frustração e podem configurar propaganda enganosa. Escopo: o atendente deve informar que a loja trabalha exclusivamente com instrumentos musicais. Pedidos de acessórios (cordas, cabos, palhetas, pedais, amplificadores, cases) devem ser educadamente redirecionados. Sugerir lojas parceiras quando possível.

Ferramentas: `search_policies`.

- Fonte `policy-p2-2-0`: Horário de funcionamento; página 2.
- Fonte `policy-p6-7.1-0`: Diretrizes de atendimento; página 6.

**Cliente:** Qual o endereço da loja?

**Mel:** Encontrei estas orientações no manual da loja:

Dados da empresa (página 2):
1.2 Dados da Empresa Campo Informação Razão Social Empório da Música Instrumentos Musicais Ltda. Nome Fantasia Empório da Música CNPJ 12.345.678/0001-90 Endereço Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, 79202-333 Telefone / WhatsApp (67) 3341 - 4444 E-mail contato@empóriodamusica.com.br Fundação 2008

Privacidade e proteção de dados (página 7):
9. Privacidade e Proteção de Dados A Empório da Música está em conformidade com a Lei Geral de Proteção de Dados (LGPD — Lei nº 13.709/2018). Os dados pessoais coletados durante o atendimento (nome, telefone, e-mail, endereço) são utilizados exclusivamente para:

Ferramentas: `search_policies`.

- Fonte `policy-p2-1.2-0`: Dados da empresa; página 2.
- Fonte `policy-p7-9-0`: Privacidade e proteção de dados; página 7.
- Fonte `policy-p1-1-0`: Sobre a Empório da Música; página 1.
- Fonte `policy-p2-1.1-0`: Missão; página 2.

**Cliente:** Quais as formas de pagamento e parcelamento?

**Mel:** Encontrei estas orientações no manual da loja:

Regras de parcelamento (página 3):
3.1 Regras de Parcelamento
• Parcelamento em até 3x: sem juros, sem valor mínimo de parcela (exceto abaixo de R$ 50,00).
• Parcelamento de 4x a 6x: sem juros, parcela mínima de R$ 80,00.
• Parcelamento de 7x a 12x: sem juros, parcela mínima de R$ 100,00.
• Combinação de formas de pagamento: permitida (ex.: PIX + cartão) para compras acima de R$ 2.000,00.

Formas de pagamento (página 3):
3. Formas de Pagamento Aceitamos as seguintes formas de pagamento para compras presenciais e online: Forma Condições Observações PIX Pagamento à vista 5% de desconto sobre o preço de tabela Cartão de Débito Pagamento à vista Todas as bandeiras aceitas Cartão de Crédito Até 12x sem juros Parcela mínima de R$ 100,00 Boleto Bancário Pagamento à vista Compensação em até 3 dias úteis

Ferramentas: `search_policies`.

- Fonte `policy-p3-3.1-0`: Regras de parcelamento; página 3.
- Fonte `policy-p3-3-0`: Formas de pagamento; página 3.
- Fonte `policy-p4-4.1-0`: Arrependimento em compras online; página 4.
