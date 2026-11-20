# hotdocs-criterion: sha256:55bae9b7d2bc5dcd68f43edaa49301f616b0b774efb25482e0fc39f5dcf559a1
import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


FAKE_LLM_ENDPOINT_BODY = '''
import json as _json
from pathlib import Path as _Path

try:
    import tomllib as _tomllib
except ImportError:  # pragma: no cover
    _tomllib = None


def _log(name, payload):
    p = _Path(LOG_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps({"call": name, "args": payload}, default=str) + "\\n")


PROVIDERS = {
    "claude-cli": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "anthropic": {
        "default_base_url": "https://api.anthropic.com",
        "default_api_key_env": "ANTHROPIC_API_KEY",
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "openai": {
        "default_base_url": "https://api.openai.com/v1",
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-6-astra",
    },
    "openai-compatible": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": True,
        "suggested_model": "",
    },
    "gemini": {
        "default_base_url": "https://generativelanguage.googleapis.com",
        "default_api_key_env": "GEMINI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gemini-4-argon",
    },
    "ollama": {
        "default_base_url": "http://localhost:11434",
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "llama3.2",
    },
}


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", {"env_given": env is not None, "probe_ollama": probe_ollama})
    out = []
    for name, info in PROVIDERS.items():
        available = name == "claude-cli"
        out.append({
            "provider": name,
            "available": available,
            "reason": "found" if available else "not configured",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", {"provider": provider, "model": model})
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def _strip_llm(text):
    out = []
    skipping = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            skipping = s == "[llm]"
            if skipping:
                continue
        if not skipping:
            out.append(line)
    return "\\n".join(out).rstrip()


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", {"config_path": str(config_path), "provider": provider, "model": model})
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not isinstance(model, str):
        raise ValueError("invalid model")
    path = _Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    kept = _strip_llm(existing)
    lines = ["[llm]", "provider = " + _json.dumps(provider), "model = " + _json.dumps(model)]
    if base_url is not None:
        lines.append("base_url = " + _json.dumps(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + _json.dumps(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        lines.append("auth = " + _json.dumps(auth))
    body = ("\\n".join(lines)) + "\\n"
    text = (kept + "\\n\\n" + body) if kept else body
    path.write_text(text, encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", {"config_path": str(config_path)})
    path = _Path(config_path) if config_path is not None else _Path("hotdocs.toml")
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if _tomllib is None:
        return None
    try:
        data = _tomllib.loads(text)
    except Exception as exc:
        raise ValueError("invalid config") from exc
    llm = data.get("llm")
    if llm is None:
        return None
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
    tool_root = tmp_path / "tool"
    log_path = tmp_path / "logs" / "llm_endpoint_calls.log"
    llm_dir = tool_root / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_LLM_ENDPOINT_BODY
    (llm_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")

    slug_dir = tool_root / "examples" / "slugify" / "specs" / "product"
    slug_dir.mkdir(parents=True)
    (slug_dir / "slugs.md").write_text("# Slugs\n\nTurn titles into slugs.\n", encoding="utf-8")

    version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text("pytest==" + version + "\n", encoding="utf-8")
    return tool_root, log_path


def run_init(tmp_path, project, tool_root):
    outputs = []
    prompts = []

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        prompts.append(prompt)
        return ""

    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path / "home")}
    code = hotdocs_init.main(
        [str(project), "--yes"],
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=str(project),
    )
    return code, outputs


def test_ac_init_008_creates_empty_allowlist_and_no_decisions(tmp_path):
    tool_root, _log = make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()

    code, _outputs = run_init(tmp_path, project, tool_root)
    assert code in (0, 3)

    allowlist = project / ".secret-allowlist.json"
    assert allowlist.is_file()
    expected = (json.dumps({"version": 1, "entries": []}, indent=2) + "\n").encode("utf-8")
    assert allowlist.read_bytes() == expected

    decisions = project / "specs" / "decisions"
    assert decisions.is_dir()
    assert sorted(p.name for p in decisions.iterdir()) == [".gitkeep"]


def test_ac_init_008_existing_allowlist_is_skipped(tmp_path):
    tool_root, _log = make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()

    original = b'{\n  "version": 1,\n  "entries": [],\n  "note": "kept as is"\n}'
    allowlist = project / ".secret-allowlist.json"
    allowlist.write_bytes(original)

    code, outputs = run_init(tmp_path, project, tool_root)
    assert code in (0, 3)

    assert allowlist.read_bytes() == original

    lines = []
    for message in outputs:
        lines.append(message)
        lines.extend(message.splitlines())
    assert ".secret-allowlist.json: skipped (exists)" in [line.strip() for line in lines]