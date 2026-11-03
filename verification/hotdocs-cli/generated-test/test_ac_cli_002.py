import json
import os
import tempfile
import unittest
from pathlib import Path

import hotdocs_cli


FAKE_LINT_SOURCE_PLAIN = """\
import json

def main(argv):
    with open({calls_log!r}, "a") as f:
        f.write(json.dumps(argv) + "\\n")
    return 7
"""

FAKE_LINT_SOURCE_ENV = """\
import json
import os

def main(argv):
    record = {{"argv": argv, "env_var": os.environ.get("VAR_HOTDOCS_CONFIG")}}
    with open({calls_log!r}, "a") as f:
        f.write(json.dumps(record) + "\\n")
    return 7
"""


def _write_fake_lint(project, calls_log, record_env=False):
    gen_dir = Path(project) / "gen" / "spec-linter"
    gen_dir.mkdir(parents=True, exist_ok=True)
    template = FAKE_LINT_SOURCE_ENV if record_env else FAKE_LINT_SOURCE_PLAIN
    source = template.format(calls_log=str(calls_log))
    (gen_dir / "spec_linter.py").write_text(source)


def _read_log_lines(calls_log):
    with open(calls_log) as f:
        return [json.loads(line) for line in f if line.strip()]


class TestAcCli002(unittest.TestCase):
    def test_default_repo_root_is_appended_from_cwd(self):
        with tempfile.TemporaryDirectory() as project:
            calls_log = Path(project) / "calls.log"
            _write_fake_lint(project, calls_log, record_env=False)

            rc = hotdocs_cli.main(["lint", "a.md"], cwd=str(project))

            self.assertEqual(rc, 7)
            lines = _read_log_lines(calls_log)
            self.assertEqual(len(lines), 1)
            expected_repo_root = os.path.abspath(str(project))
            self.assertEqual(
                lines[0],
                ["a.md", "--repo-root={}".format(expected_repo_root)],
            )

    def test_explicit_repo_root_forwarded_unchanged(self):
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as elsewhere:
            calls_log = Path(project) / "calls.log"
            _write_fake_lint(project, calls_log, record_env=False)

            rc1 = hotdocs_cli.main(
                ["lint", "--repo-root", str(project), "a.md"], cwd=str(elsewhere)
            )
            self.assertEqual(rc1, 7)

            rc2 = hotdocs_cli.main(
                ["lint", "--repo-root={}".format(project)], cwd=str(elsewhere)
            )
            self.assertEqual(rc2, 7)

            lines = _read_log_lines(calls_log)
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0], ["--repo-root", str(project), "a.md"])
            self.assertEqual(lines[1], ["--repo-root={}".format(project)])

    def test_var_hotdocs_config_set_and_restored(self):
        original = os.environ.pop("VAR_HOTDOCS_CONFIG", None)
        try:
            with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as elsewhere:
                (Path(project) / "hotdocs.toml").write_text("")
                calls_log = Path(project) / "calls.log"
                _write_fake_lint(project, calls_log, record_env=True)

                self.assertIsNone(os.environ.get("VAR_HOTDOCS_CONFIG"))
                rc1 = hotdocs_cli.main(
                    ["lint", "--repo-root", str(project)], cwd=str(elsewhere)
                )
                self.assertEqual(rc1, 7)
                self.assertIsNone(os.environ.get("VAR_HOTDOCS_CONFIG"))

                os.environ["VAR_HOTDOCS_CONFIG"] = "/x"
                rc2 = hotdocs_cli.main(
                    ["lint", "--repo-root", str(project)], cwd=str(elsewhere)
                )
                self.assertEqual(rc2, 7)
                self.assertEqual(os.environ.get("VAR_HOTDOCS_CONFIG"), "/x")

                lines = _read_log_lines(calls_log)
                self.assertEqual(len(lines), 2)
                expected_config_path = os.path.join(
                    os.path.abspath(str(project)), "hotdocs.toml"
                )
                self.assertEqual(lines[0]["env_var"], expected_config_path)
                self.assertEqual(lines[1]["env_var"], "/x")
        finally:
            if original is None:
                os.environ.pop("VAR_HOTDOCS_CONFIG", None)
            else:
                os.environ["VAR_HOTDOCS_CONFIG"] = original


if __name__ == "__main__":
    unittest.main()