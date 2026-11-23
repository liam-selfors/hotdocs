# hotdocs-criterion: sha256:3a000d6395c2fb5edbece697de5dac0982b6fb750582af4f383fc8072a9405ca
import importlib.metadata
import json
import os
import stat
from pathlib import Path

import hotdocs_init


OPENAI_COMPAT = "openai-compatible"

BASE_PROVIDERS = {
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
    OPENAI_COMPAT: {
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


FAKE_BODY = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "_KEYS = ('provider', 'model', 'base_url', 'api_key_env', 'timeout_seconds', 'auth')\n"
    "\n"
    "def _log(fn, **kw):\n"
    "    with open(LOG, 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps({'fn': fn, 'args': kw}, default=str) + '\\n')\n"
    "\n"
    "def detect_providers(env=None, probe_ollama=True):\n"
    "    _log('detect_providers', probe_ollama=probe_ollama)\n"
    "    return [dict(d) for d in _DETECTED]\n"
    "\n"
    "def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30, auth=None):\n"
    "    _log('check_connection', provider=provider, model=model, base_url=base_url,\n"
    "         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)\n"
    "    if provider not in PROVIDERS:\n"
    "        raise ValueError('unknown provider')\n"
    "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
    "        raise ValueError('base_url required')\n"
    "    return {'ok': True, 'error': None}\n"
    "\n"
    "def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None, auth=None):\n"
    "    _log('save_config', config_path=str(config_path), provider=provider, model=model,\n"
    "         base_url=base_url, api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)\n"
    "    if provider not in PROVIDERS or not model:\n"
    "        raise ValueError('invalid')\n"
    "    p = Path(config_path)\n"
    "    p.parent.mkdir(parents=True, exist_ok=True)\n"
    "    lines = ['[llm]']\n"
    "    vals = {'provider': provider, 'model': model, 'base_url': base_url,\n"
    "            'api_key_env': api_key_env, 'timeout_seconds': timeout_seconds, 'auth': auth}\n"
    "    for k in _KEYS:\n"
    "        if vals[k] is not None:\n"
    "            lines.append(k + ' = ' + json.dumps(vals[k]))\n"
    "    p.write_text('\\n'.join(lines) + '\\n', encoding='utf-8')\n"
    "\n"
    "def load_config(config_path=None):\n"
    "    _log('load_config', config_path=None if config_path is None else str(config_path))\n"
    "    import tomllib\n"
    "    p = Path(config_path) if config_path is not None else Path.cwd() / 'hotdocs.toml'\n"
    "    if not p.is_file():\n"
    "        return None\n"
    "    data = tomllib.loads(p.read_text(encoding='utf-8'))\n"
    "    llm = data.get('llm')\n"
    "    if llm is None:\n"
    "        return None\n"
    "    return {k: llm.get(k) for k in _KEYS}\n"
)


def make_tool_root(tmp_path, listing, providers=None, with_endpoint=True):
    tool_root = tmp_path / "tool"
    tool_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir(exist_ok=True)
    log = log_dir / "calls.jsonl"
    if with_endpoint:
        ep = tool_root / "gen" / "llm-endpoint"
        ep.mkdir(parents=True)
        source = (
            "LOG = " + repr(str(log)) + "\n"
            + "PROVIDERS = " + repr(providers if providers is not None else BASE_PROVIDERS) + "\n"
            + "_DETECTED = " + repr(listing) + "\n"
            + FAKE_BODY
        )
        (ep / "llm_endpoint.py").write_text(source, encoding="utf-8")
    else:
        (tool_root / "gen" / "other-thing").mkdir(parents=True)
        (tool_root / "gen" / "other-thing" / "other_thing.py").write_text("X = 1\n", encoding="utf-8")
    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n", encoding="utf-8")
    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    (tool_root / "pyproject.toml").write_text(
        '[project]\nname = "hotdocs"\nversion = "9.8.7a1"\n', encoding="utf-8"
    )
    return tool_root, log


def read_log(log, fn):
    if not log.is_file():
        return []
    out = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            if entry["fn"] == fn:
                out.append(entry["args"])
    return out


def make_project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    return proj


def empty_bin(tmp_path):
    b = tmp_path / "emptybin"
    b.mkdir(exist_ok=True)
    return b


class Recorder:
    def __init__(self, answers):
        self.answers = list(answers)
        self.questions = []
        self.outputs = []

    def input_fn(self, prompt=""):
        self.questions.append(prompt)
        if self.answers:
            return self.answers.pop(0)
        return ""

    def output_fn(self, *args, **kwargs):
        self.outputs.append(" ".join(str(a) for a in args))

    def output_text(self):
        return "\n".join(self.outputs)


def do_run(argv, tool_root, rec, env, cwd):
    return hotdocs_init.run(
        argv,
        tool_root=tool_root,
        input_fn=rec.input_fn,
        output_fn=rec.output_fn,
        env=env,
        cwd=cwd,
    )


def test_interactive_all_defaults_asks_provider_model_key(tmp_path):
    tool_root, log = make_tool_root(tmp_path, OLLAMA_OPENAI_LISTING)
    proj = make_project(tmp_path)
    rec = Recorder([])
    env = {"PATH": str(empty_bin(tmp_path))}
    do_run([str(proj)], tool_root, rec, env, proj)

    qs = rec.questions
    assert len(qs) == 3, qs
    assert "provider" in qs[0].lower()
    assert "model" in qs[1].lower()
    assert "key" in qs[2].lower()
    for q in qs:
        assert "url" not in q.lower()
        assert q.endswith(" ")

    text = rec.output_text()
    assert "ollama" in text
    assert "openai" in text

    saves = read_log(log, "save_config")
    assert len(saves) == 1
    s = saves[0]
    assert s["provider"] == "openai"
    assert s["model"] == "gpt-x"
    assert s["api_key_env"] == "OPENAI_API_KEY"


def test_unrecognised_provider_is_asked_again_and_number_selects(tmp_path):
    tool_root, log = make_tool_root(tmp_path, OLLAMA_OPENAI_LISTING)
    proj = make_project(tmp_path)
    rec = Recorder(["bogus", "2"])
    env = {"PATH": str(empty_bin(tmp_path))}
    do_run([str(proj)], tool_root, rec, env, proj)

    qs = rec.questions
    assert len(qs) == 4, qs
    assert "provider" in qs[0].lower()
    assert "provider" in qs[1].lower()
    assert "model" in qs[2].lower()

    saves = read_log(log, "save_config")
    assert len(saves) == 1
    assert saves[0]["provider"] == "openai"
    assert saves[0]["model"] == "gpt-x"


def test_openai_compatible_reasks_model_and_base_url(tmp_path):
    listing = [
        {
            "provider": OPENAI_COMPAT,
            "available": True,
            "reason": "configurable",
            "suggested_model": "",
            "api_key_env": None,
        }
    ]
    tool_root, log = make_tool_root(tmp_path, listing)
    proj = make_project(tmp_path)
    rec = Recorder(["1", "", "m", "", "http://h/v1", ""])
    env = {"PATH": str(empty_bin(tmp_path))}
    do_run([str(proj)], tool_root, rec, env, proj)

    qs = rec.questions
    assert len(qs) == 6, qs
    assert qs[1] == qs[2]
    assert qs[3] == qs[4]
    assert "model" in qs[1].lower()
    assert "url" in qs[3].lower()

    saves = read_log(log, "save_config")
    assert len(saves) == 1
    s = saves[0]
    assert s["provider"] == OPENAI_COMPAT
    assert s["model"] == "m"
    assert s["base_url"] == "http://h/v1"
    assert s["api_key_env"] is None


def test_claude_cli_asks_no_base_url_or_key_and_returns_0(tmp_path):
    listing = [
        {
            "provider": "claude-cli",
            "available": True,
            "reason": "claude found",
            "suggested_model": "claude-sonnet-5",
            "api_key_env": None,
        }
    ]
    tool_root, log = make_tool_root(tmp_path, listing)
    proj = make_project(tmp_path)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    claude = bindir / "claude"
    claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | stat.S_IRUSR)
    env = {"PATH": str(bindir)}
    rec = Recorder([])
    code = do_run([str(proj)], tool_root, rec, env, proj)

    qs = rec.questions
    assert len(qs) == 2, qs
    for q in qs:
        assert "url" not in q.lower()
        assert "key" not in q.lower()
    assert code == 0

    saves = read_log(log, "save_config")
    assert len(saves) == 1
    assert saves[0]["provider"] == "claude-cli"


