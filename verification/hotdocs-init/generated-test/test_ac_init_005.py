import json
import importlib.metadata

import hotdocs_init


FAKE_LLM_ENDPOINT_SOURCE = '''
import json
import os

PROVIDERS = {
    "openai": {
        "default_base_url": None,
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-4",
    },
    "openai-compatible": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": True,
        "suggested_model": "",
    },
}

_UNSET = object()


def _log_path():
    return os.environ.get("HOTDOCS_TEST_LOG")


def _log(event, payload):
    path = _log_path()
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"event": event, **payload}) + "\\n")


def _control():
    path = os.environ.get("HOTDOCS_TEST_CONTROL")
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", {
        "env_keys": sorted((env or {}).keys()),
        "probe_ollama": probe_ollama,
    })
    return [{
        "provider": "openai",
        "available": True,
        "reason": "",
        "suggested_model": "m",
        "api_key_env": "MY_KEY",
    }]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log("check_connection", {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
    })
    control = _control().get("check_connection", {"mode": "ok"})
    mode = control.get("mode", "ok")
    if mode == "ok":
        return {"ok": True, "error": None}
    if mode == "fail":
        return {
            "ok": False,
            "error": {
                "category": control.get("category", "network"),
                "message": control.get("message", ""),
            },
        }
    if mode == "raise":
        raise ValueError(control.get("message", ""))
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=_UNSET, api_key_env=_UNSET, timeout_seconds=_UNSET):
    passed_keywords = sorted(
        name for name, value in (
            ("base_url", base_url),
            ("api_key_env", api_key_env),
            ("timeout_seconds", timeout_seconds),
        )
        if value is not _UNSET
    )
    _log("save_config", {
        "config_path": str(config_path),
        "provider": provider,
        "model": model,
        "passed_keywords": passed_keywords,
        "base_url": None if base_url is _UNSET else base_url,
        "api_key_env": None if api_key_env is _UNSET else api_key_env,
        "timeout_seconds": None if timeout_seconds is _UNSET else timeout_seconds,
    })
    control = _control().get("save_config", {"mode": "ok"})
    mode = control.get("mode", "ok")
    if mode == "raise":
        raise ValueError(control.get("message", ""))
    return None


def load_config(config_path=None):
    _log("load_config", {"config_path": str(config_path) if config_path else None})
    return None
'''


def _write_tool_root(tmp_path):
    tool_root = tmp_path / "tool_root"
    (tool_root / "gen" / "llm-endpoint").mkdir(parents=True)
    (tool_root / "gen" / "llm-endpoint" / "llm_endpoint.py").write_text(
        FAKE_LLM_ENDPOINT_SOURCE, encoding="utf-8"
    )
    (tool_root / "examples" / "slugify" / "specs" / "product").mkdir(parents=True)
    (tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md").write_text(
        "# slugs\n", encoding="utf-8"
    )
    pytest_version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text(
        f"pytest=={pytest_version}\n", encoding="utf-8"
    )
    return tool_root


def _set_control(monkeypatch, tmp_path, control, log_path, name):
    control_path = tmp_path / f"control_{name}.json"
    control_path.write_text(json.dumps(control), encoding="utf-8")
    monkeypatch.setenv("HOTDOCS_TEST_CONTROL", str(control_path))
    monkeypatch.setenv("HOTDOCS_TEST_LOG", str(log_path))
    return control_path


def _read_log(log_path):
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _make_output_fn():
    lines = []

    def output_fn(*args, **kwargs):
        lines.append(" ".join(str(a) for a in args))

    return output_fn, lines


def _make_input_fn(answers):
    calls = []

    def input_fn(prompt):
        calls.append(prompt)
        for prefix, answer in answers.items():
            if prompt.startswith(prefix):
                return answer
        return ""

    return input_fn, calls


