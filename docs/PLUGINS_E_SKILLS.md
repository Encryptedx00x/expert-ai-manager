# Plugins, skills e ferramentas | O que conectar e como validar

Este guia acompanha o **Expert AI Manager** em novos projetos. A ferramenta é um script Python local, **não é um plugin do ChatGPT**. O ChatGPT precisa de permissão e ferramentas para trabalhar no seu PC; as skills oferecem orientações específicas de desenvolvimento.

## 1. Plugins: conectados na conta do ChatGPT

No ChatGPT, abra a barra lateral ou **Configurações → Plugins**, procure a ferramenta pelo nome, conecte a conta/dispositivo e confira as permissões. Os nomes de menus podem variar por versão. Não compartilhe senhas com o GPT; conclua a autorização pela própria interface oficial.

| Plugin | Uso no desenvolvimento | Prioridade | Como verificar |
|---|---|---|---|
| **Remote Desktop Commander** | Ler/criar/editar arquivos, Git local, terminal Windows, testes | Essencial para o fluxo com arquivos locais | Peça ao ChatGPT: “Liste meus dispositivos conectados no Remote Desktop Commander; mostre apenas nome e status.” Depois peça para ler um `README.md` conhecido |
| **GitHub** | Repositórios privados, commits, issues e PRs conforme permissões | Recomendado | Peça: “Mostre os repositórios aos quais tenho acesso e confirme se o repositório deste projeto é privado.” |
| **Context7** | Documentação atual de bibliotecas e APIs, evitando exemplos antigos | Recomendado em programação | Peça para consultar documentação específica de uma biblioteca com versão informada |
| **Google Drive / Docs / Sheets** | Requisitos, relatórios, planilhas e arquivos compartilhados | Opcional | Teste listar ou abrir um arquivo autorizado |

**Conexão mínima recomendada:** Remote Desktop Commander + GitHub. Adicione Context7 quando precisar pesquisar APIs e documentação de bibliotecas.

**Conferência indispensável:** conectar um plugin não significa que o ChatGPT tem acesso a tudo. Acesso ao terminal, arquivos, organizações do GitHub e permissões de escrita podem ser diferentes. O assistente deve declarar exatamente o que consegue acessar. Se uma ferramenta não estiver disponível, não inventar acesso nem usar dados de exemplo como se fossem reais.

### Configuração do Remote Desktop Commander

1. Instale/abra o componente do Remote Desktop Commander no computador que contém o projeto, seguindo o fluxo oficial apresentado pelo próprio plugin.
2. No ChatGPT, conecte o plugin e autorize esse computador.
3. Confirme o dispositivo **online** pela conversa de planejamento.
4. Teste uma operação somente de leitura dentro do diretório do projeto.
5. Restrinja o escopo de escrita ao projeto. Evite alterar servidores e aplicações que não fazem parte dele.
6. Registre no `AGENTS.md` o caminho do projeto e as regras de segurança do ambiente.

### GitHub

1. Conecte a conta no plugin do GitHub ou autentique o GitHub CLI no PC, conforme a forma escolhida.
2. Para uso novo, prefira um repositório **privado**; não dê acesso a organizações desnecessárias.
3. Defina o remoto correto, confira `git status` antes de commits e inclua `.dev-loop/`, `.env`, dumps, logs e segredos no `.gitignore`.
4. **Publicação e deploy são decisões separadas da instalação.** O Expert AI Manager não publica projetos automaticamente.

### Context7

1. Conecte o plugin no ChatGPT.
2. Informe biblioteca, versão e dúvida concreta.
3. Peça referências específicas e registre decisões que dependem de versão em `docs/ARCHITECTURE.md`.
4. Context7 não é obrigatório para um projeto que não depende de APIs externas ou bibliotecas atuais.

## 2. Skills: instruções instaladas no repositório ou no ambiente

Skills **não são a mesma coisa** que plugins. Uma skill costuma ser um `SKILL.md` com orientações e regras para uma atividade. O Expert AI Manager **não baixa nem instala automaticamente** skills de terceiros.

