# Comece aqui | Expert AI Manager em outro projeto

**Objetivo:** sair de uma pasta vazia (ou de um código existente) até uma conversa do ChatGPT com planejamento completo, HUD e supervisor prontos. Este é o primeiro arquivo a ler. Não é preciso conhecer o Óliver's Burger.

O Expert AI Manager **não é uma IA nem um plugin do ChatGPT**. É um conjunto de scripts locais que acompanha arquivos do projeto, abre um HUD leve e, quando autorizado, coordena etapas na conversa calibrada. O planejamento e o desenvolvimento acontecem pelo ChatGPT com o acesso do **Remote Desktop Commander**.

## Passo 0. Antes de iniciar

- Windows 10/11, Python 3.11+ com Tkinter, Git e Microsoft Edge.
- Acesso aos arquivos/terminal do PC via Remote Desktop Commander, conectado ao ChatGPT.
- Uma pasta exclusiva e **uma conversa exclusiva** para o novo projeto.
- **Feche ou pare primeiro o supervisor de outro projeto.** No Óliver's, por exemplo, use o botão **Pausar** no HUD e encerre o processo Python do supervisor pelo terminal que o iniciou (Ctrl+C). Pausar sozinho impede envios, mas não encerra o processo. É possível manter outros HUDs abertos; não inicie dois supervisores usando a mesma janela/conversa.
- Verifique se o método de automação empregado é autorizado pelas regras aplicáveis. O programa não é uma integração oficial da OpenAI. Diante de CAPTCHA, limite, alerta ou sessão inesperada, pause e faça revisão manual.

**As três etapas são diferentes:** (1) instalar o script na pasta; (2) planejar com o GPT; (3) iniciar o loop. Não comece pelo passo 3.

## Passo 1. Baixar/abrir o Expert AI Manager

