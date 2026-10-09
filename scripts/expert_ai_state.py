"""Expert AI Manager checkpoint and configuration updater. Windows stdlib only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / ".dev-loop"
STATE = RUNTIME / "chat-state.json"
CONFIG = RUNTIME / "rpa-config.json"
PAUSE = RUNTIME / "PAUSE"


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(path: Path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def atomic_save(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def change_status(action: str, request_id: str, summary: str = ""):
    old = load(STATE)
    if old.get("request_id") != request_id:
        raise RuntimeError("Request ID mismatch; refusing to mutate another turn")
    status = old.get("status")
    if action == "ack":
        # The GPT may receive the message before the RPA finishes marking
        # a successful Send-button click. Matching request_id is mandatory.
        if status not in ("requested", "pending_send"):
            raise RuntimeError(f"Expected requested/pending_send; got {status}")
        old.update(status="running", started_at=utc_now(), heartbeat_at=utc_now(),
                   updated_at=utc_now())
    elif action == "heartbeat":
        if status != "running":
            raise RuntimeError(f"Expected running; got {status}")
        old.update(heartbeat_at=utc_now(), updated_at=utc_now())
    elif action == "ready":
        if status != "running":
            raise RuntimeError(f"Expected running; got {status}")
        old.update(status="ready", summary=summary or "Rodada validada",
                   updated_at=utc_now(), reason="")
    elif action == "reconcile":
        # Administrative recovery only after explicitly verifying that this
        # request_id is already present in the user's conversation.
        # It is NOT a development task completion or Git checkpoint.
        if status not in ("blocked", "requested"):
            raise RuntimeError(f"Expected blocked/requested; got {status}")
        if not summary:
            raise RuntimeError("Manual reconciliation requires an explanation")
        old.update(status="ready", summary=summary, reason="",
                   reconciled_at=utc_now(), updated_at=utc_now())
    elif action == "blocked":
        if status not in ("running", "requested"):
            raise RuntimeError(f"Expected running or requested; got {status}")
        old.update(status="blocked", summary=summary or "Blocked",
                   reason=summary or "Intervention required", updated_at=utc_now())
    elif action == "done":
        if status != "running":
            raise RuntimeError(f"Expected running; got {status}")
        import re
        tasks = (ROOT / "docs" / "TASKS.md").read_text(encoding="utf-8")
        config = load(CONFIG)
        prefix = config.get("task_prefix", "APP")
        if not re.fullmatch(r"[A-Z][A-Z0-9]{1,16}", prefix):
            raise ValueError("Invalid project task prefix")
        remaining = re.findall(rf"(?m)^- \[(?: |~)\] {re.escape(prefix)}-", tasks)
        if remaining:
            raise RuntimeError(f"Cannot mark done with {len(remaining)} incomplete tasks")
        old.update(status="done", summary=summary or "All tasks verified",
                   updated_at=utc_now())
    else:
        raise ValueError(action)
    atomic_save(STATE, old)
    print(f"{action.upper()} OK request_id={request_id} status={old['status']} round={old['round']}")


def configure():
    """Configure generic defaults without replacing a project's own instructions."""
    config = load(CONFIG)
    config.pop("interval_minutes", None)
    config.setdefault("min_periodic_minutes", 10)
    config.setdefault("max_periodic_minutes", 20)
    config.setdefault("min_user_idle_seconds", 90)
    config.setdefault("max_auto_requests", 0)
    config.setdefault("min_free_ram_gib", 2)
    config.setdefault("max_unacknowledged_minutes", 45)
    config.setdefault("max_pending_send_minutes", 30)
    config.setdefault("task_prefix", "APP")
    config.setdefault("project_name", "My Project")
    config.setdefault("message", (
        f"CONTINUE {config['project_name']}: verify the request_id in the chat "
        f"and .dev-loop/chat-state.json. ACK with scripts/expert_ai_state.py; "
        "read AGENTS.md, docs/TASKS.md and docs/STATE.md, implement one tested "
        "step, review the diff, update checkpoint metadata, and mark ready, "
        "blocked or done. Preserve other project resources. Never fabricate "
        "test results or bypass platform limits."
    ))
    atomic_save(CONFIG, config)
    print("CONFIGURED project:", config["project_name"])



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["configure", "ack", "heartbeat", "ready", "blocked", "done", "reconcile"])
    parser.add_argument("request_id", nargs="?")
    parser.add_argument("summary", nargs="?", default="")
    args = parser.parse_args()
    if args.action == "configure":
        configure()
    else:
        if not args.request_id:
            parser.error("request_id required")
        change_status(args.action, args.request_id, args.summary)
