import importlib.metadata
import json
from pathlib import Path

import hotdocs_init


def _make_tool_root(root: Path) -> Path:
    (root / "gen").mkdir(parents=True, exist_ok=True)
    (root / "pipeline" / "criterion-compiler").mkdir(parents=True, exist_ok=True)
    (root / "pipeline" / "criterion-compiler" / "criterion_compiler.py").write_text(
        "def compile(*a, **kw):\n    return None\n"
    )
    (root / "examples" / "slugify" / "specs" / "product").mkdir(parents=True, exist_ok=True)
    (root / "examples" / "slugify" / "specs" / "product" / "slugs.md").write_text("# slugs\n")
    version = importlib.metadata.version("pytest")
    (root / "requirements.txt").write_text(f"pytest=={version}\n")
    return root


def _write_fake_llm_endpoint(tool_root, log_path, check_connection_mode, save_config_mode, detect_result=None):
    mod_dir = tool_root / "gen" / "llm-endpoint"
    mod_dir.mkdir(parents=True, exist_ok=True)

    cc_bodies = {
        "ok": "return {'ok': True, 'error': None}",
        "auth_fail": "return {'ok': False, 'error': {'category': 'auth', 'message': 'bad'}}",
        "raise_invalid": "raise ValueError('no base_url')",
    }
    sc_bodies = {
        "ok": "return None",
        "raise": "raise ValueError('nope')",
    }
    detect_result = detect_result if detect_result is not None else []

    source = (
        "import json\n"
        "\n"
        f"LOG_PATH = {str(log_path)!r}\n"
        "\n"
        "def _log(name, args, kwargs):\n"
        "    with open(LOG_PATH, 'a') as f:\n"
        "        f.write(json.dumps({'call': name, 'args': [str(a) for a in args],"
        " 'kwargs': {k: str(v) for k, v in kwargs.items()}}) + '\\n')\n"
        "\n"
        "PROVIDERS = {\n"
        "    'openai': {'default_base_url': None, 'default_api_key_env': 'OPENAI_API_KEY',"
        " 'needs_base_url': False, 'suggested_model': 'gpt-4o-mini'},\n"
        "    'openai-compatible': {'default_base_url': None, 'default_api_key_env': None,"
        " 'needs_base_url': True, 'suggested_model': ''},\n"
        "}\n"
        "\n"
        "def detect_providers(env=None, probe_ollama=True):\n"
        "    _log('detect_providers', (), {'probe_ollama': probe_ollama})\n"
        f"    return {detect_result!r}\n"
        "\n"
        "def check_connection(*args, **kwargs):\n"
        "    _log('check_connection', args, kwargs)\n"
        f"    {cc_bodies[check_connection_mode]}\n"
        "\n"
        "def save_config(*args, **kwargs):\n"
        "    _log('save_config', args, kwargs)\n"
        f"    {sc_bodies[save_config_mode]}\n"
        "\n"
        "def load_config(config_path=None):\n"
        "    _log('load_config', (), {'config_path': str(config_path)})\n"
        "    return None\n"
    )
    (mod_dir / "llm_endpoint.py").write_text(source)


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def _make_input_fn(log, save_answer):
    def input_fn(prompt):
        log.append(prompt)
        if prompt == "Save anyway? [y/N] ":
            return save_answer
        lower = prompt.lower()
        if "provider" in lower:
            return "openai"
        if "model" in lower:
            return "m"
        if "key" in lower or "env" in lower:
            return "MY_KEY"
        return ""

    return input_fn


def _refusing_input_fn(prompt):
    raise AssertionError(f"init asked an unexpected question: {prompt!r}")


