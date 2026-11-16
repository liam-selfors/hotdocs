import os
import textwrap

import pytest

import hotdocs_cli


LLM_ENDPOINT_STANDIN = textwrap.dedent(
    '''
    class ModelResolutionError(Exception):
        pass


    def load_config(config_path=None):
        return None
    '''
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_root(root):
    """A project or tool root with an llm-endpoint stand-in only."""
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "gen" / "llm-endpoint" / "llm_endpoint.py", LLM_ENDPOINT_STANDIN)
    return root


def _lint_fake(project, body):
    log = project / "calls.log"
    source = textwrap.dedent(
        '''
        import json

        LOG_PATH = {log!r}


        class ModelResolutionError(Exception):
            pass


        def main(argv):
            with open(LOG_PATH, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(list(argv)) + "\\n")
        {body}
        '''
    ).format(log=str(log), body=textwrap.indent(textwrap.dedent(body), "    "))
    _write(project / "gen" / "spec-linter" / "spec_linter.py", source)


def _env():
    env = dict(os.environ)
    env.pop("VAR_HOTDOCS_CONFIG", None)
    return env


def _quiet(*args, **kwargs):
    return None


def _run(argv, project, tool_root):
    return hotdocs_cli.main(
        argv,
        tool_root=tool_root,
        output_fn=_quiet,
        env=_env(),
        cwd=project,
    )


def test_routed_verb_returns_component_exit_code(tmp_path):
    tool_root = _make_root(tmp_path / "toolroot")

    project_zero = _make_root(tmp_path / "project_zero")
    _lint_fake(project_zero, "return 0\n")

    project_seven = _make_root(tmp_path / "project_seven")
    _lint_fake(project_seven, "return 7\n")

    assert _run(["lint"], project_zero, tool_root) == 0
    assert _run(["lint"], project_seven, tool_root) == 7


def test_unknown_verb_version_and_missing_component(tmp_path):
    tool_root = _make_root(tmp_path / "toolroot")
    project = _make_root(tmp_path / "project")

    assert _run(["frobnicate"], project, tool_root) == 2
    assert _run(["--version"], project, tool_root) == 0
    # No fake for "impact" in the project nor in the empty fake tool root.
    assert _run(["impact"], project, tool_root) == 2


def test_model_resolution_error_is_usage_error(tmp_path, capsys):
    tool_root = _make_root(tmp_path / "toolroot")
    project = _make_root(tmp_path / "project")
    _lint_fake(
        project,
        '''raise ModelResolutionError("model 'x' names no provider")\n''',
    )

    capsys.readouterr()
    code = _run(["lint"], project, tool_root)
    captured = capsys.readouterr()

    assert code == 2
    assert captured.err.splitlines() == ["usage error: model 'x' names no provider"]


def test_other_exception_propagates(tmp_path):
    tool_root = _make_root(tmp_path / "toolroot")
    project = _make_root(tmp_path / "project")
    _lint_fake(project, 'raise ValueError("boom")\n')

    with pytest.raises(ValueError, match="boom"):
        _run(["lint"], project, tool_root)