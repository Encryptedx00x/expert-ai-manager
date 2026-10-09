"""Small, explicit conversation-budget hints. Not a ChatGPT token counter.

The marker tracks requests per conversation, using the existing round number.
It never reads other conversations or modifies a development checkpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import uuid

ROOT = Path(__file__).resolve().parent.parent
SESSION = ROOT / ".dev-loop" / "conversation-session.json"

SOFT_ROUNDS = 5
STRONG_ROUNDS = 8

COMPACT_INSTRUCTIONS = (
    "Nesta rodada priorize 2 a 4 tarefas RELACIONADAS quando viável; "
    "se depender de serviços indisponíveis ou exceder o tempo, faça só uma. "
    "Use resultados resumidos de ferramentas (git diff --stat, trechos e erros), "
    "evite reler arquivos inteiros e não despeje logs enormes. "
    "Preserve testes completos, revisão crítica de segurança, documentação, commits "
    "e a verificação individual de cada tarefa. "
    "Ao concluir, informe em até 6 linhas commit, testes, tarefas e próximo passo."
)


def compact_message(message: str, request_id: str, enabled: bool = True) -> str:
    """Keep messages single-line for safe text injection into a chat composer."""
    instruction = " ".join(COMPACT_INSTRUCTIONS.split()) if enabled else ""
    parts = [" ".join(message.split())]
    if instruction and instruction not in message:
        parts.append(instruction)
    parts.append(f"[request_id: {request_id}]")
    return " ".join(parts)


def read_session(path: Path = SESSION) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}  # Unknown is safer than crashing the development supervisor.
    return value if isinstance(value, dict) else {}


def write_session(data: dict, path: Path = SESSION) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def start_session(round_number: int, window_title: str, *, known_new: bool,
                  path: Path = SESSION) -> dict:
    """Only call for initial setup or after an explicitly verified migration."""
    baseline = max(0, int(round_number))
    result = {
        "schema_version": 1,
        "start_round": baseline,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window_title": window_title,
        "baseline_known": known_new,
    }
    write_session(result, path)
    return result


def initialize_if_missing(round_number: int, window_title: str,
                          path: Path = SESSION) -> dict:
    existing = read_session(path)
    return existing if existing else start_session(
        round_number, window_title, known_new=False, path=path,
    )


def context_budget(round_number: int, session: dict, *,
                   soft_rounds: int = SOFT_ROUNDS,
                   strong_rounds: int = STRONG_ROUNDS) -> dict:
    """Estimate round count; request length/tool output/token usage are unknown."""
    if not session:
        return {"level": "unknown", "rounds": None,
                "label": "Sem histórico desta conversa; migração preventiva disponível"}
    start = session.get("start_round")
    if not isinstance(start, int) or start < 0:
        return {"level": "unknown", "rounds": None,
                "label": "Marco de início inválido; confira a conversa"}
    current = int(round_number)
    if current < start:
        return {"level": "unknown", "rounds": None,
                "label": "Rodada anterior ao início registrado; confira o checkpoint"}
    if not isinstance(soft_rounds, int) or not isinstance(strong_rounds, int) or (
        soft_rounds < 1 or strong_rounds <= soft_rounds
    ):
        raise ValueError("conversation round thresholds must be increasing positive integers")
    rounds = current - start
    known = bool(session.get("baseline_known"))
    if not known:
        return {"level": "unknown", "rounds": rounds,
                "label": f"{rounds} rodadas observadas; histórico anterior desconhecido"}
    if rounds >= strong_rounds:
        level, label = "recommend", f"{rounds} rodadas neste chat; planeje migrar agora"
    elif rounds >= soft_rounds:
        level, label = "suggest", f"{rounds} rodadas neste chat; considere uma conversa nova"
    else:
        level, label = "ok", f"{rounds} rodadas neste chat (estimativa, não tokens)"
    return {"level": level, "rounds": rounds, "label": label}
