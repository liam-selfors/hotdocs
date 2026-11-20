# hotdocs-criterion: sha256:6704befffb63e1e49c7f220cd1fb24bb67d29dca8eb40f3257d34d42b2e1f920
import importlib.metadata
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import hotdocs_init


pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="the Python 3.11 prerequisite would itself be reported missing",
)


FAKE_LLM_ENDPOINT_BODY = (
    "import json\n"
    "import os\n"
    "import tomllib\n"
    "from pathlib import Path\n"
    "\n"
    "PROVIDERS = {\n"
    "    'claude-cli': {'default_base_url': None, 'default_api_key_env': None,\n"
    "                   'needs_base_url': False, 'suggested_model': 'claude-sonnet-5'},\n"
    "    'anthropic': {'default_base_url': 'https://api.anthropic.com',\n"
    "                  'default_api_key_env': 'ANTHROPIC_API_KEY',\n"
    "                  'needs_base_url': False, 'suggested_model': 'claude-sonnet-5'},\n"
    "    'openai': {'default_base_url': 'https://api.openai.com/v1',\n"
    "               'default_api_key_env': 'OPENAI_API_KEY',\n"
    "               'needs_base_url': False, 'suggested_model': 'gpt-6-astra'},\n"
    "    'openai-compatible': {'default_base_url': None, 'default_api_key_env': None,\n"
    "                          'needs_base_url': True, 'suggested_model': ''},\n"
    "    'gemini': {'default_base_url': 'https://generativelanguage.googleapis.com',\n"
    "               'default_api_key_env': 'GEMINI_API_KEY',\n"
    "               'needs_base_url': False, 'suggested_model': 'gemini-4-argon'},\n"
    "    'ollama': {'default_base_url': 'http://localhost:11434', 'default_api_key_env': None,\n"
    "               'needs_base_url': False, 'suggested_model': 'llama3.2'},\n"
    "}\n"
    "\n"
    "_KEYS = ('provider', 'model', 'base_url', 'api_key_env', 'timeout_seconds', 'auth')\n"
    "\n"
    "\n"
    "def _log(name, **kwargs):\n"
    "    entry = {'call': name, 'args': {k: repr(v) for k, v in kwargs.items()}}\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "\n"
    "def detect_providers(env=None, probe_ollama=True):\n"
    "    _log('detect_providers', env=env is not None, probe_ollama=probe_ollama)\n"
    "    out = []\n"
    "    for name, info in PROVIDERS.items():\n"
    "        out.append({\n"
    "            'provider': name,\n"
    "            'available': name == 'ollama',\n"
    "            'reason': 'fake detection',\n"
    "            'suggested_model': info['suggested_model'],\n"
    "            'api_key_env': info['default_api_key_env'],\n"
    "        })\n"
    "    return out\n"
    "\n"
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
    "\n"
    "def save_config(config_path, provider, model, base_url=None, api_key_env=None,\n"
    "                timeout_seconds=None, auth=None):\n"
    "    _log('save_config', config_path=str(config_path), provider=provider, model=model,\n"
    "         base_url=base_url, api_key_env=api_key_env,\n"
    "         timeout_seconds=timeout_seconds, auth=auth)\n"
    "    if provider not in PROVIDERS:\n"
    "        raise ValueError('unknown provider')\n"
    "    if not model:\n"
    "        raise ValueError('model required')\n"
    "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
    "        raise ValueError('base_url required')\n"
    "    path = Path(config_path)\n"
    "    path.parent.mkdir(parents=True, exist_ok=True)\n"
    "    kept = []\n"
    "    if path.exists():\n"
    "        in_llm = False\n"
    "        for line in path.read_text(encoding='utf-8').splitlines():\n"
    "            stripped = line.strip()\n"
    "            if stripped.startswith('['):\n"
    "                in_llm = stripped == '[llm]'\n"
    "            if not in_llm:\n"
    "                kept.append(line)\n"
    "    values = {'provider': provider, 'model': model, 'base_url': base_url,\n"
    "              'api_key_env': api_key_env, 'timeout_seconds': timeout_seconds,\n"
    "              'auth': auth}\n"
    "    lines = list(kept)\n"
    "    if lines and lines[-1].strip():\n"
    "        lines.append('')\n"
    "    lines.append('[llm]')\n"
    "    for key, value in values.items():\n"
    "        if value is None:\n"
    "            continue\n"
    "        lines.append(key + ' = ' + json.dumps(value))\n"
    "    path.write_text('\\n'.join(lines) + '\\n', encoding='utf-8')\n"
    "\n"
    "\n"
    "def load_config(config_path=None):\n"
    "    _log('load_config', config_path=None if config_path is None else str(config_path))\n"
    "    if config_path is None:\n"
    "        return None\n"
    "    path = Path(config_path)\n"
    "    if not path.is_file():\n"
    "        return None\n"
    "    try:\n"
    "        data = tomllib.loads(path.read_text(encoding='utf-8'))\n"
    "    except tomllib.TOMLDecodeError as exc:\n"
    "        raise ValueError('invalid config') from exc\n"
    "    llm = data.get('llm')\n"
    "    if llm is None:\n"
    "        return None\n"
    "    return {key: llm.get(key) for key in _KEYS}\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_tool_root(base, requirement_lines):
    tool = base / "tool"
    logs = base / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / "llm_endpoint_calls.log"

    fake_dir = tool / "gen" / "llm-endpoint"
    fake_dir.mkdir(parents=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_LLM_ENDPOINT_BODY
    (fake_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")

    slugs = tool / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nA fake example product spec.\n", encoding="utf-8")

    (tool / "requirements.txt").write_text(
        "\n".join(requirement_lines) + "\n", encoding="utf-8"
    )
    return tool, log_path


def installed_requirements():
    return ["pytest==" + importlib.metadata.version("pytest")]


def make_env(base, with_claude):
    bindir = base / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    if with_claude:
        claude = bindir / "claude"
        claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    home = base / "home"
    home.mkdir(parents=True, exist_ok=True)
    return {"PATH": str(bindir), "HOME": str(home)}


class Recorder:
    def __init__(self):
        self.lines = []
        self.questions = []

    def output_fn(self, *args, **kwargs):
        text = " ".join(str(a) for a in args)
        self.lines.extend(text.split("\n"))

    def input_fn(self, prompt=""):
        self.questions.append(prompt)
        return ""


@pytest.fixture
def no_commands(monkeypatch):
    calls = []

    def refuse(*args, **kwargs):
        calls.append(args)
        raise AssertionError("init ran a command: " + repr(args))

    for name in ("run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"):
        if hasattr(subprocess, name):
            monkeypatch.setattr(subprocess, name, refuse)
    monkeypatch.setattr(os, "system", refuse)
    if hasattr(os, "popen"):
        monkeypatch.setattr(os, "popen", refuse)
    return calls


def run_init(base, tool, env, provider, model, recorder):
    project = base / "project"
    project.mkdir(parents=True, exist_ok=True)
    argv = [
        str(project),
        "--provider", provider,
        "--model", model,
        "--no-test",
        "--yes",
    ]
    code = hotdocs_init.main(
        argv,
        tool_root=str(tool),
        input_fn=recorder.input_fn,
        output_fn=recorder.output_fn,
        env=env,
        cwd=str(base),
    )
    return code, project


def assert_consecutive(lines, first, second):
    for i in range(len(lines) - 1):
        if lines[i] == first and lines[i + 1] == second:
            return
    raise AssertionError(
        "expected consecutive lines " + repr(first) + " / " + repr(second) + " in " + repr(lines)
    )


def test_missing_requirement_reported_and_returns_3(tmp_path, no_commands, capsys):
    tool, _log = make_tool_root(tmp_path, ["pytest==9.2.0", "no-such-pkg-xyz==1.0"])
    env = make_env(tmp_path, with_claude=False)
    rec = Recorder()

    code, project = run_init(tmp_path, tool, env, "ollama", "llama3.2", rec)

    assert code == 3, rec.lines
    # The skeleton was still created.
    assert project.is_dir()
    assert any(project.iterdir()), "init created no skeleton"
    # No example was involved.
    assert not list(project.rglob("slugs.md"))

    assert_consecutive(
        rec.lines,
        "missing: no-such-pkg-xyz==1.0",
        "  fix: pip install -r " + str(tool) + "/requirements.txt",
    )
    assert "missing: pytest==9.2.0" not in rec.lines
    assert no_commands == []

    captured = capsys.readouterr()
    assert "missing:" not in captured.err


def test_claude_missing_on_path_returns_3(tmp_path, no_commands, capsys):
    tool, _log = make_tool_root(tmp_path, installed_requirements())
    env = make_env(tmp_path, with_claude=False)
    rec = Recorder()

    code, project = run_init(tmp_path, tool, env, "claude-cli", "claude-sonnet-5", rec)

    assert code == 3, rec.lines
    assert_consecutive(
        rec.lines,
        "missing: claude on PATH",
        "  fix: install Claude Code and sign in",
    )
    assert no_commands == []
    captured = capsys.readouterr()
    assert "missing:" not in captured.err


def test_claude_present_on_path_returns_0(tmp_path, no_commands):
    tool, _log = make_tool_root(tmp_path, installed_requirements())
    env = make_env(tmp_path, with_claude=True)
    rec = Recorder()

    code, project = run_init(tmp_path, tool, env, "claude-cli", "claude-sonnet-5", rec)

    assert code == 0, rec.lines
    assert "missing: claude on PATH" not in rec.lines
    assert no_commands == []


def test_ollama_without_claude_returns_0(tmp_path, no_commands):
    tool, _log = make_tool_root(tmp_path, installed_requirements())
    env = make_env(tmp_path, with_claude=False)
    rec = Recorder()

    code, project = run_init(tmp_path, tool, env, "ollama", "llama3.2", rec)

    assert code == 0, rec.lines
    assert "missing: claude on PATH" not in rec.lines
    assert no_commands == []