"""Expert AI Manager: lightweight Windows HUD for supervised development.

Tkinter only. Never sends chat messages or starts a browser.
The RPA is controlled by local JSON/PAUSE markers, not hidden UI behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from expert_ai_control import RUNTIME, command, load, atomic_save, SETTABLE
from expert_ai_hud_data import progress_snapshot

SETTINGS = RUNTIME / "hud-preferences.json"
REFRESH_MS = 1500
BG = "#f7f8fa"
WHITE = "#ffffff"
INK = "#202a39"
MUTED = "#5e6b7d"
ACCENT = "#176b55"
BORDER = "#dfe5ed"
MONO = ("Consolas", 10)

def hms(seconds: int | None) -> str:
    if seconds is None:
        return "Aguardando atualização"
    minutes, seconds = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    return f"{minutes}m {seconds:02d}s"

def short(text: object, limit: int = 95) -> str:
    value = str(text or "—").replace("\r", " ").replace("\n", " ")
    return value if len(value) <= limit else value[:limit - 1] + "…"

class HUD:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Expert AI Manager")
        self.root.configure(bg=BG)
        self.root.minsize(395, 410)
        self.root.geometry(load(SETTINGS, {}).get("geometry", "445x640+80+90"))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.resizable(True, True)
        self.topmost = tk.BooleanVar(value=bool(load(SETTINGS, {}).get("always_on_top", True)))
        self.root.attributes("-topmost", self.topmost.get())
        self.vars = {key: tk.StringVar(value="…") for key in (
            "status", "decision", "round", "check", "pacing", "usage",
            "commit", "quality", "task", "summary", "tasks", "heartbeat",
        )}
        self.safe_var = tk.BooleanVar(value=True)
        self.breaks_var = tk.BooleanVar(value=True)
        self.tab = ttk.Notebook(root)
        self.tab.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_overview = ttk.Frame(self.tab, padding=12)
        self.tab_tasks = ttk.Frame(self.tab, padding=10)
        self.tab_settings = ttk.Frame(self.tab, padding=10)
        self.tab.add(self.tab_overview, text="Visão geral")
        self.tab.add(self.tab_tasks, text="Tarefas")
        self.tab.add(self.tab_settings, text="Configuração")
        self.build_overview()
        self.build_tasks()
        self.build_settings()
        self.footer = ttk.Label(root, text="RPA local • sem novas mensagens para atualizar o HUD",
                                foreground=MUTED)
        self.footer.pack(anchor="w", padx=16, pady=(0, 8))
        self.last_error = None
        self.poll()

    def headline(self, parent, title):
        label = ttk.Label(parent, text=title, font=("Segoe UI", 11, "bold"))
        label.pack(anchor="w", pady=(8, 4))
        return label

    def value_row(self, parent, label, key, wrap=390):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=3)
        ttk.Label(frame, text=label, width=15, foreground=MUTED).pack(side="left", anchor="n")
        ttk.Label(frame, textvariable=self.vars[key], font=("Segoe UI", 9),
                  wraplength=wrap-110, justify="left").pack(side="left", fill="x", expand=True)

    def action(self, command_name):
        try:
            command(command_name)
            self.poll()
        except Exception as exc:
            messagebox.showerror("Falha ao alterar RPA", str(exc), parent=self.root)

    def build_overview(self):
        tab = self.tab_overview
        self.headline(tab, "Supervisor")
        ttk.Label(tab, textvariable=self.vars["status"], font=("Segoe UI", 17, "bold"),
                  foreground=ACCENT).pack(anchor="w", pady=2)
        for label, key in (
            ("Situação", "decision"), ("Rodada", "round"),
            ("Próx. verificação", "check"),
            ("Próx. solicitação", "pacing"), ("Uso recente", "usage")):
            self.value_row(tab, label, key)
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(8, 4))
        ttk.Button(bar, text="Pausar", command=lambda: self.action("pause")).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Retomar", command=lambda: self.action("resume")).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Limite detectado", command=lambda: self.action("limit-hold")).pack(side="left")
        self.headline(tab, "Última entrega")
        for label, key in (("Commit", "commit"), ("Tarefa", "task"), ("Testes", "quality"),
                           ("Resumo", "summary")):
            self.value_row(tab, label, key)
        self.headline(tab, "Progresso")
        self.value_row(tab, "Checklist", "tasks")
        self.progressbar = ttk.Progressbar(tab, mode="determinate", maximum=100)
        self.progressbar.pack(fill="x", pady=(6, 3))
        options = ttk.Frame(tab)
        options.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(options, text="Manter acima", variable=self.topmost,
                        command=self.set_topmost).pack(side="left")
        ttk.Button(options, text="Ver tarefas", command=lambda: self.tab.select(self.tab_tasks)).pack(side="right")

    def build_tasks(self):
        tab = self.tab_tasks
        ttk.Label(tab, text="Atualizado diretamente de docs/TASKS.md",
                  foreground=MUTED).pack(anchor="w", pady=(0, 5))
        columns = ("state", "id", "title")
        frame = ttk.Frame(tab)
        frame.pack(fill="both", expand=True)
        self.task_table = ttk.Treeview(frame, columns=columns, show="headings", height=15)
        self.task_table.heading("state", text="Estado")
        self.task_table.heading("id", text="ID")
        self.task_table.heading("title", text="Tarefa")
        self.task_table.column("state", width=64, anchor="w", stretch=False)
        self.task_table.column("id", width=86, stretch=False)
        self.task_table.column("title", width=250, stretch=True)
        self.task_table.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(frame, command=self.task_table.yview)
        scrollbar.pack(side="right", fill="y")
        self.task_table.configure(yscrollcommand=scrollbar.set)
        self.task_table.tag_configure("done", foreground=ACCENT)
        self.task_table.tag_configure("active", foreground="#9a620f")
        self.task_counts = ttk.Label(tab, text="…", foreground=MUTED)
        self.task_counts.pack(anchor="w", pady=8)

    def build_settings(self):
        tab = self.tab_settings
        self.headline(tab, "Conforto e limites")
        ttk.Checkbutton(tab, text="Modo Seguro", variable=self.safe_var,
                        command=self.change_safe).pack(anchor="w", pady=4)
        ttk.Checkbutton(tab, text="Descansos programados", variable=self.breaks_var,
                        command=self.change_breaks).pack(anchor="w", pady=4)
        ttk.Label(tab, text="Os limites reduzem volume de uso. Não ocultam a automação.",
                  foreground=MUTED, wraplength=370).pack(anchor="w", pady=(0, 8))
        self.entries = {}
        labels = {
            "min_minutes_between_requests": "Mín. entre envios (min)",
            "max_requests_per_hour": "Máx. por hora",
            "max_requests_per_24_hours": "Máx. em 24 horas",
            "short_break_every_requests": "Pausa curta a cada",
            "short_break_min_minutes": "Pausa curta mín. (min)",
            "short_break_max_minutes": "Pausa curta máx. (min)",
            "long_break_every_requests": "Pausa longa a cada",
            "long_break_min_minutes": "Pausa longa mín. (min)",
            "long_break_max_minutes": "Pausa longa máx. (min)",
        }
        for key, label in labels.items():
            line = ttk.Frame(tab)
            line.pack(fill="x", pady=3)
            ttk.Label(line, text=label, width=27).pack(side="left")
            entry = ttk.Entry(line, width=10, font=MONO)
            entry.pack(side="right")
            entry.bind("<Return>", lambda _e, k=key: self.save_entry(k))
            self.entries[key] = entry
        ttk.Label(tab, text="Pressione Enter após alterar um valor.",
                  foreground=MUTED).pack(anchor="w", pady=(8, 8))
        ttk.Button(tab, text="Ver dados atualizados", command=self.poll).pack(anchor="w")
        ttk.Separator(tab).pack(fill="x", pady=12)
        ttk.Button(tab, text="Limpar alerta de limite (mantém pausa)",
                   command=lambda: self.action("limit-clear")).pack(anchor="w")
        ttk.Label(tab, text="Somente remova o alerta depois de verificar os limites da plataforma.",
                  foreground=MUTED, wraplength=370).pack(anchor="w", pady=5)

    def set_topmost(self):
        self.root.attributes("-topmost", self.topmost.get())

    def change_safe(self):
        self.action("safe-on" if self.safe_var.get() else "safe-off")

    def change_breaks(self):
        self.action("breaks-on" if self.breaks_var.get() else "breaks-off")

    def save_entry(self, field):
        entry = self.entries[field]
        try:
            command("set", field, entry.get().strip())
            entry.configure(background=WHITE)
            self.poll()
        except Exception as exc:
            messagebox.showerror("Valor inválido", str(exc), parent=self.root)

    def update_tasks(self, data: dict):
        rows = [("Pendente", t) for t in data["pending_tasks"]] + [
            ("Concluída", t) for t in reversed(data["completed_tasks"])]
        current_selection = self.task_table.selection()
        selected_id = self.task_table.item(current_selection[0], "values")[1] if current_selection else None
        signatures = [(label, t["id"], t["title"]) for label, t in rows]
        if getattr(self, "_task_sig", None) != signatures:
            items = self.task_table.get_children()
            if items:
                self.task_table.delete(*items)
            for label, task in rows:
                item = self.task_table.insert("", "end",
                                              values=(label, task["id"], short(task["title"], 130)),
                                              tags=("done" if label == "Concluída" else "active",))
                if task["id"] == selected_id:
                    self.task_table.selection_set(item)
            self._task_sig = signatures
        counts = data["task_counts"]
        total = counts["done"] + counts["active"] + counts["todo"]
        percent = round(counts["done"] / total * 100) if total else 0
        self.progressbar["value"] = percent
        self.vars["tasks"].set(
            f'{counts["done"]} concluídas · {counts["active"]} em andamento · '
            f'{counts["todo"]} pendentes · {counts["deferred"]} adiadas'
        )
        self.task_counts.configure(text=f"{percent}% das tarefas ativas concluídas")

    def poll(self):
        try:
            data = progress_snapshot()
            state = data["state"]
            paused = data["paused"]
            color = "#b34b2e" if paused or data["limit_hold"] or state == "blocked" else ACCENT
            self.vars["status"].set(("PAUSADO · " if paused else "") + state.upper())
            self.vars["decision"].set(
                ("Supervisor ativo · " if data["supervisor_live"] else "Supervisor não confirmado · ")
                + short(data["supervisor_action"], 50)
            )
            self.vars["round"].set(f'{data["round"]} · ID {short(data["request_id"], 15)}')
            self.vars["check"].set(hms(data["next_check_seconds"]) +
                (f' ({data["next_check_kind"]})' if data["supervisor_live"] else ""))
            self.vars["pacing"].set(
                "Pode enviar" if data["pacing_seconds"] in (None, 0)
                else f'{hms(data["pacing_seconds"])} · {data["pacing_reason"]}'
            )
            c = data["config"]
            self.vars["usage"].set(
                f'{data["requests_hour"]}/{c["max_requests_per_hour"]} na hora  ·  '
                f'{data["requests_day"]}/{c["max_requests_per_24_hours"]} em 24h'
            )
            self.vars["commit"].set(short(data["last_commit"], 18))
            self.vars["task"].set(short(data["last_task"], 80))
            self.vars["quality"].set(short(data["last_quality_check"], 170))
            self.vars["summary"].set(short(data["summary"], 170))
            self.safe_var.set(data["safe_mode"])
            self.breaks_var.set(data["breaks_enabled"])
            self.update_tasks(data)
            if self.tab.index("current") == 2 and self.root.focus_get() not in self.entries.values():
                for key, widget in self.entries.items():
                    value = data["config"][key]
                    if widget.get() != str(value):
                        widget.delete(0, tk.END)
                        widget.insert(0, str(value))
            self.last_error = None
        except Exception as exc:
            if self.last_error != str(exc):
                self.vars["decision"].set("Erro de leitura: " + short(str(exc), 110))
                self.last_error = str(exc)
        self.root.after(REFRESH_MS, self.poll)

    def close(self):
        atomic_save(SETTINGS, {"geometry": self.root.geometry(),
                               "always_on_top": self.topmost.get()})
        self.root.destroy()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true",
                        help="Print read-only JSON status without opening UI")
    args = parser.parse_args()
    if args.snapshot:
        print(json.dumps(progress_snapshot(), indent=2, ensure_ascii=False))
        return
    root = tk.Tk()
    theme = ttk.Style(root)
    if "clam" in theme.theme_names():
        theme.theme_use("clam")
    theme.configure("TFrame", background=BG)
    theme.configure("TLabel", background=BG, foreground=INK)
    theme.configure("TCheckbutton", background=BG, foreground=INK)
    HUD(root)
    root.mainloop()

if __name__ == "__main__":
    main()
