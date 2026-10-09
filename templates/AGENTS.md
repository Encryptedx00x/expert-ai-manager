# {{PROJECT_NAME}} | Regras do agente

## Objetivo e contexto
Este projeto será conduzido em etapas pequenas, rastreáveis e verificáveis. O ChatGPT não deve supor que uma tarefa passou ou que um serviço está disponível sem conferir.

## Hierarquia de verdade
1. Código, testes e dados reais do projeto.
2. Decisões registradas em docs/ARCHITECTURE.md.
3. Checklist docs/TASKS.md e checkpoint docs/STATE.md.
4. Orientações recebidas do usuário nesta conversa.

## Ciclo de desenvolvimento
1. Ler .dev-loop/chat-state.json, verificar o request_id desta mensagem e confirmar status requested ou pending_send.
2. Marcar running: py -3 -B scripts/expert_ai_state.py ack <request_id>.
3. Ler AGENTS.md, docs/TASKS.md, docs/STATE.md, docs/ARCHITECTURE.md e o código relevante.
4. Escolher uma etapa pequena com critérios de aceite e dependências atendidas.
5. Implementar, testar (incluindo um teste de regressão quando couber), revisar diff e riscos.
6. Atualizar docs/TASKS.md: [x] feito/validado, [~] parcial, [ ] pendente, [!] adiado com motivo.
7. Registrar no docs/STATE.md a entrega, pendências, resultado dos testes, commit e próximo passo.
8. Fazer commit apenas quando seguro; não incluir .env, segredos, logs, dumps ou .dev-loop.
9. Atualizar o JSON de checkpoint com last_commit, last_task e last_quality_check preservando request_id/round; usar update atômico.
10. Encerrar com py -3 -B scripts/expert_ai_state.py ready <request_id> "resumo", ou blocked/done conforme a situação.

## Segurança e recursos
- Não modificar Docker/WSL/serviços de projetos não relacionados.
- Não contornar limites de plataforma ou autenticação.
- Usar plug-ins e skills conforme sua disponibilidade e permissões reais.
- Não publicar repositórios, fazer deploy ou modificar dados pessoais sem instrução do usuário.
- Este supervisor usa automação visível no desktop: mantenha revisão humana e a compatibilidade com os termos dos serviços.
- Pausas e limites são para uso responsável e conforto, não para disfarçar a ferramenta.

## Projeto atual
Nome: {{PROJECT_NAME}}
Prefixo de tarefas: {{TASK_PREFIX}}
As referências de design e requisitos detalhados são registradas nos documentos do projeto.
