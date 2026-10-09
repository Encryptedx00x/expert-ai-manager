# Prompts prontos | Expert AI Manager

Esta é a sequência de mensagens para começar um **novo projeto**. Copie somente o bloco correspondente à fase atual. **Não envie o prompt de execução com request_id manualmente:** o supervisor cria esse identificador quando chega a hora.

## Prompt A. Criar projeto, auditar ferramentas e planejar (primeira mensagem)

**Quando:** depois de instalar os scripts no projeto e abrir uma nova conversa do ChatGPT. Com o supervisor parado, preencha os campos entre colchetes.

```text
Quero estruturar e desenvolver o projeto [NOME DO PROJETO] na pasta [CAMINHO COMPLETO].

Objetivo do produto: [O QUE É, QUEM USA E QUE PROBLEMA RESOLVE].
Funcionalidades e restrições conhecidas: [DESCREVA].
Design, anexos, imagens ou referências: [CAMINHOS/ARQUIVOS OU NENHUM].
Tecnologias já definidas ou preferidas: [TECNOLOGIAS OU ABERTO A PROPOSTAS].
Infraestrutura/limitações: [PORTAS, BANCO, SERVIDORES, MEMÓRIA, PRAZO E CUSTO].
Contexto: [PROJETO NOVO OU CÓDIGO EXISTENTE].

Você será o arquiteto e desenvolvedor responsável, mas nesta primeira etapa NÃO inicie o loop automático nem faça deploy.

1. Use Remote Desktop Commander para identificar o computador correto, verificar a pasta e fazer o inventário do código, Git, dependências e referências existentes.
2. Confira quais plugins realmente estão conectados, especialmente Remote Desktop Commander, GitHub e Context7. Verifique quais skills podem ser usadas neste projeto. Se for um app web, investigue Ponytail, Playwright CLI, React Best Practices e Web Design Guidelines. Não afirme acesso que não testou.
3. Leia AGENTS.md, docs/TASKS.md, docs/STATE.md e docs/ARCHITECTURE.md gerados pelo instalador do Expert AI Manager. Preserve decisões e código existentes.
4. Planeje os requisitos funcionais/não funcionais, fluxos de usuário, modelo de dados, arquitetura, integrações, UX, segurança, testes, prioridades, dependências e marcos de entrega.
5. Atualize AGENTS.md, docs/ARCHITECTURE.md, docs/TASKS.md, docs/STATE.md e crie docs/ROADMAP.md e docs/TEST_PLAN.md. No TASKS.md, utilize IDs com prefixo [PREFIXO, EX: CRM] e [ ] pendente, [~] parcial, [x] verificado, [!] adiado com motivo.
6. Revise criticamente o plano, procurando inconsistências, excesso de escopo, dependências não atendidas, riscos e critérios de aceite vagos.
7. Registre como cada verificação será executada de verdade, sem prometer testes impossíveis. Não invente resultados.
8. Mostre um resumo objetivo do planejamento, a lista de ferramentas confirmadas, os arquivos atualizados, pontos que precisam de decisão e a primeira etapa de implementação.

Não mexa nos processos, containers ou arquivos de outros projetos. Não altere .dev-loop/chat-state.json por causa desta primeira mensagem de planejamento. Se encontrar uma decisão bloqueante, identifique-a antes da execução.
```

O arquivo [PROMPT_PLANEJAMENTO.md](PROMPT_PLANEJAMENTO.md) contém uma versão mais longa para projetos grandes.

## Prompt B. Revisar plano antes do desenvolvimento

**Quando:** após o primeiro planejamento. Com o supervisor ainda parado.