A ferramenta está no repositório privado [Encryptedx00x/expert-ai-manager](https://github.com/Encryptedx00x/expert-ai-manager). Entre no GitHub com sua conta autorizada. Na máquina em que já foi instalado, também existe a pasta:

`$env:USERPROFILE\Desktop\Expert AI Manager` (no PowerShell, abra a pasta **Expert AI Manager** na sua Área de Trabalho)

Em outra máquina, depois de conectar o GitHub CLI à conta que tem acesso, clone:

```powershell
cd "$env:USERPROFILE\Desktop"
gh repo clone Encryptedx00x/expert-ai-manager "Expert AI Manager"
cd "Expert AI Manager"
```

Se já possui a pasta, basta abri-la no PowerShell. Os arquivos essenciais são `install.py`, `docs/`, `templates/` e `scripts/`.

## Passo 2. Conectar plugins e conferir skills

Abra [PLUGINS_E_SKILLS.md](PLUGINS_E_SKILLS.md). Comece pelo **Remote Desktop Commander**. GitHub e Context7 são recomendados conforme o trabalho. Ponytail, Playwright CLI, React Best Practices e Web Design Guidelines são skills/ferramentas que devem ser verificadas e instaladas conforme o projeto. **O instalador não conecta plugins nem instala skills automaticamente.**

Peça ao ChatGPT para inventariar as ferramentas disponíveis e registrar em `AGENTS.md` quais realmente poderá usar. Se algo não estiver conectado, não permita que o modelo finja ter acesso.

## Passo 3. Criar e preparar a pasta do novo projeto

Exemplo: um CRM. No PowerShell, troque o caminho, o nome e o prefixo pelos seus.

```powershell
New-Item -ItemType Directory -Force -Path "C:\Projetos\MeuCRM" | Out-Null
cd "$env:USERPROFILE\Desktop\Expert AI Manager"
py -3 -B install.py --project "C:\Projetos\MeuCRM" --name "Meu CRM" --prefix CRM
```

**Significado:**
- `--project`: pasta existente do projeto, com ou sem código.
- `--name`: nome que aparecerá no prompt.
- `--prefix`: prefixo dos IDs do checklist, por exemplo `CRM-001`, `CRM-002`. Use 2–17 caracteres maiúsculos/números, começando por letra.
- O instalador preserva `AGENTS.md`, `docs/` e `.dev-loop/` existentes, não publica nem inicia nada.
- Os arquivos temporários de estado ficam em `.dev-loop` (ignorado pelo Git).

**Depois de instalar**, há um guia e os prompts também dentro do seu projeto em `docs/expert-ai-manager/`, sem precisar manter o repositório de ferramentas aberto para copiá-los.

## Passo 4. Criar a conversa e mandar o prompt inicial

1. No ChatGPT, abra uma **nova conversa** exclusiva para o CRM. Use um título identificável, como **Dev CRM**.
2. Copie o **Prompt A** de [PROMPTS_PRONTOS.md](PROMPTS_PRONTOS.md), preencha nome, diretório, requisitos e referências; envie **uma vez**.
3. O GPT deverá inventariar o código com Remote Desktop Commander, consultar as skills/plug-ins realmente disponíveis e preencher os arquivos `AGENTS.md`, `docs/TASKS.md`, `docs/STATE.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/TEST_PLAN.md`.
4. Analise o plano: módulos, design, critérios de aceite, riscos, dependências, custos e testes. Use o **Prompt B** para fazer uma revisão crítica. Não marque tarefas como concluídas sem comprovação.
5. **Não deixe o RPA rodando durante o planejamento inicial.** O primeiro planejamento é conduzido normalmente nesta conversa.

O [PROMPT_PLANEJAMENTO.md](PROMPT_PLANEJAMENTO.md) é uma versão detalhada do prompt mestre para casos mais complexos.

## Passo 5. Validar o projeto e o protocolo

No novo projeto:

```powershell
cd "C:\Projetos\MeuCRM"
py -3 -B -m unittest discover -s scripts -p "test_expert_ai*.py" -q
py -3 -B scripts\expert_ai_control.py status
```

Confira:
- `docs/TASKS.md` tem tarefas reais e pendentes com o prefixo `CRM-`.
- `docs/STATE.md` tem o próximo passo real.
- `AGENTS.md` instrui o GPT sobre o `request_id`, `ack`, `heartbeat`, `ready`, `blocked` e `done`.
- `rpa-config.json` está em `.dev-loop/` com `calibrated=false` até a calibração.
- O **Modo Seguro** é ligado por padrão. As pausas são opcionais e também vêm ligadas.

## Passo 6. Calibrar a conversa correta (sem enviar mensagem)

Na conversa **Dev CRM**, abra o ChatGPT pelo Edge e deixe essa janela **em primeiro plano**. Em seguida, no terminal:

```powershell
cd "C:\Projetos\MeuCRM"
py -3 -B scripts\expert_ai_rpa.py calibrate-auto
py -3 -B scripts\expert_ai_rpa.py status
```

A calibração automática verifica o campo acessível de mensagem do ChatGPT e grava a identificação da janela. **Não envia nenhuma mensagem.** Confirme `calibrated: true` e que o título da janela corresponde à conversa certa. Se não identificar, **não force envios**: revise o navegador/aba e a versão do seletor.

**Importante:** o supervisor depende do Edge/ChatGPT compatível, da janela calibrada e de sua interface atual. Para outra conversa/projeto, faça nova calibração; não copie `.dev-loop/` do projeto anterior.

## Passo 7. Abrir o HUD e iniciar o supervisor

Abra o HUD sem servidor/site:

```powershell
pyw -3 -B scripts\expert_ai_hud.py
```

Ele mostra tarefas, commits, testes, condições de envio e inatividade. Pode permanecer no segundo monitor e salvar posição.

**Somente depois** de revisar planejamento, testes, janela calibrada e conformidade, inicie o supervisor em um terminal **dedicado**:

```powershell
py -3 -B -u scripts\expert_ai_rpa.py run
```

Deixe esse terminal em execução. A primeira continuação será enviada apenas quando as condições e limites permitirem. O prompt automático, o `request_id` e o estado são gerenciados pelo script; **não é necessário digitar “continue” a cada etapa**.

## Para economizar contexto e trocar antes do limite

O manager instrui o GPT a implementar **2–4 tarefas relacionadas** quando viável e a mostrar saídas resumidas. Ele mede apenas a quantidade de rodadas da conversa desde uma migração registrada: em 5 rodadas há um aviso preventivo, e em 8 um aviso mais forte. Verifique `py -3 -B scripts/expert_ai_rpa.py status` e consulte o log; isso **não é uma contagem real de tokens** e não pausa a produção sozinho. Para trocar, use os passos abaixo.

## Se a conversa atingir o limite de tamanho

Na aba **Conversa** do HUD, clique **Preparar troca e pausar envios**; o aplicativo entregará um prompt para copiar para uma conversa nova, que deve ter título diferente. Com o novo chat aberto, use o comando `py -3 -B scripts/expert_ai_rpa.py migrate-attach` e finalize somente após o checkpoint anterior ser reconciliado e ficar `ready`. Veja [TROCA_DE_CONVERSA.md](TROCA_DE_CONVERSA.md). O aplicativo ainda não abre o novo chat automaticamente e não consegue identificar com certeza o alerta de limite.

## Passo 8. Acompanhar, pausar e voltar

No projeto:

```powershell
py -3 -B scripts\expert_ai_control.py status
py -3 -B scripts\expert_ai_control.py pause
py -3 -B scripts\expert_ai_control.py resume
py -3 -B scripts\expert_ai_hud.py --snapshot
```

- **Pausar** desabilita novas solicitações, mas não mata o supervisor.
- **Retomar** só remove a pausa; não ignora limites e não altera um `blocked` sem revisão.
- **Ctrl+C** no terminal dedicado encerra o supervisor. Fechar o HUD não encerra o supervisor.
- O trabalho feito aparece em `docs/TASKS.md`, `docs/STATE.md`, Git e no HUD.
- Se houver erro, use o **Prompt C** de [PROMPTS_PRONTOS.md](PROMPTS_PRONTOS.md) para diagnóstico. Não apague manualmente o request_id.

## Problemas frequentes

| Sintoma | O que verificar |
|---|---|
| `calibration required` | Abra a conversa correta no Edge e rode `calibrate-auto` |
| Nenhuma tarefa aparece | Prefixo `CRM-` em `TASKS.md`; `task_prefix` da configuração |
| HUD mostra pausa | Confira PAUSE e o botão Retomar, depois o estado JSON |
| Conta 90 segundos e reinicia | É atividade do usuário; não é um ciclo de mensagens |
| `pending_send` | Pode haver rascunho; não envie manualmente o mesmo `request_id` |
| `blocked` | Consulte o motivo, logs e o checkpoint; não ignore o bloqueio |
| Dois projetos na mesma janela | Pare o supervisor antigo e calibre a conversa nova |
| Falha ao acessar arquivo | Confirme Remote Desktop Commander conectado ao PC certo |

**Para repetir depois:** abra este arquivo, execute os passos 1–7 com novo caminho/prefixo e use os prompts A e B. O projeto anterior fica preservado.
