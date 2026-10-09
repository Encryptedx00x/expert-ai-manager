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
from expert_ai_hud_data import progress_snapshot, timing_view
from expert_ai_migration import migration_status, recovery_prompt

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
        self.tab_migration = ttk.Frame(self.tab, padding=12)
        self.tab.add(self.tab_overview, text="Visão geral")
        self.tab.add(self.tab_tasks, text="Tarefas")
        self.tab.add(self.tab_settings, text="Configuração")
        self.tab.add(self.tab_migration, text="Conversa")
        self.build_overview()
        self.build_tasks()
        self.build_settings()
        self.build_migration()
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
            ("Acompanhamento", "check"),
            ("Próx. solicitação", "pacing"), ("Uso recente", "usage")):
            self.value_row(tab, label, key)
        self.idle_frame = ttk.Frame(tab)
        self.idle_progress = ttk.Progressbar(self.idle_frame, mode="determinate", maximum=100)
        self.idle_progress.pack(fill="x", pady=(0, 4))
        self.idle_note = ttk.Label(self.idle_frame, text="A contagem reinicia quando você volta a usar o PC.",
                                   foreground=MUTED, wraplength=365)
        self.idle_note.pack(anchor="w")
        bar = ttk.Frame(tab)
        self.action_bar = bar
        bar.pack(fill="x", pady=(8, 4))
        ttk.Button(bar, text="Pausar", command=lambda: self.action("pause")).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Retomar", command=lambda: self.action("resume")).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Limite detectado", command=lambda: self.action("limit-hold")).pack(side="left")
        self.migration_banner = ttk.Label(tab, text="Troca de conversa em andamento. Abra a aba Conversa.",
                                          foreground="#9a620f", wraplength=380)
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

    def build_migration(self):
        tab = self.tab_migration
        self.headline(tab, "Trocar de conversa")
        ttk.Label(
            tab,
            text="Se o chat chegar ao limite, prepare uma troca segura. "
                 "A ferramenta NÃO abre, envia ou troca conversas sozinha.",
            foreground=MUTED, wraplength=370,
        ).pack(anchor="w", pady=(0, 10))
        self.migration_label = ttk.Label(tab, text="Nenhuma troca em andamento.",
                                         font=("Segoe UI", 10, "bold"), wraplength=370)
        self.migration_label.pack(anchor="w", pady=(4, 12))
        ttk.Button(tab, text="1. Preparar troca e pausar envios",
                   command=self.prepare_migration_ui).pack(fill="x", pady=4)
        ttk.Button(tab, text="2. Ver / copiar prompt para o novo chat",
                   command=self.show_migration_prompt).pack(fill="x", pady=4)
        ttk.Label(
            tab,
            text="3. Abra a nova conversa e envie o prompt. Depois, no PowerShell "
                 "do projeto, rode migrate-attach e volte ao Edge durante a contagem.",
            wraplength=370, foreground=MUTED,
        ).pack(anchor="w", pady=(12, 4))
        ttk.Label(
            tab,
            text="py -3 -B scripts\\expert_ai_rpa.py migrate-attach",
            font=MONO, wraplength=370,
        ).pack(anchor="w", pady=4)
        ttk.Label(
            tab,
            text="4. Reconcile a rodada antiga até ready no novo chat. "
                 "Finalize somente depois de verificar os arquivos e o checkpoint.",
            wraplength=370, foreground=MUTED,
        ).pack(anchor="w", pady=(12, 4))
        ttk.Button(tab, text="5. Finalizar e retomar, se seguro",
                   command=self.finish_migration_ui).pack(fill="x", pady=4)
        ttk.Button(tab, text="Cancelar preparação (sem mudar chat)",
                   command=self.cancel_migration_ui).pack(fill="x", pady=(12, 4))
        ttk.Label(
            tab,
            text="A migração preserva request_id, rodada, rascunhos, commits e limites. "
                 "Se houver uma tarefa running, a retomada aguarda a conclusão verificada.",
            wraplength=370, foreground=MUTED,
        ).pack(anchor="w", pady=(10, 0))

    def prepare_migration_ui(self):
        if not messagebox.askyesno(
            "Preparar nova conversa",
            "Pausar novos envios e gerar o prompt para migrar? "
            "O trabalho já iniciado continuará exigindo reconciliação.",
            parent=self.root,
        ):
            return
        try:
            command("migrate-start")
            self.poll()
            self.show_migration_prompt()
        except Exception as exc:
            messagebox.showerror("Não foi possível preparar", str(exc), parent=self.root)

    def show_migration_prompt(self):
        handoff = migration_status()
        if not handoff:
            messagebox.showinfo("Troca de conversa",
                                "Primeiro clique em 'Preparar troca'.", parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Prompt para continuar em outro chat")
        dialog.geometry("650x540")
        dialog.transient(self.root)
        ttk.Label(dialog, text="Copie o texto para a conversa NOVA. Não inicie outro supervisor.",
                  wraplength=590).pack(fill="x", padx=12, pady=(12, 4))
        frame = ttk.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=8)
        scroll = ttk.Scrollbar(frame)
        scroll.pack(side="right", fill="y")
        text = tk.Text(frame, wrap="word", font=("Consolas", 10), yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.configure(command=text.yview)
        content = recovery_prompt(handoff)
        text.insert("1.0", content)
        text.configure(state="disabled")
        actions = ttk.Frame(dialog)
        actions.pack(fill="x", padx=12, pady=(0, 12))

        def copy_prompt():
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("Copiado", "Prompt copiado. Abra o novo chat e cole.",
                                parent=dialog)

        ttk.Button(actions, text="Copiar prompt", command=copy_prompt).pack(side="left")
        ttk.Button(actions, text="Fechar", command=dialog.destroy).pack(side="right")

    def finish_migration_ui(self):
        try:
            command("migrate-finish")
            self.poll()
            messagebox.showinfo("Migração", "Conversa migrada. O supervisor pode continuar "
                                "quando os limites permitirem.", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Migração ainda pendente", str(exc), parent=self.root)

    def cancel_migration_ui(self):
        if not messagebox.askyesno(
            "Cancelar preparação",
            "Continuar usando a conversa anterior? Só cancele se ainda for possível.",
            parent=self.root,
        ):
            return
        try:
            command("migrate-cancel")
            self.poll()
        except Exception as exc:
            messagebox.showerror("Não foi possível cancelar", str(exc), parent=self.root)

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
            migration_phase = data.get("migration_phase")
            migration_labels = {
                "awaiting_new_chat": "Aguardando novo chat e calibração.",
                "attached": "Novo chat vinculado. Confira checkpoint e finalize.",
            }
            self.migration_label.configure(
                text=migration_labels.get(migration_phase, "Nenhuma troca em andamento.")
            )
            if migration_phase:
                if not self.migration_banner.winfo_manager():
                    self.migration_banner.pack(before=self.action_bar, anchor="w", pady=(5, 2))
            elif self.migration_banner.winfo_manager():
                self.migration_banner.pack_forget()
            color = "#b34b2e" if paused or data["limit_hold"] or state == "blocked" else ACCENT
            self.vars["status"].set(("PAUSADO · " if paused else "") + state.upper())
            timing = timing_view(data)
            self.vars["decision"].set(timing["decision"])
            self.vars["round"].set(f'{data["round"]} · ID {short(data["request_id"], 15)}')
            self.vars["check"].set(timing["check"])
            if timing["idle_visible"]:
                self.idle_progress["value"] = timing["idle_percent"]
                self.idle_note.configure(text=timing["idle_hint"])
                if not self.idle_frame.winfo_manager():
                    self.idle_frame.pack(before=self.action_bar, fill="x", pady=(2, 6))
            elif self.idle_frame.winfo_manager():
                self.idle_frame.pack_forget()
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
