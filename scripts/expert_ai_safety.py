"""User-controlled RPA pacing and rest breaks. No fingerprint or detection evasion.

Pure helpers used by the Windows UI supervisor. Counts *attempted new turns*
rather than successful clicks: transient UI retries keep the same request_id.
The JSON usage ledger is persisted atomically by the calling supervisor.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random

DEFAULT_SAFETY = {
    "safe_mode_enabled": True,
    "breaks_enabled": True,
    "min_minutes_between_requests": 12,
    "max_requests_per_hour": 5,
    "max_requests_per_24_hours": 120,
    "short_break_every_requests": 3,
    "short_break_min_minutes": 3,
    "short_break_max_minutes": 7,
    "long_break_every_requests": 9,
    "long_break_min_minutes": 15,
    "long_break_max_minutes": 30,
}

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return None
        return stamp.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None

def validate_safety(config: dict) -> None:
    for key in ("safe_mode_enabled", "breaks_enabled"):
        if not isinstance(config.get(key), bool):
            raise ValueError(f"{key} must be true or false")
    if not 1 <= config["max_requests_per_hour"] <= 60:
        raise ValueError("max_requests_per_hour must be between 1 and 60")
    if not 1 <= config["max_requests_per_24_hours"] <= 500:
        raise ValueError("max_requests_per_24_hours must be between 1 and 500")
    if not 1 <= config["min_minutes_between_requests"] <= 240:
        raise ValueError("min_minutes_between_requests must be between 1 and 240")
    for name in ("short", "long"):
        each = config[f"{name}_break_every_requests"]
        minimum = config[f"{name}_break_min_minutes"]
        maximum = config[f"{name}_break_max_minutes"]
        if not isinstance(each, int) or isinstance(each, bool) or not 1 <= each <= 100:
            raise ValueError(f"{name}_break_every_requests must be 1..100")
        if not (0.1 <= minimum <= maximum <= 240):
            raise ValueError(f"{name} break duration must be 0.1..240 minutes")
    if config["long_break_every_requests"] <= config["short_break_every_requests"]:
        raise ValueError("Long breaks should be less frequent than short breaks")

def new_ledger() -> dict:
    return {"schema_version": 1, "attempts": [], "total_attempts": 0,
            "break_until": None, "break_kind": None, "last_break_request_id": None}

def recent_attempts(ledger: dict, at: datetime) -> list[dict]:
    items = ledger.get("attempts", [])
    if not isinstance(items, list):
        raise ValueError("Usage ledger attempts must be a list")
    kept = []
    for record in items:
        if not isinstance(record, dict) or not isinstance(record.get("request_id"), str):
            raise ValueError("Malformed usage ledger entry")
        time = parse_utc(record.get("at"))
        if time is None or time > at + timedelta(minutes=5):
            raise ValueError("Usage ledger has missing or invalid UTC timestamps")
        if at - time < timedelta(hours=24):
            kept.append(record)
    return kept

def pace_status(config: dict, ledger: dict, at: datetime | None = None) -> dict:
    """Return permission, reason, UTC resume time and counts. No side effects."""
    validate_safety(config)
    at = at or utc_now()
    records = recent_attempts(ledger, at)
    hour = [r for r in records if at - parse_utc(r["at"]) < timedelta(hours=1)]
    result = {
        "safe_mode_enabled": config["safe_mode_enabled"],
        "breaks_enabled": config["breaks_enabled"],
        "requests_last_hour": len(hour), "requests_last_24_hours": len(records),
        "allowed": True, "reason": "ready", "next_eligible_at": None,
    }
    if not config["safe_mode_enabled"]:
        return result
    boundaries: list[tuple[datetime, str]] = []
    if records:
        last = max(parse_utc(r["at"]) for r in records)
        boundaries.append((last + timedelta(minutes=config["min_minutes_between_requests"]),
                           "minimum gap"))
    if len(hour) >= config["max_requests_per_hour"]:
        oldest_hour = min(parse_utc(r["at"]) for r in hour)
        boundaries.append((oldest_hour + timedelta(hours=1), "hourly cap"))
    if len(records) >= config["max_requests_per_24_hours"]:
        oldest_day = min(parse_utc(r["at"]) for r in records)
        boundaries.append((oldest_day + timedelta(hours=24), "24-hour cap"))
    rest_until = parse_utc(ledger.get("break_until"))
    if config["breaks_enabled"] and rest_until:
        boundaries.append((rest_until, "rest break"))
    active = [(until, label) for until, label in boundaries if until > at]
    if active:
        until, label = max(active, key=lambda item: item[0])
        result.update(allowed=False, reason=label, next_eligible_at=until.isoformat())
    return result

def record_attempt(config: dict, ledger: dict, request_id: str,
                   at: datetime | None = None, choose_duration=None) -> dict:
    """Reserve one new request before UI typing, preserving a single count per ID."""
    validate_safety(config)
    at = at or utc_now()
    if not request_id:
        raise ValueError("request_id is required")
    records = recent_attempts(ledger, at)
    if any(r["request_id"] == request_id for r in records):
        return ledger
    verdict = pace_status(config, ledger, at)
    if not verdict["allowed"]:
        raise ValueError("Pacing window not ready: " + verdict["reason"])
    records.append({"request_id": request_id, "at": at.isoformat()})
    result = {**ledger, "schema_version": 1, "attempts": records,
              "total_attempts": int(ledger.get("total_attempts", 0)) + 1}
    if config["safe_mode_enabled"] and config["breaks_enabled"]:
        total = result["total_attempts"]
        label = ("long" if total % config["long_break_every_requests"] == 0
                 else "short" if total % config["short_break_every_requests"] == 0
                 else None)
        if label:
            if choose_duration is None:
                choose_duration = random.uniform
            minutes = float(choose_duration(config[f"{label}_break_min_minutes"],
                                            config[f"{label}_break_max_minutes"]))
            result.update(break_until=(at + timedelta(minutes=minutes)).isoformat(),
                          break_kind=label, last_break_request_id=request_id)
    return result
