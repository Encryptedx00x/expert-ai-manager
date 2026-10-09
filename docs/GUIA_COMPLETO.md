# Expert AI Manager
## Manual completo de instalação, planejamento e operação

**Versão:** 0.1 (Windows / Python 3.11+). **Natureza:** ferramenta de supervisão de desenvolvimento com ChatGPT já aberto no navegador. O código é genérico; o Óliver's Burger foi apenas o projeto-piloto.

**Primeira instalação em outro projeto?** Comece por **[COMECE_AQUI.md](COMECE_AQUI.md)**. Esse tutorial conduz da instalação até a primeira execução. Os passos para conectar ferramentas estão em **[PLUGINS_E_SKILLS.md](PLUGINS_E_SKILLS.md)**, e as mensagens de planejamento/revisão estão em **[PROMPTS_PRONTOS.md](PROMPTS_PRONTOS.md)**.

### 1. O que foi construído
Uma aplicação local com cinco partes:
- **Supervisor Python**: consulta checkpoint JSON e tarefas Markdown, monitora a janela calibrada, evita envios duplicados, mantém request_id/round e inicia a próxima etapa somente quando houver condição segura.
- **Modo Seguro**: limites configuráveis de volume e cadência, 90 segundos de inatividade por padrão, interrupção manual e retenção ao detectar bloqueios ou riscos de duplicidade. Esses limites são para responsabilidade e conforto, não para disfarçar o script.
- **Descansos opcionais**: pausa curta a cada 3 solicitações (duração entre 3 e 7 min por padrão) e pausa longa a cada 9 (15 a 30 min). A duração é escolhida dentro do intervalo configurado. Intervalos periódicos de *verificação de saúde* são sorteados separadamente entre 10 e 20 minutos. A retomada via checkpoint não precisa esperar a verificação periódica, mas respeita os limites e a inatividade.
- **HUD nativo**: janela Tkinter, sem servidor web, com três abas: Visão geral, Tarefas e Configuração. Pode ficar no outro monitor e acima das demais janelas, lembrando a última posição. Atualiza localmente sem consumir requisições de IA.
- **Pacote reutilizável**: scripts, templates AGENTS/TASKS/STATE/ARCHITECTURE, exemplos de comandos, testes e prompt mestre.

### 2. Pré-requisitos
1. Windows 10/11, Python 3.11 ou superior (com Tkinter e PowerShell), Git e navegador Edge. O projeto a desenvolver pode usar outras tecnologias, mas a automação atual foi calibrada para uma janela do ChatGPT no Edge.
2. Uma pasta própria para o projeto e uma conversa dedicada ao projeto no ChatGPT.
3. Plugins/skills que o projeto realmente precisar. O instalador NÃO instala plugins, não obtém permissões e não cria contas sozinho.
4. Verificar os Termos de Uso e limites aplicáveis. O uso automatizado da interface do ChatGPT pode estar sujeito a restrições. Se houver aviso de uso indevido, CAPTCHA, rate limit ou outra proteção, interrompa a automação; não tente contornar. Use uma integração oficialmente suportada quando aplicável.

### 3. Plugins e como configurar
**Necessários para repetir o fluxo no ChatGPT conectado ao computador:**
- **Remote Desktop Commander**: conecte o computador correto pelo diretório de plugins; autorize o acesso ao sistema de arquivos e ao terminal somente onde fizer sentido. Confira o nome do dispositivo e o caminho antes de executar mudanças. Sem ele, o GPT não poderá trabalhar diretamente no seu projeto local.
- **GitHub**: conecte uma conta com acesso apenas aos repositórios desejados; mantenha o repositório privado no início; confira o remoto e nunca adicione segredos nem `.dev-loop` ao Git.
- **Context7** (recomendado para programação): use quando precisar de documentação atual de Next.js, Prisma, Better Auth, React e outras bibliotecas. Adicione pelo diretório de plugins e confirme autorização.
**Opcionais conforme o escopo:** Google Drive/Docs/Sheets para planejamento compartilhado; ferramentas de comunicação ou banco somente com a permissão necessária. Não integre aplicativos só porque estão disponíveis.

### 4. Skills e ferramentas locais
Estas foram úteis no projeto-piloto, mas instale somente as que forem aplicáveis e verifique a versão:
- **Ponytail**: revisão de componentes, acessibilidade e consistência visual, caso disponível.
- **Playwright CLI**: testes reais de navegação e screenshots de desktop/mobile, evitando alegar E2E sem abrir o navegador autenticado.
- **React Best Practices**: revisão de React/Next.js, componentes, renderização e estados.
- **Web Design Guidelines**: auditoria de UI/UX, responsividade, semântica e acessibilidade.
- **RTK (CLI)**: opcional, apenas se fizer parte do fluxo existente.
- **ai-memory**: opcional, memória local; Git e docs continuam a ser a fonte principal. Não copie banco de memória, histórico ou credenciais entre projetos sem necessidade.
- **Git, Node.js/pnpm, Docker, PostgreSQL**: somente quando o stack exigir. Use servidores e portas exclusivos para cada projeto.

