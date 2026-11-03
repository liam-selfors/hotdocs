import json

import hotdocs_init


_TEMPLATE = '''
import json

LOG_PATH = __LOG_PATH__
PROVIDERS = __PROVIDERS__
_DETECT = __DETECT__


def _log(name, kwargs):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"name": name, "kwargs": kwargs}) + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", {"env": env, "probe_ollama": probe_ollama})
    return [dict(p) for p in _DETECT]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log(
        "check_connection",
        {
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "api_key_env": api_key_env,
            "timeout_seconds": timeout_seconds,
        },
    )
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log(
        "save_config",
        {
            "config_path": str(config_path),
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "api_key_env": api_key_env,
            "timeout_seconds": timeout_seconds,
        },
    )
    lines = ["[llm]"]
    lines.append("provider = " + json.dumps(provider))
    lines.append("model = " + json.dumps(model))
    if base_url is not None:
        lines.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + json.dumps(timeout_seconds))
    with open(config_path, "w") as f:
        f.write("\\n".join(lines) + "\\n")


def load_config(config_path=None):
    _log("load_config", {"config_path": str(config_path) if config_path else None})
    return None
'''


def _llm_endpoint_source(log_path, providers, detect_list):
    src = _TEMPLATE
    src = src.replace("__LOG_PATH__", repr(str(log_path)))
    src = src.replace("__PROVIDERS__", repr(providers))
    src = src.replace("__DETECT__", repr(detect_list))
    return src


def _make_tool_root(tmp_path, name, llm_endpoint_source=None):
    tool_root = tmp_path / name
    (tool_root / "pipeline" / "criterion-compiler").mkdir(parents=True)
    (tool_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py").write_text(
        "def compile_criterion(*args, **kwargs):\n    raise NotImplementedError\n"
    )
    (tool_root / "examples" / "slugify" / "specs" / "product").mkdir(parents=True)
    (tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md").write_text(
        "# slugs\n"
    )
    (tool_root / "requirements.txt").write_text("pytest\n")
    if llm_endpoint_source is not None:
        endpoint_dir = tool_root / "gen" / "llm-endpoint"
        endpoint_dir.mkdir(parents=True)
        (endpoint_dir / "llm_endpoint.py").write_text(llm_endpoint_source)
    return tool_root


def _read_log(log_path):
    if not log_path.exists():
        return []
    entries = []
    for line in log_path.read_text().splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def _classify_prompt(prompt):
    lowered = str(prompt).lower()
    if "api" in lowered and "key" in lowered:
        return "apikey"
    if "base" in lowered or "url" in lowered:
        return "baseurl"
    if "provider" in lowered:
        return "provider"
    if "model" in lowered:
        return "model"
    return "unknown"


class _ScriptedInput:
    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, prompt=""):
        self.prompts.append(prompt)
        if not self.answers:
            raise AssertionError(
                "ran out of scripted answers; last prompt was %r" % (prompt,)
            )
        return self.answers.pop(0)


class _Recorder:
    def __init__(self):
        self.messages = []

    def __call__(self, *args, **kwargs):
        self.messages.append(" ".join(str(a) for a in args))


def _failing_input(prompt=""):
    raise AssertionError("input_fn should not be called, got prompt %r" % (prompt,))


