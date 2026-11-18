# hotdocs-criterion: sha256:f49ade56ab76640497e72a4ee51035987936c6a158c1203d71870bb848be6b9a
import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def fake_llm_endpoint_source(log_path, check_mode, save_mode):
    lines = [
        "import json",
        "from pathlib import Path",
        "",
        "LOG_PATH = " + repr(str(log_path)),
        "CHECK_MODE = " + repr(check_mode),
        "SAVE_MODE = " + repr(save_mode),
        "PROVIDERS = " + repr(PROVIDERS),
        "",
        "",
        "def _log(fn, data):",
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps({'fn': fn, 'args': data}, default=str) + '\\n')",
        "",
        "",
        "def detect_providers(env=None, probe_ollama=True):",
        "    _log('detect_providers', {'env_given': env is not None, 'probe_ollama': probe_ollama})",
        "    out = []",
        "    for name, info in PROVIDERS.items():",
        "        out.append({",
        "            'provider': name,",
        "            'available': name == 'openai',",
        "            'reason': 'fake',",
        "            'suggested_model': info['suggested_model'],",
        "            'api_key_env': info['default_api_key_env'],",
        "        })",
        "    return out",
        "",
        "",
        "def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30, auth=None):",
        "    _log('check_connection', {'provider': provider, 'model': model, 'base_url': base_url,",
        "         'api_key_env': api_key_env, 'timeout_seconds': timeout_seconds, 'auth': auth})",
        "    if CHECK_MODE == 'raise':",
        "        raise ValueError('no base_url')",
        "    if CHECK_MODE == 'fail_auth':",
        "        return {'ok': False, 'error': {'category': 'auth', 'message': 'bad'}}",
        "    return {'ok': True, 'error': None}",
        "",
        "",
        "def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None, auth=None):",
        "    _log('save_config', {'config_path': str(config_path), 'provider': provider, 'model': model,",
        "         'base_url': base_url, 'api_key_env': api_key_env, 'timeout_seconds': timeout_seconds, 'auth': auth})",
        "    if SAVE_MODE == 'raise':",
        "        raise ValueError('nope')",
        "    p = Path(config_path)",
        "    p.parent.mkdir(parents=True, exist_ok=True)",
        "    out = ['[llm]']",
        "    for key, val in (('provider', provider), ('model', model), ('base_url', base_url),",
        "                     ('api_key_env', api_key_env), ('timeout_seconds', timeout_seconds), ('auth', auth)):",
        "        if val is not None:",
        "            out.append(key + ' = ' + json.dumps(val))",
        "    p.write_text('\\n'.join(out) + '\\n', encoding='utf-8')",
        "",
        "",
        "def load_config(config_path=None):",
        "    _log('load_config', {'config_path': None if config_path is None else str(config_path)})",
        "    if config_path is None:",
        "        return None",
        "    p = Path(config_path)",
        "    if not p.is_file():",
        "        return None",
        "    text = p.read_text(encoding='utf-8')",
        "    if '[llm]' not in text:",
        "        return None",
        "    result = {'provider': None, 'model': None, 'base_url': None,",
        "              'api_key_env': None, 'timeout_seconds': None, 'auth': None}",
        "    in_llm = False",
        "    for line in text.splitlines():",
        "        s = line.strip()",
        "        if s.startswith('['):",
        "            in_llm = s == '[llm]'",
        "            continue",
        "        if in_llm and ' = ' in s:",
        "            k, v = s.split(' = ', 1)",
        "            if k in result:",
        "                result[k] = json.loads(v)",
        "    return result",
        "",
    ]
    return "\n".join(lines)


