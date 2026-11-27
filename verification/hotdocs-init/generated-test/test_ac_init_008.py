# hotdocs-criterion: sha256:ab392577c87d33fadc2ef1fd85372523eb4d72a3b961150b1a8fde5bd985f2a9
"""AC-INIT-008: .secret-allowlist.json content, and specs/decisions holds only .gitkeep."""

import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


ALLOWLIST = ".secret-allowlist.json"


FAKE_LLM_ENDPOINT_TEMPLATE = '''
import json
import tomllib
from pathlib import Path

_LOG = Path(LOG_PATH)


def _log(name, **kwargs):
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, "args": {k: repr(v) for k, v in kwargs.items()}}) + "\\n")


PROVIDERS = {
    "claude-cli": {"default_base_url": None, "default_api_key_env": None,
                   "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "anthropic": {"default_base_url": "https://api.anthropic.com",
                  "default_api_key_env": "ANTHROPIC_API_KEY",
                  "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "openai": {"default_base_url": "https://api.openai.com/v1",
               "default_api_key_env": "OPENAI_API_KEY",
               "needs_base_url": False, "suggested_model": "gpt-6-astra"},
    "openai-compatible": {"default_base_url": None, "default_api_key_env": None,
                          "needs_base_url": True, "suggested_model": ""},
    "gemini": {"default_base_url": "https://generativelanguage.googleapis.com",
               "default_api_key_env": "GEMINI_API_KEY",
               "needs_base_url": False, "suggested_model": "gemini-4-argon"},
    "ollama": {"default_base_url": "http://localhost:11434", "default_api_key_env": None,
               "needs_base_url": False, "suggested_model": "llama3.2"},
}


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", env=env, probe_ollama=probe_ollama)
    out = []
    for name, info in PROVIDERS.items():
        available = name == "ollama"
        out.append({
            "provider": name,
            "available": available,
            "reason": "reachable" if available else "not configured",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def _toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    return json.dumps(str(v))


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if not isinstance(model, str):
        raise ValueError("invalid model")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.exists():
        in_llm = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_llm = stripped == "[llm]"
                if in_llm:
                    continue
            if not in_llm:
                kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    lines = list(kept)
    if lines:
        lines.append("")
    lines.append("[llm]")
    lines.append("provider = " + _toml_value(provider))
    lines.append("model = " + _toml_value(model))
    for key, val in (("base_url", base_url), ("api_key_env", api_key_env),
                     ("timeout_seconds", timeout_seconds), ("auth", auth)):
        if val is not None:
            lines.append(key + " = " + _toml_value(val))
    path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=str(config_path))
    if config_path is None:
        config_path = Path("hotdocs.toml")
    path = Path(config_path)
    if not path.exists():
        return None
    try:
        data = tomllib.loads(path.read_bytes().decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid config: " + str(exc))
    llm = data.get("llm")
    if llm is None:
        return None
    if not isinstance(llm, dict):
        raise ValueError("invalid [llm] table")
    return {
        "provider": llm.get("provider"),
        "model": llm.get("model"),
        "base_url": llm.get("base_url"),
        "api_key_env": llm.get("api_key_env"),
        "timeout_seconds": llm.get("timeout_seconds"),
        "auth": llm.get("auth"),
    }
'''


def _make_tool_root(tmp_path):
    tool_root = tmp_path / "tool"
    log_path = tmp_path / "logs" / "llm_endpoint_calls.log"
    llm_dir = tool_root / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_LLM_ENDPOINT_TEMPLATE
    (llm_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")

    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nA tiny example product.\n", encoding="utf-8")

    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    (tool_root / "pyproject.toml").write_text(
        "[project]\n" + "name = " + json.dumps("hotdocs") + "\n"
        + "version = " + json.dumps("9.8.7a1") + "\n",
        encoding="utf-8",
    )
    return tool_root, log_path


def _run(project, tool_root, tmp_path):
    messages = []

    def output_fn(*args, **kwargs):
        messages.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        return ""

    env = {"PATH": os.environ.get("PATH", "")}
    code = hotdocs_init.run(
        [str(project), "--yes"],
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=tmp_path,
    )
    return code, messages


def _expected_allowlist_bytes():
    return (json.dumps({"version": 1, "entries": []}, indent=2) + "\n").encode("utf-8")


def test_init_writes_allowlist_bytes_and_only_gitkeep_in_decisions(tmp_path):
    tool_root, _log_path = _make_tool_root(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    code, _messages = _run(project, tool_root, tmp_path)
    assert code in (0, 3), code

    allowlist = project / ALLOWLIST
    assert allowlist.is_file()
    assert allowlist.read_bytes() == _expected_allowlist_bytes()

    decisions = project / "specs" / "decisions"
    assert decisions.is_dir()
    entries = sorted(p.relative_to(decisions).as_posix() for p in decisions.rglob("*"))
    assert entries == [".gitkeep"], entries


def test_existing_allowlist_is_skipped_and_unchanged(tmp_path):
    tool_root, _log_path = _make_tool_root(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    existing = (
        json.dumps({"version": 1, "entries": [], "note": "keep me"}, indent=4) + "\n"
    ).encode("utf-8")
    assert existing != _expected_allowlist_bytes()
    allowlist = project / ALLOWLIST
    allowlist.write_bytes(existing)

    code, messages = _run(project, tool_root, tmp_path)
    assert code in (0, 3), (code, messages)

    assert allowlist.read_bytes() == existing

    lines = []
    for message in messages:
        lines.extend(line.strip() for line in message.splitlines())
    assert ".secret-allowlist.json: skipped (exists)" in lines, messages