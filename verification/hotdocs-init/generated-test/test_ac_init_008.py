# hotdocs-criterion: sha256:7bdd56a5e16fadf089c5522135d758caed092d2424f8bf311a59ddae29eb2e75
import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_LLM_ENDPOINT_BODY = '''
import json
import tomllib
from pathlib import Path


def _log(name, **kwargs):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, "args": {k: str(v) for k, v in kwargs.items()}}) + "\\n")


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
    _log("detect_providers", env=env is not None, probe_ollama=probe_ollama)
    result = []
    for name, info in PROVIDERS.items():
        available = name == "ollama"
        result.append({
            "provider": name,
            "available": available,
            "reason": "fake: available" if available else "fake: not available",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return result


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", config_path=config_path, provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if not isinstance(model, str) or not model:
        raise ValueError("model required")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.exists():
        in_llm = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_llm = stripped == "[llm]"
            if not in_llm:
                kept.append(line)
    block = ["[llm]", "provider = " + json.dumps(provider), "model = " + json.dumps(model)]
    if base_url is not None:
        block.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        block.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        block.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        block.append("auth = " + json.dumps(auth))
    text = "\\n".join(kept).strip()
    text = (text + "\\n\\n" if text else "") + "\\n".join(block) + "\\n"
    path.write_text(text, encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=config_path)
    path = Path(config_path) if config_path is not None else Path("hotdocs.toml")
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("invalid config") from exc
    llm = data.get("llm")
    if llm is None:
        return None
    if not isinstance(llm, dict):
        raise ValueError("invalid [llm]")
    return {
        "provider": llm.get("provider"),
        "model": llm.get("model"),
        "base_url": llm.get("base_url"),
        "api_key_env": llm.get("api_key_env"),
        "timeout_seconds": llm.get("timeout_seconds"),
        "auth": llm.get("auth"),
    }
'''


def make_tool_root(tmp_path):
    tool = tmp_path / "tool"
    log_path = tmp_path / "logs" / "llm_endpoint_calls.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    llm_dir = tool / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    (llm_dir / "llm_endpoint.py").write_text(
        "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_LLM_ENDPOINT_BODY,
        encoding="utf-8",
    )

    slugs = tool / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nA fake example product spec.\n", encoding="utf-8")

    (tool / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    (tool / "pyproject.toml").write_text(
        "[project]\n" + "name = " + json.dumps("hotdocs") + "\n"
        + "version = " + json.dumps("9.8.7a1") + "\n",
        encoding="utf-8",
    )
    return tool


def run_init(project, tool, outputs):
    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        return ""

    env = {"PATH": os.environ.get("PATH", "")}
    return hotdocs_init.run(
        [str(project), "--yes"],
        tool_root=tool,
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=project,
    )


def output_lines(outputs):
    lines = []
    for text in outputs:
        lines.extend(line.strip() for line in text.splitlines())
    return lines


def test_empty_allowlist_written_and_no_decision_files(tmp_path):
    tool = make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    outputs = []

    code = run_init(project, tool, outputs)
    assert code in (0, 3), outputs

    allowlist = project / ".secret-allowlist.json"
    assert allowlist.is_file()
    expected = (json.dumps({"version": 1, "entries": []}, indent=2) + "\n").encode("utf-8")
    assert allowlist.read_bytes() == expected

    decisions = project / "specs" / "decisions"
    assert decisions.is_dir()
    entries = sorted(p.relative_to(decisions).as_posix() for p in decisions.rglob("*"))
    assert entries == [".gitkeep"]


def test_existing_allowlist_is_skipped(tmp_path):
    tool = make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    allowlist = project / ".secret-allowlist.json"
    original = b'{\n  "version": 1,\n  "entries": [],\n  "note": "kept as is"\n}\n'
    allowlist.write_bytes(original)
    outputs = []

    code = run_init(project, tool, outputs)
    assert code in (0, 3), outputs

    assert allowlist.read_bytes() == original
    assert ".secret-allowlist.json: skipped (exists)" in output_lines(outputs), outputs