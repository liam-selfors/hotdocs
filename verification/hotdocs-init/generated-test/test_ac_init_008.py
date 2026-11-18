# hotdocs-criterion: sha256:79d13fa08faebf628be0619782d52a7d10f287139d999febf35637b143d41620
import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


FAKE_LLM_ENDPOINT_BODY = '''
import json
import os
from pathlib import Path


def _log(name, **kwargs):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, "args": {k: repr(v) for k, v in kwargs.items()}}) + "\\n")


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
    _log("detect_providers", env=env is not None, probe_ollama=probe_ollama)
    result = []
    for name, info in PROVIDERS.items():
        available = name == "claude-cli"
        result.append({
            "provider": name,
            "available": available,
            "reason": "fake: available" if available else "fake: not available",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return result


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def _strip_llm(text):
    out = []
    in_llm = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_llm = s == "[llm]"
            if in_llm:
                continue
        if not in_llm:
            out.append(line)
    return "\\n".join(out).strip()


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not isinstance(model, str):
        raise ValueError("invalid model")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    kept = _strip_llm(existing)
    lines = ["[llm]", "provider = " + json.dumps(provider), "model = " + json.dumps(model)]
    if base_url is not None:
        lines.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        lines.append("auth = " + json.dumps(auth))
    body = "\\n".join(lines) + "\\n"
    if kept:
        body = kept + "\\n\\n" + body
    path.write_text(body, encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=str(config_path))
    path = Path(config_path) if config_path is not None else Path("hotdocs.toml")
    if not path.is_file():
        return None
    result = None
    in_llm = False
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            in_llm = s == "[llm]"
            if in_llm and result is None:
                result = {"provider": None, "model": None, "base_url": None,
                          "api_key_env": None, "timeout_seconds": None, "auth": None}
            continue
        if in_llm and "=" in s:
            key, _, value = s.partition("=")
            key = key.strip()
            try:
                parsed = json.loads(value.strip())
            except Exception:
                raise ValueError("invalid config value")
            if key in result:
                result[key] = parsed
    return result
'''


def _make_tool_root(base: Path) -> Path:
    tool = base / "tool"
    log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "llm_endpoint_calls.log"

    ep_dir = tool / "gen" / "llm-endpoint"
    ep_dir.mkdir(parents=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_LLM_ENDPOINT_BODY
    (ep_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")

    slug_dir = tool / "examples" / "slugify" / "specs" / "product"
    slug_dir.mkdir(parents=True)
    (slug_dir / "slugs.md").write_text("# Slugs\n\nTurn titles into slugs.\n", encoding="utf-8")

    version = importlib.metadata.version("pytest")
    (tool / "requirements.txt").write_text("pytest==" + version + "\n", encoding="utf-8")
    return tool


def _run(project: Path, tool: Path, cwd: Path):
    messages = []

    def output_fn(*args, **kwargs):
        messages.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        return ""

    env = {"PATH": os.environ.get("PATH", "")}
    rc = hotdocs_init.main(
        [str(project), "--yes"],
        tool_root=tool,
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=cwd,
    )
    return rc, messages


def test_creates_empty_allowlist_and_no_decisions(tmp_path):
    tool = _make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()

    rc, _messages = _run(project, tool, tmp_path)
    assert rc in (0, 3)

    allowlist = project / ".secret-allowlist.json"
    assert allowlist.is_file()
    expected = (json.dumps({"version": 1, "entries": []}, indent=2) + "\n").encode("utf-8")
    assert allowlist.read_bytes() == expected

    decisions = project / "specs" / "decisions"
    assert decisions.is_dir()
    contents = sorted(str(p.relative_to(decisions)) for p in decisions.rglob("*"))
    assert contents == [".gitkeep"]


def test_existing_allowlist_is_skipped_and_unchanged(tmp_path):
    tool = _make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()

    allowlist = project / ".secret-allowlist.json"
    original = b'{"version":1,"entries":[]}'
    allowlist.write_bytes(original)

    rc, messages = _run(project, tool, tmp_path)
    assert rc in (0, 3)

    assert allowlist.read_bytes() == original
    assert any(".secret-allowlist.json: skipped (exists)" in m for m in messages), messages