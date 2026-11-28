# hotdocs-criterion: sha256:ff06207e02aa64a4566ec68b13a081f063bbee5ffb65de2e16ae1db4ecf10d04
import importlib.metadata
import json
import os
import sys
from pathlib import Path

import hotdocs_init


FAKE_BODY = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "_UNSET = object()\n"
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
    "    'ollama': {'default_base_url': 'http://localhost:11434',\n"
    "               'default_api_key_env': None,\n"
    "               'needs_base_url': False, 'suggested_model': 'llama3.2'},\n"
    "}\n"
    "\n"
    "\n"
    "def _log(entry):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "\n"
    "def _behavior():\n"
    "    try:\n"
    "        return json.loads(Path(BEHAVIOR_PATH).read_text(encoding='utf-8'))\n"
    "    except Exception:\n"
    "        return {}\n"
    "\n"
    "\n"
    "def _passed(**kw):\n"
    "    passed = {}\n"
    "    for k, v in kw.items():\n"
    "        if v is not _UNSET:\n"
    "            passed[k] = v\n"
    "    return passed\n"
    "\n"
    "\n"
    "def detect_providers(env=None, probe_ollama=True):\n"
    "    _log({'name': 'detect_providers'})\n"
    "    out = []\n"
    "    for name, info in PROVIDERS.items():\n"
    "        avail = name == 'openai'\n"
    "        out.append({'provider': name, 'available': avail,\n"
    "                    'reason': 'fake ' + ('available' if avail else 'unavailable'),\n"
    "                    'suggested_model': info['suggested_model'],\n"
    "                    'api_key_env': info['default_api_key_env']})\n"
    "    return out\n"
    "\n"
    "\n"
    "def check_connection(provider, model, base_url=_UNSET, api_key_env=_UNSET,\n"
    "                     timeout_seconds=_UNSET, auth=_UNSET):\n"
    "    passed = _passed(base_url=base_url, api_key_env=api_key_env,\n"
    "                     timeout_seconds=timeout_seconds, auth=auth)\n"
    "    _log({'name': 'check_connection', 'provider': provider, 'model': model,\n"
    "          'passed': sorted(passed), 'values': passed})\n"
    "    mode = _behavior().get('check', 'ok')\n"
    "    if mode == 'raise':\n"
    "        raise ValueError(_behavior().get('check_message', 'no base_url'))\n"
    "    if mode == 'fail':\n"
    "        return {'ok': False, 'error': {'category': 'auth', 'message': 'bad'}}\n"
    "    return {'ok': True, 'error': None}\n"
    "\n"
    "\n"
    "def save_config(config_path, provider, model, base_url=_UNSET, api_key_env=_UNSET,\n"
    "                timeout_seconds=_UNSET, auth=_UNSET):\n"
    "    passed = _passed(base_url=base_url, api_key_env=api_key_env,\n"
    "                     timeout_seconds=timeout_seconds, auth=auth)\n"
    "    _log({'name': 'save_config', 'config_path': str(config_path),\n"
    "          'provider': provider, 'model': model,\n"
    "          'passed': sorted(passed), 'values': passed})\n"
    "    if _behavior().get('save', 'ok') == 'raise':\n"
    "        raise ValueError('nope')\n"
    "    path = Path(config_path)\n"
    "    path.parent.mkdir(parents=True, exist_ok=True)\n"
    "    kept = []\n"
    "    if path.is_file():\n"
    "        in_llm = False\n"
    "        for line in path.read_text(encoding='utf-8').splitlines():\n"
    "            s = line.strip()\n"
    "            if s.startswith('['):\n"
    "                in_llm = s == '[llm]'\n"
    "            if not in_llm:\n"
    "                kept.append(line)\n"
    "    lines = ['[llm]', 'provider = ' + json.dumps(provider), 'model = ' + json.dumps(model)]\n"
    "    for k in ('base_url', 'api_key_env', 'auth'):\n"
    "        v = passed.get(k)\n"
    "        if v is not None:\n"
    "            lines.append(k + ' = ' + json.dumps(v))\n"
    "    v = passed.get('timeout_seconds')\n"
    "    if v is not None:\n"
    "        lines.append('timeout_seconds = ' + str(int(v)))\n"
    "    text = '\\n'.join(kept).strip()\n"
    "    text = (text + '\\n\\n' if text else '') + '\\n'.join(lines) + '\\n'\n"
    "    path.write_text(text, encoding='utf-8')\n"
    "\n"
    "\n"
    "def load_config(config_path=None):\n"
    "    import tomllib\n"
    "    _log({'name': 'load_config', 'config_path': None if config_path is None else str(config_path)})\n"
    "    path = Path('hotdocs.toml') if config_path is None else Path(config_path)\n"
    "    if not path.is_file():\n"
    "        return None\n"
    "    try:\n"
    "        data = tomllib.loads(path.read_text(encoding='utf-8'))\n"
    "    except Exception as exc:\n"
    "        raise ValueError('invalid config: ' + str(exc))\n"
    "    llm = data.get('llm')\n"
    "    if llm is None:\n"
    "        return None\n"
    "    return {'provider': llm.get('provider'), 'model': llm.get('model'),\n"
    "            'base_url': llm.get('base_url'), 'api_key_env': llm.get('api_key_env'),\n"
    "            'timeout_seconds': llm.get('timeout_seconds'), 'auth': llm.get('auth')}\n"
)


