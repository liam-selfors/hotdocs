# hotdocs-criterion: sha256:eada71abba1e8d85a0751b0b12f27a75b171125f92b19c0682d148ae61e69d77
import importlib.metadata
import json
import os
import stat
import sys
from pathlib import Path

import pytest

import hotdocs_init


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


MISSING_MESSAGE = "provider not configured: gen/llm-endpoint is missing"


def _fake_endpoint_source(providers, listing, log_path):
    return (
        "import json\n"
        "import tomllib\n"
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "PROVIDERS = " + repr(providers) + "\n"
        "_LISTING = " + repr(listing) + "\n"
        "_MISSING = object()\n"
        "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry, default=str) + '\\n')\n"
        "\n"
        "\n"
        "def detect_providers(env=None, probe_ollama=True):\n"
        "    _log({'fn': 'detect_providers', 'env_given': env is not None,\n"
        "          'probe_ollama': probe_ollama})\n"
        "    return [dict(e) for e in _LISTING]\n"
        "\n"
        "\n"
        "def check_connection(provider, model, base_url=None, api_key_env=None,\n"
        "                     timeout_seconds=30, auth=None):\n"
        "    _log({'fn': 'check_connection', 'provider': provider, 'model': model,\n"
        "          'base_url': base_url, 'api_key_env': api_key_env,\n"
        "          'timeout_seconds': timeout_seconds, 'auth': auth})\n"
        "    if provider not in PROVIDERS:\n"
        "        raise ValueError('unknown provider')\n"
        "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
        "        raise ValueError('base_url required')\n"
        "    return {'ok': True, 'error': None}\n"
        "\n"
        "\n"
        "def _toml_str(value):\n"
        "    return json.dumps(str(value))\n"
        "\n"
        "\n"
        "def save_config(config_path, provider, model, base_url=None,\n"
        "                api_key_env=_MISSING, timeout_seconds=None, auth=None):\n"
        "    passed = api_key_env is not _MISSING\n"
        "    if not passed:\n"
        "        api_key_env = None\n"
        "    _log({'fn': 'save_config', 'config_path': str(config_path),\n"
        "          'provider': provider, 'model': model, 'base_url': base_url,\n"
        "          'api_key_env': api_key_env, 'api_key_env_passed': passed,\n"
        "          'timeout_seconds': timeout_seconds, 'auth': auth})\n"
        "    if provider not in PROVIDERS or not model:\n"
        "        raise ValueError('invalid config')\n"
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
        "    lines = ['[llm]', 'provider = ' + _toml_str(provider),\n"
        "             'model = ' + _toml_str(model)]\n"
        "    if base_url is not None:\n"
        "        lines.append('base_url = ' + _toml_str(base_url))\n"
        "    if api_key_env is not None:\n"
        "        lines.append('api_key_env = ' + _toml_str(api_key_env))\n"
        "    if timeout_seconds is not None:\n"
        "        lines.append('timeout_seconds = ' + str(int(timeout_seconds)))\n"
        "    if auth is not None:\n"
        "        lines.append('auth = ' + _toml_str(auth))\n"
        "    text = '\\n'.join(kept + [''] + lines) if kept else '\\n'.join(lines)\n"
        "    path.write_text(text + '\\n', encoding='utf-8')\n"
        "\n"
        "\n"
        "def load_config(config_path=None):\n"
        "    _log({'fn': 'load_config', 'config_path': str(config_path)})\n"
        "    path = Path(config_path) if config_path is not None else Path.cwd() / 'hotdocs.toml'\n"
        "    if not path.exists():\n"
        "        return None\n"
        "    try:\n"
        "        data = tomllib.loads(path.read_text(encoding='utf-8'))\n"
        "    except tomllib.TOMLDecodeError as exc:\n"
        "        raise ValueError('invalid config') from exc\n"
        "    llm = data.get('llm')\n"
        "    if llm is None:\n"
        "        return None\n"
        "    return {'provider': llm.get('provider'), 'model': llm.get('model'),\n"
        "            'base_url': llm.get('base_url'), 'api_key_env': llm.get('api_key_env'),\n"
        "            'timeout_seconds': llm.get('timeout_seconds'), 'auth': llm.get('auth')}\n"
    )


