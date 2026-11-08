import json
import os
from pathlib import Path

import hotdocs_cli


def _write_fake_lint(project: Path, calls_log: Path) -> None:
    lint_dir = project / "gen" / "spec-linter"
    lint_dir.mkdir(parents=True, exist_ok=True)
    (lint_dir / "spec_linter.py").write_text(
        "import json\n"
        "import os\n"
        "\n"
        "def main(argv):\n"
        f"    with open({str(calls_log)!r}, 'a') as f:\n"
        "        f.write(json.dumps({\n"
        "            'argv': argv,\n"
        "            'var_hotdocs_config': os.environ.get('VAR_HOTDOCS_CONFIG'),\n"
        "        }) + '\\n')\n"
        "    return 7\n"
    )


def _read_calls(calls_log: Path):
    if not calls_log.exists():
        return []
    return [json.loads(line) for line in calls_log.read_text().splitlines() if line]


def test_repo_root_appended_when_absent(tmp_path):
    project = (tmp_path / "project").resolve()
    project.mkdir()
    calls_log = project / "calls.log"
    _write_fake_lint(project, calls_log)

    rc = hotdocs_cli.main(["lint", "a.md"], cwd=str(project))

    assert rc == 7
    calls = _read_calls(calls_log)
    assert len(calls) == 1
    assert calls[0]["argv"] == ["a.md", f"--repo-root={project}"]


def test_explicit_repo_root_forwarded_unchanged(tmp_path):
    project = (tmp_path / "project").resolve()
    project.mkdir()
    calls_log = project / "calls.log"
    _write_fake_lint(project, calls_log)
    project_str = str(project)

    rc1 = hotdocs_cli.main(["lint", "--repo-root", project_str, "a.md"])
    rc2 = hotdocs_cli.main(["lint", f"--repo-root={project_str}"])

    assert rc1 == 7
    assert rc2 == 7
    calls = _read_calls(calls_log)
    assert len(calls) == 2
    assert calls[0]["argv"] == ["--repo-root", project_str, "a.md"]
    assert calls[1]["argv"] == [f"--repo-root={project_str}"]


def test_var_hotdocs_config_set_and_restored(tmp_path, monkeypatch):
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / "hotdocs.toml").write_text('[llm]\nprovider = "anthropic"\n')
    calls_log = project / "calls.log"
    _write_fake_lint(project, calls_log)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    project_str = str(project)

    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    rc1 = hotdocs_cli.main(["lint", "--repo-root", project_str], cwd=str(elsewhere))
    assert rc1 == 7
    assert os.environ.get("VAR_HOTDOCS_CONFIG") is None

    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", "/x")

    rc2 = hotdocs_cli.main(["lint", "--repo-root", project_str], cwd=str(elsewhere))
    assert rc2 == 7
    assert os.environ.get("VAR_HOTDOCS_CONFIG") == "/x"

    calls = _read_calls(calls_log)
    assert len(calls) == 2
    expected_config_path = str(project / "hotdocs.toml")
    assert calls[0]["var_hotdocs_config"] == expected_config_path
    assert calls[1]["var_hotdocs_config"] == "/x"