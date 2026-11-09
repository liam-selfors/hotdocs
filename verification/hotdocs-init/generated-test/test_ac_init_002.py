import importlib.metadata
import json

import hotdocs_init

_LLM_ENDPOINT_TEMPLATE = r'''import json

LOG_PATH = __LOG_PATH__


def _log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


PROVIDERS = {
    "fake-provider": {
        "default_base_url": None,
        "default_api_key_env": "FAKE_API_KEY",
        "needs_base_url": False,
        "suggested_model": "fake-model",
    }
}


def detect_providers(env=None, probe_ollama=True):
    _log({"fn": "detect_providers"})
    return [
        {
            "provider": "fake-provider",
            "available": True,
            "reason": "fake",
            "suggested_model": "fake-model",
            "api_key_env": "FAKE_API_KEY",
        }
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log({"fn": "check_connection"})
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log({"fn": "save_config"})
    import re
    content = ""
    try:
        with open(config_path, "r") as f:
            content = f.read()
    except OSError:
        content = ""
    content = re.sub(r"\[llm\].*?(?=\n\[|\Z)", "", content, flags=re.S)
    content = content.rstrip() + "\n\n[llm]\n"
    content += "provider = " + json.dumps(provider) + "\n"
    content += "model = " + json.dumps(model) + "\n"
    if base_url is not None:
        content += "base_url = " + json.dumps(base_url) + "\n"
    if api_key_env is not None:
        content += "api_key_env = " + json.dumps(api_key_env) + "\n"
    if timeout_seconds is not None:
        content += "timeout_seconds = " + str(timeout_seconds) + "\n"
    with open(config_path, "w") as f:
        f.write(content)


def load_config(config_path=None):
    _log({"fn": "load_config"})
    return None
'''


def _build_fake_tool_root(tool_root, log_path):
    tool_root.mkdir(parents=True)
    gen_dir = tool_root / "gen"
    gen_dir.mkdir()

    llm_endpoint_dir = gen_dir / "llm-endpoint"
    llm_endpoint_dir.mkdir()
    content = _LLM_ENDPOINT_TEMPLATE.replace("__LOG_PATH__", json.dumps(str(log_path)))
    (llm_endpoint_dir / "llm_endpoint.py").write_text(content)

    a_b_dir = gen_dir / "a-b"
    a_b_dir.mkdir()
    (a_b_dir / "a_b.py").write_text("placeholder = True\n")

    pytest_version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text("pytest==" + pytest_version + "\n")

    return tool_root


def _snapshot(root):
    result = {}
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_dir():
            result[rel] = ("dir", None)
        else:
            result[rel] = ("file", p.read_bytes())
    return result


def test_init_on_empty_directory_writes_tool_json_and_is_idempotent(tmp_path):
    tool_root = _build_fake_tool_root(tmp_path / "toolroot", tmp_path / "log.jsonl")
    target_dir = tmp_path / "project"
    target_dir.mkdir()

    def _answer_yes(prompt):
        return "y"

    argv = [
        str(target_dir),
        "--provider", "fake-provider",
        "--model", "fake-model",
        "--no-test",
        "--yes",
    ]

    hotdocs_init.main(
        argv,
        tool_root=str(tool_root),
        input_fn=_answer_yes,
        output_fn=lambda *a, **k: None,
        env={},
        cwd=str(target_dir),
    )

    gen_dir = target_dir / "gen"
    assert gen_dir.is_dir()
    assert list(gen_dir.iterdir()) == []

    entries = {p.name for p in target_dir.iterdir()}
    assert "gen" in entries
    assert ".hotdocs-tool.json" in entries
    assert entries - {"gen", ".hotdocs-tool.json"}

    assert not (target_dir / "pipeline").exists()

    tool_json_path = target_dir / ".hotdocs-tool.json"
    data = json.loads(tool_json_path.read_bytes())
    assert data == {"tool_version": "0.1.0"}

    bytes_before = tool_json_path.read_bytes()
    stat_before = tool_json_path.stat()

    hotdocs_init.main(
        argv,
        tool_root=str(tool_root),
        input_fn=_answer_yes,
        output_fn=lambda *a, **k: None,
        env={},
        cwd=str(target_dir),
    )

    bytes_after = tool_json_path.read_bytes()
    stat_after = tool_json_path.stat()
    assert bytes_after == bytes_before
    assert stat_after.st_mtime_ns == stat_before.st_mtime_ns


def test_gen_name_collision_with_tool_refuses_and_writes_nothing(tmp_path, capsys):
    tool_root = _build_fake_tool_root(tmp_path / "toolroot", tmp_path / "log.jsonl")
    log_path = tmp_path / "log.jsonl"

    target_dir = tmp_path / "project"
    target_dir.mkdir()
    gen_dir = target_dir / "gen"
    gen_dir.mkdir()
    (gen_dir / "a-b").mkdir()
    (gen_dir / "a-b" / "placeholder.py").write_text("x = 1\n")
    (gen_dir / "mine").mkdir()
    (gen_dir / "mine" / "placeholder.py").write_text("y = 2\n")

    before = _snapshot(target_dir)

    def _fail_input(prompt):
        raise AssertionError("must not prompt before refusing: " + prompt)

    ret = hotdocs_init.main(
        [str(target_dir)],
        tool_root=str(tool_root),
        input_fn=_fail_input,
        output_fn=lambda *a, **k: None,
        env={},
        cwd=str(target_dir),
    )

    captured = capsys.readouterr()
    assert ret == 1
    assert "gen/a-b" in captured.err
    assert "gen/mine" not in captured.err
    assert _snapshot(target_dir) == before
    assert not log_path.exists()


def test_target_is_tool_root_refuses_and_writes_nothing(tmp_path):
    tool_root = _build_fake_tool_root(tmp_path / "toolroot", tmp_path / "log.jsonl")
    log_path = tmp_path / "log.jsonl"
    before = _snapshot(tool_root)

    def _fail_input(prompt):
        raise AssertionError("must not prompt before refusing: " + prompt)

    ret = hotdocs_init.main(
        [str(tool_root)],
        tool_root=str(tool_root),
        input_fn=_fail_input,
        output_fn=lambda *a, **k: None,
        env={},
        cwd=str(tool_root),
    )

    assert ret == 1
    assert _snapshot(tool_root) == before
    assert not log_path.exists()
    # importing llm-endpoint creates __pycache__; refusal must precede that import.
    assert not (tool_root / "gen" / "llm-endpoint" / "__pycache__").exists()