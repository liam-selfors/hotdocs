# hotdocs-criterion: sha256:edc31356ad53fde4a69463c710d02906460515568a80797be3812ce9b6eb142a
import importlib.metadata
import json
import os
import stat
from pathlib import Path

import hotdocs_init


FULL_PROVIDERS = {
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
        "suggested_model": "gpt-x",
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
import json
from pathlib import Path


def _log(name, **kw):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, "args": kw}, default=str) + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", probe_ollama=probe_ollama)
    return [dict(e) for e in _DETECTED]


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def _strip_llm(text):
    out = []
    in_llm = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_llm = (s == "[llm]")
            if in_llm:
                continue
        if not in_llm:
            out.append(line)
    return out


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if not model:
        raise ValueError("model required")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = _strip_llm(existing)
    lines.append("[llm]")
    values = {"provider": provider, "model": model, "base_url": base_url,
              "api_key_env": api_key_env, "timeout_seconds": timeout_seconds,
              "auth": auth}
    for key in ["provider", "model", "base_url", "api_key_env", "timeout_seconds", "auth"]:
        if values[key] is not None:
            lines.append(key + " = " + json.dumps(values[key]))
    path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=str(config_path))
    if config_path is None:
        config_path = Path.cwd() / "hotdocs.toml"
    path = Path(config_path)
    if not path.is_file():
        return None
    result = {"provider": None, "model": None, "base_url": None,
              "api_key_env": None, "timeout_seconds": None, "auth": None}
    in_llm = False
    found = False
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_llm = (s == "[llm]")
            found = found or in_llm
            continue
        if in_llm and "=" in s:
            key, _, val = s.partition("=")
            key = key.strip()
            if key in result:
                try:
                    result[key] = json.loads(val.strip())
                except ValueError:
                    raise ValueError("invalid value for " + key)
    if not found:
        return None
    return result
