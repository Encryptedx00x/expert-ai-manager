# Fallback MCP gratuito para Windows

O Remote Desktop Commander atual usa um relay remoto terceirizado, com franquia propria. O Desktop Commander MCP local e open-source e nao depende daquela franquia, mas precisa de um cliente MCP **local**. Ele nao substitui automaticamente o plugin remoto dentro da mesma conversa do ChatGPT.

## Opcao pratica: Gemini CLI + Desktop Commander local

Esta opcao e gratuita dentro da quota do Gemini CLI, usa a sua conta Google e permite ler/escrever arquivos e executar comandos diretamente no Windows. O cliente e outro assistente, separado desta conversa. A documentacao do Gemini CLI indica ate 1.000 chamadas de modelo/dia na modalidade individual gratuita (com limites adicionais por minuto/modelo e sujeito a alteracoes).

Links oficiais:
- https://github.com/wonderwhy-er/DesktopCommanderMCP
- https://github.com/google-gemini/gemini-cli
- https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md
- https://github.com/google-gemini/gemini-cli/blob/main/docs/resources/quota-and-pricing.md

Comandos sugeridos no PowerShell (precisa de Node 20+):

    node --version
    npm --version
    npm install -g @google/gemini-cli
    gemini mcp add --scope user desktop-commander npx -y @wonderwhy-er/desktop-commander@latest
    gemini mcp list
    gemini

A autenticacao Google acontece dentro do CLI. Nao configure pagamento nem API paga para esse fluxo. Teste a conexao primeiro em uma pasta de testes vazia.

## Nao ter dois desenvolvedores escrevendo no Óliver's

1. Se o EAM principal estiver running, requested ou pending_send, aguarde a conclusao/recupere o checkpoint antes de usar o fallback para escrever codigo.
2. Pause o supervisor antigo e confira os IDs em .dev-loop/chat-state.json, o estado do Git e os testes.
3. Use o fallback como unico desenvolvedor ativo, seguindo AGENTS.md, docs/EXECUTION_PLAN.md, TASKS.md e STATE.md.
4. Nao iniciar outra instancia do supervisor nem compartilhar Playwright/PostgreSQL/banco e portas em paralelo.
5. Para retornar ao ChatGPT + Remote Desktop Commander, reconcilie o checkpoint e preserve os mesmos arquivos; nao invente novo request_id.

O GitHub conectado ao ChatGPT pode ajudar a revisar e preparar codigo versionado, mas nao executa seus testes locais nem acessa automaticamente arquivos nao commitados. Um servidor MCP local exposto diretamente na internet, sem autenticacao, e inseguro. Nao abra o PowerShell remoto ao publico para tentar substituir a franquia.

Nao existe promessa de uso infinito de modelos em nuvem. Para continuar usando este MESMO ChatGPT com escrita no PC, voce precisa de um plugin/conector remoto compativel; a opcao local via Gemini CLI nao oferece isso.
