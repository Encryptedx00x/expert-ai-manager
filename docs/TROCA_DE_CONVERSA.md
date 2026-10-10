# Trocar de conversa sem perder o projeto

A versao atual oferece **troca automatica** (ver secao "Troca automatica (v2)" ao final) e o fluxo **manual assistido** abaixo para recuperar casos bloqueados. A automacao so abre um novo chat quando encontra condicoes verificaveis; limites de uso da conta nao sao contornados.

## O que é preservado

- Arquivos, testes, diffs e histórico Git do projeto.
- O checkpoint local `.dev-loop/chat-state.json`, incluindo `request_id`, número da rodada e estado.
- Configurações, pausas e histórico de uso, inclusive limites de ritmo.
- Identificação da conversa antiga até que você anexe explicitamente uma nova.

**Importante:** o instalador/supervisor não copia o histórico completo do ChatGPT. O novo chat recupera o contexto lendo código, documentos e checkpoints; informações que existiam apenas na conversa anterior podem precisar ser fornecidas novamente.

## 1. Quando aparecer o limite

1. Acesse a aba **Conversa** do HUD.
2. Clique **Preparar troca e pausar envios**.
3. O Expert AI Manager pausa novas solicitações e salva a migração em `.dev-loop/chat-migration.json` (fora do Git).
4. Clique **Ver / copiar prompt para o novo chat**, depois **Copiar prompt**.
5. Abra manualmente **uma nova conversa** no ChatGPT e cole o prompt. Use um **título diferente** da conversa anterior. Exemplo: `Óliver's Dev Loop 2`.
6. O novo GPT lerá `AGENTS.md`, `docs/TASKS.md`, `docs/STATE.md`, `.dev-loop/chat-state.json` e Git para recuperar o projeto.

**Se ainda existe um rascunho `pending_send`, a preparação é recusada**. Verifique primeiro esse rascunho para não perder ou duplicar uma mensagem.

**Se a etapa antiga está `running` ou `requested`, ela NÃO será considerada concluída automaticamente.** A nova conversa deve verificar o diff, os testes e o estado real antes de reconciliar. Não envie outro request_id enquanto isso.

## 2. Anexar a nova conversa

Depois de abrir e identificar a nova conversa no Edge ou Brave, inicie o comando abaixo **em um terminal do próprio projeto**:

```powershell
py -3 -B scripts\expert_ai_rpa.py migrate-attach
```

Você terá **6 segundos** para colocar a nova janela do ChatGPT em primeiro plano. O programa verifica o compositor acessível e exige um título diferente do anterior. A calibração não envia mensagens.

Se o nome do novo chat ainda for `ChatGPT`, renomeie-o para um título único e reconhecível antes de anexar.

O marcador muda para `attached`, mas o supervisor **continua pausado**.

O título é uma proteção básica, **não prova criptograficamente a identidade da conversa**. Confirme visualmente que você está na nova conversa e na conta correta. Não vincule uma aba de outro projeto.

## 3. Terminar a etapa antiga e retomar

Na nova conversa, peça ao GPT para conferir o checkpoint atual. Quando a rodada interrompida estiver **comprovadamente concluída**, use o protocolo de `AGENTS.md` e os helpers locais para deixá-la em `ready`. Se houver bloqueio, mantenha o estado adequado e não force a migração.

Depois, clique **Finalizar e retomar, se seguro** na aba Conversa, ou execute:

```powershell
py -3 -B scripts\expert_ai_control.py migrate-finish
```

O comando só retoma envios se:
- A nova conversa estiver anexada e a calibração continuar válida.
- O checkpoint estiver em `ready`.
- A pausa da migração ainda existir e não houver alerta de limite.
- Não existir uma pausa anterior à migração que precise permanecer.

Se a pausa já estava ativada antes da troca, ela **permanece ativada**. Só use `resume` posteriormente quando tiver certeza de que é seguro.

O supervisor existente pode continuar sua verificação normal depois da migração, sem outra instância ou novo loop. Caso ele não esteja ativo, inicie uma única instância pelo procedimento do [guia completo](GUIA_COMPLETO.md), somente após revisar o checkpoint e os processos.

## Para cancelar

Se preparou a troca por engano, **antes de anexar** a nova conversa, clique **Cancelar preparação** ou execute:

```powershell
py -3 -B scripts\expert_ai_control.py migrate-cancel
```

Isso restaura a condição de pausa anterior, sem modificar o checkpoint. **Depois de anexar um novo chat, não existe retorno automático**: inspecione a configuração e o estado antes de corrigir manualmente.

## Troca automatica (v2)

O EAM pode fazer a migracao automaticamente usando o botao visivel New chat no Brave/Edge e as APIs de acessibilidade do Windows. Na configuracao nova, essa opcao fica ativada, com gatilho preventivo de 8 rodadas desde a ultima migracao segura (ajustavel de 4 a 100). O contador e uma aproximacao: o EAM nao conhece o numero de tokens nem o limite real da conversa.

Ha dois gatilhos adicionais: aviso explicito de conversa muito longa, e o alerta "Message delivery timed out. Please try again.". O ultimo caso e uma migracao de recuperacao: nao prova que a conversa chegou ao limite. Se o limite for de uso da conta/plano, o EAM pausa e NAO abre outra conversa para contorna-lo.

Procedimento: preparar PAUSE e chat-migration.json -> validar janela/URL/botao New chat -> abrir uma unica conversa -> conferir novo compositor -> enviar um prompt de recuperacao com migration_id -> novo GPT verifica AGENTS, tarefas, Git, testes e o checkpoint -> novo GPT executa migrate-ack com o mesmo migration_id -> EAM confirma URL final e marcador postado -> recalibra e conclui migrate-finish.

O envio de recuperacao e reservado no ledger de tentativas. Se o navegador perder o foco, ocorrer rascunho pendente, erro na navegacao ou entrega ambigua, o fluxo PARA para inspe??o, sem clicar ou enviar de novo sozinho. Nunca gera um novo request_id de desenvolvimento durante a migracao. Se a rodada estiver running/requested, o novo GPT devera reconciliar com evidencias antes de confirmar ready; nao pode inventar progresso.

Comandos de configuracao:
- py -3 -B scripts/expert_ai_control.py auto-handoff-on
- py -3 -B scripts/expert_ai_control.py auto-handoff-off
- py -3 -B scripts/expert_ai_control.py set handoff_after_rounds 8
- py -3 -B scripts/expert_ai_rpa.py status

HUD, aba Configuracao: Migrar conversa automaticamente e Trocar apos N rodadas.

O fluxo manual das secoes anteriores permanece como recuperacao alternativa. Nao instalar esta nova versao enquanto o supervisor anterior tiver uma rodada em execucao.
