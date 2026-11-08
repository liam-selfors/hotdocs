import importlib.metadata
import json
from pathlib import Path
from string import Template

import hotdocs_init


_LLM_ENDPOINT_TEMPLATE = Template(r'''
import json
import shutil

PROVIDERS = $providers

_DETECT_ENTRIES = $detect_entries
_LOG_PATH = $log_path
_DYNAMIC_CLAUDE_CLI = $dynamic_claude_cli


def _log(record):
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")


def detect_providers(env=None, probe_ollama=True):
    _log({
        "call": "detect_providers",
        "env": dict(env) if env is not None else None,
        "probe_ollama": probe_ollama,
    })
    entries = [dict(e) for e in _DETECT_ENTRIES]
    if _DYNAMIC_CLAUDE_CLI:
        path_value = (env or {}).get("PATH", "")
        found = shutil.which("claude", path=path_value) is not None
        for e in entries:
            if e["provider"] == "claude-cli":
                e["available"] = found
    return entries


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log({
        "call": "check_connection",
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
    })
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider].get("needs_base_url") and not base_url:
        raise ValueError("base_url required for " + str(provider))
    return {"ok": True, "error": None}


def save_config(*args, **kwargs):
    names = ["config_path", "provider", "model", "base_url", "api_key_env", "timeout_seconds"]
    provided = {}
    for i, val in enumerate(args):
        provided[names[i]] = val
    for k, v in kwargs.items():
        provided[k] = v
    _log({
        "call": "save_config",
        "provided_keys": sorted(provided.keys()),
        "values": {k: v for k, v in provided.items() if k != "config_path"},
    })
    config_path = provided.get("config_path")
    if config_path is not None:
        with open(config_path, "a") as f:
            f.write("\n[llm]\n")
            f.write("provider = " + json.dumps(provided.get("provider")) + "\n")
            f.write("model = " + json.dumps(provided.get("model")) + "\n")
    return None


def load_config(config_path=None):
    _log({"call": "load_config", "config_path": str(config_path) if config_path else None})
    return None
''')


def _llm_endpoint_source(providers, detect_entries, log_path, dynamic_claude_cli=False):
    return _LLM_ENDPOINT_TEMPLATE.substitute(
        providers=repr(providers),
        detect_entries=repr(detect_entries),
        log_path=repr(str(log_path)),
        dynamic_claude_cli=repr(bool(dynamic_claude_cli)),
    )


def _base_tool_root(root: Path) -> None:
    (root / "examples" / "slugify" / "specs" / "product").mkdir(parents=True, exist_ok=True)
    (root / "examples" / "slugify" / "specs" / "product" / "slugs.md").write_text(
        "example slugs fixture\n"
    )
    version = importlib.metadata.version("pytest")
    (root / "requirements.txt").write_text("pytest==" + version + "\n")


def _write_llm_endpoint(root: Path, source: str) -> None:
    mod_dir = root / "gen" / "llm-endpoint"
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "llm_endpoint.py").write_text(source)


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _save_config_calls(log_path: Path):
    return [r for r in _read_log(log_path) if r.get("call") == "save_config"]


def make_input_fn(answers):
    calls = []
    it = iter(answers)

    def input_fn(prompt):
        calls.append(prompt)
        try:
            return next(it)
        except StopIteration:
            raise AssertionError("unexpected extra input_fn call with prompt: " + repr(prompt))

    input_fn.calls = calls
    return input_fn


def make_output_fn():
    messages = []

    def output_fn(msg):
        messages.append(msg)

    output_fn.messages = messages
    return output_fn


def _no_input_fn(prompt):
    raise AssertionError("unexpected input prompt: " + repr(prompt))


def _assert_prompt_mentions(prompt, *keywords):
    lowered = prompt.lower()
    assert any(k in lowered for k in keywords), (
        "prompt " + repr(prompt) + " does not mention any of " + repr(keywords)
    )


