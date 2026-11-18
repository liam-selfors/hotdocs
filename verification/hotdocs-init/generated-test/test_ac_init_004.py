# hotdocs-criterion: sha256:b0a3d0a915d686ad352980d94ad7d8ad4630a52e980e58914ae13f931e9e5452
import importlib.metadata
import json
import os
import stat
from pathlib import Path

import pytest

import hotdocs_init


MISSING_MSG = "provider not configured: gen/llm-endpoint is missing"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def base_providers():
    return {
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


FAKE_BODY = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "def _log(name, **kw):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'fn': name, 'args': kw}, default=str) + '\\n')\n"
    "\n"
    "def detect_providers(env=None, probe_ollama=True):\n"
    "    _log('detect_providers', probe_ollama=probe_ollama)\n"
    "    return [dict(e) for e in _DETECTED]\n"
    "\n"
    "def check_connection(provider, model, base_url=None, api_key_env=None,\n"
    "                     timeout_seconds=30, auth=None):\n"
    "    _log('check_connection', provider=provider, model=model, base_url=base_url,\n"
    "         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)\n"
    "    if provider not in PROVIDERS:\n"
    "        raise ValueError('unknown provider')\n"
    "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
    "        raise ValueError('base_url required')\n"
    "    return {'ok': True, 'error': None}\n"
    "\n"
    "def save_config(config_path, provider, model, base_url=None, api_key_env=None,\n"
    "                timeout_seconds=None, auth=None):\n"
    "    _log('save_config', config_path=str(config_path), provider=provider, model=model,\n"
    "         base_url=base_url, api_key_env=api_key_env,\n"
    "         timeout_seconds=timeout_seconds, auth=auth)\n"
    "    if provider not in PROVIDERS or not model:\n"
    "        raise ValueError('invalid config')\n"
    "    p = Path(config_path)\n"
    "    p.parent.mkdir(parents=True, exist_ok=True)\n"
    "    existing = p.read_text(encoding='utf-8') if p.exists() else ''\n"
    "    kept = []\n"
    "    in_llm = False\n"
    "    for line in existing.splitlines():\n"
    "        s = line.strip()\n"
    "        if s.startswith('['):\n"
    "            in_llm = (s == '[llm]')\n"
    "        if not in_llm:\n"
    "            kept.append(line)\n"
    "    out = kept + ['[llm]', 'provider = ' + json.dumps(provider), 'model = ' + json.dumps(model)]\n"
    "    if base_url is not None:\n"
    "        out.append('base_url = ' + json.dumps(base_url))\n"
    "    if api_key_env is not None:\n"
    "        out.append('api_key_env = ' + json.dumps(api_key_env))\n"
    "    if timeout_seconds is not None:\n"
    "        out.append('timeout_seconds = ' + str(int(timeout_seconds)))\n"
    "    if auth is not None:\n"
    "        out.append('auth = ' + json.dumps(auth))\n"
    "    p.write_text('\\n'.join(out) + '\\n', encoding='utf-8')\n"
    "\n"
    "def load_config(config_path=None):\n"
    "    _log('load_config', config_path=None if config_path is None else str(config_path))\n"
    "    p = Path('hotdocs.toml') if config_path is None else Path(config_path)\n"
    "    if not p.exists():\n"
    "        return None\n"
    "    result = None\n"
    "    in_llm = False\n"
    "    for line in p.read_text(encoding='utf-8').splitlines():\n"
    "        s = line.strip()\n"
    "        if not s or s.startswith('#'):\n"
    "            continue\n"
    "        if s.startswith('['):\n"
    "            in_llm = (s == '[llm]')\n"
    "            if in_llm and result is None:\n"
    "                result = {'provider': None, 'model': None, 'base_url': None,\n"
    "                          'api_key_env': None, 'timeout_seconds': None, 'auth': None}\n"
    "            continue\n"
    "        if in_llm and '=' in s:\n"
    "            k, v = s.split('=', 1)\n"
    "            k = k.strip()\n"
    "            v = v.strip()\n"
    "            if v.startswith('\"'):\n"
    "                v = json.loads(v)\n"
    "            else:\n"
    "                v = int(v)\n"
    "            if k in result:\n"
    "                result[k] = v\n"
    "    return result\n"
)


def make_tool_root(tmp_path, detected, with_endpoint=True):
    root = tmp_path / "tool"
    root.mkdir()
    (root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    ex = root / "examples" / "slugify" / "specs" / "product"
    ex.mkdir(parents=True)
    (ex / "slugs.md").write_text("# Slugs\n\nTurn titles into slugs.\n", encoding="utf-8")
    logdir = tmp_path / "logs"
    logdir.mkdir()
    log = logdir / "calls.log"
    if with_endpoint:
        d = root / "gen" / "llm-endpoint"
        d.mkdir(parents=True)
        src = (
            "LOG = " + repr(str(log)) + "\n"
            + "PROVIDERS = " + repr(base_providers()) + "\n"
            + "_DETECTED = " + repr(detected) + "\n"
            + FAKE_BODY
        )
        (d / "llm_endpoint.py").write_text(src, encoding="utf-8")
    return root, log


def make_env(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    claude = bindir / "claude"
    claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    env = dict(os.environ)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    return env


def make_project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    return proj


class Prompter:
    def __init__(self, answers):
        self.answers = list(answers)
        self.questions = []

    def __call__(self, prompt=""):
        self.questions.append(prompt)
        if len(self.questions) > 60:
            raise RuntimeError("too many questions")
        if self.answers:
            return self.answers.pop(0)
        return ""


class Output:
    def __init__(self):
        self.lines = []

    def __call__(self, *args, **kwargs):
        self.lines.append(" ".join(str(a) for a in args))

    def text(self):
        return "\n".join(self.lines)


def classify(q):
    s = q.lower()
    if "url" in s:
        return "url"
    if "variable" in s or "env" in s:
        return "key"
    if "model" in s:
        return "model"
    if "provider" in s:
        return "provider"
    return None


def kinds(questions):
    return [k for k in (classify(q) for q in questions) if k is not None]


def read_log(log):
    if not log.exists():
        return []
    return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]


def save_calls(log):
    return [c["args"] for c in read_log(log) if c["fn"] == "save_config"]


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
        "reason": "OPENAI_API_KEY is set",
        "suggested_model": "gpt-x",
        "api_key_env": "OPENAI_API_KEY",
    },
]


