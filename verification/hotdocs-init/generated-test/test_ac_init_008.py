# hotdocs-criterion: sha256:2c20dc4e4735e653c00e9f2379b9fccfcaa03cfb3524e6283e65a7ea3cd9db7c
import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


FAKE_LLM_ENDPOINT_BODY = '''
import json as _json
from pathlib import Path as _Path


def _log(name, **kwargs):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps({"call": name, "args": {k: repr(v) for k, v in kwargs.items()}}) + "\\n")


PROVIDERS = {
    "claude-cli": {"default_base_url": None, "default_api_key_env": None,
                   "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "anthropic": {"default_base_url": "https://api.anthropic.com", "default_api_key_env": "ANTHROPIC_API_KEY",
                  "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "openai": {"default_base_url": "https://api.openai.com/v1", "default_api_key_env": "OPENAI_API_KEY",
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
    result = []
    for name, info in PROVIDERS.items():
        available = name == "ollama"
        result.append({
            "provider": name,
            "available": available,
            "reason": "fake ollama reachable" if available else "fake: not available",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return result


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None, auth=None):
    _log("save_config", config_path=config_path, provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    path = _Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.is_file():
        in_llm = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_llm = stripped == "[llm]"
            if not in_llm:
                kept.append(line)
    lines = ["[llm]", "provider = " + _json.dumps(provider), "model = " + _json.dumps(model)]
    if base_url is not None:
        lines.append("base_url = " + _json.dumps(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + _json.dumps(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        lines.append("auth = " + _json.dumps(auth))
    text = "\\n".join(kept).rstrip("\\n")
    if text:
        text += "\\n\\n"
    text += "\\n".join(lines) + "\\n"
    path.write_text(text, encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=config_path)
    path = _Path(config_path) if config_path is not None else _Path("hotdocs.toml")
    if not path.is_file():
        return None
    data = {}
    in_llm = False
    found = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_llm = stripped == "[llm]"
            found = found or in_llm
            continue
        if in_llm and "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip()
            if value.startswith(\'"\'):
                data[key] = _json.loads(value)
            else:
                data[key] = int(value)
    if not found:
        return None
    return {
        "provider": data.get("provider"),
        "model": data.get("model"),
        "base_url": data.get("base_url"),
        "api_key_env": data.get("api_key_env"),
        "timeout_seconds": data.get("timeout_seconds"),
        "auth": data.get("auth"),
    }
'''


def make_fake_tool_root(base):
    tool_root = base / "tool"
    log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "llm_endpoint_calls.log"

    llm_dir = tool_root / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_LLM_ENDPOINT_BODY
    (llm_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")

    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nA fake example product spec.\n", encoding="utf-8")

    version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text("pytest==" + version + "\n", encoding="utf-8")
    return tool_root


def run_init(project, tool_root, cwd):
    outputs = []

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        outputs.append("<<input>> " + str(prompt))
        return ""

    env = {"PATH": os.environ.get("PATH", "")}
    code = hotdocs_init.run(
        [str(project), "--yes"],
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=cwd,
    )
    return code, outputs


def test_ac_init_008_creates_empty_allowlist_and_no_decisions(tmp_path):
    tool_root = make_fake_tool_root(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    code, outputs = run_init(project, tool_root, tmp_path)
    assert code in (0, 3), outputs

    allowlist = project / ".secret-allowlist.json"
    assert allowlist.is_file()
    expected = (json.dumps({"version": 1, "entries": []}, indent=2) + "\n").encode("utf-8")
    assert allowlist.read_bytes() == expected

    decisions = project / "specs" / "decisions"
    assert decisions.is_dir()
    found = sorted(
        str(p.relative_to(decisions)) for p in decisions.rglob("*")
    )
    assert found == [".gitkeep"]


def test_ac_init_008_existing_allowlist_skipped(tmp_path):
    tool_root = make_fake_tool_root(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    allowlist = project / ".secret-allowlist.json"
    original = (
        json.dumps({"version": 1, "entries": [], "note": "hand written"}, indent=4)
        + "\n"
    ).encode("utf-8")
    allowlist.write_bytes(original)

    code, outputs = run_init(project, tool_root, tmp_path)
    assert code in (0, 3), outputs

    assert allowlist.read_bytes() == original
    message = ".secret-allowlist.json: skipped (exists)"
    assert any(message in line for line in outputs), outputs