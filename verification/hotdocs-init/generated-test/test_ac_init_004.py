import importlib.metadata
import json
import stat

import hotdocs_init


LLM_ENDPOINT_TEMPLATE = r'''
import json

_LOG_PATH = %r
PROVIDERS = %r
_DETECTED = %r
_UNSET = object()


def detect_providers(env=None, probe_ollama=True):
    return [dict(entry) for entry in _DETECTED]


def save_config(config_path, provider, model, base_url=None, api_key_env=_UNSET, timeout_seconds=None):
    record = {
        "config_path": str(config_path),
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env_passed": api_key_env is not _UNSET,
        "api_key_env": None if api_key_env is _UNSET else api_key_env,
        "timeout_seconds": timeout_seconds,
    }
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")
    with open(config_path, "a") as f:
        f.write("\n[llm]\n")


def load_config(config_path=None):
    return None


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    return {"ok": True, "error": None}
'''


def build_llm_endpoint_source(providers, detected, log_path):
    return LLM_ENDPOINT_TEMPLATE % (str(log_path), providers, detected)


def make_tool_root(base_dir, llm_endpoint_source=None):
    tool_root = base_dir / "tool_root"
    gen_dir = tool_root / "gen"
    gen_dir.mkdir(parents=True)
    if llm_endpoint_source is not None:
        ep_dir = gen_dir / "llm-endpoint"
        ep_dir.mkdir()
        (ep_dir / "llm_endpoint.py").write_text(llm_endpoint_source)
    slugify_dir = tool_root / "examples" / "slugify" / "specs" / "product"
    slugify_dir.mkdir(parents=True)
    (slugify_dir / "slugs.md").write_text("# slugs\n")
    pytest_version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text("pytest==" + pytest_version + "\n")
    return tool_root


def read_log(path):
    if not path.exists():
        return []
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


class ScriptedInput:
    def __init__(self, answers):
        self._answers = list(answers)
        self.questions = []

    def __call__(self, prompt):
        self.questions.append(prompt)
        if not self._answers:
            raise AssertionError("no scripted answer left for prompt: %r" % (prompt,))
        return self._answers.pop(0)


class RecordingOutput:
    def __init__(self):
        self.messages = []

    def __call__(self, *args, **kwargs):
        sep = kwargs.get("sep", " ")
        self.messages.append(sep.join(str(a) for a in args))


def test_ac_init_004_default_answers_pick_available_provider(tmp_path):
    log_path = tmp_path / "save_config.log"
    providers = {
        "ollama": {
            "default_base_url": "http://localhost:11434",
            "default_api_key_env": None,
            "needs_base_url": False,
            "suggested_model": "llama3",
        },
        "openai": {
            "default_base_url": None,
            "default_api_key_env": "OPENAI_API_KEY",
            "needs_base_url": False,
            "suggested_model": "gpt-x",
        },
    }
    detected = [
        {"provider": "ollama", "available": False, "reason": "not running",
         "suggested_model": "llama3", "api_key_env": None},
        {"provider": "openai", "available": True, "reason": "",
         "suggested_model": "gpt-x", "api_key_env": "OPENAI_API_KEY"},
    ]
    tool_root = make_tool_root(tmp_path, build_llm_endpoint_source(providers, detected, log_path))
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    scripted = ScriptedInput(["", "", ""])
    output = RecordingOutput()

    exit_code = hotdocs_init.main(
        [str(project_dir)],
        tool_root=tool_root,
        input_fn=scripted,
        output_fn=output,
        env={},
        cwd=str(project_dir),
    )

    assert exit_code == 0
    assert len(scripted.questions) == 3

    printed = "\n".join(output.messages)
    assert "ollama" in printed
    assert "openai" in printed

    records = read_log(log_path)
    assert len(records) == 1
    record = records[0]
    assert record["provider"] == "openai"
    assert record["model"] == "gpt-x"
    assert record["api_key_env"] == "OPENAI_API_KEY"


def test_ac_init_004_invalid_provider_answer_is_reasked_then_numeric_selection(tmp_path):
    log_path = tmp_path / "save_config.log"
    providers = {
        "ollama": {
            "default_base_url": "http://localhost:11434",
            "default_api_key_env": None,
            "needs_base_url": False,
            "suggested_model": "llama3",
        },
        "openai": {
            "default_base_url": None,
            "default_api_key_env": "OPENAI_API_KEY",
            "needs_base_url": False,
            "suggested_model": "gpt-x",
        },
    }
    detected = [
        {"provider": "ollama", "available": False, "reason": "not running",
         "suggested_model": "llama3", "api_key_env": None},
        {"provider": "openai", "available": True, "reason": "",
         "suggested_model": "gpt-x", "api_key_env": "OPENAI_API_KEY"},
    ]
    tool_root = make_tool_root(tmp_path, build_llm_endpoint_source(providers, detected, log_path))
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    scripted = ScriptedInput(["bogus", "2", "", ""])
    output = RecordingOutput()

    exit_code = hotdocs_init.main(
        [str(project_dir)],
        tool_root=tool_root,
        input_fn=scripted,
        output_fn=output,
        env={},
        cwd=str(project_dir),
    )

    assert exit_code == 0
    assert len(scripted.questions) == 4
    assert scripted.questions[0] == scripted.questions[1]

    records = read_log(log_path)
    assert len(records) == 1
    assert records[0]["provider"] == "openai"