def run(tmp_path, detected, answers, argv_extra=(), with_endpoint=True, pre=None):
    root, log = make_tool_root(tmp_path, detected, with_endpoint=with_endpoint)
    proj = make_project(tmp_path)
    if pre is not None:
        pre(proj)
    env = make_env(tmp_path)
    prompter = Prompter(answers)
    out = Output()
    rc = hotdocs_init.main(
        [str(proj)] + list(argv_extra),
        tool_root=root,
        input_fn=prompter,
        output_fn=out,
        env=env,
        cwd=proj,
    )
    return rc, prompter, out, log, proj


def test_all_defaults_asks_provider_model_key_in_order(tmp_path):
    rc, prompter, out, log, proj = run(tmp_path, LISTING, [])
    for q in prompter.questions:
        assert q.endswith(" ")
    ks = kinds(prompter.questions)
    assert ks[:3] == ["provider", "model", "key"], prompter.questions
    assert "url" not in ks
    assert ks.count("provider") == 1
    assert ks.count("model") == 1
    assert ks.count("key") == 1
    text = out.text()
    assert "ollama" in text
    assert "openai" in text
    calls = save_calls(log)
    assert len(calls) == 1
    c = calls[0]
    assert c["provider"] == "openai"
    assert c["model"] == "gpt-x"
    assert c["api_key_env"] == "OPENAI_API_KEY"
    assert c["timeout_seconds"] is None


def test_unrecognised_provider_asked_again_then_number_selects(tmp_path):
    rc, prompter, out, log, proj = run(tmp_path, LISTING, ["bogus", "2"])
    ks = kinds(prompter.questions)
    assert ks[:2] == ["provider", "provider"], prompter.questions
    assert ks.count("provider") == 2
    assert ks[2:4] == ["model", "key"]
    calls = save_calls(log)
    assert len(calls) == 1
    assert calls[0]["provider"] == "openai"
    assert calls[0]["model"] == "gpt-x"


def test_openai_compatible_reasks_model_and_base_url(tmp_path):
    detected = [
        {
            "provider": "openai-compatible",
            "available": True,
            "reason": "needs a base URL",
            "suggested_model": "",
            "api_key_env": None,
        }
    ]
    answers = ["openai-compatible", "", "m", "", "http://h/v1", ""]
    rc, prompter, out, log, proj = run(tmp_path, detected, answers)
    ks = kinds(prompter.questions)
    assert ks[:6] == ["provider", "model", "model", "url", "url", "key"], prompter.questions
    assert ks.count("model") == 2
    assert ks.count("url") == 2
    calls = save_calls(log)
    assert len(calls) == 1
    c = calls[0]
    assert c["provider"] == "openai-compatible"
    assert c["model"] == "m"
    assert c["base_url"] == "http://h/v1"
    assert c["api_key_env"] is None
    assert c["timeout_seconds"] is None


def test_claude_cli_asks_no_base_url_or_key_and_returns_zero(tmp_path):
    detected = [
        {
            "provider": "claude-cli",
            "available": True,
            "reason": "claude found on PATH",
            "suggested_model": "claude-sonnet-5",
            "api_key_env": None,
        }
    ]
    rc, prompter, out, log, proj = run(tmp_path, detected, [])
    ks = kinds(prompter.questions)
    assert "url" not in ks, prompter.questions
    assert "key" not in ks, prompter.questions
    assert rc == 0
    calls = save_calls(log)
    assert len(calls) == 1
    assert calls[0]["provider"] == "claude-cli"
    assert calls[0]["model"] == "claude-sonnet-5"


def test_missing_llm_endpoint_with_yes(tmp_path):
    rc, prompter, out, log, proj = run(
        tmp_path, LISTING, [], argv_extra=["--yes"], with_endpoint=False
    )
    assert any(MISSING_MSG in line for line in out.lines), out.lines
    assert rc == 0
    assert not (proj / "hotdocs.toml").exists()


def test_existing_hotdocs_toml_is_kept(tmp_path):
    content = (
        "[llm]\n"
        "provider = \"openai\"\n"
        "model = \"gpt-x\"\n"
        "api_key_env = \"OPENAI_API_KEY\"\n"
    )

    def pre(proj):
        (proj / "hotdocs.toml").write_text(content, encoding="utf-8")

    rc, prompter, out, log, proj = run(tmp_path, LISTING, [], pre=pre)
    assert save_calls(log) == []
    assert (proj / "hotdocs.toml").read_text(encoding="utf-8") == content
    ks = kinds(prompter.questions)
    assert "provider" not in ks, prompter.questions
    assert "model" not in ks, prompter.questions
    assert "hotdocs.toml" in out.text()