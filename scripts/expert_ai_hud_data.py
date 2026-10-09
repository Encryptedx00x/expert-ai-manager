"""Read-only HUD snapshot derived from existing checkpoint, config and task files.

The HUD never requests additional GPT turns just to collect progress.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from expert_ai_control import RUNTIME, STATE, MONITOR, USAGE, CONFIG, PAUSE, LIMIT, load, read_settings
from expert_ai_safety import new_ledger, pace_status, parse_utc

ROOT = RUNTIME.parent
TASKS = ROOT / "docs" / "TASKS.md"

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
        "limit_hold": LIMIT.exists(),
        "supervisor_live": live,
        "supervisor_action": monitor.get("action") or "—",
        "next_check_at": monitor.get("next_check_at"),
        "next_check_seconds": remaining_seconds(monitor.get("next_check_at"), now) if live else None,
        "next_check_kind": monitor.get("next_check_kind") or "—",
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