def make_tool_root(base, log_path, check_mode, save_mode):
    tool = base / "tool"
    mod_dir = tool / "gen" / "llm-endpoint"
    mod_dir.mkdir(parents=True)
    (mod_dir / "llm_endpoint.py").write_text(
        fake_llm_endpoint_source(log_path, check_mode, save_mode), encoding="utf-8"
    )
    ex = tool / "examples" / "slugify" / "specs" / "product"
    ex.mkdir(parents=True)
    (ex / "slugs.md").write_text("# Slugs\n\nTurn titles into slugs.\n", encoding="utf-8")
    (tool / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    return tool


def read_log(log_path, fn=None):
    if not log_path.is_file():
        return []
    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    if fn is None:
        return entries
    return [e["args"] for e in entries if e["fn"] == fn]


def run_init(base, flags, check_mode="ok", save_mode="ok", save_answer=None):
    base.mkdir(parents=True)
    project = base / "project"
    project.mkdir()
    logs = base / "logs"
    logs.mkdir()
    log_path = logs / "calls.jsonl"
    tool = make_tool_root(base, log_path, check_mode, save_mode)

    prompts = []
    outputs = []
    counts = {"provider": 0, "model": 0}

    def input_fn(prompt=""):
        prompts.append(prompt)
        if len(prompts) > 50:
            raise AssertionError("too many questions: " + repr(prompts[-5:]))
        if prompt.startswith("Save anyway?"):
            return save_answer if save_answer is not None else "n"
        low = prompt.lower()
        if "provider" in low:
            counts["provider"] += 1
            return "openai" if counts["provider"] == 1 else ""
        if "model" in low:
            counts["model"] += 1
            return "m" if counts["model"] == 1 else ""
        return ""

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    env = {"PATH": os.environ.get("PATH", "")}
    code = hotdocs_init.main(
        [str(project)] + list(flags),
        tool_root=tool,
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=project,
    )
    return {
        "code": code,
        "project": project,
        "log": log_path,
        "prompts": prompts,
        "text": "\n".join(outputs),
    }


def same_path(a, b):
    return Path(a).resolve() == Path(b).resolve()


def test_connection_ok_saves_with_only_given_keywords_and_asks_nothing(tmp_path):
    r = run_init(
        tmp_path / "run",
        ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
    )
    assert "connection ok" in r["text"]
    assert r["prompts"] == []
    assert len(read_log(r["log"], "check_connection")) == 1
    saves = read_log(r["log"], "save_config")
    assert len(saves) == 1
    s = saves[0]
    assert same_path(s["config_path"], r["project"] / "hotdocs.toml")
    assert s["provider"] == "openai"
    assert s["model"] == "m"
    assert s["api_key_env"] == "MY_KEY"
    assert s["base_url"] is None
    assert s["timeout_seconds"] is None
    assert s["auth"] is None


def test_failed_connection_interactive_save_anyway_n_then_y(tmp_path):
    r1 = run_init(tmp_path / "run_n", [], check_mode="fail_auth", save_answer="n")
    assert "connection failed: auth: bad" in r1["text"]
    assert "Save anyway? [y/N] " in r1["prompts"]
    assert read_log(r1["log"], "save_config") == []
    assert not (r1["project"] / "hotdocs.toml").exists()

    r2 = run_init(tmp_path / "run_y", [], check_mode="fail_auth", save_answer="y")
    assert "connection failed: auth: bad" in r2["text"]
    assert "Save anyway? [y/N] " in r2["prompts"]
    saves = read_log(r2["log"], "save_config")
    assert len(saves) == 1
    assert same_path(saves[0]["config_path"], r2["project"] / "hotdocs.toml")


def test_value_error_from_check_connection_printed_as_invalid(tmp_path):
    r = run_init(
        tmp_path / "run",
        ["--provider", "openai", "--model", "m"],
        check_mode="raise",
    )
    assert "connection failed: invalid: no base_url" in r["text"]


def test_save_config_value_error_goes_to_stderr_and_does_not_change_exit_code(tmp_path, capsys):
    flags = ["--provider", "openai", "--model", "m"]
    baseline = run_init(tmp_path / "baseline", flags)
    capsys.readouterr()

    r = run_init(tmp_path / "failing", flags, save_mode="raise")
    captured = capsys.readouterr()
    assert "could not save: nope" in captured.err
    assert len(read_log(r["log"], "save_config")) == 1
    assert not (r["project"] / "hotdocs.toml").exists()
    assert r["code"] == baseline["code"]


def test_no_test_never_calls_check_connection(tmp_path):
    r = run_init(
        tmp_path / "run",
        ["--provider", "openai", "--model", "m", "--no-test"],
    )
    assert read_log(r["log"], "check_connection") == []


def test_auth_reaches_check_connection_and_save_config(tmp_path):
    r = run_init(
        tmp_path / "run",
        ["--provider", "claude-cli", "--model", "m", "--auth", "login", "--yes"],
    )
    checks = read_log(r["log"], "check_connection")
    assert len(checks) == 1
    assert checks[0]["auth"] == "login"
    assert checks[0]["provider"] == "claude-cli"
    assert checks[0]["model"] == "m"
    saves = read_log(r["log"], "save_config")
    assert len(saves) == 1
    s = saves[0]
    assert same_path(s["config_path"], r["project"] / "hotdocs.toml")
    assert s["provider"] == "claude-cli"
    assert s["model"] == "m"
    assert s["auth"] == "login"
    assert s["base_url"] is None
    assert s["api_key_env"] is None
    assert s["timeout_seconds"] is None