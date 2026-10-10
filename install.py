"""Install Expert AI Manager into a chosen project without overwriting its data.

Usage:
    py -3 -B install.py --project "C:\\Projects\\MyApp" --name "My App" --prefix APP
    py -3 -B install.py --project "C:\\Projects\\MyApp" --name "My App" --prefix APP --update

Requires Windows, Python 3.11+; no third-party Python packages.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
from datetime import datetime, timezone
import uuid

PACKAGE = Path(__file__).resolve().parent
SCRIPTS = [
    "expert_ai_rpa.py", "expert_ai_state.py", "expert_ai_composer.ps1",
    "expert_ai_safety.py", "expert_ai_control.py", "expert_ai_migration.py",
    "expert_ai_context.py", "expert_ai_auto_chat.py", "expert_ai_chat_nav.ps1",
    "expert_ai_hud_data.py", "expert_ai_hud.py",
]
TESTS = [
    "test_expert_ai_rpa.py", "test_expert_ai_rpa_delivery.py",
    "test_expert_ai_state.py", "test_expert_ai_safety.py",
    "test_expert_ai_hud.py", "test_expert_ai_migration.py",
    "test_expert_ai_context.py", "test_expert_ai_auto_chat.py",
]
DEFAULT_CONFIG = {
    "schema_version": 1,
    "calibrated": False,
    "process_name": "msedge.exe",
    "window_title": "",
    "composer_ratio_x": None,
    "composer_ratio_y": None,
    "task_prefix": "APP",
    "project_name": "My Project",
    "min_periodic_minutes": 10,
    "max_periodic_minutes": 20,
    "min_user_idle_seconds": 90,
    "min_free_ram_gib": 2.0,
    "max_auto_requests": 0,
    "max_unacknowledged_minutes": 45,
    "max_pending_send_minutes": 30,
    "max_running_minutes": 120,
    "automatic_conversation_handoff": True,
    "handoff_after_rounds": 8,
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

def write_json_if_absent(path: Path, data: dict):
    if not path.exists():
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    return False

def install(project: Path, name: str, prefix: str, *, update: bool = False):
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,16}", prefix):
        raise ValueError("Prefix must be 2–17 uppercase letters/digits, e.g. CRM or APP")
    if not project.is_dir():
        raise ValueError("Project directory must exist: " + str(project))
    if not name.strip() or len(name) > 120:
        raise ValueError("Specify a descriptive project name (1–120 characters)")
    scripts = project / "scripts"
    docs = project / "docs"
    runtime = project / ".dev-loop"
    for folder in (scripts, docs, runtime):
        folder.mkdir(parents=True, exist_ok=True)

    copied = []
    skipped = []
    for filename in SCRIPTS + TESTS:
        source = PACKAGE / "scripts" / filename
        target = scripts / filename
        if not source.is_file():
            raise FileNotFoundError("Distribution is incomplete: " + str(source))
        if target.exists():
            if not update or target.read_bytes() == source.read_bytes():
                skipped.append(filename)
                continue
            # Never put backups beside tracked source files; keep Git clean.
            backups = runtime / "backups"
            backups.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup = backups / f"{filename}.backup-{timestamp}-{uuid.uuid4().hex[:8]}"
            shutil.copy2(target, backup)
        shutil.copy2(source, target)
        copied.append(filename)

    cfg = {**DEFAULT_CONFIG, "task_prefix": prefix, "project_name": name}
    cfg["message"] = (
        f"CONTINUAR {name}: trabalhe somente neste projeto na conversa atual, usando "
        f"Remote Desktop Commander. Leia AGENTS.md, docs/TASKS.md e docs/STATE.md. "
        f"Valide o request_id na mensagem e em .dev-loop/chat-state.json; "
        f"use py -3 -B scripts/expert_ai_state.py ack <request_id> para marcar running. "
        f"Trabalhe em até 2 a 4 tarefas relacionadas, quando viável; teste e revise o diff, "
        f"atualize tarefas e faça commit apenas quando seguro. Use heartbeat em etapas longas. "
        f"Antes de encerrar, marque ready, blocked ou done com o mesmo request_id. "
        f"Informe resumo dos testes e commit. Preserve os demais projetos e serviços. "
        f"Não fabrique conclusões nem contorne limites da plataforma."
    )
    new_config = write_json_if_absent(runtime / "rpa-config.json", cfg)
    new_state = write_json_if_absent(runtime / "chat-state.json", {
        "schema_version": 1, "status": "ready", "round": 0,
        "request_id": "", "summary": "Initialized; not yet calibrated"
    })
    notes = {
        "AGENTS.md": "Template principal de regras",
        "docs/TASKS.md": "Checklist por etapa",
        "docs/STATE.md": "Checkpoint do projeto",
        "docs/ARCHITECTURE.md": "Decisões e arquitetura",
    }
    created_docs = []
    for filename in notes:
        source = PACKAGE / "templates" / filename
        target = project / filename
        if not target.exists() and source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                source.read_text(encoding="utf-8")
                .replace("{{PROJECT_NAME}}", name).replace("{{TASK_PREFIX}}", prefix),
                encoding="utf-8"
            )
            created_docs.append(filename)

    # Keep onboarding instructions and prompts next to each new project.
    # They are documentation, not executable state, and are never overwritten.
    handbook = docs / "expert-ai-manager"
    handbook.mkdir(parents=True, exist_ok=True)
    installed_guides = []
    for filename in (
        "COMECE_AQUI.md", "PLUGINS_E_SKILLS.md",
        "PROMPTS_PRONTOS.md", "PROMPT_PLANEJAMENTO.md",
        "TROCA_DE_CONVERSA.md",
    ):
        source = PACKAGE / "docs" / filename
        target = handbook / filename
        if not source.is_file():
            raise FileNotFoundError("Distribution is incomplete: " + str(source))
        if not target.exists():
            shutil.copy2(source, target)
            installed_guides.append(filename)

    ignore = project / ".gitignore"
    content = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    if ".dev-loop/" not in content.splitlines():
        with ignore.open("a", encoding="utf-8") as file:
            file.write(("\n" if content and not content.endswith("\n") else "") + "\n.dev-loop/\n")
    print(f"Expert AI Manager: {name} [{prefix}]")
    print("Project:", project)
    print("Scripts installed:", len(copied), "| skipped:", len(skipped))
    print("Created project docs:", created_docs)
    print("Added onboarding guides:", installed_guides)
    print("Created configuration:", new_config, "| created checkpoint:", new_state)
    print("State and usage files remain local and ignored by Git.")
    print("FIRST: Open docs/expert-ai-manager/COMECE_AQUI.md in this project.")
    print("SECOND: Copy Prompt A from docs/expert-ai-manager/PROMPTS_PRONTOS.md")
    print("THIRD: Review the plan; only then calibrate and run the supervisor.")
    print("Calibration (Edge/Brave ChatGPT chat in front): py -3 -B scripts/expert_ai_rpa.py calibrate-auto")
    print("HUD: pyw -3 -B scripts/expert_ai_hud.py")
    print("Supervisor, after approval: py -3 -B -u scripts/expert_ai_rpa.py run")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--update", action="store_true", help="Back up and replace only previously installed scripts")
    args = parser.parse_args()
    install(args.project.resolve(), args.name, args.prefix, update=args.update)


if __name__ == "__main__":
    main()