def test_ac_init_004_empty_answers_order_and_save(tmp_path):
    tool_root = tmp_path / "tool_root1"
    tool_root.mkdir()
    _base_tool_root(tool_root)
    log_path = tmp_path / "log1.jsonl"
    providers = {
        "ollama": {
            "default_base_url": None,
            "default_api_key_env": None,
            "needs_base_url": False,
            "suggested_model": "",
        },
        "openai": {
            "default_base_url": None,
            "default_api_key_env": "OPENAI_API_KEY",
            "needs_base_url": False,
            "suggested_model": "gpt-x",
        },
    }
    detect_entries = [
        {"provider": "ollama", "available": False, "reason": "not running", "suggested_model": "", "api_key_env": None},
        {"provider": "openai", "available": True, "reason": None, "suggested_model": "gpt-x", "api_key_env": "OPENAI_API_KEY"},
    ]
    _write_llm_endpoint(tool_root, _llm_endpoint_source(providers, detect_entries, log_path))

    project_dir = tmp_path / "project1"
    project_dir.mkdir()

    input_fn = make_input_fn(["", "", ""])
    output_fn = make_output_fn()

    rc = hotdocs_init.main(
        [str(project_dir), "--no-test"],
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=output_fn,
        env={},
    )

    assert rc == 0
    assert len(input_fn.calls) == 3
    _assert_prompt_mentions(input_fn.calls[0], "provider")
    _assert_prompt_mentions(input_fn.calls[1], "model")
    _assert_prompt_mentions(input_fn.calls[2], "key", "env")

    haystack = "\n".join(str(m) for m in output_fn.messages) + "\n" + "\n".join(input_fn.calls)
    assert "ollama" in haystack
    assert "openai" in haystack

    calls = _save_config_calls(log_path)
    assert len(calls) == 1
    values = calls[0]["values"]
    assert values.get("provider") == "openai"
    assert values.get("model") == "gpt-x"
    assert values.get("api_key_env") == "OPENAI_API_KEY"


def test_ac_init_004_invalid_then_numeric_provider_selection(tmp_path):
    tool_root = tmp_path / "tool_root2"
    tool_root.mkdir()
    _base_tool_root(tool_root)
    log_path = tmp_path / "log2.jsonl"
    providers = {
        "ollama": {
            "default_base_url": None,
            "default_api_key_env": None,
            "needs_base_url": False,
            "suggested_model": "",
        },
        "openai": {
            "default_base_url": None,
            "default_api_key_env": "OPENAI_API_KEY",
            "needs_base_url": False,
            "suggested_model": "gpt-x",
        },
    }
    detect_entries = [
        {"provider": "ollama", "available": False, "reason": "not running", "suggested_model": "", "api_key_env": None},
        {"provider": "openai", "available": True, "reason": None, "suggested_model": "gpt-x", "api_key_env": "OPENAI_API_KEY"},
    ]
    _write_llm_endpoint(tool_root, _llm_endpoint_source(providers, detect_entries, log_path))

    project_dir = tmp_path / "project2"
    project_dir.mkdir()

    input_fn = make_input_fn(["bogus", "2", "", ""])
    output_fn = make_output_fn()

    rc = hotdocs_init.main(
        [str(project_dir), "--no-test"],
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=output_fn,
        env={},
    )

    assert rc == 0
    assert len(input_fn.calls) == 4
    assert input_fn.calls[0] == input_fn.calls[1]

    calls = _save_config_calls(log_path)
    assert len(calls) == 1
    values = calls[0]["values"]
    assert values.get("provider") == "openai"
    assert values.get("model") == "gpt-x"
    assert values.get("api_key_env") == "OPENAI_API_KEY"


def test_ac_init_004_openai_compatible_base_url_retry(tmp_path):
    tool_root = tmp_path / "tool_root3"
    tool_root.mkdir()
    _base_tool_root(tool_root)
    log_path = tmp_path / "log3.jsonl"
    providers = {
        "openai-compatible": {
            "default_base_url": None,
            "default_api_key_env": None,
            "needs_base_url": True,
            "suggested_model": "",
        },
    }
    detect_entries = [
        {"provider": "openai-compatible", "available": True, "reason": None, "suggested_model": "", "api_key_env": None},
    ]
    _write_llm_endpoint(tool_root, _llm_endpoint_source(providers, detect_entries, log_path))

    project_dir = tmp_path / "project3"
    project_dir.mkdir()

    input_fn = make_input_fn(["openai-compatible", "", "m", "", "http://h/v1", ""])
    output_fn = make_output_fn()

    rc = hotdocs_init.main(
        [str(project_dir), "--no-test"],
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=output_fn,
        env={},
    )

    assert rc == 0
    assert len(input_fn.calls) == 6
    assert input_fn.calls[1] == input_fn.calls[2]
    assert input_fn.calls[3] == input_fn.calls[4]

    calls = _save_config_calls(log_path)
    assert len(calls) == 1
    record = calls[0]
    assert "api_key_env" not in record["provided_keys"]
    values = record["values"]
    assert values.get("model") == "m"
    assert values.get("base_url") == "http://h/v1"