def test_ac_init_004_default_answers_pick_first_available_provider(tmp_path):
    log_path = tmp_path / "calls_1.log"
    providers = {
        "ollama": {
            "default_base_url": "http://localhost:11434",
            "default_api_key_env": None,
            "needs_base_url": False,
            "suggested_model": "llama3.1:8b",
        },
        "openai": {
            "default_base_url": None,
            "default_api_key_env": "OPENAI_API_KEY",
            "needs_base_url": False,
            "suggested_model": "gpt-x",
        },
    }
    detect_list = [
        {
            "provider": "ollama",
            "available": False,
            "reason": "ollama is not reachable",
            "suggested_model": "llama3.1:8b",
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
    tool_root = _make_tool_root(
        tmp_path, "tool_root_1", _llm_endpoint_source(log_path, providers, detect_list)
    )
    project_dir = tmp_path / "project_1"
    project_dir.mkdir()

    scripted = _ScriptedInput(["", "", ""])
    output = _Recorder()

    exit_code = hotdocs_init.main(
        [str(project_dir)],
        tool_root=str(tool_root),
        input_fn=scripted,
        output_fn=output,
        cwd=str(project_dir),
    )

    assert exit_code == 0

    kinds = [_classify_prompt(p) for p in scripted.prompts]
    assert kinds == ["provider", "model", "apikey"]

    printed = "\n".join(output.messages).lower()
    assert "ollama" in printed
    assert "openai" in printed

    calls = _read_log(log_path)
    save_calls = [c for c in calls if c["name"] == "save_config"]
    assert len(save_calls) == 1
    save = save_calls[0]["kwargs"]
    assert save["provider"] == "openai"
    assert save["model"] == "gpt-x"
    assert save["api_key_env"] == "OPENAI_API_KEY"


def test_ac_init_004_invalid_provider_then_numeric_selection(tmp_path):
    log_path = tmp_path / "calls_2.log"
    providers = {
        "ollama": {
            "default_base_url": "http://localhost:11434",
            "default_api_key_env": None,
            "needs_base_url": False,
            "suggested_model": "llama3.1:8b",
        },
        "openai": {
            "default_base_url": None,
            "default_api_key_env": "OPENAI_API_KEY",
            "needs_base_url": False,
            "suggested_model": "gpt-x",
        },
    }
    detect_list = [
        {
            "provider": "ollama",
            "available": False,
            "reason": "ollama is not reachable",
            "suggested_model": "llama3.1:8b",
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
    tool_root = _make_tool_root(
        tmp_path, "tool_root_2", _llm_endpoint_source(log_path, providers, detect_list)
    )
    project_dir = tmp_path / "project_2"
    project_dir.mkdir()

    scripted = _ScriptedInput(["bogus", "2", "", ""])
    output = _Recorder()

    exit_code = hotdocs_init.main(
        [str(project_dir)],
        tool_root=str(tool_root),
        input_fn=scripted,
        output_fn=output,
        cwd=str(project_dir),
    )

    assert exit_code == 0
    assert len(scripted.prompts) >= 2
    assert _classify_prompt(scripted.prompts[0]) == "provider"
    assert _classify_prompt(scripted.prompts[1]) == "provider"

    calls = _read_log(log_path)
    save_calls = [c for c in calls if c["name"] == "save_config"]
    assert len(save_calls) == 1
    assert save_calls[0]["kwargs"]["provider"] == "openai"


def test_ac_init_004_openai_compatible_retries_model_and_base_url(tmp_path):
    log_path = tmp_path / "calls_3.log"
    providers = {
        "openai-compatible": {
            "default_base_url": None,
            "default_api_key_env": None,
            "needs_base_url": True,
            "suggested_model": "",
        },
    }
    detect_list = [
        {
            "provider": "openai-compatible",
            "available": True,
            "reason": None,
            "suggested_model": "",
            "api_key_env": None,
        },
    ]
    tool_root = _make_tool_root(
        tmp_path, "tool_root_3", _llm_endpoint_source(log_path, providers, detect_list)
    )
    project_dir = tmp_path / "project_3"
    project_dir.mkdir()

    scripted = _ScriptedInput(
        ["openai-compatible", "", "m", "", "http://h/v1", ""]
    )
    output = _Recorder()

    exit_code = hotdocs_init.main(
        [str(project_dir)],
        tool_root=str(tool_root),
        input_fn=scripted,
        output_fn=output,
        cwd=str(project_dir),
    )

    assert exit_code == 0

    kinds = [_classify_prompt(p) for p in scripted.prompts]
    assert kinds.count("model") == 2
    assert kinds.count("baseurl") == 2

    calls = _read_log(log_path)
    save_calls = [c for c in calls if c["name"] == "save_config"]
    assert len(save_calls) == 1
    save = save_calls[0]["kwargs"]
    assert save["model"] == "m"
    assert save["base_url"] == "http://h/v1"
    assert save["api_key_env"] is None


def test_ac_init_004_claude_cli_skips_base_url_and_api_key_questions(tmp_path):
    log_path = tmp_path / "calls_4.log"
    providers = {
        "claude-cli": {
            "default_base_url": None,
            "default_api_key_env": None,
            "needs_base_url": False,
            "suggested_model": "claude-sonnet-5",
        },
    }
    detect_list = [
        {
            "provider": "claude-cli",
            "available": True,
            "reason": None,
            "suggested_model": "claude-sonnet-5",
            "api_key_env": None,
        },
    ]
    tool_root = _make_tool_root(
        tmp_path, "tool_root_4", _llm_endpoint_source(log_path, providers, detect_list)
    )
    project_dir = tmp_path / "project_4"
    project_dir.mkdir()

    scripted = _ScriptedInput(["", ""])
    output = _Recorder()

    exit_code = hotdocs_init.main(
        [str(project_dir)],
        tool_root=str(tool_root),
        input_fn=scripted,
        output_fn=output,
        cwd=str(project_dir),
    )

    assert exit_code == 0
    assert len(scripted.prompts) == 2
    for prompt in scripted.prompts:
        lowered = str(prompt).lower()
        assert "base" not in lowered
        assert not ("api" in lowered and "key" in lowered)

    calls = _read_log(log_path)
    save_calls = [c for c in calls if c["name"] == "save_config"]
    assert len(save_calls) == 1
    save = save_calls[0]["kwargs"]
    assert save["provider"] == "claude-cli"
    assert save["base_url"] is None
    assert save["api_key_env"] is None


def test_ac_init_004_missing_llm_endpoint_reports_and_continues(tmp_path):
    tool_root = _make_tool_root(tmp_path, "tool_root_5", llm_endpoint_source=None)
    project_dir = tmp_path / "project_5"
    project_dir.mkdir()

    output = _Recorder()

    exit_code = hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=str(tool_root),
        input_fn=_failing_input,
        output_fn=output,
        cwd=str(project_dir),
    )

    assert exit_code == 0
    assert "provider not configured: gen/llm-endpoint is missing" in output.messages
    assert not (project_dir / "hotdocs.toml").exists()


def test_ac_init_004_existing_hotdocs_toml_skips_provider_step(tmp_path):
    log_path = tmp_path / "calls_6.log"
    providers = {
        "claude-cli": {
            "default_base_url": None,
            "default_api_key_env": None,
            "needs_base_url": False,
            "suggested_model": "claude-sonnet-5",
        },
    }
    detect_list = [
        {
            "provider": "claude-cli",
            "available": True,
            "reason": None,
            "suggested_model": "claude-sonnet-5",
            "api_key_env": None,
        },
    ]
    tool_root = _make_tool_root(
        tmp_path, "tool_root_6", _llm_endpoint_source(log_path, providers, detect_list)
    )
    project_dir = tmp_path / "project_6"
    project_dir.mkdir()

    existing_content = (
        "[llm]\nprovider = \"existing-provider\"\nmodel = \"existing-model\"\n"
    )
    (project_dir / "hotdocs.toml").write_text(existing_content)

    output = _Recorder()

    hotdocs_init.main(
        [str(project_dir)],
        tool_root=str(tool_root),
        input_fn=_failing_input,
        output_fn=output,
        cwd=str(project_dir),
    )

    assert (project_dir / "hotdocs.toml").read_text() == existing_content

    calls = _read_log(log_path)
    assert not any(c["name"] == "save_config" for c in calls)

    combined = "\n".join(output.messages).lower()
    assert "hotdocs.toml" in combined