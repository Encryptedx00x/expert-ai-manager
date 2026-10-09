# Expert AI Manager

Ferramenta local de **supervisão de desenvolvimento por etapas com ChatGPT**, Python e um HUD nativo do Windows.

**Status:** protótipo funcional, testado no Windows. Repositório privado por padrão. Não é uma integração oficial da OpenAI e **não tem recursos de ocultação ou contorno de limites**.

## Começar outro projeto (leia primeiro)

**[Abrir o tutorial “Do zero à primeira execução”](docs/COMECE_AQUI.md)**. Ele explica tudo, incluindo como conectar plugins, conferir skills, planejar com prompts prontos, instalar, calibrar e iniciar o supervisor.

1. **[Plugins e skills](docs/PLUGINS_E_SKILLS.md):** o que conectar e como verificar acesso real.
2. **[Prompts prontos](docs/PROMPTS_PRONTOS.md):** copie o **Prompt A** para planejar e o **Prompt B** para revisar antes de iniciar o loop.
3. **[Prompt mestre detalhado](docs/PROMPT_PLANEJAMENTO.md):** alternativa mais extensa para projetos complexos.
4. **[Manual completo](docs/GUIA_COMPLETO.md):** operação, HUD, limites, recuperação e restrições.

O projeto Óliver's Burger foi apenas o piloto. O script pode ser instalado em qualquer pasta de projeto **sem copiar seu checkpoint ou seus dados**.

## Visão geral
- Controla o checkpoint em `.dev-loop/chat-state.json`: `ready → pending_send → requested → running → ready`.
- Evita novos envios enquanto o GPT gera uma resposta e evita duplicar um request_id.
- Acompanha `AGENTS.md`, `docs/TASKS.md`, `docs/STATE.md`.
- **Modo Seguro** ativo por padrão: até 5 novas solicitações por hora, 120 em 24 horas, no mínimo 12 minutos entre tentativas, 90 segundos de inatividade do usuário.
- **Pausas de descanso** opcionais: curtas e ocasionais longas, com duração dentro de intervalos configuráveis.
- Inspeções periódicas entre 10 e 20 minutos, sem atrasar arbitrariamente um checkpoint pronto (os limites de uso continuam valendo).
- **HUD Tkinter** leve, sem servidor web: estados e progresso em linguagem clara, contador visual de inatividade até 90 segundos (reinicia com mouse/teclado), pausas, tarefas, commit e testes. As checagens técnicas de 10 segundos ficam ocultas no painel.
- Reutilizável em qualquer projeto que tenha um diretório de trabalho e uma conversa própria.

## Instalação rápida (Windows)

Pré-requisitos: Python 3.11+, Windows, Edge, Git e Remote Desktop Commander conectado ao ChatGPT. Para usar outro projeto, primeiro **pare o supervisor do projeto anterior**. Se preferir não digitar comandos para instalar, dê dois cliques em **`Instalar em outro projeto.cmd`** nesta pasta e informe caminho, nome e prefixo.

```powershell
New-Item -ItemType Directory -Force -Path "C:\Projetos\MeuProjeto" | Out-Null
cd "$env:USERPROFILE\Desktop\Expert AI Manager"
py -3 -B install.py --project "C:\Projetos\MeuProjeto" --name "Meu Projeto" --prefix APP
```

Agora **abra no projeto** `docs/expert-ai-manager/COMECE_AQUI.md` e copie o **Prompt A** de `docs/expert-ai-manager/PROMPTS_PRONTOS.md` para uma conversa nova. Após o planejamento e a revisão, abra essa conversa no Edge em primeiro plano:

```powershell
cd "C:\Projetos\MeuProjeto"
py -3 -B -m unittest discover -s scripts -p "test_expert_ai*.py" -q
py -3 -B scripts\expert_ai_rpa.py calibrate-auto
py -3 -B scripts\expert_ai_rpa.py status
pyw -3 -B scripts\expert_ai_hud.py
# Somente após conferir a conversa, o plano e os limites:
py -3 -B -u scripts\expert_ai_rpa.py run
```

**Calibrar não envia mensagem.** O HUD é independente e pode ser fechado sem encerrar o supervisor. O supervisor precisa permanecer rodando em um terminal dedicado. Não inicie duas instâncias para a mesma conversa.

## Documentos
- [Comece aqui](docs/COMECE_AQUI.md): caminho exato para ativar em um projeto diferente.
- [Plugins e skills](docs/PLUGINS_E_SKILLS.md): conexão, verificação e uso por fase.
- [Prompts prontos](docs/PROMPTS_PRONTOS.md): mensagens A (planejar), B (revisar), C (diagnosticar), D (status), E (ferramentas).
- [Prompt mestre](docs/PROMPT_PLANEJAMENTO.md): planejamento aprofundado.
- [Guia completo](docs/GUIA_COMPLETO.md): configurações e solução de problemas.
- [Templates](templates): AGENTS, TASKS, STATE e ARCHITECTURE para novos projetos.

## Controles
```powershell
py -3 -B scripts\expert_ai_control.py status
py -3 -B scripts\expert_ai_control.py pause
py -3 -B scripts\expert_ai_control.py resume
py -3 -B scripts\expert_ai_control.py safe-on
py -3 -B scripts\expert_ai_control.py safe-off
py -3 -B scripts\expert_ai_control.py breaks-on
py -3 -B scripts\expert_ai_control.py breaks-off
py -3 -B scripts\expert_ai_control.py set max_requests_per_hour 3
```

## Plugins e skills
O fluxo que motivou a ferramenta usa Remote Desktop Commander, GitHub e Context7. Para projetos web, considere Ponytail, Playwright CLI, React Best Practices e Web Design Guidelines. Essas ferramentas devem ser conectadas/instaladas separadamente, conforme suas permissões e documentação. Veja o passo a passo no [guia](docs/GUIA_COMPLETO.md).

## Segurança e privacidade
A ferramenta não acessa APIs secretas nem obtém credenciais. Nunca envie `.dev-loop`, `.env`, dados pessoais, banco, logs, histórico da conversa ou chaves ao GitHub. O instalador preserva os arquivos preexistentes; o comando `--update` guarda backup dos scripts substituídos.

O acesso e automação da interface do ChatGPT podem estar sujeitos às políticas da plataforma. O Modo Seguro **não garante permissão nem evita sinalizações**; ele existe para reduzir uso excessivo e oferecer um ritmo de trabalho confortável. Diante de rate limit, CAPTCHA ou alerta, suspenda a execução e faça uma revisão manual.

## Licença e manutenção
Código distribuído para uso privado do proprietário. Não há garantia de estabilidade frente a alterações na interface do ChatGPT. As correções precisam ser testadas antes de uso contínuo.