def test_connection_ok_prints_ok_saves_without_extra_keywords_and_asks_nothing(tmp_path, monkeypatch):
    tool_root = _write_tool_root(tmp_path)
    project_dir = tmp_path / "proj1"
    project_dir.mkdir()
    log_path = tmp_path / "log1.jsonl"
    _set_control(monkeypatch, tmp_path, {"check_connection": {"mode": "ok"}}, log_path, "s1")

    output_fn, lines = _make_output_fn()
    input_fn, input_calls = _make_input_fn({})

    hotdocs_init.main(
        [str(project_dir), "--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=output_fn,
        env={},
        cwd=str(project_dir),
    )

    assert any("connection ok" in line for line in lines)
    assert input_calls == []

    records = _read_log(log_path)
    save_records = [r for r in records if r["event"] == "save_config"]
    assert len(save_records) == 1
    save = save_records[0]
    assert save["config_path"] == str(project_dir / "hotdocs.toml")
    assert save["provider"] == "openai"
    assert save["model"] == "m"
    assert save["passed_keywords"] == ["api_key_env"]
    assert save["api_key_env"] == "MY_KEY"


def test_connection_failed_auth_asks_to_save_and_saves_only_on_yes(tmp_path, monkeypatch):
    tool_root = _write_tool_root(tmp_path)
    control = {"check_connection": {"mode": "fail", "category": "auth", "message": "bad"}}

    project_dir_no = tmp_path / "proj_a"
    project_dir_no.mkdir()
    log_path_no = tmp_path / "log_a.jsonl"
    _set_control(monkeypatch, tmp_path, control, log_path_no, "s2a")
    output_fn_no, lines_no = _make_output_fn()
    input_fn_no, input_calls_no = _make_input_fn({"Save anyway? [y/N] ": "n"})

    hotdocs_init.main(
        [str(project_dir_no)],
        tool_root=str(tool_root),
        input_fn=input_fn_no,
        output_fn=output_fn_no,
        env={},
        cwd=str(project_dir_no),
    )

    assert any("connection failed: auth: bad" in line for line in lines_no)
    assert any(p.startswith("Save anyway?") for p in input_calls_no)
    records_no = _read_log(log_path_no)
    assert [r for r in records_no if r["event"] == "save_config"] == []

    project_dir_yes = tmp_path / "proj_b"
    project_dir_yes.mkdir()
    log_path_yes = tmp_path / "log_b.jsonl"
    _set_control(monkeypatch, tmp_path, control, log_path_yes, "s2b")
    output_fn_yes, lines_yes = _make_output_fn()
    input_fn_yes, input_calls_yes = _make_input_fn({"Save anyway? [y/N] ": "y"})

    hotdocs_init.main(
        [str(project_dir_yes)],
        tool_root=str(tool_root),
        input_fn=input_fn_yes,
        output_fn=output_fn_yes,
        env={},
        cwd=str(project_dir_yes),
    )

    assert any("connection failed: auth: bad" in line for line in lines_yes)
    assert any(p.startswith("Save anyway?") for p in input_calls_yes)
    records_yes = _read_log(log_path_yes)
    save_records_yes = [r for r in records_yes if r["event"] == "save_config"]
    assert len(save_records_yes) == 1


def test_check_connection_value_error_prints_invalid(tmp_path, monkeypatch):
    tool_root = _write_tool_root(tmp_path)
    project_dir = tmp_path / "proj3"
    project_dir.mkdir()
    log_path = tmp_path / "log3.jsonl"
    _set_control(
        monkeypatch,
        tmp_path,
        {"check_connection": {"mode": "raise", "message": "no base_url"}},
        log_path,
        "s3",
    )

    output_fn, lines = _make_output_fn()
    input_fn, _ = _make_input_fn({})

    hotdocs_init.main(
        [str(project_dir), "--provider", "openai", "--model", "m"],
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=output_fn,
        env={},
        cwd=str(project_dir),
    )

    assert any("connection failed: invalid: no base_url" in line for line in lines)


def test_save_config_value_error_goes_to_stderr_without_changing_exit_code(tmp_path, monkeypatch, capsys):
    tool_root = _write_tool_root(tmp_path)

    def run(save_mode, tag):
        project_dir = tmp_path / f"proj4_{tag}"
        project_dir.mkdir()
        log_path = tmp_path / f"log4_{tag}.jsonl"
        control = {
            "check_connection": {"mode": "ok"},
            "save_config": {"mode": save_mode, "message": "nope"},
        }
        _set_control(monkeypatch, tmp_path, control, log_path, tag)
        output_fn, lines = _make_output_fn()
        input_fn, _ = _make_input_fn({})
        capsys.readouterr()

        exit_code = hotdocs_init.main(
            [str(project_dir), "--provider", "openai", "--model", "m"],
            tool_root=str(tool_root),
            input_fn=input_fn,
            output_fn=output_fn,
            env={},
            cwd=str(project_dir),
        )

        captured = capsys.readouterr()
        return exit_code, captured.err

    exit_code_ok, stderr_ok = run("ok", "ok")
    exit_code_fail, stderr_fail = run("raise", "fail")

    assert "could not save: nope" in stderr_fail
    assert "could not save: nope" not in stderr_ok
    assert exit_code_fail == exit_code_ok


def test_no_test_skips_check_connection(tmp_path, monkeypatch):
    tool_root = _write_tool_root(tmp_path)
    project_dir = tmp_path / "proj5"
    project_dir.mkdir()
    log_path = tmp_path / "log5.jsonl"
    _set_control(monkeypatch, tmp_path, {"check_connection": {"mode": "ok"}}, log_path, "s5")

    output_fn, lines = _make_output_fn()
    input_fn, _ = _make_input_fn({})

    hotdocs_init.main(
        [str(project_dir), "--provider", "openai", "--model", "m", "--no-test"],
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=output_fn,
        env={},
        cwd=str(project_dir),
    )

    records = _read_log(log_path)
    assert [r for r in records if r["event"] == "check_connection"] == []