Para instalar skills, consulte a documentação oficial da origem e registre em `AGENTS.md` seu caminho e versão. Confirme a presença das skills no projeto antes de afirmar que foram usadas. Para plugins, faça a conexão pelo diretório do ChatGPT; o instalador Python não tem permissão para fazê-la.

### 5. Instalar no próximo projeto
Abra PowerShell na pasta `Expert AI Manager` da Área de Trabalho:

```powershell
cd "$env:USERPROFILE\Desktop\Expert AI Manager"
py -3 -B install.py --project "C:\Projetos\MeuProjeto" --name "Meu Projeto" --prefix APP
```

A pasta `C:\Projetos\MeuProjeto` precisa existir (use `New-Item -ItemType Directory -Force -Path "C:\Projetos\MeuProjeto"` antes, se necessário). O instalador copia scripts para `scripts\`, cria templates só quando os arquivos não existem, adiciona `.dev-loop/` ao .gitignore sem apagar entradas e cria `.dev-loop/rpa-config.json` com o **Modo Seguro habilitado**. Além disso, copia o tutorial, a lista de plugins/skills e os prompts para `docs/expert-ai-manager/` no próprio projeto. Com `--update`, scripts existentes recebem cópia de segurança. Nunca sobrescreve a documentação ou o estado local. Ele não acessa o GitHub nem conecta a conta.

### 6. Faça o planejamento ANTES da automação
1. Descreva o produto, usuários, limites, tecnologias, integrações, custos, referências visuais e estado atual.
2. Na conversa do ChatGPT dedicada ao projeto, cole o **Prompt A** de `docs/expert-ai-manager/PROMPTS_PRONTOS.md` (ou o prompt mestre `docs/expert-ai-manager/PROMPT_PLANEJAMENTO.md` se for um projeto complexo), substituindo os campos obrigatórios.
3. Peça ao GPT que leia o repositório, inventarie riscos e crie `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/TASKS.md`, `docs/STATE.md`, `docs/ROADMAP.md` e `docs/TEST_PLAN.md`.
4. Use o **Prompt B** para revisar prioridades, critérios de aceite, dependências e o que realmente poderá ser testado. Não deixe o GPT marcar tarefas como concluídas sem evidência.
5. Faça o commit do planejamento e só então autorize o início das etapas. O HUD lê automaticamente as tarefas do arquivo, distinguindo [x], [~], [ ], [!].

### 7. Calibração e início do supervisor
No projeto instalado:
```powershell
cd "C:\Projetos\MeuProjeto"
py -3 -B scripts\expert_ai_rpa.py calibrate-auto
py -3 -B scripts\expert_ai_rpa.py status
py -3 -B -m unittest discover -s scripts -p "test_expert_ai*.py" -q
pyw -3 -B scripts\expert_ai_hud.py
```

Abra primeiro a conversa correta no Edge. Inspecione se a calibração identifica exatamente uma janela. Se o `status` indicar `calibrated=false`, não inicie o supervisor. Inicie-o em um terminal dedicado:
```powershell
py -3 -B -u scripts\expert_ai_rpa.py run
```

O HUD é um **monitor independente**: fechá-lo não para o supervisor. O supervisor deve permanecer em execução no terminal ou sessão dedicada; fechá-lo interrompe o monitoramento. Nunca rode duas instâncias ao mesmo tempo. Use o controle de pausa antes de editar a configuração ou trocar de projeto.

### 8. HUD, opções, pausas e troca de conversa

Quando uma conversa atingir seu limite de tamanho, use a nova aba **Conversa** do HUD. O programa não consegue detectar com segurança a mensagem de limite, então a troca é iniciada por você: **Preparar troca** pausa novas solicitações, gera um prompt para copiar e preserva o checkpoint. Depois de abrir um novo chat com título diferente, execute `py -3 -B scripts/expert_ai_rpa.py migrate-attach` (há 6 segundos para voltar ao Edge), reconciliando o trabalho anterior antes de clicar **Finalizar e retomar**. Os envios permanecem suspensos até o checkpoint estar `ready`, a nova conversa estar calibrada e os limites permitirem. Veja [TROCA_DE_CONVERSA.md](TROCA_DE_CONVERSA.md) para o procedimento completo.

Na aba **Visão geral**: estado, decisão, rodada, acompanhamento, próxima solicitação elegível, uso recente, último commit, última tarefa, testes e resumo. Ao aguardar inatividade, aparece **“Aguardando você terminar”**, com uma barra que avança até os 90 segundos configurados e reinicia ao detectar atividade de mouse ou teclado. O ciclo interno de checagem a cada 10 segundos não aparece como uma contagem regressiva repetitiva; a próxima verificação periódica continua visível quando for relevante. Na aba **Tarefas**: concluídas, parciais e pendentes extraídas de `docs/TASKS.md`. Na aba **Configuração**: Modo Seguro, descansos e valores de limites.
- Modo Seguro: habilitado por padrão. Intervalo mínimo entre solicitações: 12 min; teto 5 por hora e 120 em 24h. Pode ser alterado. Mesmo desativado, o supervisor continua respeitando foco, estado, inatividade e salvaguardas contra duplicidade.
- Descansos: habilitados por padrão; são opcionais e podem ser desativados mantendo os outros limites.
- Verificações periódicas: entre 10 e 20 minutos, independentes dos limites de envio.
- Estado `pending_send`: texto foi preparado mas o clique não foi confirmado; o supervisor tenta apenas o botão quando seguro, sem redigitar ou criar outro request_id.
- `requested`: mensagem já pode ter sido enviada; não tente reenviar.
- `running`: GPT desenvolvendo uma etapa; o monitor não inicia outra.
- `ready`: rodada liberada; o supervisor aguarda limites, foco e inatividade.
- `blocked`/PAUSE: intervenção necessária. Confira os logs antes de retomar.

Comandos manuais no diretório do projeto:
```powershell
py -3 -B scripts\expert_ai_control.py status
py -3 -B scripts\expert_ai_control.py pause
py -3 -B scripts\expert_ai_control.py resume
py -3 -B scripts\expert_ai_control.py safe-on
py -3 -B scripts\expert_ai_control.py safe-off
py -3 -B scripts\expert_ai_control.py breaks-on
py -3 -B scripts\expert_ai_control.py breaks-off
py -3 -B scripts\expert_ai_control.py set max_requests_per_hour 3
py -3 -B scripts\expert_ai_control.py set long_break_max_minutes 45
py -3 -B scripts\expert_ai_hud.py --snapshot
```

O comando `limit-hold` pausa e cria um marcador de bloqueio. `limit-clear` limpa somente esse alerta, mantendo a pausa até revisão e retomada manual. Nunca use esse mecanismo para contornar limites.

### 9. Recuperação de falhas
**Popup:** confirme no HUD que `pending_send` mantém o request_id, verifique o campo sem mexer no texto e aguarde o retorno do foco. Se estiver ambíguo, pause. Não gere ID novo.
**Mensagem duplicada ou estado inesperado:** pause o supervisor, leia `.dev-loop/chat-state.json`, `.dev-loop/rpa.log` e o histórico da conversa. Corrija somente com um request_id confirmado. Evite apagar o checkpoint.
**Sessão expirada, CAPTCHA, limite ou alerta:** pare, revise manualmente. Não tente automatizar sua solução.
**GPT não responde ou a tarefa falha:** use `blocked`, registre motivo no `docs/STATE.md` e retome depois de tratar a causa.
**Servidor, banco ou Docker inacessível:** não use a infraestrutura de outro projeto. Marque testes de integração como pendentes e priorize verificações independentes.

### 10. Arquivos e privacidade
`scripts/expert_ai_rpa.py`: supervisor e Windows UI Automation.
`scripts/expert_ai_state.py`: transições atômicas.
`scripts/expert_ai_composer.ps1`: identificação do campo e botão Enviar.
`scripts/expert_ai_safety.py`: cálculo de limites e descansos.
`scripts/expert_ai_control.py`: comandos de controle e validação.
`scripts/expert_ai_hud.py` + `expert_ai_hud_data.py`: painel nativo.
`scripts/test_expert_ai*.py`: testes.
`docs/` e `templates/`: documentação reutilizável.

Arquivos de `.dev-loop/` incluem títulos da janela, request_ids, logs, estado, contadores de uso e preferências do HUD. **Nunca envie essa pasta ao GitHub**. Evite incluir caminhos locais, e-mails, credenciais, bancos, screenshots pessoais ou tokens nos commits.

### 11. Checklist ao concluir cada etapa
Confirme: request_id correto; docs atualizados; testes executados com resultados reais; diff revisado; segredos ausentes; commit criado quando seguro; metadados `last_task`, `last_commit`, `last_quality_check` registrados no JSON; state final `ready` ou `blocked`. O HUD consome esses dados diretamente, sem chamadas extras ao ChatGPT.

### 12. Limitações
- O supervisor depende da UI atual do ChatGPT e da janela calibrada; mudanças no Edge ou no ChatGPT podem quebrar o seletor.
- Uso via automação de interface pode estar sujeito às políticas/limites da plataforma. Nem pausas nem limites garantem permissão ou ausência de alertas.
- O HUD não desenvolve código: ele mostra arquivos, estados e testes que o GPT efetivamente registrou.
- A ferramenta não inicia um servidor HTTP nem precisa estar conectada a um site para exibir status.
- O primeiro uso com um novo projeto exige revisão humana de arquitetura, testes, permissões e calibração.

### 13. Registro do projeto-piloto
Foi validado no Óliver's Burger, com checkpoint JSON, testes em Python, regras de segurança e HUD de progresso. A API, banco e navegador autenticado do Óliver's não são pré-requisitos do Expert AI Manager; testes próprios desses serviços continuam sendo responsabilidade do projeto. A distribuição privada contém apenas os scripts genéricos e os manuais, não o código do restaurante.