def test_missing_llm_endpoint_reports_and_carries_on(tmp_path):
    tool_root, log = make_tool_root(tmp_path, [], with_endpoint=False)
    proj = make_project(tmp_path)
    rec = Recorder([])
    env = {"PATH": str(empty_bin(tmp_path))}
    code = do_run([str(proj), "--yes"], tool_root, rec, env, proj)

    lines = []
    for o in rec.outputs:
        lines.extend(l.strip() for l in o.splitlines())
    assert "provider not configured: gen/llm-endpoint is missing" in lines
    assert code == 0
    assert not (proj / "hotdocs.toml").exists()


def test_existing_hotdocs_toml_is_kept(tmp_path):
    tool_root, log = make_tool_root(tmp_path, OLLAMA_OPENAI_LISTING)
    proj = make_project(tmp_path)
    original = b'[llm]\nprovider = "openai"\nmodel = "gpt-x"\n'
    (proj / "hotdocs.toml").write_bytes(original)
    rec = Recorder([])
    env = {"PATH": str(empty_bin(tmp_path))}
    do_run([str(proj)], tool_root, rec, env, proj)

    assert read_log(log, "save_config") == []
    assert (proj / "hotdocs.toml").read_bytes() == original
    assert "hotdocs.toml" in rec.output_text()
    for q in rec.questions:
        assert "provider" not in q.lower()