'''


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_tool_root(tmp_path, detected, with_endpoint=True):
    root = tmp_path / "tool"
    root.mkdir()
    (root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    slugs = root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n", encoding="utf-8")
    log = tmp_path / "logs" / "calls.log"
    log.parent.mkdir()
    log.write_text("", encoding="utf-8")
    if with_endpoint:
        d = root / "gen" / "llm-endpoint"
        d.mkdir(parents=True)
        src = (
            "LOG = " + repr(str(log)) + "\n"
            + "PROVIDERS = " + repr(FULL_PROVIDERS) + "\n"
            + "_DETECTED = " + repr(detected) + "\n"
            + FAKE_BODY
        )
        (d / "llm_endpoint.py").write_text(src, encoding="utf-8")
    return root, log


def make_project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    return proj


def read_calls(log, name):
    out = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec["call"] == name:
                out.append(rec["args"])
    return out


def classify(question):
    q = question.lower()
    if "url" in q:
        return "base_url"
    if "key" in q:
        return "api_key"
    if "model" in q:
        return "model"
    if "provider" in q:
        return "provider"
    return "other"


class Asker:
    def __init__(self, answers):
        self.answers = list(answers)
        self.questions = []

    def __call__(self, prompt=""):
        self.questions.append(prompt)
        if self.answers:
            return self.answers.pop(0)
        return ""

    def kinds(self):
        return [k for k in (classify(q) for q in self.questions) if k != "other"]


class Output:
    def __init__(self):
        self.lines = []

    def __call__(self, *args, **kwargs):
        self.lines.append(" ".join(str(a) for a in args))

    def text(self):
        return "\n".join(self.lines)


LISTING = [
    {
        "provider": "ollama",
        "available": False,
        "reason": "not running",
        "suggested_model": "llama3.2",
        "api_key_env": None,
    },
    {
        "provider": "openai",
        "available": True,
        "reason": "key set",
        "suggested_model": "gpt-x",
        "api_key_env": "OPENAI_API_KEY",
    },
]


def run(tool_root, proj, asker, out, env, extra=None):
    argv = [str(proj)] + list(extra or [])
    return hotdocs_init.main(
        argv, tool_root=tool_root, input_fn=asker, output_fn=out, env=env, cwd=proj
    )


def test_empty_answers_use_defaults(tmp_path):
    tool_root, log = make_tool_root(tmp_path, LISTING)
    proj = make_project(tmp_path)
    asker = Asker([])
    out = Output()
    run(tool_root, proj, asker, out, {"PATH": ""})

    assert asker.kinds() == ["provider", "model", "api_key"], asker.questions
    text = out.text()
    assert "ollama" in text
    assert "openai" in text
    saves = read_calls(log, "save_config")
    assert len(saves) == 1
    s = saves[0]
    assert s["provider"] == "openai"
    assert s["model"] == "gpt-x"
    assert s["api_key_env"] == "OPENAI_API_KEY"
    assert s["base_url"] is None
    assert s["timeout_seconds"] is None


def test_unrecognised_provider_is_asked_again(tmp_path):
    tool_root, log = make_tool_root(tmp_path, LISTING)
    proj = make_project(tmp_path)
    asker = Asker(["bogus", "2"])
    out = Output()
    run(tool_root, proj, asker, out, {"PATH": ""})

    kinds = asker.kinds()
    assert kinds[:2] == ["provider", "provider"], asker.questions
    assert kinds.count("provider") == 2
    saves = read_calls(log, "save_config")
    assert len(saves) == 1
    assert saves[0]["provider"] == "openai"


def test_openai_compatible_reasks_model_and_base_url(tmp_path):
    listing = [
        {
            "provider": "openai-compatible",
            "available": True,
            "reason": "configurable",
            "suggested_model": "",
            "api_key_env": None,
        },
    ]
    tool_root, log = make_tool_root(tmp_path, listing)
    proj = make_project(tmp_path)
    asker = Asker(["openai-compatible", "", "m", "", "http://h/v1", ""])
    out = Output()
    run(tool_root, proj, asker, out, {"PATH": ""})

    kinds = asker.kinds()
    assert kinds == [
        "provider", "model", "model", "base_url", "base_url", "api_key"
    ], asker.questions
    saves = read_calls(log, "save_config")
    assert len(saves) == 1
    s = saves[0]
    assert s["provider"] == "openai-compatible"
    assert s["model"] == "m"
    assert s["base_url"] == "http://h/v1"
    assert s["api_key_env"] is None
    assert s["timeout_seconds"] is None


def test_claude_cli_asks_no_base_url_or_key(tmp_path):
    listing = [
        {
            "provider": "claude-cli",
            "available": True,
            "reason": "claude found on PATH",
            "suggested_model": "claude-sonnet-5",
            "api_key_env": None,
        },
    ]
    tool_root, log = make_tool_root(tmp_path, listing)
    proj = make_project(tmp_path)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    claude = bindir / "claude"
    claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    asker = Asker([])
    out = Output()
    rc = run(tool_root, proj, asker, out, {"PATH": str(bindir)})

    kinds = asker.kinds()
    assert "base_url" not in kinds, asker.questions
    assert "api_key" not in kinds, asker.questions
    assert rc == 0
    saves = read_calls(log, "save_config")
    assert len(saves) == 1
    assert saves[0]["provider"] == "claude-cli"


def test_missing_llm_endpoint_with_yes(tmp_path):
    tool_root, log = make_tool_root(tmp_path, LISTING, with_endpoint=False)
    proj = make_project(tmp_path)
    asker = Asker([])
    out = Output()
    rc = run(tool_root, proj, asker, out, {"PATH": ""}, ["--yes"])

    assert any(
        "provider not configured: gen/llm-endpoint is missing" in line
        for line in out.lines
    ), out.lines
    assert rc == 0
    assert not (proj / "hotdocs.toml").exists()


def test_existing_hotdocs_toml_is_kept(tmp_path):
    tool_root, log = make_tool_root(tmp_path, LISTING)
    proj = make_project(tmp_path)
    toml = proj / "hotdocs.toml"
    content = '[llm]\nprovider = "openai"\nmodel = "gpt-x"\napi_key_env = "OPENAI_API_KEY"\n'
    toml.write_text(content, encoding="utf-8")
    before = toml.read_bytes()
    asker = Asker([])
    out = Output()
    run(tool_root, proj, asker, out, {"PATH": ""})

    assert "provider" not in asker.kinds(), asker.questions
    assert "hotdocs.toml" in out.text()
    assert read_calls(log, "save_config") == []
    assert toml.read_bytes() == before