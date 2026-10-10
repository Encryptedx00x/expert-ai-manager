"""Guarded ChatGPT browser inspection for conversation-length handoff.

This module reads only visible UI Automation text. It does not infer account
quotas from ordinary messages and never treats account usage limits as a
conversation limit. Navigation/submission are separate explicit actions.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess


def classify_visible_warnings(texts: list[str]) -> str | None:
    """Recognize explicit conversation exhaustion, not mentions of generic limits.

    Unknown UI wording is intentionally ignored. Never infer a quota reset by
    opening another chat. Usage limits take precedence over conversation text.
    """
    if not isinstance(texts, list):
        return None
    normalized = [re.sub(r"\s+", " ", str(text).casefold()).strip()
                  for text in texts if isinstance(text, str)]
    for text in normalized:
        if any(phrase in text for phrase in (
            "you've reached your limit", "you have reached your limit",
            "usage limit", "rate limit", "too many requests",
            "limite de uso", "limite do plano",
            "limite de mensagens da conta",
            "reached your message limit",
        )):
            return "account_limit"
    for text in normalized:
        if any(phrase in text for phrase in (
            "message delivery timed out. please try again.",
            "message delivery timed out",
            "a entrega da mensagem expirou",
            "tempo limite de entrega da mensagem",
        )):
            return "delivery_timeout"
    for text in normalized:
        if any(phrase in text for phrase in (
            "maximum length for this conversation",
            "this conversation has reached its maximum length",
            "this conversation has reached the maximum length",
            "this conversation has reached its limit",
            "conversation has reached the limit",
            "this conversation is too long",
            "conversation is too long",
            "this chat has reached its maximum length",
            "esta conversa atingiu o limite",
            "essa conversa atingiu o limite",
            "esta conversa atingiu o tamanho máximo",
            "essa conversa atingiu o tamanho máximo",
            "esta conversa chegou ao limite",
            "conversa ficou longa demais",
            "limite de tamanho desta conversa",
            "limite de comprimento desta conversa",
        )):
            return "conversation_length"
    return None


def browser_navigation(script: Path, hwnd: int, *,
                       action: str = "inspect",
                       old_url: str = "", expected_new_url: str = "",
                       handoff_id: str = "") -> dict:
    if action not in ("inspect", "open", "send-handoff"):
        raise ValueError("Unknown browser navigation operation")
    cmd = ["powershell.exe", "-NoProfile", "-NonInteractive",
           "-ExecutionPolicy", "Bypass", "-File", str(script),
           "-WindowHandle", str(int(hwnd)), "-Action", action]
    if old_url:
        cmd += ["-OldConversationUrl", old_url]
    if expected_new_url:
        cmd += ["-ExpectedNewChatUrl", expected_new_url]
    if handoff_id:
        cmd += ["-HandoffId", handoff_id]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=18)
    if result.returncode:
        raise RuntimeError("ChatGPT browser navigation/inspection failed: "
                           + result.stderr.strip()[-350:])
    value = json.loads(result.stdout.strip())
    if not isinstance(value, dict):
        raise ValueError("Invalid browser navigation result")
    return value