def test_ac_init_004_claude_cli_no_base_url_no_api_key(tmp_path):
    tool_root = tmp_path / "tool_root4"
    tool_root.mkdir()
    _base_tool_root(tool_root)
    log_path = tmp_path / "log4.jsonl"
    providers = {
        "claude-cli": {
            "default_base_url": None,
            "default_api_key_env": None,
            "needs_base_url": False,
            "suggested_model": "claude-sonnet-5",
        },
    }
    detect_entries = [
        {"provider": "claude-cli", "available": False, "reason": None, "suggested_model": "claude-sonnet-5", "api_key_env": None},
    ]
    _write_llm_endpoint(
        tool_root, _llm_endpoint_source(providers, detect_entries, log_path, dynamic_claude_cli=True)
    )

    bin_dir = tmp_path / "bin4"
    bin_dir.mkdir()
    claude_path = bin_dir / "claude"
    claude_path.write_text("#!/bin/sh\necho fake-claude\n")
    claude_path.chmod(0o755)

    project_dir = tmp_path / "project4"
    project_dir.mkdir()

    input_fn = make_input_fn(["", ""])
    output_fn = make_output_fn()

    rc = hotdocs_init.main(
        [str(project_dir), "--no-test"],
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=output_fn,
        env={"PATH": str(bin_dir)},
    )

    assert rc == 0
    assert len(input_fn.calls) == 2

    calls = _save_config_calls(log_path)
    assert len(calls) == 1
    assert calls[0]["values"].get("provider") == "claude-cli"


def test_ac_init_004_missing_llm_endpoint(tmp_path):
    tool_root = tmp_path / "tool_root5"
    tool_root.mkdir()
    _base_tool_root(tool_root)

    project_dir = tmp_path / "project5"
    project_dir.mkdir()

    output_fn = make_output_fn()

    rc = hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=str(tool_root),
        input_fn=_no_input_fn,
        output_fn=output_fn,
        env={},
    )

    assert rc == 0
    assert "provider not configured: gen/llm-endpoint is missing" in output_fn.messages
    assert not (project_dir / "hotdocs.toml").exists()


def test_ac_init_004_existing_config_skips_provider_step(tmp_path):
    tool_root = tmp_path / "tool_root6"
    tool_root.mkdir()
    _base_tool_root(tool_root)
    log_path = tmp_path / "log6.jsonl"
    providers = {
        "openai": {
            "default_base_url": None,
            "default_api_key_env": "OPENAI_API_KEY",
            "needs_base_url": False,
            "suggested_model": "gpt-x",
        },
    }
    detect_entries = [
        {"provider": "openai", "available": True, "reason": None, "suggested_model": "gpt-x", "api_key_env": "OPENAI_API_KEY"},
    ]
    _write_llm_endpoint(tool_root, _llm_endpoint_source(providers, detect_entries, log_path))

    project_dir = tmp_path / "project6"
    project_dir.mkdir()
    existing_content = "[other]\nfoo = 1\n"
    (project_dir / "hotdocs.toml").write_text(existing_content)

    output_fn = make_output_fn()

    hotdocs_init.main(
        [str(project_dir), "--no-test"],
        tool_root=str(tool_root),
        input_fn=_no_input_fn,
        output_fn=output_fn,
        env={},
    )

    assert (project_dir / "hotdocs.toml").read_text() == existing_content
    joined_output = "\n".join(str(m) for m in output_fn.messages).lower()
    assert "hotdocs.toml" in joined_output
    assert _save_config_calls(log_path) == []