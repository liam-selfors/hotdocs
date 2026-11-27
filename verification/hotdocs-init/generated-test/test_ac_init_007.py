# hotdocs-criterion: sha256:1eddf897979c763a19d10fbd5f22a151d9d6dac8f54cdfe4b333a9189af99587
import importlib.metadata
import inspect
import os
from pathlib import Path

import pytest

import hotdocs_init


SECRET = "sk-abc123"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_BODY = '''
import json
import tomllib
from pathlib import Path


def _log(name, **kw):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps([name, {k: repr(v) for k, v in kw.items()}]) + "\\n")


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
    _log("detect_providers", env_given=env is not None, probe_ollama=probe_ollama)
    out = []
    for name, info in PROVIDERS.items():
        available = name == "openai"
        out.append({
            "provider": name,
            "available": available,
            "reason": "key set" if available else "not configured",
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


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS or not model:
        raise ValueError("invalid config")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.is_file():
        in_llm = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                in_llm = stripped == "[llm]"
            if not in_llm:
                kept.append(line)
    lines = kept + ["[llm]", "provider = " + json.dumps(provider),
                    "model = " + json.dumps(model)]
    if base_url is not None:
        lines.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        lines.append("auth = " + json.dumps(auth))
    path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=str(config_path))
    path = Path(config_path) if config_path is not None else Path.cwd() / "hotdocs.toml"
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("invalid config") from exc
    llm = data.get("llm")
    if llm is None:
        return None
    return {k: llm.get(k) for k in
            ("provider", "model", "base_url", "api_key_env", "timeout_seconds", "auth")}
'''


def make_env(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log = log_dir / "llm_calls.log"

    tool = tmp_path / "tool"
    ep = tool / "gen" / "llm-endpoint"
    ep.mkdir(parents=True)
    (ep / "llm_endpoint.py").write_text("LOG = " + repr(str(log)) + "\n" + FAKE_BODY,
                                        encoding="utf-8")
    slugs = tool / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nTurn titles into slugs.\n", encoding="utf-8")
    (tool / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8")
    (tool / "pyproject.toml").write_text(
        '[project]\nname = "hotdocs"\nversion = "9.8.7a1"\n', encoding="utf-8")

    proj = tmp_path / "proj"
    proj.mkdir()
    return tool, proj, log


def snapshot(root, exclude):
    files = {}
    dirs = set()
    for p in sorted(Path(root).rglob("*")):
        if "__pycache__" in p.parts:
            continue
        if any(p == e or e in p.parents for e in exclude):
            continue
        rel = str(p.relative_to(root))
        if p.is_dir():
            dirs.add(rel)
        else:
            files[rel] = p.read_bytes()
    return files, dirs


def call_run(argv, tool, cwd, env, capsys):
    outputs = []
    prompts = []

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        prompts.append(str(prompt))
        return ""

    capsys.readouterr()
    rc = hotdocs_init.run(argv, tool_root=tool, input_fn=input_fn,
                          output_fn=output_fn, env=env, cwd=cwd)
    captured = capsys.readouterr()
    text = "\n".join(outputs + prompts + [captured.out, captured.err])
    return rc, text


def base_env():
    return {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}


USAGE_CASES = [
    ["--bogus"],
    ["--provider"],
    ["a", "b"],
    ["--provider", "nope"],
    ["--provider=openai", "--model"],
    ["--provider", "openai", "--api-key-env", SECRET],
    ["--provider", "openai", "--api-key-env", "9X"],
    ["--provider", "claude-cli", "--base-url", "http://h"],
    ["--provider", "claude-cli", "--api-key-env", "K"],
    ["--provider", "claude-cli", "--auth", "token"],
    ["--provider", "openai", "--model", "m", "--auth", "login"],
    ["--provider", "openai-compatible", "--base-url", "http://h"],
    ["--provider", "openai-compatible", "--model", "m"],
]


@pytest.mark.parametrize("argv", USAGE_CASES, ids=lambda a: " ".join(a))
def test_usage_errors_return_2_and_write_nothing(tmp_path, capsys, argv):
    tool, proj, log = make_env(tmp_path)
    exclude = [tmp_path / "logs"]
    before = snapshot(tmp_path, exclude)

    rc, text = call_run(list(argv), tool, proj, base_env(), capsys)

    assert rc == 2
    after = snapshot(tmp_path, exclude)
    assert after == before, "a usage error wrote something"
    assert not (proj / "a").exists()
    assert not (proj / "b").exists()
    assert list(proj.iterdir()) == []

    if argv == ["--provider", "nope"]:
        for key in ("claude-cli", "anthropic", "openai", "openai-compatible",
                    "gemini", "ollama"):
            assert key in text, "the 'nope' message does not list " + key

    if SECRET in argv:
        assert SECRET not in text
        for p in tmp_path.rglob("*"):
            if p.is_file():
                assert SECRET.encode() not in p.read_bytes(), str(p)


SUCCESS_ARGVS = []
for _form in ("split", "equals"):
    _prov = ["--provider", "openai"] if _form == "split" else ["--provider=openai"]
    for _order in ("provider_first", "yes_first"):
        _flags = _prov + ["--yes"] if _order == "provider_first" else ["--yes"] + _prov
        for _dir_pos in ("last", "first"):
            SUCCESS_ARGVS.append((_form + "-" + _order + "-dir_" + _dir_pos, _flags, _dir_pos))


@pytest.mark.parametrize("case", SUCCESS_ARGVS, ids=lambda c: c[0])
def test_provider_openai_yes_returns_0(tmp_path, capsys, case):
    _, flags, dir_pos = case
    tool, proj, log = make_env(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    env = dict(os.environ)
    env["OPENAI_API_KEY"] = "placeholder-value"
    target = str(proj)
    argv = list(flags) + [target] if dir_pos == "last" else [target] + list(flags)

    rc, text = call_run(argv, tool, work, env, capsys)

    assert rc == 0, text


def test_main_signature_and_usage_error(capsys):
    params = list(inspect.signature(hotdocs_init.main).parameters)
    assert params == ["argv"]
    rc = hotdocs_init.main(["--bogus"])
    capsys.readouterr()
    assert rc == 2