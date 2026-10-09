"""Lightweight configuration interface for the Expert AI Manager RPA supervisor.

Only locally persisted, explicitly visible controls. No UI camouflage.
Run: py -3 -B scripts/expert_ai_control.py status | safe-on | safe-off |
     breaks-on | breaks-off | pause | resume | limit-hold | limit-clear |
     set <allowlisted-key> <value>
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import uuid

from expert_ai_safety import DEFAULT_SAFETY, pace_status, new_ledger, validate_safety

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / ".dev-loop"
CONFIG = RUNTIME / "rpa-config.json"
STATE = RUNTIME / "chat-state.json"
MONITOR = RUNTIME / "rpa-monitor.json"
USAGE = RUNTIME / "rpa-usage.json"
PAUSE = RUNTIME / "PAUSE"
LIMIT = RUNTIME / "LIMIT"

SETTABLE = {
    "min_minutes_between_requests": int,
    "max_requests_per_hour": int,
    "max_requests_per_24_hours": int,
    "short_break_every_requests": int,
    "short_break_min_minutes": float,
    "short_break_max_minutes": float,
    "long_break_every_requests": int,
    "long_break_min_minutes": float,
    "long_break_max_minutes": float,
    "min_user_idle_seconds": int,
}

def load(path: Path, fallback: dict | None = None) -> dict:
    if not path.exists():
        return dict(fallback or {})
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object in " + path.name)
    return data

def atomic_save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(value, file, indent=2, ensure_ascii=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def read_settings() -> dict:
    return {**DEFAULT_SAFETY, **load(CONFIG)}

def set_option(field: str, value) -> dict:
    if field not in SETTABLE and field not in ("safe_mode_enabled", "breaks_enabled"):
        raise ValueError("Option not adjustable using this command")
    current = load(CONFIG)
    merged = {**DEFAULT_SAFETY, **current, field: value}
    validate_safety(merged)
    # Never write window titles, messages, or calibration through a generic setter.
    current[field] = value
    atomic_save(CONFIG, current)
    return merged

def snapshot() -> dict:
    config = read_settings()
    usage = load(USAGE, new_ledger())
    return {
        "state": load(STATE).get("status", "unknown"),
        "request_id": load(STATE).get("request_id"),
        "round": load(STATE).get("round"),
        "last_commit": load(STATE).get("last_commit"),
        "paused": PAUSE.exists(),
        "platform_limit_hold": LIMIT.exists(),
        "config": {key: config[key] for key in DEFAULT_SAFETY},
        "periodic_check_window_minutes": [
            config.get("min_periodic_minutes", 10),
            config.get("max_periodic_minutes", 20),
        ],
        "pacing": pace_status(config, usage),
        "monitor": load(MONITOR),
    }

def command(name: str, field: str | None = None, value: str | None = None) -> dict:
    if name == "pause":
        PAUSE.touch()
    elif name == "resume":
        PAUSE.unlink(missing_ok=True)
    elif name == "limit-hold":
        LIMIT.touch()
        PAUSE.touch()
    elif name == "limit-clear":
        LIMIT.unlink(missing_ok=True)
        # Paused state intentionally remains until manually resumed.
    elif name == "safe-on":
        set_option("safe_mode_enabled", True)
    elif name == "safe-off":
        set_option("safe_mode_enabled", False)
    elif name == "breaks-on":
        set_option("breaks_enabled", True)
    elif name == "breaks-off":
        set_option("breaks_enabled", False)
    elif name == "set" and field in SETTABLE and value is not None:
        parser = SETTABLE[field]
        set_option(field, parser(value))
    elif name != "status":
        raise ValueError("Unsupported command or field")
    return snapshot()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=[
        "status", "pause", "resume", "limit-hold", "limit-clear",
        "safe-on", "safe-off", "breaks-on", "breaks-off", "set"
    ])
    parser.add_argument("field", nargs="?")
    parser.add_argument("value", nargs="?")
    args = parser.parse_args()
    print(json.dumps(command(args.command, args.field, args.value), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
