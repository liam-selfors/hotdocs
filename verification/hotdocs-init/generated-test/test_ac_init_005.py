import json
from pathlib import Path

import pytest

import hotdocs_init


def _build_fake_llm_endpoint_source(log_path: Path, control_path: Path) -> str:
    log_literal = repr(str(log_path))
    control_literal = repr(str(control_path))
    return f'''import json

_LOG_PATH = {log_literal}
_CONTROL_PATH = {control_literal}

_UNSET = object()

PROVIDERS = {{
    "openai": {{
        "default_base_url": None,
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-4",
    }},
}}


def _log(event):
    with open(_LOG_PATH, "a") as f:
        print(json.dumps(event), file=f)


def _control():
    try:
        with open(_CONTROL_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {{}}


def detect_providers(env=None, probe_ollama=True):
    _log({{
        "call": "detect_providers",
        "env_keys": sorted((env or {{}}).keys()),
        "probe_ollama": probe_ollama,
    }})
    return [
        {{
            "provider": "openai",
            "available": True,
            "reason": "",
            "suggested_model": "gpt-4",
            "api_key_env": "OPENAI_API_KEY",
        }}
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log({{
        "call": "check_connection",
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
    }})
    ctrl = _control()
    cc = ctrl.get("check_connection", {{}})
    if cc.get("raise"):
        raise ValueError(cc["raise"])
    return cc.get("result", {{"ok": True, "error": None}})


def save_config(config_path, provider, model, base_url=_UNSET, api_key_env=_UNSET, timeout_seconds=_UNSET):
    _log({{
        "call": "save_config",
        "config_path": str(config_path),
        "provider": provider,
        "model": model,
        "base_url_passed": base_url is not _UNSET,
        "base_url": None if base_url is _UNSET else base_url,
        "api_key_env_passed": api_key_env is not _UNSET,
        "api_key_env": None if api_key_env is _UNSET else api_key_env,
        "timeout_seconds_passed": timeout_seconds is not _UNSET,
        "timeout_seconds": None if timeout_seconds is _UNSET else timeout_seconds,
    }})
    ctrl = _control()
    sc = ctrl.get("save_config", {{}})
    if sc.get("raise"):
        raise ValueError(sc["raise"])
    return None


def load_config(config_path=None):
    _log({{
        "call": "load_config",
        "config_path": str(config_path) if config_path else None,
    }})
    return None
'''


def _build_tool_root(tmp_path, log_path, control_path):
    tool_root = tmp_path / "tool_root"
    (tool_root / "gen" / "llm-endpoint").mkdir(parents=True)
    (tool_root / "gen" / "llm-endpoint" / "llm_endpoint.py").write_text(
        _build_fake_llm_endpoint_source(log_path, control_path)
    )
    (tool_root / "pipeline" / "criterion-compiler").mkdir(parents=True)
    (tool_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py").write_text(
        "def compile_criterion(*args, **kwargs):\n    return None\n"
    )
    (tool_root / "examples" / "slugify" / "specs" / "product").mkdir(parents=True)
    (tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md").write_text(
        "# fake slugify example fixture\n"
    )
    (tool_root / "requirements.txt").write_text("pytest\n")
    return tool_root


def _set_control(control_path, data):
    control_path.write_text(json.dumps(data))