| Skill/ferramenta | Quando usar | Como confirmar |
|---|---|---|
| **Ponytail** | Código enxuto, manutenção e revisão de componentes | Verificar arquivo real, por exemplo `.agents/skills/ponytail/SKILL.md`, ou caminho informado pela instalação |
| **Playwright CLI** | Abrir o app, navegar, simular fluxos e validar telas | Confirmar a CLI e executar um teste em ambiente DEV/QA autorizado |
| **React Best Practices** | Projeto React/Next.js, revisão de renderização e arquitetura | Verificar `SKILL.md` correspondente no ambiente |
| **Web Design Guidelines** | Acessibilidade, design, responsividade e consistência visual | Verificar `SKILL.md` correspondente e as referências de design |
| **Outras skills de stack** | Docker, segurança, testes, Python, banco etc. quando apropriado | Conferir caminho, origem, versão e pertinência |
| **ai-memory** (opcional) | Contexto entre etapas quando um servidor/bridge próprio já existe | Testar a integração sem interromper o trabalho se estiver indisponível |

Se a skill não estiver instalada, solicite ao ChatGPT que descubra a **origem oficial** e os procedimentos atuais de instalação antes de recomendar comandos. Evite copiar diretórios de skills de projetos diferentes sem verificar licença, versão, dependências e compatibilidade.

**Para inspecionar as skills locais** no PowerShell do projeto, por exemplo:

```powershell
Get-ChildItem ".agents\skills" -Filter SKILL.md -Recurse -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty FullName
```

Um diretório vazio não prova que a skill esteja ausente do ChatGPT: algumas skills podem estar instaladas em outro local ou serem disponibilizadas pela ferramenta conectada. Peça ao modelo para conferir as skills realmente acessíveis.

## 3. Prompt para auditar plugins e skills (copiar na conversa)

```text
Antes de desenvolver este projeto, audite as ferramentas que estão realmente disponíveis.

1. Confirme se Remote Desktop Commander está conectado e identifique o computador autorizado.
2. Confira se GitHub e Context7 estão conectados. Use cada um apenas se houver necessidade.
3. Leia AGENTS.md e procure os SKILL.md disponíveis no repositório ou nas skills instaladas.
4. Para um projeto web React, considere Ponytail, Playwright CLI, React Best Practices e Web Design Guidelines; para outras stacks, proponha apenas skills relevantes.
5. Faça um quadro curto com: ferramenta/skill, status (confirmada, não disponível ou não necessária), finalidade, caminho/origem e teste real de verificação.
6. Não instale plugins ou amplie permissões sem minha ação explícita. Não invente ferramentas, versões ou resultados de testes.
7. Atualize a seção de ferramentas no AGENTS.md apenas depois de verificar o que está disponível.
```

## 4. Ordem de uso recomendada no projeto

| Momento | Ferramentas |
|---|---|
| Descoberta de requisitos | Remote Desktop Commander; GitHub se existir repositório |
| Planejamento/arquitetura | GitHub, Context7 e skills específicas da stack |
| Implementação | Remote Desktop Commander, compilador/test runner, Git |
| UI/UX | Ponytail, React Best Practices, Web Design Guidelines |
| Verificação visual/E2E | Playwright CLI com aplicativo realmente em execução |
| Documentação/relatórios | Markdown no Git; Drive/Docs opcional |
| Continuação por etapas | Expert AI Manager com `chat-state.json` e `TASKS.md` |

## 5. Ambientes compartilhados e segurança

- Antes de iniciar um novo projeto, **pause e encerre o supervisor do anterior**. Dois supervisores podem interferir no foco do navegador, mesmo que tenham arquivos diferentes.
- Não use PostgreSQL, Redis, Docker ou serviços de outro projeto só porque já estão funcionando.
- Não copie `.dev-loop/` entre projetos: o checkpoint e a calibração pertencem à conversa do projeto original.
- Não confunda “skill instalada” com “verificação executada”. Exija comandos e resultados concretos nos checkpoints.
- Em caso de alerta de uso, CAPTCHA ou limitação da plataforma, suspenda a automação e verifique as regras. Pausas e limites não equivalem a permissão.
