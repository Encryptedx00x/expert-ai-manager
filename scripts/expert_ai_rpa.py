"""Óliver's ChatGPT RPA supervisor (stdlib, Windows only).

The GPT itself writes .dev-loop/chat-state.json. The supervisor sends exactly
one continuation when state=ready, the user is idle, and the calibrated ChatGPT
window is uniquely identified. It never reads the chat or bypasses UI limits.

Commands:
  py -3 scripts/expert_ai_rpa.py status
  py -3 scripts/expert_ai_rpa.py calibrate
  py -3 scripts/expert_ai_rpa.py check
  py -3 scripts/expert_ai_rpa.py run
  py -3 scripts/expert_ai_rpa.py pause
  py -3 scripts/expert_ai_rpa.py resume
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import random
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from expert_ai_safety import DEFAULT_SAFETY, new_ledger, pace_status, record_attempt, parse_utc
from expert_ai_migration import MIGRATION, migration_status, attach_migration
from expert_ai_context import (compact_message, initialize_if_missing,
                               read_session, context_budget)

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / ".dev-loop"
CONFIG = RUNTIME / "rpa-config.json"
STATE = RUNTIME / "chat-state.json"
PAUSE = RUNTIME / "PAUSE"
LOGFILE = RUNTIME / "rpa.log"
LOCKFILE = RUNTIME / "rpa.lock"
USAGE = RUNTIME / "rpa-usage.json"
MONITOR = RUNTIME / "rpa-monitor.json"
LIMIT = RUNTIME / "LIMIT"
TASKS = ROOT / "docs" / "TASKS.md"
DEFAULTS = {
    **DEFAULT_SAFETY,
    "min_periodic_minutes": 10,
    "max_periodic_minutes": 20,
    "task_prefix": "APP",
    "min_user_idle_seconds": 90,
    "max_auto_requests": 0,  # 0: no cap; test mode sets 2
    "min_free_ram_gib": 2.0,
    "max_unacknowledged_minutes": 45,
    "max_pending_send_minutes": 30,
    "max_running_minutes": 120,
    "window_title": "",
    "process_name": "",
    "composer_ratio_x": None,
    "composer_ratio_y": None,
    "calibrated": False,
    "message": (
        "Continue o desenvolvimento do the selected project neste chat usando Remote Desktop "
        "Commander. Leia AGENTS.md, docs/TASKS.md, docs/STATE.md e "
        ".dev-loop/chat-state.json. Marque o JSON como running com o mesmo request_id "
        "desta mensagem assim que comecar; trabalhe na proxima etapa, teste e registre "
        "o commit. No fim, marque ready para continuar, blocked para impedimento real "
        "ou done apenas se tudo estiver validado. Informe um resumo breve."
    ),
}

if sys.platform == "win32":
    U = ctypes.WinDLL("user32", use_last_error=True)
    K = ctypes.WinDLL("kernel32", use_last_error=True)
    ULONG_PTR = wintypes.WPARAM

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG), ("top", wintypes.LONG),
            ("right", wintypes.LONG), ("bottom", wintypes.LONG),
        ]

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", INPUTUNION)]

    # Keep HWND as pointer-sized on 64-bit Windows to avoid truncating window handles.
    U.GetForegroundWindow.restype = wintypes.HWND
    U.SetForegroundWindow.argtypes = [wintypes.HWND]
    U.SetForegroundWindow.restype = wintypes.BOOL
    U.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    U.ShowWindow.restype = wintypes.BOOL
    U.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    U.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    U.GetWindowTextW.restype = ctypes.c_int
    U.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
    U.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    U.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    U.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    U.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
    U.IsWindowVisible.argtypes = [wintypes.HWND]
    U.SetForegroundWindow.argtypes = [wintypes.HWND]
    U.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
    U.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    K.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MEMORYSTATUSEX)]
    # Use consistent physical screen coordinates on scaled Windows displays.
    try:
        U.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path, fallback: dict | None = None) -> dict:
    if not path.exists():
        return dict(fallback or {})
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def write_monitor(value: dict) -> None:
    """Best-effort HUD telemetry: never stop development over a temporary file lock."""
    for attempt in range(5):
        try:
            write_json(MONITOR, value)
            return
        except PermissionError as exc:
            if attempt == 4:
                logging.warning("HUD monitor file busy; continuing supervisor: %s", exc)
                return
            time.sleep(0.05 * (attempt + 1))


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def age_minutes(value: str | None) -> float | None:
    dt = parse_time(value)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 60 if dt else None


def pending_tasks(prefix: str = "APP") -> list[str]:
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,16}", prefix):
        raise ValueError("task_prefix must be 2–17 uppercase letters/digits")
    text = TASKS.read_text(encoding="utf-8")
    return re.findall(rf"(?m)^- \[(?: |~)\] ({re.escape(prefix)}-\d+[A-Z]?)\b", text)


def win_title(hwnd: int) -> str:
    size = U.GetWindowTextLengthW(hwnd) + 1
    buf = ctypes.create_unicode_buffer(max(1, size))
    U.GetWindowTextW(hwnd, buf, len(buf))
    return buf.value


def window_rect(hwnd: int) -> RECT:
    rect = RECT()
    if not U.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise OSError("Unable to inspect target window geometry")
    return rect


def process_name(hwnd: int) -> str:
    pid = wintypes.DWORD()
    U.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    result = subprocess.run(
        ["tasklist.exe", "/FI", f"PID eq {pid.value}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, timeout=5,
    )
    import csv
    rows = list(csv.reader(result.stdout.splitlines()))
    return rows[0][0].lower() if rows and len(rows[0]) > 1 else ""


def matching_windows(config: dict) -> list[int]:
    """Match the ChatGPT conversation URL; browser tab titles are mutable."""
    windows: list[int] = []
    conversation_url = config.get("conversation_url")
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def visit(hwnd, _):
        if U.IsWindowVisible(hwnd):
            title = win_title(hwnd)
            if title and (conversation_url or config["window_title"].casefold() in title.casefold()):
                windows.append(hwnd)
        return True

    U.EnumWindows(visit, 0)
    eligible = [w for w in windows if process_name(w) == config["process_name"].lower()]
    if not conversation_url:
        return eligible

    matched = []
    for hwnd in eligible:
        try:
            if composer_bounds(hwnd).get("conversation_url") == conversation_url:
                matched.append(hwnd)
        except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired):
            continue
    return matched


def free_ram_gib() -> float:
    memory = MEMORYSTATUSEX()
    memory.dwLength = ctypes.sizeof(memory)
    if not K.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("Cannot read free RAM")
    return memory.ullAvailPhys / (1024 ** 3)


def user_idle_seconds() -> float:
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not U.GetLastInputInfo(ctypes.byref(info)):
        raise OSError("Cannot inspect user idle time")
    return ((K.GetTickCount() & 0xFFFFFFFF) - info.dwTime) % (2 ** 32) / 1000


def input_event(event: INPUT) -> None:
    if U.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
        raise OSError("Windows SendInput failed")


def press_key(vk: int, release: bool = False) -> None:
    data = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=2 if release else 0)
    input_event(INPUT(type=1, u=INPUTUNION(ki=data)))


def send_text(message: str, expected_hwnd: int | None = None) -> None:
    # Send Unicode without altering the user's clipboard; stop on stolen focus.
    codes = message.encode("utf-16-le")
    for n in range(0, len(codes), 2):
        if expected_hwnd is not None and n % 24 == 0 and U.GetForegroundWindow() != expected_hwnd:
            raise RpaBlocked("Popup stole focus while typing; inspect incomplete draft")
        code = codes[n] | (codes[n + 1] << 8)
        for flags in (0x4, 0x6):  # KEYEVENTF_UNICODE, then KEYUP
            input_event(INPUT(type=1, u=INPUTUNION(ki=KEYBDINPUT(
                wVk=0, wScan=code, dwFlags=flags))))
        time.sleep(0.004)


def click_at(x: int, y: int) -> None:
    U.SetCursorPos(x, y)
    for flag in (0x0002, 0x0004):  # left down, left up
        input_event(INPUT(type=0, u=INPUTUNION(mi=MOUSEINPUT(dwFlags=flag))))
        time.sleep(0.08)


def composer_bounds(hwnd: int) -> dict:
    """Find the live ChatGPT input via Windows UI Automation, read-only."""
    script = ROOT / "scripts" / "expert_ai_composer.ps1"
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(script), "-WindowHandle", str(hwnd)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=12,
    )
    if result.returncode != 0:
        raise RuntimeError("ChatGPT composer accessibility lookup failed: "
                           + result.stderr.strip()[-400:])
    try:
        bounds = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid ChatGPT composer geometry") from exc
    if bounds["width"] < 100 or bounds["height"] < 20:
        raise RuntimeError("ChatGPT message composer is not available")
    return bounds


def calibrate_auto(*, migration_title: str | None = None,
                   migration_url: str | None = None) -> None:
    """Bind to the foreground ChatGPT composer; optionally guard a chat migration."""
    if MIGRATION.exists() and migration_title is None:
        raise RuntimeError("Troca de conversa em andamento: use migrate-attach.")
    hwnd = U.GetForegroundWindow()
    title = win_title(hwnd)
    exe = process_name(hwnd)
    if exe not in ("msedge.exe", "brave.exe", "chatgpt.exe"):
        raise RuntimeError(f"Foreground app is {exe!r}, expected Edge/Brave/ChatGPT")
    if not title.strip():
        raise RuntimeError("The selected ChatGPT window must have a title")
    if migration_title is not None and title.casefold() == migration_title.casefold():
        raise RuntimeError("A nova conversa precisa de um título diferente da anterior.")
    # Identify the live ChatGPT composer by its accessible name instead of
    # assuming every project conversation has the same browser window title.
    bounds = composer_bounds(hwnd)
    if bounds.get("name") not in ("Pergunte ao ChatGPT", "Ask anything", "Ask ChatGPT", "Message ChatGPT"):
        raise RuntimeError("Expected the accessible ChatGPT message composer")
    if exe in ("msedge.exe", "brave.exe") and not bounds.get("conversation_url"):
        raise RuntimeError("Cannot verify ChatGPT conversation address; calibration refused")
    if migration_url and bounds.get("conversation_url") == migration_url:
        raise RuntimeError("A nova janela ainda aponta para a conversa anterior.")
    rect = window_rect(hwnd)
    width, height = rect.right - rect.left, rect.bottom - rect.top
    rx = (bounds["x"] + bounds["width"]/2 - rect.left) / width
    ry = (bounds["y"] + bounds["height"]/2 - rect.top) / height
    if width < 550 or height < 350 or not (0.05 < rx < 0.95 and 0.35 < ry < 0.99):
        raise RuntimeError("Composer does not fit the expected window area")
    config = {**DEFAULTS, **read_json(CONFIG)}
    config.update({"window_title": title, "process_name": exe,
                   "conversation_url": bounds.get("conversation_url", ""),
                   "composer_ratio_x": round(rx, 5), "composer_ratio_y": round(ry, 5),
                   "calibrated": True})
    write_json(CONFIG, config)
    initialize_if_missing(read_json(STATE).get("round", 0), title,
                          path=CONFIG.with_name("conversation-session.json"))
    print(f"Auto-calibrated browser/app: {title!r}, {exe}, "
          f"composer ({rx:.3f}, {ry:.3f}); NO MESSAGE SENT")


def migrate_attach() -> None:
    """User-selected new chat: read-only composer check followed by calibration."""
    handoff = migration_status()
    if handoff.get("phase") != "awaiting_new_chat" or not PAUSE.exists():
        raise RuntimeError("Prepare a troca e confirme a pausa antes de anexar.")
    if read_json(STATE).get("status") == "pending_send":
        raise RuntimeError("Há um rascunho pendente; resolva antes de trocar de chat.")
    print("Abra o NOVO chat no Edge ou Brave em primeiro plano. Captura em 6 segundos...")
    time.sleep(6)
    calibrate_auto(migration_title=handoff.get("previous_window_title", ""),
                   migration_url=handoff.get("previous_conversation_url", ""))
    current = read_json(CONFIG)
    attach_migration(current["window_title"])
    print("Nova conversa anexada, supervisor AINDA PAUSADO.")
    print("Depois de reconciliar o checkpoint até ready, execute:")
    print("py -3 -B scripts/expert_ai_control.py migrate-finish")


def calibrate() -> None:
    if MIGRATION.exists():
        raise RuntimeError("Troca de conversa em andamento: use migrate-attach.")
    print("Abra ESTA conversa no ChatGPT, deixe a janela ativa e posicione o mouse")
    print("sobre o CENTRO da caixa de mensagem. Captura em 6 segundos...")
    time.sleep(6)
    hwnd = U.GetForegroundWindow()
    title = win_title(hwnd)
    exe = process_name(hwnd)
    if exe not in ("msedge.exe", "brave.exe", "chatgpt.exe"):
        raise RuntimeError(f"Foreground app is {exe!r}, expected Edge/Brave/ChatGPT")
    if not title.strip():
        raise RuntimeError("The selected window has no title")
    view = composer_bounds(hwnd)
    if view.get("name") not in ("Pergunte ao ChatGPT", "Ask anything", "Ask ChatGPT", "Message ChatGPT"):
        raise RuntimeError("Expected the accessible ChatGPT message composer")
    if exe in ("msedge.exe", "brave.exe") and not view.get("conversation_url"):
        raise RuntimeError("Cannot verify ChatGPT conversation address; calibration refused")
    rect = window_rect(hwnd)
    point = POINT()
    U.GetCursorPos(ctypes.byref(point))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    rx = (point.x - rect.left) / width
    ry = (point.y - rect.top) / height
    if width < 550 or height < 350 or not (0.05 < rx < 0.95 and 0.3 < ry < 0.99):
        raise RuntimeError("Mouse must be within the lower area of a normal ChatGPT window")
    config = {**DEFAULTS, **read_json(CONFIG)}
    config.update({"window_title": title, "process_name": exe,
                   "conversation_url": view.get("conversation_url", ""),
                   "composer_ratio_x": round(rx, 5), "composer_ratio_y": round(ry, 5),
                   "calibrated": True})
    write_json(CONFIG, config)
    initialize_if_missing(read_json(STATE).get("round", 0), title,
                          path=CONFIG.with_name("conversation-session.json"))
    print(f"Calibrated: {title!r}, {exe}, textbox at ({rx:.3f}, {ry:.3f})")
    print("No message was sent. Start with: py -3 scripts/expert_ai_rpa.py run")


def decision(state: dict, config: dict, pending: list[str],
             ram: float, idle: float, paused: bool) -> str:
    if MIGRATION.exists():
        return "conversation migration pending"
    status = state.get("status", "idle")
    if paused:
        return "paused by PAUSE file"
    if status == "done":
        return "finished" if not pending else "done rejected: tasks remain"
    if status == "blocked":
        return "blocked: " + str(state.get("reason", "inspect JSON"))
    if LIMIT.exists() and status in ("ready", "pending_send"):
        return "platform limit hold (requires manual review)"
    if status == "pending_send":
        age = age_minutes(state.get("draft_started_at"))
        if age is None or age >= config.get("max_pending_send_minutes", 30):
            return "pending send timed out"
        if ram < config["min_free_ram_gib"]:
            return f"low RAM: {ram:.2f} GiB"
        if idle < config["min_user_idle_seconds"]:
            return f"user active ({idle:.0f}s idle)"
        return "retry pending send"
    if status == "running":
        a = age_minutes(state.get("heartbeat_at") or state.get("started_at"))
        return "running: stale heartbeat" if a is not None and a > config["max_running_minutes"] else "running"
    if status in ("requested", "sending"):
        a = age_minutes(state.get("requested_at"))
        return "missing GPT acknowledgement" if a is None or a > config["max_unacknowledged_minutes"] else "awaiting GPT acknowledgement"
    if status != "ready":
        return f"unrecognized status: {status}"
    if not pending:
        return "no pending tasks; GPT must validate final reviews and mark done"
    if config.get("max_auto_requests", 0) > 0 and int(state.get("round", 0)) >= int(config["max_auto_requests"]):
        return "test request limit reached"
    if not config.get("calibrated"):
        return "calibration required"
    if ram < config["min_free_ram_gib"]:
        return f"low RAM: {ram:.2f} GiB"
    if idle < config["min_user_idle_seconds"]:
        return f"user active ({idle:.0f}s idle)"
    if config["safe_mode_enabled"]:
        try:
            verdict = pace_status(config, read_json(USAGE, new_ledger()))
        except (ValueError, TypeError, KeyError) as exc:
            return f"invalid pacing configuration/usage ledger: {exc}"
        if not verdict["allowed"]:
            return f"pacing: {verdict['reason']}"
    return "send"


class RpaDeferred(Exception):
    """ChatGPT is busy or the user already has a message draft."""


class RpaBlocked(Exception):
    """Unsafe or ambiguous draft state; require human inspection."""


def submit_pending_send(config: dict, state: dict) -> str:
    """Retry the UI Send action for the SAME request_id, never retyping.

    A popup, missing Send button or model generation defers the action.
    An empty composer is ambiguous: perhaps the message was sent, so only
    transition to requested and await GPT acknowledgement, never resend.
    """
    request_id = state.get("request_id")
    if not request_id or state.get("status") != "pending_send":
        raise RpaBlocked("No pending_send request_id to retry")
    if user_idle_seconds() < config["min_user_idle_seconds"]:
        raise RpaDeferred("User active; respecting idle window")
    windows = matching_windows(config)
    if len(windows) != 1:
        raise RpaDeferred("Calibrated ChatGPT window unavailable or ambiguous")
    hwnd = windows[0]
    U.ShowWindow(hwnd, 9)
    if not U.SetForegroundWindow(hwnd):
        raise RpaDeferred("Popup prevents restoring ChatGPT focus")
    time.sleep(0.3)
    if U.GetForegroundWindow() != hwnd:
        raise RpaDeferred("Another window still has focus")
    view = composer_bounds(hwnd)
    if config.get("conversation_url") and view.get("conversation_url") != config["conversation_url"]:
        raise RpaDeferred("ChatGPT switched to another conversation")
    if view.get("generating"):
        raise RpaDeferred("ChatGPT is still generating")
    if not view.get("request_id_present"):
        if view.get("text_length", 0) == 0 and state.get("draft_typed", False):
            # The original message might have been sent and the composer cleared.
            # No second typing/clicking is permitted; await GPT acknowledgement.
            updated = {**state, "status": "requested", "requested_at": now(),
                       "updated_at": now(),
                       "delivery_note": "Draft disappeared; waiting for confirmation without retrying"}
            write_json(STATE, updated)
            logging.warning("Draft disappeared for %s; awaiting GPT ack, no resend", request_id)
            return "awaiting_ack"
        raise RpaBlocked("Pending message is incomplete or has a different draft")
    if not view.get("send_button_enabled"):
        raise RpaDeferred("Send button not available (popup, UI transition or disabled)")
    # Only one attempt per poll, with an exact request_id verification in PowerShell.
    script = ROOT / "scripts" / "expert_ai_composer.ps1"
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(script), "-WindowHandle", str(hwnd),
         "-RequestId", request_id,
         "-ExpectedConversationUrl", config.get("conversation_url", ""),
         "-InvokeSend"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=15,
    )
    if result.returncode:
        raise RpaDeferred("Send button refused; will recheck same draft: "
                          + result.stderr[-220:])
    try:
        invoked = json.loads(result.stdout).get("invoked") is True
    except (ValueError, TypeError):
        invoked = False
    if not invoked:
        raise RpaDeferred("Send action not confirmed; inspect next time")
    current = read_json(STATE)
    if current.get("request_id") == request_id and current.get("status") == "pending_send":
        write_json(STATE, {**current, "status": "requested",
                           "requested_at": now(), "updated_at": now(),
                           "delivery_note": "Send button invoked, waiting for GPT ack"})
    logging.info("ChatGPT Send invoked for %s (no duplicate)", request_id)
    return "invoked"


def send_once(config: dict, state: dict) -> None:
    """Prepare one message, then submit it or leave it pending for safe retry."""
    windows = matching_windows(config)
    if len(windows) != 1:
        raise RpaDeferred("Expected exactly one calibrated ChatGPT window")
    hwnd = windows[0]
    rect = window_rect(hwnd)
    if rect.right - rect.left < 550 or rect.bottom - rect.top < 350:
        raise RpaDeferred("ChatGPT window too small")
    bounds = composer_bounds(hwnd)
    if config.get("conversation_url") and bounds.get("conversation_url") != config["conversation_url"]:
        raise RpaDeferred("ChatGPT switched to another conversation")
    if bounds.get("generating"):
        raise RpaDeferred("ChatGPT is generating")
    if bounds.get("text_length", 0) > 0:
        raise RpaDeferred("Composer contains another draft")
    x = bounds["x"] + bounds["width"] // 2
    y = bounds["y"] + bounds["height"] // 2
    if not (rect.left < x < rect.right and rect.top < y < rect.bottom):
        raise RpaDeferred("Composer is outside ChatGPT window")
    if user_idle_seconds() < config["min_user_idle_seconds"]:
        raise RpaDeferred("User became active before UI interaction")
    # A popup must be dismissed before creating a new request_id.
    U.ShowWindow(hwnd, 9)
    if not U.SetForegroundWindow(hwnd):
        raise RpaDeferred("Popup prevented focus, retry without changing JSON")
    time.sleep(0.4)
    if U.GetForegroundWindow() != hwnd:
        raise RpaDeferred("Another window stole focus before typing")

    cursor = POINT()
    U.GetCursorPos(ctypes.byref(cursor))
    try:
        if config.get("conversation_url") and composer_bounds(hwnd).get("conversation_url") != config["conversation_url"]:
            raise RpaDeferred("ChatGPT switched conversations before typing")
        click_at(x, y)
        if U.GetForegroundWindow() != hwnd:
            raise RpaDeferred("Popup stole focus before typing")
        if read_json(STATE) != state:
            raise RpaDeferred("Checkpoint changed during focus acquisition")
        request_id = uuid.uuid4().hex[:12]
        # Reserve usage conservatively BEFORE keyboard injection; a crash may
        # count an unsent request, but can never undercount or double-send it.
        ledger = read_json(USAGE, new_ledger())
        ledger = record_attempt(config, ledger, request_id)
        write_json(USAGE, ledger)
        drafted = {
            **state, "status": "pending_send", "request_id": request_id,
            "round": int(state.get("round", 0)) + 1,
            "draft_started_at": now(), "draft_typed": False,
            "updated_at": now(), "reason": "",
        }
        # Persist before typing, so a crash cannot generate a second ID.
        write_json(STATE, drafted)
        text = compact_message(config["message"], request_id)
        send_text(text, expected_hwnd=hwnd)
        written = read_json(STATE)
        if written.get("status") != "pending_send" or written.get("request_id") != request_id:
            raise RpaBlocked("Checkpoint changed while preparing draft")
        written["draft_typed"] = True
        written["updated_at"] = now()
        write_json(STATE, written)
        # UI may still be transitioning or a popup may have appeared.
        # A failure here does NOT mark blocked; the same draft will be retried.
        submit_pending_send(config, written)
    finally:
        # Keep the user's cursor where it was, even if a popup interrupted us.
        U.SetCursorPos(cursor.x, cursor.y)


def recover_pending(max_minutes: int = 10) -> None:
    """Manual retry uses the identical safe pending_send logic as the supervisor."""
    lock = acquire_lock()
    try:
        deadline = time.monotonic() + max_minutes * 60
        while time.monotonic() < deadline:
            state = read_json(STATE)
            if state.get("status") != "pending_send" or PAUSE.exists():
                print("No active pending_send draft, or supervisor is paused")
                return
            config = {**DEFAULTS, **read_json(CONFIG)}
            action = decision(state, config, pending_tasks(), free_ram_gib(),
                              user_idle_seconds(), False)
            if action == "retry pending send":
                try:
                    print(submit_pending_send(config, state))
                    return
                except RpaDeferred as exc:
                    logging.info("Still waiting for safe send: %s", exc)
            elif action == "pending send timed out":
                print("Pending draft expired; manual review required")
                return
            time.sleep(10)
        print("Recovery timed out; draft and request_id preserved")
    finally:
        lock.close()


def show_status() -> None:
    config = {**DEFAULTS, **read_json(CONFIG)}
    state = read_json(STATE)
    pending = pending_tasks(config.get("task_prefix", "APP"))
    print(json.dumps({
        "state": state,
        "periodic_check_window_minutes": [config["min_periodic_minutes"],
                                          config["max_periodic_minutes"]],
        "calibrated": config["calibrated"], "pending_count": len(pending),
        "safe_mode_enabled": config["safe_mode_enabled"],
        "breaks_enabled": config["breaks_enabled"],
        "pacing": pace_status(config, read_json(USAGE, new_ledger())),
        "monitor": read_json(MONITOR),
        "next_tasks": pending[:6], "paused": PAUSE.exists(),
        "conversation_budget": context_budget(state.get("round", 0), read_session()),
        "ram_gib": round(free_ram_gib(), 2),
        "user_idle_seconds": round(user_idle_seconds(), 1),
    }, indent=2, ensure_ascii=False))


def acquire_lock():
    import msvcrt
    RUNTIME.mkdir(parents=True, exist_ok=True)
    file = LOCKFILE.open("a+b")
    try:
        msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        return file
    except OSError:
        file.close()
        raise RuntimeError("RPA supervisor already running")


def periodic_check_delay_seconds(config: dict) -> float:
    """Sample a bounded, less predictable 10–20 minute health-check interval."""
    minimum = float(config["min_periodic_minutes"])
    maximum = float(config["max_periodic_minutes"])
    if not (10 <= minimum < maximum <= 20):
        raise ValueError("Periodic window must stay between 10 and 20 minutes")
    # Triangular sampling favors the center, without an exact repeating cadence.
    return random.triangular(minimum, maximum, (minimum + maximum) / 2) * 60


def wait_for_change(state: dict, config: dict, timeout_seconds: float,
                    monitor: dict | None = None) -> str:
    """Wake on GPT state changes or when the sampled periodic check is due.

    The randomized interval is a health-check fallback, not an artificial
    delay when GPT marks a checkpoint ready.
    """
    until = time.monotonic() + timeout_seconds
    original_status = (state.get("status"), state.get("request_id"), state.get("round"))
    original_pause = PAUSE.exists()
    original_config = CONFIG.stat().st_mtime_ns if CONFIG.exists() else 0
    while time.monotonic() < until:
        time.sleep(min(5.0, max(0.1, until - time.monotonic())))
        if monitor is not None:
            write_monitor({**monitor, "updated_at": now(),
                           "paused": PAUSE.exists(),
                           "platform_limit_hold": LIMIT.exists()})
        next_state = read_json(STATE)
        next_status = (next_state.get("status"), next_state.get("request_id"),
                       next_state.get("round"))
        if next_status != original_status:
            return "GPT state changed"
        if PAUSE.exists() != original_pause:
            return "pause state changed"
        next_config = CONFIG.stat().st_mtime_ns if CONFIG.exists() else 0
        if next_config != original_config:
            return "configuration changed"
    return "periodic health check"


def run(once: bool = False, dry_run: bool = False) -> None:
    lock = acquire_lock()
    last_action = None
    last_context_notice = None
    try:
        logging.info("Supervisor active: event-driven completion plus configurable periodic checks")
        while True:
            config = {**DEFAULTS, **read_json(CONFIG)}
            state = read_json(STATE)
            pending = pending_tasks(config.get("task_prefix", "APP"))
            ram, idle = free_ram_gib(), user_idle_seconds()
            action = decision(state, config, pending, ram, idle, PAUSE.exists())
            try:
                mode = pace_status(config, read_json(USAGE, new_ledger()))
            except (ValueError, TypeError, KeyError) as exc:
                mode = {"allowed": False, "reason": f"invalid config or ledger: {exc}",
                        "next_eligible_at": None}
            if not mode["allowed"] and action == "send":
                action = "pacing: " + mode["reason"]
            if action != last_action or once or dry_run:
                logging.info("state=%s pending=%d RAM=%.2fGiB idle=%.0fs decision=%s",
                             state.get("status"), len(pending), ram, idle, action)
            last_action = action
            budget = context_budget(state.get("round", 0), read_session())
            notice = (budget["level"], budget["rounds"])
            if (budget["level"] in ("suggest", "recommend") and notice != last_context_notice
                    and state.get("status") == "ready"):
                logging.warning("Conversa longa: %s. Migração pelo HUD na aba Conversa.",
                                budget["label"])
                last_context_notice = notice
            if action == "finished":
                print("All tasks concluded and verified by GPT; stopping supervisor.")
                return
            if action == "test request limit reached":
                print("Test message limit reached; stopping supervisor.")
                return
            if action in ("send", "retry pending send") and not dry_run:
                if read_json(STATE) != state:
                    logging.info("Checkpoint changed before UI action")
                else:
                    try:
                        if action == "send":
                            send_once(config, state)
                        else:
                            submit_pending_send(config, state)
                    except RpaDeferred as e:
                        logging.info("Transient UI issue; same request will retry: %s", e)
                    except Exception as exc:
                        logging.exception("Unsafe RPA state; pausing for inspection")
                        current = read_json(STATE)
                        if current.get("status") == "pending_send":
                            write_json(STATE, {**current, "status": "blocked",
                                              "reason": f"Unsafe or incomplete message draft: {exc}"[:500],
                                              "updated_at": now()})
                        PAUSE.touch()
                        return
            elif action in ("missing GPT acknowledgement", "running: stale heartbeat",
                            "done rejected: tasks remain", "pending send timed out") and not dry_run:
                logging.error("Manual intervention needed: %s. Pausing.", action)
                if action == "pending send timed out":
                    current = read_json(STATE)
                    if current.get("status") == "pending_send":
                        write_json(STATE, {**current, "status": "blocked",
                                          "reason": "Draft could not be submitted within the configured retry window",
                                          "updated_at": now()})
                PAUSE.touch()
            if once or dry_run:
                print(action)
                return
            # Ready: retry quickly after idle/ChatGPT stops generating.
            # Running/requested: draw a fresh 10–20 minute fallback interval;
            # GPT state/config changes still wake us immediately (within ~5s).
            next_check_seconds = (10 if action in ("send", "retry pending send") or
                                  action.startswith(("user active", "low RAM", "calibration", "pacing:"))
                                  else periodic_check_delay_seconds(config))
            if next_check_seconds >= 600:
                logging.info("Next periodic health check in %.1f minutes (randomized)",
                             next_check_seconds / 60)
            monitor = {
                "schema_version": 1,
                "process_id": os.getpid(),
                "state": state.get("status"),
                "request_id": state.get("request_id"),
                "round": state.get("round"),
                "action": action,
                "updated_at": now(),
                "next_check_at": (datetime.now(timezone.utc)
                                  + timedelta(seconds=next_check_seconds)).isoformat(),
                "next_check_kind": ("interactive" if next_check_seconds < 600
                                     else "periodic"),
                "paused": PAUSE.exists(),
                "platform_limit_hold": LIMIT.exists(),
                "safe_mode_enabled": config["safe_mode_enabled"],
                "breaks_enabled": config["breaks_enabled"],
                "conversation_budget": budget,
            }
            write_monitor(monitor)
            wake_reason = wait_for_change(state, config, next_check_seconds, monitor=monitor)
            if wake_reason == "GPT state changed":
                logging.info("GPT checkpoint updated; checking next stage immediately")
    finally:
        lock.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "calibrate", "calibrate-auto", "migrate-attach", "check", "run", "pause", "resume", "recover"])
    args = parser.parse_args()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(LOGFILE, encoding="utf-8"), logging.StreamHandler()],
    )
    if args.command == "status":
        show_status()
    elif args.command == "calibrate":
        calibrate()
    elif args.command == "calibrate-auto":
        calibrate_auto()
    elif args.command == "migrate-attach":
        migrate_attach()
    elif args.command == "check":
        run(once=True, dry_run=True)
    elif args.command == "recover":
        recover_pending()
    elif args.command == "pause":
        PAUSE.touch()
        print("Paused; running supervisor will stop sending.")
    elif args.command == "resume":
        if MIGRATION.exists():
            raise RuntimeError("Finalize a migração antes de retomar os envios.")
        PAUSE.unlink(missing_ok=True)
        print("Resumed; a blocked JSON state must still be inspected manually.")
    else:
        run()


if __name__ == "__main__":
    main()
