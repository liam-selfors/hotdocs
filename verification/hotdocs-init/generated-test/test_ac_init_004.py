import importlib.metadata
import json

import hotdocs_init

_FAKE_LLM_ENDPOINT_TEMPLATE = '''
import json

LOG_PATH = %r

def _log(record):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\\n")

PROVIDERS = %r

_DETECT_RESULT = %r

_UNSET = "__unset_sentinel__"

def detect_providers(env=None, probe_ollama=True):
    _log({"call": "detect_providers"})
    return _DETECT_RESULT

def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log({
        "call": "check_connection",
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
    })
    return {"ok": True, "error": None}

def save_config(config_path, provider, model, base_url=None, api_key_env=_UNSET, timeout_seconds=None):
    passed = api_key_env is not _UNSET
    value = api_key_env if passed else None
    _log({
        "call": "save_config",
        "config_path": str(config_path),
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": value,
        "api_key_env_passed": passed,
        "timeout_seconds": timeout_seconds,
    })
    with open(config_path, "w") as f:
        f.write("[llm]\\n")

def load_config(config_path=None):
    _log({"call": "load_config"})
    return None
'''


def _write_fake_llm_endpoint(gen_dir, providers, detect_result, log_path):
    module_dir = gen_dir / "llm-endpoint"
    module_dir.mkdir(parents=True, exist_ok=True)
    source = _FAKE_LLM_ENDPOINT_TEMPLATE % (str(log_path), providers, detect_result)
    (module_dir / "llm_endpoint.py").write_text(source)


def _build_fixture(tmp_path, providers=None, detect_result=None, *, include_llm_endpoint=True):
    tool_root = tmp_path / "tool_root"
    project_dir = tmp_path / "project"
    log_path = tmp_path / "log.jsonl"
    tool_root.mkdir()
    project_dir.mkdir()

    gen_dir = tool_root / "gen"
    gen_dir.mkdir()
    if include_llm_endpoint:
        _write_fake_llm_endpoint(gen_dir, providers, detect_result, log_path)

    pipeline_dir = tool_root / "pipeline" / "criterion-compiler"
    pipeline_dir.mkdir(parents=True)
    (pipeline_dir / "criterion_compiler.py").write_text("# stub\n")

    pytest_version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text("pytest==%s\n" % pytest_version)

    return tool_root, project_dir, log_path


def _run_init(tool_root, project_dir, input_fn, output_fn, *, env=None, extra_args=None):
    argv = [str(project_dir)] + (extra_args or [])
    kwargs = {"tool_root": tool_root, "input_fn": input_fn, "output_fn": output_fn}
    if env is not None:
        kwargs["env"] = env
    return hotdocs_init.main(argv, **kwargs)


def _read_log(log_path):
    if not log_path.exists():
        return []
    lines = [line for line in log_path.read_text().splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


_OLLAMA_OPENAI_PROVIDERS = {
    "ollama": {
        "default_base_url": "http://localhost:11434",
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "llama3.1",
    },
    "openai": {
        "default_base_url": None,
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-x",
    },
}

_OLLAMA_OPENAI_DETECT_RESULT = [
    {
        "provider": "ollama",
        "available": False,
        "reason": "not running",
        "suggested_model": "llama3.1",
        "api_key_env": None,
    },
    {
        "provider": "openai",
        "available": True,
        "reason": None,
        "suggested_model": "gpt-x",
        "api_key_env": "OPENAI_API_KEY",
    },
]


def test_empty_answers_pick_first_available_provider_and_its_defaults(tmp_path):
    tool_root, project_dir, log_path = _build_fixture(
        tmp_path, _OLLAMA_OPENAI_PROVIDERS, _OLLAMA_OPENAI_DETECT_RESULT
    )

    prompts = []

    def input_fn(prompt):
        prompts.append(prompt)
        return ""

    outputs = []
    code = _run_init(
        tool_root, project_dir, input_fn, outputs.append, extra_args=["--no-test"]
    )

    assert code == 0
    assert len(prompts) == 3
    assert "provider" in prompts[0].lower()
    assert "model" in prompts[1].lower()
    assert any(
        kw in prompts[2].lower()
        for kw in ("api key", "api-key", "key env", "environment variable", "env var")
    )

    joined = "\n".join(str(o) for o in outputs).lower()
    assert "ollama" in joined
    assert "openai" in joined

    save_calls = [c for c in _read_log(log_path) if c["call"] == "save_config"]
    assert len(save_calls) == 1
    assert save_calls[0]["provider"] == "openai"
    assert save_calls[0]["model"] == "gpt-x"
    assert save_calls[0]["api_key_env_passed"] is True
    assert save_calls[0]["api_key_env"] == "OPENAI_API_KEY"


def test_invalid_provider_answer_is_reasked_then_number_selects_second(tmp_path):
    tool_root, project_dir, log_path = _build_fixture(
        tmp_path, _OLLAMA_OPENAI_PROVIDERS, _OLLAMA_OPENAI_DETECT_RESULT
    )

    answers = iter(["bogus", "2", "", ""])
    prompts = []

    def input_fn(prompt):
        prompts.append(prompt)
        return next(answers)

    outputs = []
    code = _run_init(
        tool_root, project_dir, input_fn, outputs.append, extra_args=["--no-test"]
    )

    assert code == 0
    assert len(prompts) == 4
    assert prompts[0] == prompts[1]
    assert "provider" in prompts[0].lower()
    assert "model" in prompts[2].lower()

    save_calls = [c for c in _read_log(log_path) if c["call"] == "save_config"]
    assert len(save_calls) == 1
    assert save_calls[0]["provider"] == "openai"


_OPENAI_COMPATIBLE_PROVIDERS = {
    "openai-compatible": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": True,
        "suggested_model": "",
    },
}

