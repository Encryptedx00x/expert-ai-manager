# Expert AI Manager

Ferramenta local de **supervisão de desenvolvimento por etapas com ChatGPT**, Python e um HUD nativo do Windows.

**Status:** protótipo funcional, testado no Windows. Repositório privado por padrão. Não é uma integração oficial da OpenAI e **não tem recursos de ocultação ou contorno de limites**.

## Visão geral
- Controla o checkpoint em `.dev-loop/chat-state.json`: `ready → pending_send → requested → running → ready`.
- Evita novos envios enquanto o GPT gera uma resposta e evita duplicar um request_id.
- Acompanha `AGENTS.md`, `docs/TASKS.md`, `docs/STATE.md`.
- **Modo Seguro** ativo por padrão: até 4 novas solicitações por hora, 24 em 24 horas, no mínimo 12 minutos entre tentativas, 90 segundos de inatividade do usuário.
- **Pausas de descanso** opcionais: curtas e ocasionais longas, com duração dentro de intervalos configuráveis.
- Inspeções periódicas entre 10 e 20 minutos, sem atrasar arbitrariamente um checkpoint pronto (os limites de uso continuam valendo).
- **HUD Tkinter** leve, sem servidor web: próximo check, limites e pausas, estado, progresso, tarefas, último commit e testes.
- Reutilizável em qualquer projeto que tenha um diretório de trabalho e uma conversa própria.

## Início rápido (Windows)
Pré-requisitos: Python 3.11+, Windows, Edge e acesso autorizado ao Remote Desktop Commander no ChatGPT.

```powershell
# No diretório do Expert AI Manager
py -3 -B install.py --project "C:\Projetos\MeuProjeto" --name "Meu Projeto" --prefix APP

# Depois de planejar e revisar AGENTS/TASKS/STATE, no projeto instalado
cd "C:\Projetos\MeuProjeto"
py -3 -B scripts\expert_ai_rpa.py calibrate-auto
py -3 -B scripts\expert_ai_rpa.py status
py -3 -B -m unittest discover -s scripts -p "test_expert_ai*.py" -q
pyw -3 -B scripts\expert_ai_hud.py
py -3 -B -u scripts\expert_ai_rpa.py run
```

**Não inicie o supervisor antes de revisar a janela calibrada e o planejamento.** O HUD é independente e pode ser fechado sem encerrar o supervisor.

## Documentos
- [Guia completo](docs/GUIA_COMPLETO.md): instalação, configuração, limites, HUD, recuperação, recursos e privacidade.
- [Prompt mestre](docs/PROMPT_PLANEJAMENTO.md): criação de roadmap, arquitetura, backlog, plano de testes e regras do agente.
- [Templates](templates): arquivos iniciais AGENTS, TASKS, STATE e ARCHITECTURE para novos projetos.

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