```text
Revise o planejamento deste projeto como um arquiteto e QA sênior.

Leia o código e os arquivos AGENTS.md, docs/ARCHITECTURE.md, docs/TASKS.md,
docs/STATE.md, docs/ROADMAP.md e docs/TEST_PLAN.md.

Confirme se:
- todas as funcionalidades solicitadas estão representadas em tarefas verificáveis;
- as dependências permitem implementar uma tarefa por rodada sem retrabalho;
- os critérios de aceite e testes são objetivos;
- o escopo não incluiu módulos não solicitados;
- a stack, a arquitetura e o design foram justificados;
- os cuidados com segurança, dados, ambientes e outros projetos estão documentados;
- os plugins e skills citados realmente estão disponíveis.

Corrija lacunas, registre decisões e atualize o Git quando seguro.
Não inicie o loop ainda. Ao final, informe se o projeto está pronto
para iniciar pelo Expert AI Manager, e o que ainda impede isso.
```

## Prompt C. Diagnosticar supervisor ou etapa bloqueada

**Quando:** o HUD indicar blocked, mensagem duplicada/ambígua, erro ou processo parado. **Pause** antes de diagnosticar.

```text
O Expert AI Manager está pausado ou bloqueado neste projeto.
Use Remote Desktop Commander apenas para diagnóstico inicialmente.
Leia .dev-loop/chat-state.json, .dev-loop/rpa-config.json,
o trecho final de .dev-loop/rpa.log, AGENTS.md, docs/TASKS.md,
docs/STATE.md e o status do Git.

Identifique a causa com evidências. Confira se há um request_id
pendente, rascunho no ChatGPT ou uma etapa ainda executando.
Não envie outra mensagem, não altere manualmente o request_id,
não contorne limites e não inicie uma segunda instância.
Apresente o caminho mais seguro de recuperação e só execute
correções reversíveis que não coloquem os dados em risco.
```

## Prompt D. Conferir status e o que falta

**Quando:** quiser um resumo na conversa, sem recomeçar o fluxo.

```text
Leia docs/TASKS.md, docs/STATE.md e o estado do Git deste projeto.
Resuma em até 8 linhas: última etapa concluída, testes e resultados,
último commit, principais pendências, bloqueios reais e próxima tarefa.
Não marque novas tarefas como concluídas e não dispare outra instância
do supervisor.
```

## Prompt E. Solicitar conexão/instalação de ferramentas relevantes

**Quando:** antes do planejamento ou quando o modelo informar ferramenta ausente.

```text
Avalie que plugins, ferramentas e skills são realmente necessários
para este projeto, considerando sua stack e requisitos.
Verifique os que já estão disponíveis nesta conversa e na pasta local.
Considere Remote Desktop Commander, GitHub e Context7, e, para projetos web,
Ponytail, Playwright CLI, React Best Practices e Web Design Guidelines.
Para cada um, explique finalidade, como confirmar instalação e se é obrigatório
ou opcional. Não assuma que ferramentas não verificadas estão disponíveis.
Se conectar um plugin ou conceder permissões exigir minha ação, indique
exatamente qual é a etapa de autorização, sem tentar substituí-la.
Registre as escolhas confirmadas no AGENTS.md.
```

## Como funciona o prompt automático (não precisa copiar)

Após calibrar a conversa e iniciar o supervisor, o arquivo
`.dev-loop/rpa-config.json` contém o campo `message` com a instrução de
continuação correspondente ao **nome do seu projeto**. O supervisor acrescenta
`[request_id: ...]` e envia uma mensagem somente quando as condições são atendidas.

Na chegada desse identificador, as regras de `AGENTS.md` instruem o GPT a:

1. Verificar `request_id` e `status` no checkpoint JSON.
2. Marcar `running` com `scripts/expert_ai_state.py ack`.
3. Ler tarefas e estado, realizar **uma etapa coerente** e rodar os testes.
4. Registrar resultados e commit em `docs/TASKS.md`, `docs/STATE.md` e JSON.
5. Marcar `ready`, `blocked` ou `done` com o **mesmo ID**.

Se esses arquivos ainda não refletirem o projeto, volte aos Prompts A e B. Não tente acelerar a execução simulando IDs ou repetindo envios manualmente.
