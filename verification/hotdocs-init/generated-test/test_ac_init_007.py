# hotdocs-criterion: sha256:471153b2ffbc9f96046d47310691c0875fae105b5eed8333a5f4d0bae57061b9
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

# Built by concatenation so the test file itself holds no secret-shaped literal.
PASTED_VALUE = "sk" + "-" + "abc" + "123"


FAKE_BODY = r'''
import json
import os
from pathlib import Path


def _log(name, **kw):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, "args": {k: repr(v) for k, v in kw.items()}}) + "\n")


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
    _log("detect_providers", env_given=env is not None, probe_ollama=probe_ollama)
    source = os.environ if env is None else env
    out = []
    for name, info in PROVIDERS.items():
        key = info["default_api_key_env"]
        if key:
            available = bool(source.get(key))
            reason = (key + " is set") if available else (key + " is not set")
        elif name == "ollama":
            available = False
            reason = "not probed"
        elif name == "claude-cli":
            available = False
            reason = "claude command not checked"
        else:
            available = False
            reason = "needs a base URL"
        out.append({
            "provider": name,
            "available": available,
            "reason": reason,
            "suggested_model": info["suggested_model"],
            "api_key_env": key,
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


def save_config(config_path, provider, model, base_url=None,
                api_key_env=None, timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS or not model:
        raise ValueError("invalid llm config")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    if auth is not None and auth not in ("login", "key"):
        raise ValueError("invalid auth")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    kept = []
    skipping = False
    for line in existing.splitlines():
        s = line.strip()
        if s.startswith("["):
            skipping = (s == "[llm]")
        if not skipping:
            kept.append(line)
    lines = list(kept)
    lines.append("[llm]")
    lines.append("provider = " + json.dumps(provider))
    lines.append("model = " + json.dumps(model))
    if base_url is not None:
        lines.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        lines.append("auth = " + json.dumps(auth))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=None if config_path is None else str(config_path))
    path = Path("hotdocs.toml") if config_path is None else Path(config_path)
    if not path.is_file():
        return None
    in_llm = False
    found = False
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("["):
            in_llm = (s == "[llm]")
            if in_llm:
                found = True
            continue
        if in_llm and "=" in s:
            k, v = s.split("=", 1)
            try:
                values[k.strip()] = json.loads(v.strip())
            except Exception:
                raise ValueError("invalid hotdocs.toml")
    if not found:
        return None
    result = {
        "provider": None,
        "model": None,
        "base_url": None,
        "api_key_env": None,
        "timeout_seconds": None,
        "auth": None,
    }
    for k, v in values.items():
        if k in result:
            result[k] = v
    if result["provider"] not in PROVIDERS or not result["model"]:
        raise ValueError("invalid [llm] table")
    return result
'''


def _snapshot(root, ignore_pycache=False):
    snap = {}
    root = Path(root)
    if not root.exists():
        return snap
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if ignore_pycache and "__pycache__" in rel.parts:
            continue
        if p.is_file():
            snap[str(rel)] = p.read_bytes()
        else:
            snap[str(rel)] = None
    return snap


@pytest.fixture
def setup(tmp_path):
    tool_root = tmp_path / "tool"
    proj = tmp_path / "proj"
    logs = tmp_path / "logs"
    for d in (tool_root, proj, logs):
        d.mkdir()
    log_path = logs / "llm_endpoint_calls.log"

    fake_dir = tool_root / "gen" / "llm-endpoint"
    fake_dir.mkdir(parents=True)
    (fake_dir / "llm_endpoint.py").write_text(
        "LOG = " + repr(str(log_path)) + "\n" + FAKE_BODY, encoding="utf-8"
    )

    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nTurn titles into slugs.\n", encoding="utf-8")

    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )

    env = {"PATH": os.environ.get("PATH", ""), "OPENAI_API_KEY": "placeholder"}
    return {
        "tmp": tmp_path,
        "tool_root": tool_root,
        "proj": proj,
        "log": log_path,
        "env": env,
    }


def _run(setup, argv, cwd=None):
    out = []
    prompts = []

    def output_fn(*args, **kwargs):
        out.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        prompts.append(str(prompt))
        return ""

    rc = hotdocs_init.main(
        list(argv),
        tool_root=setup["tool_root"],
        input_fn=input_fn,
        output_fn=output_fn,
        env=dict(setup["env"]),
        cwd=setup["proj"] if cwd is None else cwd,
    )
    return rc, "\n".join(out), "\n".join(prompts)


USAGE_CASES = [
    ["--bogus"],
    ["--provider"],
    ["a", "b"],
    ["--provider", "nope"],
    ["--provider=openai", "--model"],
    ["--provider", "openai", "--api-key-env", "9X"],
    ["--provider", "claude-cli", "--base-url", "http://h"],
    ["--provider", "claude-cli", "--api-key-env", "K"],
    ["--provider", "claude-cli", "--auth", "token"],
    ["--provider", "openai", "--model", "m", "--auth", "login"],
    ["--provider", "openai-compatible", "--base-url", "http://h"],
    ["--provider", "openai-compatible", "--model", "m"],
]


@pytest.mark.parametrize("argv", USAGE_CASES, ids=lambda a: " ".join(a))
def test_usage_errors_return_2_and_write_nothing(setup, capsys, argv):
    proj_before = _snapshot(setup["proj"])
    tool_before = _snapshot(setup["tool_root"], ignore_pycache=True)

    rc, out, prompts = _run(setup, argv)
    captured = capsys.readouterr()

    assert rc == 2
    assert _snapshot(setup["proj"]) == proj_before
    assert _snapshot(setup["tool_root"], ignore_pycache=True) == tool_before

    if "nope" in argv:
        text = captured.err + captured.out + out
        for key in PROVIDER_KEYS:
            assert key in text, "provider key " + repr(key) + " missing from message"


def test_pasted_key_as_api_key_env_is_never_echoed_or_stored(setup, capsys):
    argv = ["--provider", "openai", "--api-key-env", PASTED_VALUE]
    proj_before = _snapshot(setup["proj"])
    tool_before = _snapshot(setup["tool_root"], ignore_pycache=True)

    rc, out, prompts = _run(setup, argv)
    captured = capsys.readouterr()

    assert rc == 2
    assert _snapshot(setup["proj"]) == proj_before
    assert _snapshot(setup["tool_root"], ignore_pycache=True) == tool_before
    for text in (captured.out, captured.err, out, prompts):
        assert PASTED_VALUE not in text
    if setup["log"].exists():
        assert PASTED_VALUE not in setup["log"].read_text(encoding="utf-8")
    for p in setup["tmp"].rglob("*"):
        if p.is_file():
            assert PASTED_VALUE.encode() not in p.read_bytes()


def _success_argvs(d):
    return [
        ["--provider", "openai", "--yes", d],
        [d, "--provider", "openai", "--yes"],
        ["--yes", d, "--provider", "openai"],
        ["--provider=openai", "--yes", d],
        [d, "--yes", "--provider=openai"],
        ["--yes", "--provider=openai", d],
    ]


@pytest.mark.parametrize("index", range(6))
def test_provider_openai_yes_dir_returns_0(setup, capsys, index):
    target = setup["tmp"] / "target"
    target.mkdir()
    elsewhere = setup["tmp"] / "elsewhere"
    elsewhere.mkdir()
    argv = _success_argvs(str(target))[index]

    rc, out, prompts = _run(setup, argv, cwd=elsewhere)
    capsys.readouterr()

    assert rc == 0