# hotdocs-criterion: sha256:448ca10064a66e08e44e51b09ab3a96789250f7f509b0917772d1e5ebb0acb4f
import importlib.metadata
import inspect
import os
import sys
from pathlib import Path

import pytest

import hotdocs_init


PROVIDER_NAMES = [
    "claude-cli",
    "anthropic",
    "openai",
    "openai-compatible",
    "gemini",
    "ollama",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_BODY = '''
import json
import os
from pathlib import Path

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


def _log(name):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(name + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers")
    result = []
    for name, info in PROVIDERS.items():
        result.append({
            "provider": name,
            "available": True,
            "reason": "fake",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return result


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection")
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def _strip_llm(text):
    out = []
    skipping = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            skipping = stripped == "[llm]"
            if skipping:
                continue
        if not skipping:
            out.append(line)
    return "\\n".join(out).rstrip("\\n")


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config")
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not model:
        raise ValueError("model required")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
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
    text = (kept + "\\n\\n" if kept else "") + "\\n".join(lines) + "\\n"
    path.write_text(text, encoding="utf-8")


def load_config(config_path=None):
    _log("load_config")
    path = Path(config_path) if config_path is not None else Path("hotdocs.toml")
    if not path.exists():
        return None
    table = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            table = {} if stripped == "[llm]" else (table if table is not None and False else None)
            if stripped == "[llm]":
                found = table
            continue
        if table is not None and "=" in stripped:
            key, _, val = stripped.partition("=")
            val = val.strip()
            try:
                table[key.strip()] = json.loads(val)
            except Exception:
                raise ValueError("invalid hotdocs.toml")
    try:
        found
    except NameError:
        return None
    result = {}
    for key in ("provider", "model", "base_url", "api_key_env", "timeout_seconds", "auth"):
        result[key] = found.get(key)
    return result
'''


def make_tool_root(base):
    tool_root = base / "tool"
    log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "llm_calls.log"
    llm_dir = tool_root / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_BODY
    (llm_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")
    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nTurn a title into a slug.\n", encoding="utf-8")
    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    return tool_root, log_path


def snapshot(root, skip_pycache=False):
    result = {}
    root = Path(root)
    if not root.exists():
        return result
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if skip_pycache and "__pycache__" in rel.parts:
            continue
        if p.is_file():
            result[str(rel)] = p.read_bytes()
        else:
            result[str(rel)] = None
    return result


def make_env():
    return {"PATH": os.environ.get("PATH", ""), "OPENAI_API_KEY": "placeholder"}


def call_run(argv, tool_root, cwd, capsys):
    out = []
    asked = []

    def output_fn(*args, **kwargs):
        out.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        asked.append(prompt)
        return ""

    capsys.readouterr()
    code = hotdocs_init.run(
        argv,
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env=make_env(),
        cwd=cwd,
    )
    captured = capsys.readouterr()
    text = "\n".join(out) + "\n" + captured.out + "\n" + captured.err + "\n" + "\n".join(asked)
    return code, text


def read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def assert_usage_error(argv, tmp_path, capsys, name):
    base = tmp_path / name
    base.mkdir()
    tool_root, log_path = make_tool_root(base)
    proj = base / "proj"
    proj.mkdir()
    tool_before = snapshot(tool_root, skip_pycache=True)
    code, text = call_run(argv, tool_root, proj, capsys)
    assert code == 2, (argv, code, text)
    assert snapshot(proj) == {}, (argv, snapshot(proj))
    assert snapshot(tool_root, skip_pycache=True) == tool_before, argv
    assert "save_config" not in read_log(log_path), argv
    return text


def test_basic_usage_errors(tmp_path, capsys):
    cases = [
        ["--bogus"],
        ["--provider"],
        ["a", "b"],
        ["--provider", "nope"],
        ["--provider=openai", "--model"],
    ]
    for i, argv in enumerate(cases):
        text = assert_usage_error(argv, tmp_path, capsys, "basic" + str(i))
        if argv == ["--provider", "nope"]:
            for key in PROVIDER_NAMES:
                assert key in text, (key, text)


def test_invalid_api_key_env_not_echoed(tmp_path, capsys):
    secret_like = "sk-" + "abc123"
    cases = [
        ["--provider", "openai", "--api-key-env", secret_like],
        ["--provider", "openai", "--api-key-env", "9X"],
    ]
    for i, argv in enumerate(cases):
        text = assert_usage_error(argv, tmp_path, capsys, "keyenv" + str(i))
        assert secret_like not in text


def test_claude_cli_and_auth_errors(tmp_path, capsys):
    cases = [
        ["--provider", "claude-cli", "--base-url", "http://h"],
        ["--provider", "claude-cli", "--api-key-env", "K"],
        ["--provider", "claude-cli", "--auth", "token"],
        ["--provider", "openai", "--model", "m", "--auth", "login"],
    ]
    for i, argv in enumerate(cases):
        assert_usage_error(argv, tmp_path, capsys, "auth" + str(i))


def test_openai_compatible_missing_model_or_base_url(tmp_path, capsys):
    cases = [
        ["--provider", "openai-compatible", "--base-url", "http://h"],
        ["--provider", "openai-compatible", "--model", "m"],
    ]
    for i, argv in enumerate(cases):
        assert_usage_error(argv, tmp_path, capsys, "compat" + str(i))


def test_yes_with_provider_succeeds_any_order_and_form(tmp_path, capsys):
    orders = [
        lambda d: ["--provider", "openai", "--yes", d],
        lambda d: ["--provider=openai", "--yes", d],
        lambda d: [d, "--yes", "--provider", "openai"],
        lambda d: ["--yes", d, "--provider=openai"],
    ]
    for i, build in enumerate(orders):
        base = tmp_path / ("ok" + str(i))
        base.mkdir()
        tool_root, _log_path = make_tool_root(base)
        cwd = base / "cwd"
        cwd.mkdir()
        proj = base / "proj"
        proj.mkdir()
        argv = build(str(proj))
        code, text = call_run(argv, tool_root, cwd, capsys)
        assert code == 0, (argv, code, text)


def test_main_signature_and_usage_error(tmp_path, monkeypatch):
    params = list(inspect.signature(hotdocs_init.main).parameters)
    assert params == ["argv"]
    work = tmp_path / "mainwork"
    work.mkdir()
    monkeypatch.chdir(work)
    code = hotdocs_init.main(["--bogus"])
    assert code == 2
    assert snapshot(work) == {}