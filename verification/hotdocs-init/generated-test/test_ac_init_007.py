# hotdocs-criterion: sha256:83a3024dbab51e2269e98331d1c6ee8f7390204a672520ccfc54b47d07e0a03d
import importlib.metadata
import os
from pathlib import Path

import pytest

import hotdocs_init


PROVIDER_KEYS = [
    "claude-cli",
    "anthropic",
    "openai",
    "openai-compatible",
    "gemini",
    "ollama",
]

# Built by concatenation so the source holds no secret-shaped literal.
PASTED_VALUE = "sk" + "-" + "abc" + "123"


FAKE_BODY = '''
import json
from pathlib import Path


def _log(name, **kw):
    record = {"call": name, "args": {k: (None if v is None else str(v)) for k, v in kw.items()}}
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


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
    _log("detect_providers", env=None if env is None else "given", probe_ollama=probe_ollama)
    out = []
    for name, info in PROVIDERS.items():
        out.append({
            "provider": name,
            "available": True,
            "reason": "available",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


_KEYS = ["provider", "model", "base_url", "api_key_env", "timeout_seconds", "auth"]


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", config_path=config_path, provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not model:
        raise ValueError("model required")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    p = Path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if p.exists():
        in_llm = False
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("["):
                in_llm = (s == "[llm]")
            if not in_llm:
                kept.append(line)
    out = list(kept)
    out.append("[llm]")
    out.append("provider = " + json.dumps(provider))
    out.append("model = " + json.dumps(model))
    if base_url is not None:
        out.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        out.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        out.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        out.append("auth = " + json.dumps(auth))
    p.write_text("\\n".join(out) + "\\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=config_path)
    p = Path(config_path) if config_path is not None else Path("hotdocs.toml")
    if not p.exists():
        return None
    data = None
    in_llm = False
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("["):
            in_llm = (s == "[llm]")
            if in_llm:
                data = {}
            continue
        if in_llm and "=" in s:
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip()
            if v.startswith('"'):
                v = json.loads(v)
            else:
                try:
                    v = int(v)
                except ValueError:
                    raise ValueError("invalid value")
            data[k] = v
    if data is None:
        return None
    result = {k: data.get(k) for k in _KEYS}
    if result["provider"] not in PROVIDERS or not result["model"]:
        raise ValueError("invalid [llm] table")
    return result
'''


def _build(tmp_path):
    tool_root = tmp_path / "tool"
    project = tmp_path / "project"
    logs = tmp_path / "logs"
    for d in (tool_root, project, logs):
        d.mkdir(parents=True, exist_ok=True)
    log_path = logs / "llm_endpoint_calls.log"

    fake_dir = tool_root / "gen" / "llm-endpoint"
    fake_dir.mkdir(parents=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_BODY
    (fake_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")

    other_dir = tool_root / "gen" / "slugify"
    other_dir.mkdir(parents=True)
    (other_dir / "slugify.py").write_text(
        "def slugify(text):\n    return text.lower().replace(' ', '-')\n",
        encoding="utf-8",
    )

    ex = tool_root / "examples" / "slugify" / "specs" / "product"
    ex.mkdir(parents=True)
    (ex / "slugs.md").write_text("# Slugs\n\nTurn titles into slugs.\n", encoding="utf-8")

    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )

    env = {"PATH": os.environ.get("PATH", ""), "OPENAI_API_KEY": "dummy"}
    return tool_root, project, log_path, env


def _snapshot(root):
    snap = {}
    root = Path(root)
    if not root.exists():
        return snap
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if "__pycache__" in rel.parts:
            continue
        if p.is_file():
            snap[str(rel)] = p.read_bytes()
        else:
            snap[str(rel)] = None
    return snap


def _make_input():
    calls = {"n": 0}

    def input_fn(prompt=""):
        calls["n"] += 1
        if calls["n"] > 50:
            raise EOFError("too many prompts")
        return ""

    return input_fn


def _run(argv, tool_root, project, env, capsys):
    outputs = []

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    capsys.readouterr()
    code = hotdocs_init.main(
        argv,
        tool_root=tool_root,
        input_fn=_make_input(),
        output_fn=output_fn,
        env=env,
        cwd=project,
    )
    captured = capsys.readouterr()
    combined = "\n".join(outputs) + "\n" + captured.out + "\n" + captured.err
    return code, combined


def _read_log(log_path):
    if not Path(log_path).exists():
        return ""
    return Path(log_path).read_text(encoding="utf-8")


USAGE_ERROR_CASES = [
    ["--bogus"],
    ["--provider"],
    ["a", "b"],
    ["--provider", "nope"],
    ["--provider=openai", "--model"],
    ["--provider", "openai", "--api-key-env", PASTED_VALUE],
    ["--provider", "openai", "--api-key-env", "9X"],
    ["--provider", "claude-cli", "--base-url", "http://h"],
    ["--provider", "claude-cli", "--api-key-env", "K"],
    ["--provider", "claude-cli", "--auth", "token"],
    ["--provider", "openai", "--model", "m", "--auth", "login"],
    ["--provider", "openai-compatible", "--base-url", "http://h"],
    ["--provider", "openai-compatible", "--model", "m"],
]


@pytest.mark.parametrize("argv", USAGE_ERROR_CASES, ids=lambda a: "|".join(
    ("<pasted>" if x == PASTED_VALUE else x) for x in a))
def test_usage_errors_exit_2_and_write_nothing(tmp_path, capsys, argv):
    tool_root, project, log_path, env = _build(tmp_path)
    before = _snapshot(project)

    code, combined = _run(list(argv), tool_root, project, env, capsys)

    assert code == 2
    assert _snapshot(project) == before
    assert "save_config" not in _read_log(log_path)

    if argv == ["--provider", "nope"]:
        for key in PROVIDER_KEYS:
            assert key in combined, "provider key missing from message: " + key

    if PASTED_VALUE in argv:
        assert PASTED_VALUE not in combined
        assert PASTED_VALUE not in _read_log(log_path)
        for p in tmp_path.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                assert PASTED_VALUE not in p.read_text(encoding="utf-8", errors="replace")


def test_invalid_api_key_env_9x_not_echoed(tmp_path, capsys):
    tool_root, project, log_path, env = _build(tmp_path)
    before = _snapshot(project)
    code, combined = _run(
        ["--provider", "openai", "--api-key-env", "9X"], tool_root, project, env, capsys
    )
    assert code == 2
    assert _snapshot(project) == before
    assert "save_config" not in _read_log(log_path)


@pytest.mark.parametrize("make_argv", [
    lambda d: ["--provider", "openai", "--yes", d],
    lambda d: ["--yes", "--provider", "openai", d],
    lambda d: [d, "--provider", "openai", "--yes"],
    lambda d: [d, "--yes", "--provider", "openai"],
    lambda d: ["--provider=openai", "--yes", d],
    lambda d: ["--yes", "--provider=openai", d],
    lambda d: [d, "--provider=openai", "--yes"],
    lambda d: [d, "--yes", "--provider=openai"],
], ids=[
    "next-provider-yes-dir",
    "next-yes-provider-dir",
    "next-dir-provider-yes",
    "next-dir-yes-provider",
    "eq-provider-yes-dir",
    "eq-yes-provider-dir",
    "eq-dir-provider-yes",
    "eq-dir-yes-provider",
])
def test_valid_provider_yes_dir_returns_0(tmp_path, capsys, make_argv):
    tool_root, project, log_path, env = _build(tmp_path)
    target = project / "target"
    target.mkdir()
    code, combined = _run(make_argv(str(target)), tool_root, project, env, capsys)
    assert code == 0, combined