def _base_tool_root(tool_root):
    (tool_root / "examples" / "slugify" / "specs" / "product").mkdir(parents=True)
    (tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md").write_text(
        "# Slugs\n\nTurn titles into slugs.\n", encoding="utf-8"
    )
    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    (tool_root / "pyproject.toml").write_text(
        '[project]\nname = "hotdocs"\nversion = "9.8.7a1"\n', encoding="utf-8"
    )
    (tool_root / "gen").mkdir(parents=True, exist_ok=True)


def _make_tool_root(tmp_path, providers, listing):
    tool_root = tmp_path / "tool"
    _base_tool_root(tool_root)
    log_path = tmp_path / "endpoint-log.jsonl"
    ep = tool_root / "gen" / "llm-endpoint"
    ep.mkdir(parents=True)
    (ep / "llm_endpoint.py").write_text(
        _fake_endpoint_source(providers, listing, log_path), encoding="utf-8"
    )
    return tool_root, log_path


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _saves(log_path):
    return [e for e in _read_log(log_path) if e["fn"] == "save_config"]


def _classify(prompt):
    low = prompt.lower()
    if "url" in low:
        return "base_url"
    if "variable" in low or "env" in low or "key name" in low:
        return "api_key"
    if "model" in low:
        return "model"
    if "provider" in low:
        return "provider"
    return None


class Console:
    def __init__(self, answers=None, default=""):
        self.answers = list(answers or [])
        self.default = default
        self.prompts = []
        self.outputs = []

    def input_fn(self, prompt=""):
        self.prompts.append(prompt)
        if len(self.prompts) > 60:
            raise RuntimeError("too many questions asked")
        if self.answers:
            return self.answers.pop(0)
        return self.default

    def output_fn(self, *args, **kwargs):
        self.outputs.append(" ".join(str(a) for a in args))

    def classified(self):
        return [c for c in (_classify(p) for p in self.prompts) if c is not None]

    def text(self):
        return "\n".join(self.outputs)


@pytest.fixture(autouse=True)
def _clean_modules():
    sys.modules.pop("llm_endpoint", None)
    yield
    sys.modules.pop("llm_endpoint", None)


def _project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    return proj


def _env(extra_path=None):
    path = os.environ.get("PATH", "")
    if extra_path is not None:
        path = str(extra_path) + os.pathsep + path
    return {"PATH": path}


OLLAMA_OPENAI_PROVIDERS = {
    "ollama": {
        "default_base_url": "http://localhost:11434",
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "llama3.2",
    },
    "openai": {
        "default_base_url": "https://api.openai.com/v1",
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-x",
    },
}

