import importlib.metadata
import json
from pathlib import Path

import hotdocs_init


FAKE_LLM_ENDPOINT_SOURCE = '''
import json
import os

PROVIDERS = {
    "openai": {
        "default_base_url": None,
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "m",
    },
}


def _control():
    with open(os.environ["HOTDOCS_TEST_CONTROL"]) as f:
        return json.load(f)


def _log(entry):
    with open(os.environ["HOTDOCS_TEST_LOG"], "a") as f:
        f.write(json.dumps(entry) + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log({"call": "detect_providers"})
    return [
        {
            "provider": "openai",
            "available": True,
            "reason": "ok",
            "suggested_model": "m",
            "api_key_env": "MY_KEY",
        }
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log({
        "call": "check_connection",
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
    })
    c = _control()["check_connection"]
    if "raise" in c:
        raise ValueError(c["raise"])
    return {"ok": c["ok"], "error": c.get("error")}


def save_config(config_path, provider, model, *args, **kwargs):
    if args:
        raise TypeError("save_config takes no extra positional args")
    entry = {
        "call": "save_config",
        "config_path": str(config_path),
        "provider": provider,
        "model": model,
        "kwargs": sorted(kwargs.keys()),
        "values": dict(kwargs),
    }
    _log(entry)
    c = _control()["save_config"]
    if "raise" in c:
        raise ValueError(c["raise"])
    return None


def load_config(config_path=None):
    return None
'''


def _no_input(prompt):
    raise AssertionError(f"unexpected prompt: {prompt!r}")


def make_tool_root(path):
    path.mkdir(parents=True, exist_ok=True)

    gen_dir = path / "gen" / "llm-endpoint"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "llm_endpoint.py").write_text(FAKE_LLM_ENDPOINT_SOURCE)

    slugify_dir = path / "examples" / "slugify" / "specs" / "product"
    slugify_dir.mkdir(parents=True, exist_ok=True)
    (slugify_dir / "slugs.md").write_text("# slugs\n\nFixture content.\n")

    pytest_version = importlib.metadata.version("pytest")
    (path / "requirements.txt").write_text(f"pytest=={pytest_version}")

    return path


def _write_control(path, check_connection_behavior, save_config_behavior):
    path.write_text(json.dumps({
        "check_connection": check_connection_behavior,
        "save_config": save_config_behavior,
    }))


def test_ac_init_005_success_prints_ok_and_saves_without_unset_keywords(tmp_path, monkeypatch):
    harness = tmp_path / "harness"
    harness.mkdir()
    log_path = harness / "log.jsonl"
    log_path.write_text("")
    control_path = harness / "control.json"
    _write_control(control_path, {"ok": True, "error": None}, {"ok": True})

    tool_root = make_tool_root(tmp_path / "tool_root")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    monkeypatch.setenv("HOTDOCS_TEST_CONTROL", str(control_path))
    monkeypatch.setenv("HOTDOCS_TEST_LOG", str(log_path))

    outputs = []
    hotdocs_init.main(
        ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        tool_root=str(tool_root),
        input_fn=_no_input,
        output_fn=outputs.append,
        env={},
        cwd=str(project_dir),
    )

    assert any("connection ok" in line for line in outputs)

    entries = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
    save_entries = [e for e in entries if e["call"] == "save_config"]
    assert len(save_entries) == 1
    save = save_entries[0]
    assert Path(save["config_path"]) == project_dir / "hotdocs.toml"
    assert save["provider"] == "openai"
    assert save["model"] == "m"
    assert save["kwargs"] == ["api_key_env"]
    assert save["values"]["api_key_env"] == "MY_KEY"