_OPENAI_COMPATIBLE_DETECT_RESULT = [
    {
        "provider": "openai-compatible",
        "available": True,
        "reason": None,
        "suggested_model": "",
        "api_key_env": None,
    },
]


def test_openai_compatible_asks_model_and_base_url_twice_each(tmp_path):
    tool_root, project_dir, log_path = _build_fixture(
        tmp_path, _OPENAI_COMPATIBLE_PROVIDERS, _OPENAI_COMPATIBLE_DETECT_RESULT
    )

    answers = iter(["openai-compatible", "", "m", "", "http://h/v1", ""])
    prompts = []

    def input_fn(prompt):
        prompts.append(prompt)
        return next(answers)

    outputs = []
    code = _run_init(
        tool_root, project_dir, input_fn, outputs.append, extra_args=["--no-test"]
    )

    assert code == 0
    assert len(prompts) == 6
    assert prompts[1] == prompts[2]
    assert prompts[3] == prompts[4]
    assert "model" in prompts[1].lower()
    assert any(kw in prompts[3].lower() for kw in ("base url", "base-url", "url"))

    save_calls = [c for c in _read_log(log_path) if c["call"] == "save_config"]
    assert len(save_calls) == 1
    assert save_calls[0]["model"] == "m"
    assert save_calls[0]["base_url"] == "http://h/v1"
    assert save_calls[0]["api_key_env_passed"] is False


_CLAUDE_CLI_PROVIDERS = {
    "claude-cli": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
}

_CLAUDE_CLI_DETECT_RESULT = [
    {
        "provider": "claude-cli",
        "available": True,
        "reason": None,
        "suggested_model": "claude-sonnet-5",
        "api_key_env": None,
    },
]


def test_claude_cli_skips_base_url_and_api_key_questions(tmp_path):
    tool_root, project_dir, log_path = _build_fixture(
        tmp_path, _CLAUDE_CLI_PROVIDERS, _CLAUDE_CLI_DETECT_RESULT
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    claude_path = bin_dir / "claude"
    claude_path.write_text("#!/bin/sh\necho ok\n")
    claude_path.chmod(0o755)
    env = {"PATH": str(bin_dir)}

    prompts = []

    def input_fn(prompt):
        prompts.append(prompt)
        return ""

    outputs = []
    code = _run_init(
        tool_root,
        project_dir,
        input_fn,
        outputs.append,
        env=env,
        extra_args=["--no-test"],
    )

    assert code == 0
    assert len(prompts) == 2
    assert "provider" in prompts[0].lower()
    assert "model" in prompts[1].lower()

    save_calls = [c for c in _read_log(log_path) if c["call"] == "save_config"]
    assert len(save_calls) == 1
    assert save_calls[0]["provider"] == "claude-cli"
    assert save_calls[0]["api_key_env_passed"] is False


def test_missing_llm_endpoint_reports_and_continues(tmp_path):
    tool_root, project_dir, log_path = _build_fixture(
        tmp_path, include_llm_endpoint=False
    )

    def input_fn(prompt):
        raise AssertionError("input_fn should not be called with --yes")

    outputs = []
    code = _run_init(
        tool_root,
        project_dir,
        input_fn,
        outputs.append,
        extra_args=["--yes", "--no-test"],
    )

    assert code == 0
    assert "provider not configured: gen/llm-endpoint is missing" in outputs
    assert not (project_dir / "hotdocs.toml").exists()


def test_existing_hotdocs_toml_skips_provider_step_unchanged(tmp_path):
    tool_root, project_dir, log_path = _build_fixture(
        tmp_path, _OLLAMA_OPENAI_PROVIDERS, _OLLAMA_OPENAI_DETECT_RESULT
    )

    config_path = project_dir / "hotdocs.toml"
    original_content = '[llm]\nprovider = "existing"\nmodel = "existing-model"\n'
    config_path.write_text(original_content)

    def input_fn(prompt):
        raise AssertionError("input_fn should not be called when hotdocs.toml exists")

    outputs = []
    code = _run_init(
        tool_root, project_dir, input_fn, outputs.append, extra_args=["--no-test"]
    )

    assert code == 0
    assert config_path.read_text() == original_content

    save_calls = [c for c in _read_log(log_path) if c["call"] == "save_config"]
    assert len(save_calls) == 0

    joined = "\n".join(str(o) for o in outputs).lower()
    assert "hotdocs.toml" in joined or "already" in joined or "skip" in joined