OLLAMA_OPENAI_LISTING = [
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


def test_all_empty_answers_ask_provider_model_key_in_order(tmp_path):
    tool_root, log_path = _make_tool_root(tmp_path, OLLAMA_OPENAI_PROVIDERS, OLLAMA_OPENAI_LISTING)
    proj = _project(tmp_path)
    con = Console()
    hotdocs_init.run(
        [str(proj)], tool_root=tool_root, input_fn=con.input_fn,
        output_fn=con.output_fn, env=_env(), cwd=proj,
    )
    for p in con.prompts:
        assert p.endswith(" ")
    assert con.classified() == ["provider", "model", "api_key"], con.prompts
    out = con.text()
    assert "ollama" in out
    assert "openai" in out
    saves = _saves(log_path)
    assert len(saves) == 1
    s = saves[0]
    assert s["provider"] == "openai"
    assert s["model"] == "gpt-x"
    assert s["api_key_env"] == "OPENAI_API_KEY"


def test_unrecognised_provider_is_asked_again_and_number_selects(tmp_path):
    tool_root, log_path = _make_tool_root(tmp_path, OLLAMA_OPENAI_PROVIDERS, OLLAMA_OPENAI_LISTING)
    proj = _project(tmp_path)
    con = Console(answers=["bogus", "2"])
    hotdocs_init.run(
        [str(proj)], tool_root=tool_root, input_fn=con.input_fn,
        output_fn=con.output_fn, env=_env(), cwd=proj,
    )
    classified = con.classified()
    assert classified[:2] == ["provider", "provider"], con.prompts
    assert classified.count("provider") == 2, con.prompts
    saves = _saves(log_path)
    assert len(saves) == 1
    assert saves[0]["provider"] == "openai"


def test_openai_compatible_reasks_model_and_base_url(tmp_path):
    providers = {
        "openai-compatible": {
            "default_base_url": None,
            "default_api_key_env": None,
            "needs_base_url": True,
            "suggested_model": "",
        },
    }
    listing = [
        {
            "provider": "openai-compatible",
            "available": True,
            "reason": "configurable",
            "suggested_model": "",
            "api_key_env": None,
        },
    ]
    tool_root, log_path = _make_tool_root(tmp_path, providers, listing)
    proj = _project(tmp_path)
    con = Console(answers=["openai-compatible", "", "m", "", "http://h/v1", ""])
    hotdocs_init.run(
        [str(proj)], tool_root=tool_root, input_fn=con.input_fn,
        output_fn=con.output_fn, env=_env(), cwd=proj,
    )
    classified = con.classified()
    assert classified[:6] == [
        "provider", "model", "model", "base_url", "base_url", "api_key",
    ], con.prompts
    assert classified.count("model") == 2
    assert classified.count("base_url") == 2
    saves = _saves(log_path)
    assert len(saves) == 1
    s = saves[0]
    assert s["provider"] == "openai-compatible"
    assert s["model"] == "m"
    assert s["base_url"] == "http://h/v1"
    assert s["api_key_env_passed"] is False


def test_claude_cli_asks_no_base_url_or_api_key(tmp_path):
    providers = {
        "claude-cli": {
            "default_base_url": None,
            "default_api_key_env": None,
            "needs_base_url": False,
            "suggested_model": "claude-sonnet-5",
        },
    }
    listing = [
        {
            "provider": "claude-cli",
            "available": True,
            "reason": "claude on PATH",
            "suggested_model": "claude-sonnet-5",
            "api_key_env": None,
        },
    ]
    tool_root, log_path = _make_tool_root(tmp_path, providers, listing)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    claude = bindir / "claude"
    claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    proj = _project(tmp_path)
    con = Console()
    rc = hotdocs_init.run(
        [str(proj)], tool_root=tool_root, input_fn=con.input_fn,
        output_fn=con.output_fn, env=_env(bindir), cwd=proj,
    )
    classified = con.classified()
    assert "base_url" not in classified, con.prompts
    assert "api_key" not in classified, con.prompts
    assert rc == 0, con.text()


def test_missing_llm_endpoint_reports_and_carries_on(tmp_path):
    tool_root = tmp_path / "tool"
    _base_tool_root(tool_root)
    proj = _project(tmp_path)
    con = Console()
    rc = hotdocs_init.run(
        [str(proj), "--yes"], tool_root=tool_root, input_fn=con.input_fn,
        output_fn=con.output_fn, env=_env(), cwd=proj,
    )
    assert any(MISSING_MESSAGE in o for o in con.outputs), con.outputs
    assert rc == 0, con.text()
    assert not (proj / "hotdocs.toml").exists()


def test_existing_hotdocs_toml_is_kept(tmp_path):
    tool_root, log_path = _make_tool_root(tmp_path, OLLAMA_OPENAI_PROVIDERS, OLLAMA_OPENAI_LISTING)
    proj = _project(tmp_path)
    existing = proj / "hotdocs.toml"
    existing.write_bytes(b'[llm]\nprovider = "openai"\nmodel = "gpt-x"\n')
    before = existing.read_bytes()
    con = Console()
    hotdocs_init.run(
        [str(proj)], tool_root=tool_root, input_fn=con.input_fn,
        output_fn=con.output_fn, env=_env(), cwd=proj,
    )
    assert _saves(log_path) == []
    assert existing.read_bytes() == before
    assert "provider" not in con.classified(), con.prompts
    assert "hotdocs.toml" in con.text()