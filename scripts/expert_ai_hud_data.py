"""Read-only HUD snapshot derived from existing checkpoint, config and task files.

The HUD never requests additional GPT turns just to collect progress.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

from expert_ai_control import RUNTIME, STATE, MONITOR, USAGE, CONFIG, PAUSE, LIMIT, load, read_settings
from expert_ai_safety import new_ledger, pace_status, parse_utc
from expert_ai_migration import migration_status
from expert_ai_context import context_budget, read_session, handoff_policy

ROOT = RUNTIME.parent
TASKS = ROOT / "docs" / "TASKS.md"


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def read_user_idle_seconds() -> float | None:
    """Read Windows-wide inactivity locally, without sending model requests."""
    if sys.platform != "win32":
        return None
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return None
    ticks = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
    return ((ticks - info.dwTime) & 0xFFFFFFFF) / 1000


def clock_text(seconds: int | float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def timing_view(data: dict) -> dict:
    """Calm presentation of actual progress; never show the 10s internal polling loop."""
    visible = False
    percent = 0.0
    hint = ""
    decision = "Acompanhando o desenvolvimento"
    check = "Verificações internas em segundo plano"

    if data.get("migration_phase"):
        decision = ("Aguardando novo chat" if data["migration_phase"] == "awaiting_new_chat"
                    else "Conversa vinculada; confira a rodada")
        check = "Migração segura em andamento; novos envios suspensos"
    elif data["paused"]:
        decision = "Supervisor pausado"
        check = "Aguardando você retomar"
    elif data["limit_hold"]:
        decision = "Aguardando revisão de limite"
        check = "Envios suspensos até sua confirmação"
    elif not data["supervisor_live"]:
        decision = "Supervisor não confirmado"
        check = "Confira se o processo ainda está ativo"
    elif data["state"] in ("ready", "pending_send"):
        idle = data.get("idle_seconds")
        required = data.get("idle_required_seconds", 90)
        if idle is not None and required > 0 and idle < required:
            visible = True
            percent = min(100.0, max(0.0, idle / required * 100))
            decision = "Aguardando você terminar"
            check = f"Sem usar o PC: {clock_text(idle)} de {clock_text(required)}"
            hint = "A contagem reinicia quando você volta a usar o PC."
        elif data.get("pacing_seconds") not in (None, 0):
            decision = "Descansando antes de continuar"
            check = "Próxima solicitação após os limites e descansos"
        elif data["state"] == "pending_send":
            decision = "Conferindo a mensagem preparada"
            check = "Aguardando condições seguras para enviar"
        else:
            decision = "Preparando a próxima etapa"
            check = "Conferindo se a conversa está disponível"
    elif data["state"] == "running":
        decision = "Desenvolvendo a etapa atual"
    elif data["state"] == "requested":
        decision = "Aguardando confirmação da mensagem"
    elif data["state"] == "blocked":
        decision = "Precisa de atenção"
    elif data["state"] == "done":
        decision = "Etapas concluídas"

    if (not visible and data["supervisor_live"] and not data["paused"]
            and not data["limit_hold"] and data["next_check_kind"] == "periodic"
            and data.get("next_check_seconds") is not None
            and data.get("pacing_seconds") in (None, 0)
            and data["state"] in ("ready", "requested", "running", "pending_send")):
        remaining = int(data["next_check_seconds"])
        minutes, seconds = divmod(remaining, 60)
        check = f"Próxima verificação periódica: {minutes}m {seconds:02d}s"
    return {
        "decision": decision, "check": check, "idle_visible": visible,
        "idle_percent": percent, "idle_hint": hint,
    }


def list_tasks(content: str, prefix: str = "APP") -> dict:
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,16}", prefix):
        raise ValueError("Invalid task prefix")
    rows = []
    pat = re.compile(rf"^- \[([ x~!])\] ({re.escape(prefix)}-\d+[A-Z]?)\s*(.*)$", re.M)
    for match in pat.finditer(content):
        rows.append({
            "status": match.group(1), "id": match.group(2),
            "title": match.group(3).strip(),
        })
    counts = {"done": 0, "active": 0, "todo": 0, "deferred": 0}
    for row in rows:
        counts[{"x": "done", "~": "active", " ": "todo", "!": "deferred"}[row["status"]]] += 1
    return {"counts": counts, "pending": [r for r in rows if r["status"] in (" ", "~")],
            "completed": [r for r in rows if r["status"] == "x"]}

def remaining_seconds(until: str | None, now: datetime | None = None) -> int | None:
    parsed = parse_utc(until)
    if parsed is None:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0, round((parsed - now).total_seconds()))

def progress_snapshot() -> dict:
    cfg = read_settings()
    state = load(STATE)
    monitor = load(MONITOR)
    migration = migration_status()
    session = read_session()
    budget = context_budget(state.get("round", 0), session)
    usage = load(USAGE, new_ledger())
    try:
        pacing = pace_status(cfg, usage)
        pacing_error = None
    except (ValueError, TypeError, KeyError) as exc:
        pacing = {"allowed": False, "reason": "invalid settings",
                  "next_eligible_at": None, "requests_last_hour": 0,
                  "requests_last_24_hours": 0}
        pacing_error = str(exc)
    prefix = cfg.get("task_prefix", "APP")
    content = TASKS.read_text(encoding="utf-8") if TASKS.exists() else ""
    tasks = list_tasks(content, prefix)
    now = datetime.now(timezone.utc)
    monitor_age = remaining_seconds(monitor.get("updated_at"), now)
    timestamp = parse_utc(monitor.get("updated_at"))
    live = timestamp is not None and 0 <= (now - timestamp).total_seconds() <= 20
    return {
        "state": state.get("status", "unknown"),
        "request_id": state.get("request_id"),
        "round": state.get("round", 0),
        "last_commit": state.get("last_commit") or "—",
        "last_task": state.get("last_task") or "—",
        "last_quality_check": state.get("last_quality_check") or "Sem registro",
        "summary": state.get("summary", ""),
        "paused": PAUSE.exists(),
        "migration_phase": migration.get("phase"),
        "migration_trigger": migration.get("trigger"),
        "conversation_budget": budget,
        "conversation_handoff": handoff_policy(
            state, cfg, session,
            pending_count=len(tasks["pending"]), paused=PAUSE.exists(),
            migration_pending=bool(migration), limit_hold=LIMIT.exists(),
        ),
        "handoff_enabled": cfg.get("automatic_conversation_handoff", True),
        "handoff_after_rounds": cfg.get("handoff_after_rounds", 8),
        "limit_hold": LIMIT.exists(),
        "supervisor_live": live,
        "supervisor_action": monitor.get("action") or "—",
        "next_check_at": monitor.get("next_check_at"),
        "next_check_seconds": remaining_seconds(monitor.get("next_check_at"), now) if live else None,
        "next_check_kind": monitor.get("next_check_kind") or "—",
        "idle_seconds": read_user_idle_seconds(),
        "idle_required_seconds": cfg["min_user_idle_seconds"],
        "pacing_seconds": remaining_seconds(pacing.get("next_eligible_at"), now),
        "pacing_reason": pacing.get("reason", "—"),
        "pacing_error": pacing_error,
        "requests_hour": pacing.get("requests_last_hour", 0),
        "requests_day": pacing.get("requests_last_24_hours", 0),
        "safe_mode": cfg["safe_mode_enabled"],
        "breaks_enabled": cfg["breaks_enabled"],
        "break_until": usage.get("break_until"),
        "break_kind": usage.get("break_kind"),
        "task_counts": tasks["counts"],
        "pending_tasks": tasks["pending"],
        "completed_tasks": tasks["completed"],
        "config": {name: cfg[name] for name in (
            "min_minutes_between_requests", "max_requests_per_hour",
            "max_requests_per_24_hours", "short_break_every_requests",
            "short_break_min_minutes", "short_break_max_minutes",
            "long_break_every_requests", "long_break_min_minutes",
            "long_break_max_minutes", "min_periodic_minutes",
            "max_periodic_minutes", "min_user_idle_seconds")},
    }

if __name__ == "__main__":
    print(json.dumps(progress_snapshot(), indent=2, ensure_ascii=False))