def test_ac_init_005_interactive_failure_save_anyway_prompt(tmp_path, monkeypatch):
    harness = tmp_path / "harness"
    harness.mkdir()

    log1 = harness / "log1.jsonl"
    log1.write_text("")
    control1 = harness / "control1.json"
    _write_control(control1, {"ok": False, "error": {"category": "auth", "message": "bad"}}, {"ok": True})

    tool_root1 = make_tool_root(tmp_path / "tool_root1")
    project1 = tmp_path / "project1"
    project1.mkdir()

    monkeypatch.setenv("HOTDOCS_TEST_CONTROL", str(control1))
    monkeypatch.setenv("HOTDOCS_TEST_LOG", str(log1))

    outputs1 = []

    def input_fn_1(prompt):
        if prompt == "Save anyway? [y/N] ":
            return "n"
        # "" accepts whichever bracketed default the wizard offers for any other prompt
        return ""

    hotdocs_init.main(
        [],
        tool_root=str(tool_root1),
        input_fn=input_fn_1,
        output_fn=outputs1.append,
        env={},
        cwd=str(project1),
    )

    assert any("connection failed: auth: bad" in line for line in outputs1)
    entries1 = [json.loads(l) for l in log1.read_text().splitlines() if l.strip()]
    assert not any(e["call"] == "save_config" for e in entries1)

    log2 = harness / "log2.jsonl"
    log2.write_text("")
    control2 = harness / "control2.json"
    _write_control(control2, {"ok": False, "error": {"category": "auth", "message": "bad"}}, {"ok": True})

    tool_root2 = make_tool_root(tmp_path / "tool_root2")
    project2 = tmp_path / "project2"
    project2.mkdir()

    monkeypatch.setenv("HOTDOCS_TEST_CONTROL", str(control2))
    monkeypatch.setenv("HOTDOCS_TEST_LOG", str(log2))

    outputs2 = []

    def input_fn_2(prompt):
        if prompt == "Save anyway? [y/N] ":
            return "y"
        return ""

    hotdocs_init.main(
        [],
        tool_root=str(tool_root2),
        input_fn=input_fn_2,
        output_fn=outputs2.append,
        env={},
        cwd=str(project2),
    )

    assert any("connection failed: auth: bad" in line for line in outputs2)
    entries2 = [json.loads(l) for l in log2.read_text().splitlines() if l.strip()]
    assert any(e["call"] == "save_config" for e in entries2)


def test_ac_init_005_check_connection_value_error_is_invalid(tmp_path, monkeypatch):
    harness = tmp_path / "harness"
    harness.mkdir()
    log_path = harness / "log.jsonl"
    log_path.write_text("")
    control_path = harness / "control.json"
    _write_control(control_path, {"raise": "no base_url"}, {"ok": True})

    tool_root = make_tool_root(tmp_path / "tool_root")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    monkeypatch.setenv("HOTDOCS_TEST_CONTROL", str(control_path))
    monkeypatch.setenv("HOTDOCS_TEST_LOG", str(log_path))

    outputs = []
    hotdocs_init.main(
        ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        tool_root=str(tool_root),
        input_fn=_no_input,
        output_fn=outputs.append,
        env={},
        cwd=str(project_dir),
    )

    assert any("connection failed: invalid: no base_url" in line for line in outputs)


def test_ac_init_005_save_config_value_error_does_not_change_exit_code(tmp_path, monkeypatch, capsys):
    def run(save_behavior, subdir):
        harness = tmp_path / f"harness_{subdir}"
        harness.mkdir()
        log_path = harness / "log.jsonl"
        log_path.write_text("")
        control_path = harness / "control.json"
        _write_control(control_path, {"ok": True, "error": None}, save_behavior)

        tool_root = make_tool_root(tmp_path / f"tool_{subdir}")
        project_dir = tmp_path / f"project_{subdir}"
        project_dir.mkdir()

        monkeypatch.setenv("HOTDOCS_TEST_CONTROL", str(control_path))
        monkeypatch.setenv("HOTDOCS_TEST_LOG", str(log_path))

        outputs = []
        code = hotdocs_init.main(
            ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
            tool_root=str(tool_root),
            input_fn=_no_input,
            output_fn=outputs.append,
            env={},
            cwd=str(project_dir),
        )
        return code

    baseline_code = run({"ok": True}, "baseline")
    capsys.readouterr()

    fail_code = run({"raise": "nope"}, "fail")
    stderr = capsys.readouterr().err

    assert "could not save: nope" in stderr
    assert fail_code == baseline_code


def test_ac_init_005_no_test_skips_check_connection(tmp_path, monkeypatch):
    harness = tmp_path / "harness"
    harness.mkdir()
    log_path = harness / "log.jsonl"
    log_path.write_text("")
    control_path = harness / "control.json"
    _write_control(control_path, {"ok": True, "error": None}, {"ok": True})

    tool_root = make_tool_root(tmp_path / "tool_root")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    monkeypatch.setenv("HOTDOCS_TEST_CONTROL", str(control_path))
    monkeypatch.setenv("HOTDOCS_TEST_LOG", str(log_path))

    hotdocs_init.main(
        ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY", "--no-test"],
        tool_root=str(tool_root),
        input_fn=_no_input,
        output_fn=lambda msg: None,
        env={},
        cwd=str(project_dir),
    )

    entries = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
    assert not any(e["call"] == "check_connection" for e in entries)