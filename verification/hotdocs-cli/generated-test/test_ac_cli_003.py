"""Acceptance test for AC-CLI-003 (R-CLI-003): --model injection for model=required rows."""

import json
import textwrap
from pathlib import Path

import hotdocs_cli


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_fake_llm_endpoint(project, behavior):
    content = textwrap.dedent(f'''
        from pathlib import Path

        _CALL_MARKER_FILE = Path(r"{project}") / "llm_load_config_called.marker"

        def load_config(config_path=None):
            behavior = {behavior!r}
            if behavior == "config":
                return {{
                    "provider": "claude-cli",
                    "model": "sonnet",
                    "base_url": None,
                    "api_key_env": None,
                    "timeout_seconds": None,
                }}
            if behavior == "none-then-error":
                if _CALL_MARKER_FILE.exists():
                    raise ValueError("bad")
                _CALL_MARKER_FILE.write_text("called-once")
                return None
            raise AssertionError("unreachable behavior: " + behavior)
    ''')
    _write(project / "gen" / "llm-endpoint" / "llm_endpoint.py", content)


def _write_fake_component(project, dir_name, module_name, log_name="calls.log"):
    content = textwrap.dedent(f'''
        import json
        from pathlib import Path

        _LOG = Path(r"{project}") / "{log_name}"

        def main(argv):
            with open(_LOG, "a") as f:
                f.write(json.dumps(list(argv)) + "\\n")
            return 7
    ''')
    _write(project / "gen" / dir_name / f"{module_name}.py", content)


def _read_calls(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line]


def test_model_required_appends_model_last(tmp_path):
    project = tmp_path.resolve()
    _write_fake_llm_endpoint(project, "config")
    _write_fake_component(project, "component-gate-runner", "component_gate_runner")
    _write_fake_component(project, "test-author", "test_author")

    rc1 = hotdocs_cli.main(["generate", "comp-x"], cwd=str(project))
    rc2 = hotdocs_cli.main(["author-test", "comp-x", "AC-X-1"], cwd=str(project))

    assert rc1 == 7
    assert rc2 == 7

    calls = _read_calls(project / "calls.log")
    assert calls == [
        ["generate", "comp-x", f"--repo-root={project}", "--model=claude-cli:sonnet"],
        ["author-test", "comp-x", "AC-X-1", f"--repo-root={project}", "--model=claude-cli:sonnet"],
    ]


def test_explicit_model_not_duplicated(tmp_path):
    project = tmp_path.resolve()
    _write_fake_llm_endpoint(project, "config")
    _write_fake_component(project, "component-gate-runner", "component_gate_runner")

    hotdocs_cli.main(["generate", "comp-x", "--model", "m"], cwd=str(project))
    hotdocs_cli.main(["generate", "comp-x", "--model=m"], cwd=str(project))

    calls = _read_calls(project / "calls.log")
    assert calls == [
        ["generate", "comp-x", "--model", "m", f"--repo-root={project}"],
        ["generate", "comp-x", "--model=m", f"--repo-root={project}"],
    ]


def test_load_config_none_then_value_error(tmp_path, capsys):
    project = tmp_path.resolve()
    _write_fake_llm_endpoint(project, "none-then-error")
    _write_fake_component(project, "component-gate-runner", "component_gate_runner")

    rc1 = hotdocs_cli.main(["generate", "comp-x"], cwd=str(project))
    rc2 = hotdocs_cli.main(["generate", "comp-x"], cwd=str(project))

    assert rc1 == 7
    assert rc2 == 7

    calls = _read_calls(project / "calls.log")
    assert calls == [
        ["generate", "comp-x", f"--repo-root={project}"],
        ["generate", "comp-x", f"--repo-root={project}"],
    ]

    captured = capsys.readouterr()
    assert "bad" in captured.err


def test_model_no_rows_never_get_model(tmp_path):
    project = tmp_path.resolve()
    _write_fake_llm_endpoint(project, "config")
    _write_fake_component(project, "provenance-tracker", "provenance_tracker")
    _write_fake_component(project, "spec-linter", "spec_linter")
    _write_fake_component(project, "spec-completeness-assistant", "spec_completeness_assistant")

    hotdocs_cli.main(["verify"], cwd=str(project))
    hotdocs_cli.main(["lint"], cwd=str(project))
    hotdocs_cli.main(["assist"], cwd=str(project))

    calls = _read_calls(project / "calls.log")
    assert len(calls) == 3
    for call in calls:
        assert not any(
            token == "--model" or token.startswith("--model=") for token in call
        )