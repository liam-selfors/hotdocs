# hotdocs-criterion: sha256:7ed516fdba39ea58c01f005704ccdd8edd7941a5f62e3ae70ae25c7090c328ed
import importlib.metadata
import inspect
import os
from pathlib import Path

import pytest

import hotdocs_init


SECRET = "sk-" + "abc123"

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

FAKE_BODY = '''

def _log(name):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(name + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers")
    out = []
    for name, info in PROVIDERS.items():
        out.append({
            "provider": name,
            "available": True,
            "reason": "fake",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection")
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None,
                api_key_env=None, timeout_seconds=None, auth=None):
    _log("save_config")
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not model:
        raise ValueError("model required")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.is_file():
        in_llm = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                in_llm = stripped == "[llm]"
                if in_llm:
                    continue
            if not in_llm:
                kept.append(line)
    lines = ["[llm]"]
    values = [("provider", provider), ("model", model), ("base_url", base_url),
              ("api_key_env", api_key_env), ("timeout_seconds", timeout_seconds),
              ("auth", auth)]
    for key, value in values:
        if value is not None:
            lines.append(key + " = " + json.dumps(value))
    text = "\\n".join(lines) + "\\n"
    if kept:
        text = "\\n".join(kept) + "\\n\\n" + text
    path.write_text(text, encoding="utf-8")


def load_config(config_path=None):
    _log("load_config")
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
    keys = ["provider", "model", "base_url", "api_key_env", "timeout_seconds", "auth"]
    return {k: llm.get(k) for k in keys}
'''


def make_setup(tmp_path, name):
    base = tmp_path / name
    tool = base / "tool"
    proj = base / "proj"
    logs = base / "logs"
    for d in (tool, proj, logs):
        d.mkdir(parents=True)
    log_path = logs / "calls.log"
    ep = tool / "gen" / "llm-endpoint"
    ep.mkdir(parents=True)
    source = (
        "import json\n"
        "import tomllib\n"
        "from pathlib import Path\n\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "PROVIDERS = " + repr(PROVIDERS) + "\n"
        + FAKE_BODY
    )
    (ep / "llm_endpoint.py").write_text(source, encoding="utf-8")
    slugs = tool / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nA fake product spec.\n", encoding="utf-8")
    (tool / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    (tool / "pyproject.toml").write_text(
        "[project]\n" + "name = " + '"hotdocs"' + "\n" + "version = " + '"9.8.7a1"' + "\n",
        encoding="utf-8",
    )
    return tool, proj, log_path


def snapshot(root, skip_pycache=False):
    result = {}
    for p in sorted(Path(root).rglob("*")):
        rel = p.relative_to(root)
        if skip_pycache and "__pycache__" in rel.parts:
            continue
        if p.is_file():
            result[str(rel)] = p.read_bytes()
        else:
            result[str(rel)] = None
    return result


def fake_env():
    env = {"OPENAI_API_KEY": "placeholder-value"}
    if "PATH" in os.environ:
        env["PATH"] = os.environ["PATH"]
    return env


def call_run(tmp_path, name, argv, capsys):
    tool, proj, log_path = make_setup(tmp_path, name)
    before_proj = snapshot(proj)
    before_tool = snapshot(tool, skip_pycache=True)
    outputs = []
    prompts = []

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        prompts.append(str(prompt))
        return ""

    capsys.readouterr()
    code = hotdocs_init.run(
        argv,
        tool_root=tool,
        input_fn=input_fn,
        output_fn=output_fn,
        env=fake_env(),
        cwd=proj,
    )
    captured = capsys.readouterr()
    after_proj = snapshot(proj)
    after_tool = snapshot(tool, skip_pycache=True)
    log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    all_text = "\n".join(outputs + prompts + [captured.out, captured.err])
    return {
        "code": code,
        "proj_unchanged": before_proj == after_proj,
        "tool_unchanged": before_tool == after_tool,
        "log": log_text,
        "text": all_text,
        "err": captured.err,
        "proj": proj,
    }


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


@pytest.mark.parametrize("argv", USAGE_CASES, ids=[" ".join(a) for a in USAGE_CASES])
def test_usage_errors_return_2_and_write_nothing(tmp_path, capsys, argv):
    res = call_run(tmp_path, "case", list(argv), capsys)
    assert res["code"] == 2
    assert res["proj_unchanged"], "something was written under <dir>"
    assert res["tool_unchanged"], "something was written under the tool root"
    assert "save_config" not in res["log"]


def test_unknown_provider_message_lists_keys(tmp_path, capsys):
    res = call_run(tmp_path, "nope", ["--provider", "nope"], capsys)
    assert res["code"] == 2
    assert res["proj_unchanged"]
    for key in PROVIDERS:
        assert key in res["text"], key


def test_secret_like_api_key_env_is_never_echoed(tmp_path, capsys):
    res = call_run(
        tmp_path, "secret", ["--provider", "openai", "--api-key-env", SECRET], capsys
    )
    assert res["code"] == 2
    assert res["proj_unchanged"]
    assert res["tool_unchanged"]
    assert "save_config" not in res["log"]
    assert SECRET not in res["text"]
    assert SECRET not in res["log"]


def test_invalid_api_key_env_digit_start_not_echoed(tmp_path, capsys):
    res = call_run(tmp_path, "digit", ["--provider", "openai", "--api-key-env", "9X"], capsys)
    assert res["code"] == 2
    assert res["proj_unchanged"]
    assert SECRET not in res["text"]


SUCCESS_ORDERS = [
    lambda d: ["--provider", "openai", "--yes", d],
    lambda d: ["--yes", "--provider", "openai", d],
    lambda d: [d, "--provider", "openai", "--yes"],
    lambda d: ["--provider=openai", "--yes", d],
    lambda d: ["--yes", "--provider=openai", d],
    lambda d: [d, "--yes", "--provider=openai"],
]


@pytest.mark.parametrize("index", range(len(SUCCESS_ORDERS)))
def test_valid_provider_and_yes_returns_0(tmp_path, capsys, index):
    tool, proj, log_path = make_setup(tmp_path, "ok")
    argv = SUCCESS_ORDERS[index](str(proj))

    def input_fn(prompt=""):
        return ""

    def output_fn(*args, **kwargs):
        pass

    code = hotdocs_init.run(
        argv,
        tool_root=tool,
        input_fn=input_fn,
        output_fn=output_fn,
        env=fake_env(),
        cwd=proj,
    )
    assert code == 0


def test_main_signature_and_usage_error(tmp_path, monkeypatch, capsys):
    params = list(inspect.signature(hotdocs_init.main).parameters)
    assert params == ["argv"]
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    before = snapshot(work)
    assert hotdocs_init.main(["--bogus"]) == 2
    assert snapshot(work) == before