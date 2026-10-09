"""Installer smoke/regression tests; they never touch real projects or browsers."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("expert_ai_install", PACKAGE / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_new_project_includes_steps_prompts_and_safe_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "CRM"
            project.mkdir()
            installer.install(project, "Meu CRM", "CRM")
            cfg = json.loads((project / ".dev-loop/rpa-config.json").read_text(encoding="utf-8"))
            state = json.loads((project / ".dev-loop/chat-state.json").read_text(encoding="utf-8"))
            self.assertEqual(cfg["task_prefix"], "CRM")
            self.assertTrue(cfg["safe_mode_enabled"])
            self.assertTrue(cfg["breaks_enabled"])
            self.assertFalse(cfg["calibrated"])
            self.assertEqual(state["status"], "ready")
            self.assertEqual(state["round"], 0)
            self.assertIn("CRM-001", (project / "docs/TASKS.md").read_text(encoding="utf-8"))
            handbook = project / "docs/expert-ai-manager"
            for filename in ("COMECE_AQUI.md", "PLUGINS_E_SKILLS.md",
                             "PROMPTS_PRONTOS.md", "PROMPT_PLANEJAMENTO.md",
                             "TROCA_DE_CONVERSA.md"):
                self.assertTrue((handbook / filename).is_file(), filename)
            self.assertTrue((project / "scripts/expert_ai_rpa.py").is_file())
            self.assertTrue((project / "scripts/expert_ai_migration.py").is_file())
            self.assertTrue((project / "scripts/test_expert_ai_migration.py").is_file())
            self.assertEqual((project / ".gitignore").read_text(encoding="utf-8").count(".dev-loop/"), 1)

    def test_reinstall_does_not_replace_plan_configuration_or_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "CRM"
            project.mkdir()
            installer.install(project, "Meu CRM", "CRM")
            files = {
                project / "AGENTS.md": "My custom agent rules",
                project / "docs/TASKS.md": "My tasks",
                project / "docs/expert-ai-manager/PROMPTS_PRONTOS.md": "My notes on prompts",
                project / ".dev-loop/chat-state.json": '{"status":"running","request_id":"x"}',
            }
            for path, text in files.items():
                path.write_text(text, encoding="utf-8")
            installer.install(project, "Meu CRM", "CRM")
            for path, text in files.items():
                self.assertEqual(path.read_text(encoding="utf-8"), text)
            self.assertEqual((project / ".gitignore").read_text(encoding="utf-8").count(".dev-loop/"), 1)

    def test_update_backups_only_changed_scripts_outside_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "CRM"
            project.mkdir()
            installer.install(project, "Meu CRM", "CRM")
            target = project / "scripts/expert_ai_rpa.py"
            changed = target.read_text(encoding="utf-8") + "\n# local override\n"
            target.write_text(changed, encoding="utf-8")
            checkpoint = project / ".dev-loop/chat-state.json"
            checkpoint.write_text('{"status":"running","request_id":"keep"}',
                                  encoding="utf-8")
            installer.install(project, "Meu CRM", "CRM", update=True)
            self.assertEqual(target.read_bytes(),
                             (PACKAGE / "scripts/expert_ai_rpa.py").read_bytes())
            backups = list((project / ".dev-loop/backups").iterdir())
            self.assertEqual(len(backups), 1)
            self.assertIn("# local override", backups[0].read_text(encoding="utf-8"))
            self.assertEqual(list((project / "scripts").glob("*.backup-*")), [])
            self.assertIn('"request_id":"keep"', checkpoint.read_text(encoding="utf-8"))
            installer.install(project, "Meu CRM", "CRM", update=True)
            self.assertEqual(len(list((project / ".dev-loop/backups").iterdir())), 1)

    def test_invalid_prefix_rejected_without_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "CRM"
            project.mkdir()
            with self.assertRaisesRegex(ValueError, "Prefix"):
                installer.install(project, "Meu CRM", "../RISK")
            self.assertEqual(list(project.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
