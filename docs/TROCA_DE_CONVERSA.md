# Trocar de conversa sem perder o projeto

Quando o ChatGPT indicar que uma conversa ficou longa demais, use **Expert AI Manager → aba Conversa**. Esta é a migração manual assistida (v1): o programa **não detecta com precisão a mensagem de limite** e não abre chats sozinho. A ferramenta só solicita que você abra outro chat depois de clicar em **Preparar troca**.

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

Depois de abrir e identificar a nova conversa no Edge, inicie o comando abaixo **em um terminal do próprio projeto**:

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

## Prevenção de conversas muito extensas

- O Expert AI Manager agora envia orientações para agrupar **2–4 tarefas relacionadas**, sem comprometer os testes ou a segurança, e resume saídas de comandos/logs na própria conversa.
- Após uma migração **realmente concluída**, registra a rodada inicial desta conversa em `.dev-loop/conversation-session.json` (ignorado pelo Git). O contador estima rodadas, **não o número de tokens**, tamanho do contexto nem o limite exato do produto.
- Após **5 rodadas** desde a troca, recomenda considerar uma conversa nova; após **8 rodadas**, sugere planejar a migração imediatamente. São apenas avisos no log e em `py -3 -B scripts/expert_ai_rpa.py status`; não alteram o estado `ready`, não apagam `request_id` e não impedem a próxima tarefa.
- Ao atualizar um projeto antigo que nunca registrou a rodada inicial, o HUD/estado indicará histórico anterior **desconhecido**; não será inventado um consumo de tokens nem um número de rodadas passadas.
- Ao visualizar esses avisos, use os passos de migração acima em um momento com checkpoint seguro, preferencialmente `ready`.

## Limitações e segurança

- **Não há detecção automática confiável do limite da conversa.** A v1 depende de você reconhecer o aviso e acionar o botão no HUD.
- **Não é uma migração do histórico completo** da interface do ChatGPT.
- Não há automação para abrir chats, mudar de aba ou enviar o prompt de recuperação.
- O botão normal **Retomar** fica bloqueado durante a migração; use o fluxo acima.
- A recuperação não zera limites de uso nem apaga identificadores.
- Nunca renomeie/remova o marcador ou o arquivo PAUSE apenas para conseguir enviar mensagens.
- Não atualize código do supervisor em execução enquanto houver uma rodada não reconciliada; espere um checkpoint seguro.