def test_successful_connection_prints_ok_and_saves_without_asking(tmp_path):
    tool_root = _make_tool_root(tmp_path / "tool_root")
    log_path = tmp_path / "log.jsonl"
    _write_fake_llm_endpoint(tool_root, log_path, "ok", "ok")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    outputs = []

    hotdocs_init.main(
        [str(project_dir), "--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        tool_root=tool_root,
        input_fn=_refusing_input_fn,
        output_fn=outputs.append,
    )

    assert any("connection ok" in m for m in outputs)

    calls = _read_log(log_path)
    save_calls = [c for c in calls if c["call"] == "save_config"]
    assert len(save_calls) == 1
    call = save_calls[0]
    expected_path = str(project_dir / "hotdocs.toml")
    assert call["args"][0] == expected_path
    assert call["args"][1] == "openai"
    assert call["args"][2] == "m"
    assert call["kwargs"].get("api_key_env") == "MY_KEY"
    assert "base_url" not in call["kwargs"]
    assert "timeout_seconds" not in call["kwargs"]


def test_failed_connection_asks_before_saving_and_only_saves_on_yes(tmp_path):
    tool_root_1 = _make_tool_root(tmp_path / "tool_root_1")
    log_1 = tmp_path / "log1.jsonl"
    _write_fake_llm_endpoint(
        tool_root_1,
        log_1,
        "auth_fail",
        "ok",
        detect_result=[
            {"provider": "openai", "available": True, "reason": "ok", "suggested_model": "m", "api_key_env": "MY_KEY"}
        ],
    )
    project_1 = tmp_path / "project_1"
    project_1.mkdir()
    outputs_1 = []
    prompts_1 = []

    hotdocs_init.main(
        [str(project_1), "--model", "m", "--api-key-env", "MY_KEY"],
        tool_root=tool_root_1,
        input_fn=_make_input_fn(prompts_1, save_answer="n"),
        output_fn=outputs_1.append,
    )

    assert any("connection failed: auth: bad" in m for m in outputs_1)
    assert "Save anyway? [y/N] " in prompts_1
    calls_1 = _read_log(log_1)
    assert not [c for c in calls_1 if c["call"] == "save_config"]

    tool_root_2 = _make_tool_root(tmp_path / "tool_root_2")
    log_2 = tmp_path / "log2.jsonl"
    _write_fake_llm_endpoint(
        tool_root_2,
        log_2,
        "auth_fail",
        "ok",
        detect_result=[
            {"provider": "openai", "available": True, "reason": "ok", "suggested_model": "m", "api_key_env": "MY_KEY"}
        ],
    )
    project_2 = tmp_path / "project_2"
    project_2.mkdir()
    outputs_2 = []
    prompts_2 = []

    hotdocs_init.main(
        [str(project_2), "--model", "m", "--api-key-env", "MY_KEY"],
        tool_root=tool_root_2,
        input_fn=_make_input_fn(prompts_2, save_answer="y"),
        output_fn=outputs_2.append,
    )

    assert any("connection failed: auth: bad" in m for m in outputs_2)
    assert "Save anyway? [y/N] " in prompts_2
    calls_2 = _read_log(log_2)
    assert len([c for c in calls_2 if c["call"] == "save_config"]) == 1


def test_check_connection_value_error_prints_invalid(tmp_path):
    tool_root = _make_tool_root(tmp_path / "tool_root")
    log_path = tmp_path / "log.jsonl"
    _write_fake_llm_endpoint(tool_root, log_path, "raise_invalid", "ok")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    outputs = []

    hotdocs_init.main(
        [str(project_dir), "--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        tool_root=tool_root,
        input_fn=_refusing_input_fn,
        output_fn=outputs.append,
    )

    assert any("connection failed: invalid: no base_url" in m for m in outputs)


def test_save_config_value_error_is_reported_to_stderr_and_does_not_change_exit_code(tmp_path, capsys):
    tool_root = _make_tool_root(tmp_path / "tool_root")
    log_path = tmp_path / "log.jsonl"
    _write_fake_llm_endpoint(tool_root, log_path, "ok", "raise")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    outputs = []

    exit_code = hotdocs_init.main(
        [str(project_dir), "--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        tool_root=tool_root,
        input_fn=_refusing_input_fn,
        output_fn=outputs.append,
    )

    captured = capsys.readouterr()
    assert "could not save: nope" in captured.err
    assert any("connection ok" in m for m in outputs)
    assert exit_code == 0


def test_no_test_flag_skips_check_connection(tmp_path):
    tool_root = _make_tool_root(tmp_path / "tool_root")
    log_path = tmp_path / "log.jsonl"
    _write_fake_llm_endpoint(tool_root, log_path, "ok", "ok")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    outputs = []

    hotdocs_init.main(
        [str(project_dir), "--no-test", "--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        tool_root=tool_root,
        input_fn=_refusing_input_fn,
        output_fn=outputs.append,
    )

    calls = _read_log(log_path)
    assert not [c for c in calls if c["call"] == "check_connection"]