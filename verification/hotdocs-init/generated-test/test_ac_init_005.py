# hotdocs-criterion: sha256:324f5334cface524f07c3c8ca44fe4b508274a82073d8c3da5652fa691d048b0
import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


PROVIDERS_DATA = {
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


def build_fake_source(log_path, check_mode, check_result, save_raises):
    src = ""
    src += "import json\n"
    src += "from pathlib import Path\n"
    src += "\n"
    src += "LOG = " + repr(str(log_path)) + "\n"
    src += "CHECK_MODE = " + repr(check_mode) + "\n"
    src += "CHECK_RESULT = " + repr(check_result) + "\n"
    src += "SAVE_RAISES = " + repr(save_raises) + "\n"
    src += "PROVIDERS = " + repr(PROVIDERS_DATA) + "\n"
    src += "\n"
    src += "def _log(entry):\n"
    src += "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    src += "        fh.write(json.dumps(entry) + '\\n')\n"
    src += "\n"
    src += "def detect_providers(env=None, probe_ollama=True):\n"
    src += "    _log({'fn': 'detect_providers', 'probe_ollama': probe_ollama})\n"
    src += "    out = []\n"
    src += "    for name, info in PROVIDERS.items():\n"
    src += "        avail = name == 'openai'\n"
    src += "        out.append({\n"
    src += "            'provider': name,\n"
    src += "            'available': avail,\n"
    src += "            'reason': 'fake available' if avail else 'fake unavailable',\n"
    src += "            'suggested_model': info['suggested_model'],\n"
    src += "            'api_key_env': info['default_api_key_env'],\n"
    src += "        })\n"
    src += "    return out\n"
    src += "\n"
    src += "def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30, auth=None):\n"
    src += "    _log({'fn': 'check_connection', 'provider': provider, 'model': model, 'base_url': base_url, 'api_key_env': api_key_env, 'timeout_seconds': timeout_seconds, 'auth': auth})\n"
    src += "    if CHECK_MODE == 'raise':\n"
    src += "        raise ValueError('no base_url')\n"
    src += "    return dict(CHECK_RESULT)\n"
    src += "\n"
    src += "def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None, auth=None):\n"
    src += "    _log({'fn': 'save_config', 'config_path': str(config_path), 'provider': provider, 'model': model, 'base_url': base_url, 'api_key_env': api_key_env, 'timeout_seconds': timeout_seconds, 'auth': auth})\n"
    src += "    if SAVE_RAISES:\n"
    src += "        raise ValueError('nope')\n"
    src += "    p = Path(config_path)\n"
    src += "    p.parent.mkdir(parents=True, exist_ok=True)\n"
    src += "    lines = ['[llm]', 'provider = ' + json.dumps(provider), 'model = ' + json.dumps(model)]\n"
    src += "    if base_url is not None:\n"
    src += "        lines.append('base_url = ' + json.dumps(base_url))\n"
    src += "    if api_key_env is not None:\n"
    src += "        lines.append('api_key_env = ' + json.dumps(api_key_env))\n"
    src += "    if timeout_seconds is not None:\n"
    src += "        lines.append('timeout_seconds = ' + str(int(timeout_seconds)))\n"
    src += "    if auth is not None:\n"
    src += "        lines.append('auth = ' + json.dumps(auth))\n"
    src += "    p.write_text('\\n'.join(lines) + '\\n', encoding='utf-8')\n"
    src += "\n"
    src += "def load_config(config_path=None):\n"
    src += "    _log({'fn': 'load_config', 'config_path': None if config_path is None else str(config_path)})\n"
    src += "    if config_path is None:\n"
    src += "        return None\n"
    src += "    p = Path(config_path)\n"
    src += "    if not p.is_file():\n"
    src += "        return None\n"
    src += "    text = p.read_text(encoding='utf-8')\n"
    src += "    if '[llm]' not in text:\n"
    src += "        return None\n"
    src += "    result = {'provider': None, 'model': None, 'base_url': None, 'api_key_env': None, 'timeout_seconds': None, 'auth': None}\n"
    src += "    in_llm = False\n"
    src += "    for line in text.splitlines():\n"
    src += "        s = line.strip()\n"
    src += "        if s.startswith('['):\n"
    src += "            in_llm = s == '[llm]'\n"
    src += "            continue\n"
    src += "        if in_llm and '=' in s:\n"
    src += "            k, v = s.split('=', 1)\n"
    src += "            k = k.strip()\n"
    src += "            v = v.strip()\n"
    src += "            if k in result:\n"
    src += "                result[k] = json.loads(v)\n"
    src += "    return result\n"
    return src


def make_env(tmp_path, name, check_mode="ok", check_result=None, save_raises=False):
    base = tmp_path / name
    tool_root = base / "tool"
    project = base / "proj"
    log_path = base / "calls.log"
    project.mkdir(parents=True)
    fake_dir = tool_root / "gen" / "llm-endpoint"
    fake_dir.mkdir(parents=True)
    if check_result is None:
        check_result = {"ok": True, "error": None}
    (fake_dir / "llm_endpoint.py").write_text(
        build_fake_source(log_path, check_mode, check_result, save_raises),
        encoding="utf-8",
    )
    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nA fake example product spec.\n", encoding="utf-8")
    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    return tool_root, project, log_path


def read_log(log_path):
    if not Path(log_path).is_file():
        return []
    entries = []
    for line in Path(log_path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def calls(log_path, fn):
    return [e for e in read_log(log_path) if e["fn"] == fn]


class Asker:
    def __init__(self, save_answer=""):
        self.questions = []
        self.save_answer = save_answer

    def __call__(self, prompt=""):
        self.questions.append(prompt)
        if len(self.questions) > 100:
            raise EOFError("too many questions")
        if "Save anyway?" in str(prompt):
            return self.save_answer
        return ""


def run(argv, tool_root, project, input_fn=None):
    out = []

    def output_fn(*args, **kwargs):
        out.append(" ".join(str(a) for a in args))

    if input_fn is None:
        input_fn = Asker()
    code = hotdocs_init.main(
        argv,
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env={"PATH": os.environ.get("PATH", "")},
        cwd=str(project),
    )
    return code, "\n".join(out)


def same_path(a, b):
    return Path(a).resolve() == Path(b).resolve()


def test_connection_ok_saves_with_only_given_keywords_and_asks_nothing(tmp_path, capsys):
    tool_root, project, log_path = make_env(tmp_path, "ok")
    asker = Asker()
    code, out = run(
        [str(project), "--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        tool_root, project, asker,
    )
    captured = capsys.readouterr()
    assert "connection ok" in out + "\n" + captured.out + "\n" + captured.err
    assert asker.questions == []
    saves = calls(log_path, "save_config")
    assert len(saves) == 1
    s = saves[0]
    assert same_path(s["config_path"], project / "hotdocs.toml")
    assert s["provider"] == "openai"
    assert s["model"] == "m"
    assert s["api_key_env"] == "MY_KEY"
    assert s["base_url"] is None
    assert s["timeout_seconds"] is None
    assert s["auth"] is None
    assert len(calls(log_path, "check_connection")) == 1


def test_connection_failed_interactive_n_then_y(tmp_path, capsys):
    failure = {"ok": False, "error": {"category": "auth", "message": "bad"}}

    tool_root1, project1, log1 = make_env(tmp_path, "run_n", check_result=failure)
    asker1 = Asker(save_answer="n")
    code1, out1 = run([str(project1)], tool_root1, project1, asker1)
    captured1 = capsys.readouterr()
    text1 = out1 + "\n" + captured1.out + "\n" + captured1.err
    assert "connection failed: auth: bad" in text1
    assert "Save anyway? [y/N] " in asker1.questions
    assert len(calls(log1, "check_connection")) >= 1
    assert calls(log1, "save_config") == []

    tool_root2, project2, log2 = make_env(tmp_path, "run_y", check_result=failure)
    asker2 = Asker(save_answer="y")
    code2, out2 = run([str(project2)], tool_root2, project2, asker2)
    captured2 = capsys.readouterr()
    text2 = out2 + "\n" + captured2.out + "\n" + captured2.err
    assert "connection failed: auth: bad" in text2
    assert "Save anyway? [y/N] " in asker2.questions
    saves = calls(log2, "save_config")
    assert len(saves) == 1
    assert same_path(saves[0]["config_path"], project2 / "hotdocs.toml")


def test_check_connection_value_error_printed_as_invalid(tmp_path, capsys):
    tool_root, project, log_path = make_env(tmp_path, "raise", check_mode="raise")
    code, out = run(
        [str(project), "--provider", "openai", "--model", "m"],
        tool_root, project,
    )
    captured = capsys.readouterr()
    text = out + "\n" + captured.out + "\n" + captured.err
    assert "connection failed: invalid: no base_url" in text
    assert len(calls(log_path, "check_connection")) == 1


def test_save_value_error_goes_to_stderr_and_does_not_change_exit_code(tmp_path, capsys):
    argv_tail = ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"]

    tool_root0, project0, log0 = make_env(tmp_path, "baseline")
    base_code, _ = run([str(project0)] + argv_tail, tool_root0, project0)
    capsys.readouterr()
    assert len(calls(log0, "save_config")) == 1

    tool_root, project, log_path = make_env(tmp_path, "saveerr", save_raises=True)
    code, out = run([str(project)] + argv_tail, tool_root, project)
    captured = capsys.readouterr()
    assert "could not save: nope" in captured.err
    assert len(calls(log_path, "save_config")) == 1
    assert not (project / "hotdocs.toml").exists()
    assert isinstance(code, int)
    assert code == base_code


def test_no_test_never_calls_check_connection(tmp_path, capsys):
    tool_root, project, log_path = make_env(tmp_path, "notest")
    code, out = run(
        [str(project), "--provider", "openai", "--model", "m", "--no-test"],
        tool_root, project,
    )
    capsys.readouterr()
    assert calls(log_path, "check_connection") == []


def test_auth_reaches_check_connection_and_save(tmp_path, capsys):
    tool_root, project, log_path = make_env(tmp_path, "auth")
    asker = Asker()
    code, out = run(
        [str(project), "--provider", "claude-cli", "--model", "m", "--auth", "login", "--yes"],
        tool_root, project, asker,
    )
    capsys.readouterr()
    checks = calls(log_path, "check_connection")
    assert len(checks) == 1
    assert checks[0]["auth"] == "login"
    assert checks[0]["provider"] == "claude-cli"
    assert checks[0]["model"] == "m"
    saves = calls(log_path, "save_config")
    assert len(saves) == 1
    s = saves[0]
    assert same_path(s["config_path"], project / "hotdocs.toml")
    assert s["provider"] == "claude-cli"
    assert s["model"] == "m"
    assert s["auth"] == "login"
    assert s["base_url"] is None
    assert s["api_key_env"] is None
    assert s["timeout_seconds"] is None