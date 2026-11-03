"""Test for AC-CLI-003 (covers R-CLI-003)."""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import hotdocs_cli


_FAKE_COMPONENT_SRC = '''import json
from pathlib import Path

LOG_PATH = Path(__LOG_PATH__)

def main(argv):
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(argv) + "\\n")
    return 7
'''


def _write_fake_component(repo_root, dir_, module, log_path):
    comp_dir = Path(repo_root) / dir_
    comp_dir.mkdir(parents=True, exist_ok=True)
    source = _FAKE_COMPONENT_SRC.replace("__LOG_PATH__", repr(str(log_path)))
    (comp_dir / f"{module}.py").write_text(source)


def _write_fake_llm_endpoint(repo_root, source):
    comp_dir = Path(repo_root) / "gen" / "llm-endpoint"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "llm_endpoint.py").write_text(source)


def _read_log(log_path):
    log_path = Path(log_path)
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line]


def _new_project():
    project = os.path.realpath(tempfile.mkdtemp())
    (Path(project) / "hotdocs.toml").write_text("")
    return project


_LLM_FIXED_CONFIG_SRC = (
    "def load_config(config_path=None):\n"
    "    return {'provider': 'claude-cli', 'model': 'sonnet', 'base_url': None,\n"
    "            'api_key_env': None, 'timeout_seconds': None}\n"
)


class TestAcCli003(unittest.TestCase):
    def test_model_required_appends_model_after_repo_root(self):
        project = _new_project()
        try:
            _write_fake_llm_endpoint(project, _LLM_FIXED_CONFIG_SRC)

            generate_log = Path(project) / "generate_calls.log"
            _write_fake_component(
                project, "gen/component-gate-runner", "component_gate_runner", generate_log
            )

            author_log = Path(project) / "author_test_calls.log"
            _write_fake_component(project, "gen/test-author", "test_author", author_log)

            hotdocs_cli.main(["generate", "comp-x"], cwd=project)
            hotdocs_cli.main(["author-test", "comp-x", "AC-X-1"], cwd=project)

            gen_calls = _read_log(generate_log)
            author_calls = _read_log(author_log)

            self.assertEqual(len(gen_calls), 1)
            self.assertEqual(
                gen_calls[0],
                ["generate", "comp-x", f"--repo-root={project}", "--model=claude-cli:sonnet"],
            )

            self.assertEqual(len(author_calls), 1)
            self.assertEqual(
                author_calls[0],
                [
                    "author-test",
                    "comp-x",
                    "AC-X-1",
                    f"--repo-root={project}",
                    "--model=claude-cli:sonnet",
                ],
            )
        finally:
            shutil.rmtree(project, ignore_errors=True)

    def test_explicit_model_passes_unchanged(self):
        for model_tokens in (["--model", "m"], ["--model=m"]):
            project = _new_project()
            try:
                marker_path = Path(project) / "llm_called.marker"
                llm_src = (
                    "from pathlib import Path\n"
                    f"MARKER = Path({repr(str(marker_path))})\n"
                    "def load_config(config_path=None):\n"
                    "    MARKER.write_text('called')\n"
                    "    return {'provider': 'x', 'model': 'y', 'base_url': None,\n"
                    "            'api_key_env': None, 'timeout_seconds': None}\n"
                )
                _write_fake_llm_endpoint(project, llm_src)

                log_path = Path(project) / "calls.log"
                _write_fake_component(
                    project, "gen/component-gate-runner", "component_gate_runner", log_path
                )

                argv = ["generate", "comp-x"] + model_tokens
                stderr_buf = io.StringIO()
                with contextlib.redirect_stderr(stderr_buf):
                    hotdocs_cli.main(argv, cwd=project)

                calls = _read_log(log_path)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0], argv + [f"--repo-root={project}"])
                self.assertFalse(marker_path.exists())
                self.assertEqual(stderr_buf.getvalue(), "")
            finally:
                shutil.rmtree(project, ignore_errors=True)

    def test_load_config_none_then_value_error(self):
        project = _new_project()
        try:
            counter_path = Path(project) / "counter.txt"
            llm_src = (
                "from pathlib import Path\n"
                f"COUNTER = Path({repr(str(counter_path))})\n"
                "def load_config(config_path=None):\n"
                "    n = int(COUNTER.read_text()) if COUNTER.exists() else 0\n"
                "    COUNTER.write_text(str(n + 1))\n"
                "    if n == 0:\n"
                "        return None\n"
                "    raise ValueError('bad')\n"
            )
            _write_fake_llm_endpoint(project, llm_src)

            log_path = Path(project) / "calls.log"
            _write_fake_component(
                project, "gen/component-gate-runner", "component_gate_runner", log_path
            )

            stderr_buf1 = io.StringIO()
            with contextlib.redirect_stderr(stderr_buf1):
                hotdocs_cli.main(["generate", "comp-x"], cwd=project)

            stderr_buf2 = io.StringIO()
            with contextlib.redirect_stderr(stderr_buf2):
                hotdocs_cli.main(["generate", "comp-x"], cwd=project)

            calls = _read_log(log_path)
            self.assertEqual(len(calls), 2)
            expected = ["generate", "comp-x", f"--repo-root={project}"]
            self.assertEqual(calls[0], expected)
            self.assertEqual(calls[1], expected)

            self.assertEqual(stderr_buf1.getvalue(), "")
            self.assertIn("bad", stderr_buf2.getvalue())
        finally:
            shutil.rmtree(project, ignore_errors=True)

    def test_model_no_rows_never_get_model(self):
        project = _new_project()
        try:
            _write_fake_llm_endpoint(project, _LLM_FIXED_CONFIG_SRC)

            verify_log = Path(project) / "verify_calls.log"
            _write_fake_component(
                project, "gen/provenance-tracker", "provenance_tracker", verify_log
            )

            lint_log = Path(project) / "lint_calls.log"
            _write_fake_component(project, "gen/spec-linter", "spec_linter", lint_log)

            assist_log = Path(project) / "assist_calls.log"
            _write_fake_component(
                project,
                "gen/spec-completeness-assistant",
                "spec_completeness_assistant",
                assist_log,
            )

            hotdocs_cli.main(["verify"], cwd=project)
            hotdocs_cli.main(["lint"], cwd=project)
            hotdocs_cli.main(["assist"], cwd=project)

            for log_path in (verify_log, lint_log, assist_log):
                calls = _read_log(log_path)
                self.assertEqual(len(calls), 1)
                for token in calls[0]:
                    self.assertFalse(
                        isinstance(token, str) and token.startswith("--model")
                    )
        finally:
            shutil.rmtree(project, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()