def test_ac_init_004_openai_compatible_needs_base_url_and_reasks(tmp_path):
    log_path = tmp_path / "save_config.log"
    providers = {
        "openai-compatible": {
            "default_base_url": None,
            "default_api_key_env": None,
            "needs_base_url": True,
            "suggested_model": "",
        },
    }
    detected = [
        {"provider": "openai-compatible", "available": False, "reason": "needs base url",
         "suggested_model": "", "api_key_env": None},
    ]
    tool_root = make_tool_root(tmp_path, build_llm_endpoint_source(providers, detected, log_path))
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    scripted = ScriptedInput([
        "openai-compatible",
        "",
        "m",
        "",
        "http://h/v1",
        "",
    ])
    output = RecordingOutput()

    exit_code = hotdocs_init.main(
        [str(project_dir)],
        tool_root=tool_root,
        input_fn=scripted,
        output_fn=output,
        env={},
        cwd=str(project_dir),
    )

    assert exit_code == 0
    assert len(scripted.questions) == 6
    assert scripted.questions[1] == scripted.questions[2]
    assert scripted.questions[3] == scripted.questions[4]

    records = read_log(log_path)
    assert len(records) == 1
    record = records[0]
    assert record["provider"] == "openai-compatible"
    assert record["model"] == "m"
    assert record["base_url"] == "http://h/v1"
    assert record["api_key_env_passed"] is False


def test_ac_init_004_claude_cli_skips_base_url_and_api_key_question(tmp_path):
    log_path = tmp_path / "save_config.log"
    providers = {
        "claude-cli": {
            "default_base_url": None,
            "default_api_key_env": None,
            "needs_base_url": False,
            "suggested_model": "claude-sonnet-5",
        },
    }
    detected = [
        {"provider": "claude-cli", "available": True, "reason": "",
         "suggested_model": "claude-sonnet-5", "api_key_env": None},
    ]
    tool_root = make_tool_root(tmp_path, build_llm_endpoint_source(providers, detected, log_path))
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    path_dir = tmp_path / "fakebin"
    path_dir.mkdir()
    claude_bin = path_dir / "claude"
    claude_bin.write_text("#!/bin/sh\necho claude\n")
    claude_bin.chmod(claude_bin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    scripted = ScriptedInput(["", ""])
    output = RecordingOutput()

    exit_code = hotdocs_init.main(
        [str(project_dir)],
        tool_root=tool_root,
        input_fn=scripted,
        output_fn=output,
        env={"PATH": str(path_dir)},
        cwd=str(project_dir),
    )

    assert exit_code == 0
    assert len(scripted.questions) == 2

    records = read_log(log_path)
    assert len(records) == 1
    record = records[0]
    assert record["provider"] == "claude-cli"
    assert record["base_url"] is None
    assert record["api_key_env_passed"] is False


def test_ac_init_004_missing_llm_endpoint_reports_and_continues(tmp_path):
    tool_root = make_tool_root(tmp_path, llm_endpoint_source=None)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    scripted = ScriptedInput([])
    output = RecordingOutput()

    exit_code = hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        input_fn=scripted,
        output_fn=output,
        env={},
        cwd=str(project_dir),
    )

    assert exit_code == 0
    assert any("provider not configured: gen/llm-endpoint is missing" in m for m in output.messages)
    assert not (project_dir / "hotdocs.toml").exists()


def test_ac_init_004_existing_hotdocs_toml_skips_provider_step(tmp_path):
    log_path = tmp_path / "save_config.log"
    providers = {
        "openai": {
            "default_base_url": None,
            "default_api_key_env": "OPENAI_API_KEY",
            "needs_base_url": False,
            "suggested_model": "gpt-x",
        },
    }
    detected = [
        {"provider": "openai", "available": True, "reason": "",
         "suggested_model": "gpt-x", "api_key_env": "OPENAI_API_KEY"},
    ]
    tool_root = make_tool_root(tmp_path, build_llm_endpoint_source(providers, detected, log_path))

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    toml_path = project_dir / "hotdocs.toml"
    original_content = "[other]\nfoo = 1\n"
    toml_path.write_text(original_content)

    output = RecordingOutput()

    hotdocs_init.main(
        [str(project_dir)],
        tool_root=tool_root,
        input_fn=lambda prompt: "",
        output_fn=output,
        env={},
        cwd=str(project_dir),
    )

    assert toml_path.read_text() == original_content
    assert read_log(log_path) == []
    assert any("hotdocs.toml" in m for m in output.messages)