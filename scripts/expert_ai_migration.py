"""Explicit, local handoff between ChatGPT conversations (no browser automation).

A migration pause blocks NEW sends while a user manually opens another chat.
It does not acknowledge, reset, or complete an in-flight request.
"""
from __future__ import annotations

from datetime import datetime, timezone

from expert_ai_control import ROOT, RUNTIME, CONFIG, STATE, PAUSE, LIMIT, load, atomic_save
from expert_ai_context import start_session

MIGRATION = RUNTIME / "chat-migration.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def migration_status() -> dict:
    return load(MIGRATION)


def prepare_migration() -> dict:
    if MIGRATION.exists():
        raise RuntimeError("Uma troca de conversa já está pendente. Abra as instruções.")
    state = load(STATE)
    config = load(CONFIG)
    if state.get("status") == "pending_send":
        raise RuntimeError("Existe um rascunho pendente. Verifique o envio antes de trocar de conversa.")
    if state.get("status") not in ("ready", "running", "requested", "blocked"):
        raise RuntimeError("Não é seguro iniciar a troca com este estado.")
    was_paused = PAUSE.exists()
    # Pause first: a supervisor cannot create another request after preparation.
    PAUSE.touch()
    current = load(STATE)
    if (current.get("status"), current.get("request_id"), current.get("round")) != (
        state.get("status"), state.get("request_id"), state.get("round")
    ):
        raise RuntimeError("Checkpoint mudou durante a preparação. A pausa permanece por segurança.")
    handoff = {
        "schema_version": 1,
        "phase": "awaiting_new_chat",
        "created_at": utc_now(),
        "previous_window_title": config.get("window_title", ""),
        "previously_paused": was_paused,
        "request_id": state.get("request_id", ""),
        "round": state.get("round", 0),
        "initial_status": state.get("status"),
    }
    atomic_save(MIGRATION, handoff)
    return handoff


def verify_same_request(handoff: dict) -> dict:
    """A conversation switch must never silently start a different round."""
    state = load(STATE)
    if (state.get("request_id"), state.get("round")) != (
        handoff.get("request_id"), handoff.get("round")
    ):
        raise RuntimeError("O request_id/rodada mudou durante a troca. Revisão manual necessária.")
    return state


def recovery_prompt(handoff: dict) -> str:
    """Human-copyable context, without pretending the earlier task finished."""
    path = str(ROOT)
    return (
        "RETOMAR PROJETO EM UMA NOVA CONVERSA DO CHATGPT.\n\n"
        f"Diretório no computador autorizado: {path}\n"
        f"Rodada anterior: {handoff.get('round', '?')}; "
        f"request_id: {handoff.get('request_id') or 'nenhum'}; "
        f"estado observado ao preparar migração: {handoff.get('initial_status', 'desconhecido')}.\n\n"
        "A conversa anterior foi encerrada ou ficou extensa demais. "
        "O Expert AI Manager está pausado para impedir novos envios durante a troca.\n\n"
        "1. Use Remote Desktop Commander para conferir o dispositivo e ler AGENTS.md, "
        "docs/TASKS.md, docs/STATE.md, .dev-loop/chat-state.json e Git status/log.\n"
        "2. Leia o estado ATUAL, pois ele pode ter mudado desde a preparação. "
        "Preserve os arquivos locais e eventuais mudanças não commitadas.\n"
        "3. Se o checkpoint ainda estiver running, requested, pending_send ou blocked, "
        "NÃO o declare concluído nem crie outro request_id. Investigue o trabalho já "
        "feito na conversa anterior e os logs. Recupere/termine somente o que for "
        "comprovável, pelo protocolo de AGENTS.md; se inseguro, reporte o bloqueio.\n"
        "4. Se estiver ready, apresente resumo breve do último commit, tarefas, "
        "testes e próximo passo. Não dispare outro supervisor.\n"
        "5. Este chat passa a ser a conversa principal. Confirme quando posso anexar "
        "a nova janela ao Expert AI Manager. O usuário fará essa vinculação manualmente; "
        "não remova PAUSE nem .dev-loop/chat-migration.json por conta própria.\n"
        "6. Preserve serviços de outros projetos, segurança, limites e os critérios "
        "de qualidade, testes, revisão do diff e commits seguros.\n\n"
        "Após a confirmação da migração e do checkpoint seguro, o supervisor "
        "retomará as próximas etapas automaticamente."
    )


def attach_migration(new_title: str) -> dict:
    handoff = migration_status()
    if handoff.get("phase") != "awaiting_new_chat":
        raise RuntimeError("Prepare a migração antes de anexar uma conversa.")
    if not PAUSE.exists():
        raise RuntimeError("Migração requer o supervisor pausado.")
    state = verify_same_request(handoff)
    if state.get("status") == "pending_send":
        raise RuntimeError("Há rascunho pendente; inspecione antes de mudar de conversa.")
    if not new_title.strip() or new_title.casefold() == handoff.get("previous_window_title", "").casefold():
        raise RuntimeError("A janela parece ser a conversa anterior. Abra e renomeie o novo chat.")
    config = load(CONFIG)
    if not config.get("calibrated") or config.get("window_title") != new_title:
        raise RuntimeError("A nova conversa ainda não foi calibrada.")
    handoff.update(phase="attached", new_window_title=new_title, attached_at=utc_now())
    atomic_save(MIGRATION, handoff)
    return handoff


def finish_migration() -> dict:
    handoff = migration_status()
    if handoff.get("phase") != "attached":
        raise RuntimeError("Abra o novo chat e execute migrate-attach antes de retomar.")
    if not PAUSE.exists():
        raise RuntimeError("A pausa foi removida fora do fluxo; inspecione o estado.")
    if LIMIT.exists():
        raise RuntimeError("Alerta de limite ativo; revisão manual necessária.")
    state = verify_same_request(handoff)
    if state.get("status") != "ready":
        raise RuntimeError(
            "A rodada anterior ainda não está ready. Reconcile/termine no novo chat antes de retomar."
        )
    cfg = load(CONFIG)
    if not cfg.get("calibrated") or cfg.get("window_title") != handoff.get("new_window_title"):
        raise RuntimeError("Calibração mudou após o anexo; inspecione a conversa.")
    # Only an explicitly completed handoff starts a fresh conversation estimate.
    start_session(state.get("round", 0), cfg["window_title"], known_new=True,
                  path=MIGRATION.with_name("conversation-session.json"))
    MIGRATION.unlink()
    if not handoff.get("previously_paused"):
        PAUSE.unlink()
    return {"phase": "finished", "resumed": not handoff.get("previously_paused"),
            "round": state.get("round"), "request_id": state.get("request_id")}


def cancel_migration() -> dict:
    handoff = migration_status()
    if handoff.get("phase") != "awaiting_new_chat":
        raise RuntimeError("A troca já foi anexada; não é seguro voltar automaticamente.")
    if not PAUSE.exists():
        raise RuntimeError("A pausa foi removida fora do fluxo; inspecione o estado.")
    verify_same_request(handoff)
    MIGRATION.unlink()
    if not handoff.get("previously_paused"):
        PAUSE.unlink()
    return {"phase": "cancelled", "resumed": not handoff.get("previously_paused")}