def _read_calls(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def _make_input_fn(save_answers):
    answers = list(save_answers)
    calls = []

    def input_fn(prompt=""):
        calls.append(prompt)
        if "save anyway" in str(prompt).lower():
            return answers.pop(0)
        return ""

    return input_fn, calls


def _make_output_fn():
    lines = []

    def output_fn(*args, **kwargs):
        sep = kwargs.get("sep", " ")
        lines.append(sep.join(str(a) for a in args))

    return output_fn, lines


def _run_main(tool_root, argv, cwd, input_fn, output_fn, env=None):
    return hotdocs_init.main(
        list(argv),
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env={} if env is None else env,
        cwd=cwd,
    )


def test_successful_connection_saves_without_asking(tmp_path):
    log_path = tmp_path / "calls.log"
    control_path = tmp_path / "control.json"
    _set_control(control_path, {"check_connection": {"result": {"ok": True, "error": None}}})
    tool_root = _build_tool_root(tmp_path, log_path, control_path)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    input_fn, input_calls = _make_input_fn(save_answers=[])
    output_fn, outputs = _make_output_fn()

    _run_main(
        tool_root,
        ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        project_dir,
        input_fn,
        output_fn,
    )

    assert "connection ok" in outputs
    assert input_calls == []

    calls = _read_calls(log_path)
    save_calls = [c for c in calls if c["call"] == "save_config"]
    assert len(save_calls) == 1
    save_call = save_calls[0]
    assert save_call["config_path"] == str(project_dir / "hotdocs.toml")
    assert save_call["provider"] == "openai"
    assert save_call["model"] == "m"
    assert save_call["api_key_env_passed"] is True
    assert save_call["api_key_env"] == "MY_KEY"
    assert save_call["base_url_passed"] is False
    assert save_call["timeout_seconds_passed"] is False


def test_interactive_failure_asks_and_respects_answer(tmp_path):
    log_path = tmp_path / "calls.log"
    control_path = tmp_path / "control.json"
    _set_control(
        control_path,
        {"check_connection": {"result": {"ok": False, "error": {"category": "auth", "message": "bad"}}}},
    )
    tool_root = _build_tool_root(tmp_path, log_path, control_path)

    no_dir = tmp_path / "project_no"
    no_dir.mkdir()
    yes_dir = tmp_path / "project_yes"
    yes_dir.mkdir()

    before_no = len(_read_calls(log_path))
    input_fn_no, _ = _make_input_fn(save_answers=["n"])
    output_fn_no, outputs_no = _make_output_fn()
    _run_main(tool_root, [], no_dir, input_fn_no, output_fn_no)
    assert "connection failed: auth: bad" in outputs_no
    calls_no = _read_calls(log_path)[before_no:]
    assert not any(c["call"] == "save_config" for c in calls_no)

    before_yes = len(_read_calls(log_path))
    input_fn_yes, _ = _make_input_fn(save_answers=["y"])
    output_fn_yes, outputs_yes = _make_output_fn()
    _run_main(tool_root, [], yes_dir, input_fn_yes, output_fn_yes)
    assert "connection failed: auth: bad" in outputs_yes
    calls_yes = _read_calls(log_path)[before_yes:]
    assert any(c["call"] == "save_config" for c in calls_yes)


def test_check_connection_value_error_reported_as_invalid(tmp_path):
    log_path = tmp_path / "calls.log"
    control_path = tmp_path / "control.json"
    _set_control(control_path, {"check_connection": {"raise": "no base_url"}})
    tool_root = _build_tool_root(tmp_path, log_path, control_path)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    input_fn, _ = _make_input_fn(save_answers=[])
    output_fn, outputs = _make_output_fn()

    _run_main(
        tool_root,
        ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        project_dir,
        input_fn,
        output_fn,
    )

    assert "connection failed: invalid: no base_url" in outputs


def test_save_config_failure_reported_and_exit_code_unchanged(tmp_path, capsys):
    log_path = tmp_path / "calls.log"
    control_path = tmp_path / "control.json"
    _set_control(control_path, {"check_connection": {"result": {"ok": True, "error": None}}})
    tool_root = _build_tool_root(tmp_path, log_path, control_path)

    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()
    failing_dir = tmp_path / "failing"
    failing_dir.mkdir()

    input_fn_base, _ = _make_input_fn(save_answers=[])
    output_fn_base, _ = _make_output_fn()
    exit_baseline = _run_main(
        tool_root,
        ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        baseline_dir,
        input_fn_base,
        output_fn_base,
    )
    capsys.readouterr()

    _set_control(
        control_path,
        {
            "check_connection": {"result": {"ok": True, "error": None}},
            "save_config": {"raise": "nope"},
        },
    )

    input_fn_fail, _ = _make_input_fn(save_answers=[])
    output_fn_fail, _ = _make_output_fn()
    exit_failing = _run_main(
        tool_root,
        ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        failing_dir,
        input_fn_fail,
        output_fn_fail,
    )
    captured = capsys.readouterr()

    assert "could not save: nope" in captured.err
    assert exit_failing == exit_baseline


def test_no_test_skips_check_connection(tmp_path):
    log_path = tmp_path / "calls.log"
    control_path = tmp_path / "control.json"
    _set_control(control_path, {"check_connection": {"result": {"ok": True, "error": None}}})
    tool_root = _build_tool_root(tmp_path, log_path, control_path)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    input_fn, _ = _make_input_fn(save_answers=[])
    output_fn, _ = _make_output_fn()

    _run_main(
        tool_root,
        ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY", "--no-test"],
        project_dir,
        input_fn,
        output_fn,
    )

    calls = _read_calls(log_path)
    assert not any(c["call"] == "check_connection" for c in calls)