def _make_tool_root(tool, log_path, behavior_path):
    llm_dir = tool / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    src = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        + "BEHAVIOR_PATH = " + repr(str(behavior_path)) + "\n"
        + FAKE_BODY
    )
    (llm_dir / "llm_endpoint.py").write_text(src, encoding="utf-8")
    slugs = tool / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nTurn text into slugs.\n", encoding="utf-8")
    (tool / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    (tool / "pyproject.toml").write_text(
        "[project]\nname = \"hotdocs\"\nversion = \"9.8.7a1\"\n", encoding="utf-8"
    )
    return tool


def _read_log(log_path):
    if not log_path.is_file():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _calls(log, name):
    return [e for e in log if e.get("name") == name]


def _same_path(a, b):
    return Path(a).resolve() == Path(b).resolve()


def _run(tmp_path, capsys, name, extra_args, behavior, save_answer=None):
    base = tmp_path / name
    project = base / "project"
    project.mkdir(parents=True)
    log_path = base / "calls.jsonl"
    behavior_path = base / "behavior.json"
    behavior_path.write_text(json.dumps(behavior), encoding="utf-8")
    tool = _make_tool_root(base / "tool", log_path, behavior_path)

    prompts = []
    outputs = []

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        prompts.append(prompt)
        if len(prompts) > 60:
            raise RuntimeError("too many questions asked")
        low = str(prompt).lower()
        if "save anyway" in low:
            return save_answer if save_answer is not None else ""
        repeated = prompts.count(prompt) > 1
        if repeated:
            return ""
        if "provider" in low:
            return "openai"
        if "model" in low:
            return "m"
        return ""

    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(base / "home")}
    sys.modules.pop("llm_endpoint", None)
    capsys.readouterr()
    code = hotdocs_init.run(
        [str(project)] + list(extra_args),
        tool_root=tool,
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=project,
    )
    captured = capsys.readouterr()
    return {
        "code": code,
        "project": project,
        "log": _read_log(log_path),
        "prompts": prompts,
        "out": "\n".join(outputs) + "\n" + captured.out,
        "err": captured.err,
    }


def test_connection_ok_saves_with_only_given_keywords_and_asks_nothing(tmp_path, capsys):
    r = _run(tmp_path, capsys, "ok",
             ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
             {"check": "ok", "save": "ok"})
    assert "connection ok" in r["out"]
    assert r["prompts"] == []
    assert len(_calls(r["log"], "check_connection")) == 1
    saves = _calls(r["log"], "save_config")
    assert len(saves) == 1
    s = saves[0]
    assert _same_path(s["config_path"], r["project"] / "hotdocs.toml")
    assert s["provider"] == "openai"
    assert s["model"] == "m"
    assert s["values"].get("api_key_env") == "MY_KEY"
    assert "base_url" not in s["passed"]
    assert "timeout_seconds" not in s["passed"]


def test_interactive_failure_asks_save_anyway_n_then_y(tmp_path, capsys):
    r1 = _run(tmp_path, capsys, "first", [], {"check": "fail", "save": "ok"}, save_answer="n")
    assert "connection failed: auth: bad" in r1["out"]
    assert "Save anyway? [y/N] " in r1["prompts"]
    assert _calls(r1["log"], "save_config") == []
    assert not (r1["project"] / "hotdocs.toml").exists()

    r2 = _run(tmp_path, capsys, "second", [], {"check": "fail", "save": "ok"}, save_answer="y")
    assert "connection failed: auth: bad" in r2["out"]
    assert "Save anyway? [y/N] " in r2["prompts"]
    saves = _calls(r2["log"], "save_config")
    assert len(saves) == 1
    assert _same_path(saves[0]["config_path"], r2["project"] / "hotdocs.toml")


def test_value_error_from_check_connection_is_reported_as_invalid(tmp_path, capsys):
    r = _run(tmp_path, capsys, "raise",
             ["--provider", "openai", "--model", "m"],
             {"check": "raise", "check_message": "no base_url", "save": "ok"})
    assert len(_calls(r["log"], "check_connection")) == 1
    assert "connection failed: invalid: no base_url" in r["out"]


def test_save_config_value_error_goes_to_stderr_and_does_not_change_exit_code(tmp_path, capsys):
    bad = _run(tmp_path, capsys, "badsave",
               ["--provider", "openai", "--model", "m"],
               {"check": "ok", "save": "raise"})
    assert "could not save: nope" in bad["err"]
    assert len(_calls(bad["log"], "save_config")) == 1
    assert not (bad["project"] / "hotdocs.toml").exists()

    good = _run(tmp_path, capsys, "goodsave",
                ["--provider", "openai", "--model", "m"],
                {"check": "ok", "save": "ok"})
    assert len(_calls(good["log"], "save_config")) == 1
    assert "could not save" not in good["err"]
    assert bad["code"] == good["code"]


def test_no_test_never_calls_check_connection(tmp_path, capsys):
    r = _run(tmp_path, capsys, "notest",
             ["--provider", "openai", "--model", "m", "--no-test"],
             {"check": "ok", "save": "ok"})
    assert _calls(r["log"], "check_connection") == []


def test_auth_reaches_check_connection_and_save_config(tmp_path, capsys):
    r = _run(tmp_path, capsys, "auth",
             ["--provider", "claude-cli", "--model", "m", "--auth", "login", "--yes"],
             {"check": "ok", "save": "ok"})
    checks = _calls(r["log"], "check_connection")
    assert len(checks) == 1
    assert checks[0]["values"].get("auth") == "login"
    saves = _calls(r["log"], "save_config")
    assert len(saves) == 1
    s = saves[0]
    assert _same_path(s["config_path"], r["project"] / "hotdocs.toml")
    assert s["provider"] == "claude-cli"
    assert s["model"] == "m"
    assert s["passed"] == ["auth"]
    assert s["values"]["auth"] == "login"