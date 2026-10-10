"""Explicit, local handoff between ChatGPT conversations (no browser automation).

A migration pause blocks NEW sends while a user manually opens another chat.
It does not acknowledge, reset, or complete an in-flight request.
"""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

from expert_ai_control import ROOT, RUNTIME, CONFIG, STATE, PAUSE, LIMIT, load, atomic_save
from expert_ai_context import start_session

MIGRATION = RUNTIME / "chat-migration.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def migration_status() -> dict:
    return load(MIGRATION)


def prepare_migration(*, trigger: str = "manual", budget_rounds: int | None = None) -> dict:
    if MIGRATION.exists():
        raise RuntimeError("Uma troca de conversa já está pendente. Abra as instruções.")
    state = load(STATE)
    config = load(CONFIG)
    if state.get("status") == "pending_send":
        raise RuntimeError("Existe um rascunho pendente. Verifique o envio antes de trocar de conversa.")
    if state.get("status") not in ("ready", "running", "requested", "blocked"):
        raise RuntimeError("Não é seguro iniciar a troca com este estado.")
    if trigger not in ("manual", "round_budget", "conversation_limit", "delivery_timeout"):
        raise ValueError("Unknown conversation handoff trigger")
    if trigger == "round_budget" and (
        state.get("status") != "ready"
        or not isinstance(budget_rounds, int) or budget_rounds < 0
    ):
        raise RuntimeError("Automatic handoff requires a ready checkpoint and valid round count")
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
        "previous_conversation_url": config.get("conversation_url", ""),
        "previously_paused": was_paused,
        "request_id": state.get("request_id", ""),
        "round": state.get("round", 0),
        "initial_status": state.get("status"),
        "trigger": trigger,
        "migration_id": uuid.uuid4().hex[:16],
        "budget_rounds": budget_rounds if trigger == "round_budget" else None,
        "last_commit": state.get("last_commit"),
        "last_task": state.get("last_task"),
        "last_quality_check": state.get("last_quality_check"),
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
    """Human-copyable verified checkpoint; no new development request_id."""
    path = str(ROOT)
    identifier = str(handoff.get("migration_id") or "")
    return (
        "RECUPERAR PROJETO NESTE NOVO CHAT DO CHATGPT.\\n\\n"
        f"Diretorio local: {path}\\n"
        f"Rodada anterior: {handoff.get('round', '?')}; "
        f"request_id anterior: {handoff.get('request_id') or 'nenhum'}; "
        f"status anterior: {handoff.get('initial_status', 'desconhecido')}.\\n"
        f"Commit anterior: {handoff.get('last_commit') or 'nao registrado'}.\\n"
        f"Ultima tarefa: {handoff.get('last_task') or 'nao registrada'}.\\n"
        f"Testes informados: {handoff.get('last_quality_check') or 'nao registrados'}.\\n\\n"
        "1. Conecte ao computador autorizado via Remote Desktop Commander. "
        "Leia AGENTS.md, docs/EXECUTION_PLAN.md (se existir), docs/TASKS.md, "
        "docs/STATE.md, .dev-loop/chat-state.json, "
        ".dev-loop/chat-migration.json e Git status/log.\\n"
        "2. Preserve absolutamente o request_id e a rodada anterior. "
        "n\u00e3o registre nova rodada de desenvolvimento nem reinicie supervisor ou HUD.\\n"
        "3. Se houver running, requested ou blocked, verifique o diff, os testes "
        "e os logs da rodada anterior; apenas reconcilie para ready se tiver "
        "comprovado que ela foi concluida, ou mantenha blocked e explique.\\n"
        "4. Se o checkpoint for ready, confirme as tarefas/commit/testes e o "
        "proximo lote. O EAM esta intencionalmente PAUSADO durante a migracao.\\n"
        "5. Se a fase no chat-migration.json for bootstrap_sent e o checkpoint "
        "estiver ready, confirme a recuperacao executando via Remote Desktop: "
        f"py -3 -B scripts/expert_ai_control.py migrate-ack {identifier}. "
        "Nunca execute migrate-ack se houver incerteza. Isso nao envia mensagem.\\n"
        "6. Se a migracao for manual, use o HUD ou migrate-attach e "
        "migrate-finish conforme docs/expert-ai-manager/TROCA_DE_CONVERSA.md. "
        "A vinculacao automatica exige a URL exata do novo chat e o ACK local. "
        "Nao remova PAUSE nem o marcador de migracao manualmente. "
        "Mantenha todas as regras, testes, seguranca e limites de uso.\\n\\n"
        f"[migration_id: {identifier}]"
    )


def attach_migration(new_title: str) -> dict:
    handoff = migration_status()
    if handoff.get("phase") not in ("awaiting_new_chat", "acknowledged"):
        raise RuntimeError("Prepare a migração antes de anexar uma conversa.")
    if not PAUSE.exists():
        raise RuntimeError("Migração requer o supervisor pausado.")
    state = verify_same_request(handoff)
    if state.get("status") == "pending_send":
        raise RuntimeError("Há rascunho pendente; inspecione antes de mudar de conversa.")
    if not new_title.strip():
        raise RuntimeError("New conversation must have a browser title")
    if (new_title.casefold() == handoff.get("previous_window_title", "").casefold()
            and not handoff.get("previous_conversation_url")):
        raise RuntimeError("A janela parece ser da conversa anterior; confira o endereco.")
    config = load(CONFIG)
    if not config.get("calibrated") or config.get("window_title") != new_title:
        raise RuntimeError("A nova conversa ainda não foi calibrada.")
    old_url, new_url = handoff.get("previous_conversation_url"), config.get("conversation_url")
    if old_url and (not new_url or new_url == old_url):
        raise RuntimeError("A conversa vinculada precisa de um novo endereço confirmado.")
    handoff.update(phase="attached", new_window_title=new_title,
                   new_conversation_url=new_url or "", attached_at=utc_now())
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
    if cfg.get("conversation_url", "") != handoff.get("new_conversation_url", ""):
        raise RuntimeError("Endereço da conversa mudou após a migração.")
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


def acknowledge_auto_migration(migration_id: str) -> dict:
    """Only the recovered GPT explicitly confirms the prior work is safe."""
    handoff = migration_status()
    if handoff.get("phase") != "bootstrap_sent":
        raise RuntimeError("Auto migration is not awaiting recovery acknowledgement")
    if not migration_id or migration_id != handoff.get("migration_id"):
        raise RuntimeError("Migration ID mismatch; cannot acknowledge another conversation")
    if not PAUSE.exists() or LIMIT.exists():
        raise RuntimeError("Migration pause missing or platform limit present")
    state = verify_same_request(handoff)
    if state.get("status") != "ready":
        raise RuntimeError("Reconcile the previous request to ready before acknowledgement")
    handoff.update(phase="acknowledged", acknowledged_at=utc_now())
    atomic_save(MIGRATION, handoff)
    return handoff
