import json
import os
from pathlib import Path

import pytest

import hotdocs_cli


VAR = "VAR_HOTDOCS_CONFIG"


def _write_fake_lint(project: Path, env_log: Path = None) -> Path:
    """Write a fake spec-linter at <project>/gen/spec-linter/spec_linter.py.

    Its main(argv) appends json.dumps(argv) to <project>/calls.log and
    returns 7. When env_log is given, it also appends
    json.dumps(os.environ.get("VAR_HOTDOCS_CONFIG")) to env_log.
    """
    calls_log = project / "calls.log"
    fake_dir = project / "gen" / "spec-linter"
    fake_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "import json",
        "import os",
        "",
        "CALLS_LOG = " + repr(str(calls_log)),
        "ENV_LOG = " + repr(str(env_log) if env_log is not None else None),
        "",
        "",
        "def main(argv):",
        "    with open(CALLS_LOG, 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps(list(argv)) + '\\n')",
        "    if ENV_LOG is not None:",
        "        with open(ENV_LOG, 'a', encoding='utf-8') as fh:",
        "            fh.write(json.dumps(os.environ.get('VAR_HOTDOCS_CONFIG')) + '\\n')",
        "    return 7",
        "",
    ]
    (fake_dir / "spec_linter.py").write_text("\n".join(lines), encoding="utf-8")
    return calls_log


def _read_lines(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _same_path(a, b) -> bool:
    return Path(a).resolve() == Path(b).resolve()


@pytest.fixture
def dirs(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    (tool_root / "gen").mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    return project, tool_root, elsewhere


def _quiet(*args, **kwargs):
    return None


def test_repo_root_appended_when_absent(dirs, monkeypatch):
    project, tool_root, _ = dirs
    calls_log = _write_fake_lint(project)
    monkeypatch.chdir(project)

    rc = hotdocs_cli.main(
        ["lint", "a.md"], tool_root=tool_root, output_fn=_quiet, cwd=project
    )
    assert rc == 7

    calls = _read_lines(calls_log)
    assert len(calls) == 1
    received = calls[0]
    assert len(received) == 2, received
    assert received[0] == "a.md"
    token = received[1]
    assert token.startswith("--repo-root="), received
    value = token[len("--repo-root="):]
    assert Path(value).is_absolute(), value
    assert _same_path(value, project)
    # No other --repo-root token was added.
    assert sum(1 for t in received if t.startswith("--repo-root")) == 1


def test_repo_root_separate_token_forwarded_unchanged(dirs, monkeypatch):
    project, tool_root, _ = dirs
    calls_log = _write_fake_lint(project)
    monkeypatch.chdir(project)

    given = ["--repo-root", str(project), "a.md"]
    rc = hotdocs_cli.main(
        ["lint"] + given, tool_root=tool_root, output_fn=_quiet, cwd=project
    )
    assert rc == 7

    calls = _read_lines(calls_log)
    assert calls == [given]


def test_repo_root_equals_form_forwarded_unchanged(dirs, monkeypatch):
    project, tool_root, _ = dirs
    calls_log = _write_fake_lint(project)
    monkeypatch.chdir(project)

    given = ["--repo-root=" + str(project)]
    rc = hotdocs_cli.main(
        ["lint"] + given, tool_root=tool_root, output_fn=_quiet, cwd=project
    )
    assert rc == 7

    calls = _read_lines(calls_log)
    assert calls == [given]


def test_hotdocs_config_var_set_and_restored(dirs, monkeypatch):
    project, tool_root, elsewhere = dirs
    (project / "hotdocs.toml").write_text(
        '[llm]\nprovider = "ollama"\nmodel = "llama3.2"\n', encoding="utf-8"
    )
    env_log = project / "env.log"
    _write_fake_lint(project, env_log=env_log)
    monkeypatch.chdir(elsewhere)

    # First: variable unset.
    monkeypatch.delenv(VAR, raising=False)
    rc = hotdocs_cli.main(
        ["lint", "--repo-root", str(project)],
        tool_root=tool_root,
        output_fn=_quiet,
        cwd=elsewhere,
    )
    assert rc == 7
    seen = _read_lines(env_log)
    assert len(seen) == 1
    assert seen[0] is not None, "fake did not see VAR_HOTDOCS_CONFIG set"
    assert _same_path(seen[0], project / "hotdocs.toml"), seen[0]
    assert VAR not in os.environ, "VAR_HOTDOCS_CONFIG was not restored to unset"

    # Second: variable already set to "/x" — left as-is.
    monkeypatch.setenv(VAR, "/x")
    rc = hotdocs_cli.main(
        ["lint", "--repo-root", str(project)],
        tool_root=tool_root,
        output_fn=_quiet,
        cwd=elsewhere,
    )
    assert rc == 7
    seen = _read_lines(env_log)
    assert len(seen) == 2
    assert seen[1] == "/x"
    assert os.environ.get(VAR) == "/x"

    monkeypatch.delenv(VAR, raising=False)
    assert VAR not in os.environ