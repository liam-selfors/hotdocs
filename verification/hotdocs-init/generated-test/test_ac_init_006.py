# hotdocs-criterion: sha256:e4ebd78d4b94c69124d4da6c48c066fc43d62dc3a3668af400713aebee598cca
import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


SLUGS_EXAMPLE_TEXT = "# Slugs\n\nExample product spec for slugify.\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_ENDPOINT_BODY = (
    "import json\n"
    "import tomllib\n"
    "from pathlib import Path\n"
    "\n"
    "PROVIDERS = {\n"
    "    'claude-cli': {'default_base_url': None, 'default_api_key_env': None, 'needs_base_url': False, 'suggested_model': 'claude-sonnet-5'},\n"
    "    'anthropic': {'default_base_url': 'https://api.anthropic.com', 'default_api_key_env': 'ANTHROPIC_API_KEY', 'needs_base_url': False, 'suggested_model': 'claude-sonnet-5'},\n"
    "    'openai': {'default_base_url': 'https://api.openai.com/v1', 'default_api_key_env': 'OPENAI_API_KEY', 'needs_base_url': False, 'suggested_model': 'gpt-6-astra'},\n"
    "    'openai-compatible': {'default_base_url': None, 'default_api_key_env': None, 'needs_base_url': True, 'suggested_model': ''},\n"
    "    'gemini': {'default_base_url': 'https://generativelanguage.googleapis.com', 'default_api_key_env': 'GEMINI_API_KEY', 'needs_base_url': False, 'suggested_model': 'gemini-4-argon'},\n"
    "    'ollama': {'default_base_url': 'http://localhost:11434', 'default_api_key_env': None, 'needs_base_url': False, 'suggested_model': 'llama3.2'},\n"
    "}\n"
    "\n"
    "\n"
    "def _log(name, **kw):\n"
    "    entry = {'call': name}\n"
    "    entry.update(kw)\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry, default=str) + '\\n')\n"
    "\n"
    "\n"
    "def detect_providers(env=None, probe_ollama=True):\n"
    "    _log('detect_providers', probe_ollama=probe_ollama)\n"
    "    out = []\n"
    "    for name, info in PROVIDERS.items():\n"
    "        out.append({\n"
    "            'provider': name,\n"
    "            'available': name in ('openai', 'ollama'),\n"
    "            'reason': 'fake detection',\n"
    "            'suggested_model': info['suggested_model'],\n"
    "            'api_key_env': info['default_api_key_env'],\n"
    "        })\n"
    "    return out\n"
    "\n"
    "\n"
    "def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30, auth=None):\n"
    "    _log('check_connection', provider=provider, model=model)\n"
    "    if provider not in PROVIDERS:\n"
    "        raise ValueError('unknown provider')\n"
    "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
    "        raise ValueError('base_url required')\n"
    "    return {'ok': True, 'error': None}\n"
    "\n"
    "\n"
    "def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None, auth=None):\n"
    "    _log('save_config', config_path=str(config_path), provider=provider, model=model)\n"
    "    if provider not in PROVIDERS:\n"
    "        raise ValueError('unknown provider')\n"
    "    if not isinstance(model, str) or not model:\n"
    "        raise ValueError('model required')\n"
    "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
    "        raise ValueError('base_url required')\n"
    "    path = Path(config_path)\n"
    "    path.parent.mkdir(parents=True, exist_ok=True)\n"
    "    kept = []\n"
    "    if path.is_file():\n"
    "        in_llm = False\n"
    "        for line in path.read_text(encoding='utf-8').splitlines():\n"
    "            stripped = line.strip()\n"
    "            if stripped.startswith('[') and stripped.endswith(']'):\n"
    "                in_llm = stripped == '[llm]'\n"
    "            if not in_llm:\n"
    "                kept.append(line)\n"
    "    lines = [l for l in kept]\n"
    "    while lines and not lines[-1].strip():\n"
    "        lines.pop()\n"
    "    if lines:\n"
    "        lines.append('')\n"
    "    lines.append('[llm]')\n"
    "    lines.append('provider = ' + json.dumps(provider))\n"
    "    lines.append('model = ' + json.dumps(model))\n"
    "    if base_url is not None:\n"
    "        lines.append('base_url = ' + json.dumps(base_url))\n"
    "    if api_key_env is not None:\n"
    "        lines.append('api_key_env = ' + json.dumps(api_key_env))\n"
    "    if timeout_seconds is not None:\n"
    "        lines.append('timeout_seconds = ' + str(int(timeout_seconds)))\n"
    "    if auth is not None:\n"
    "        lines.append('auth = ' + json.dumps(auth))\n"
    "    path.write_text('\\n'.join(lines) + '\\n', encoding='utf-8')\n"
    "\n"
    "\n"
    "def load_config(config_path=None):\n"
    "    _log('load_config', config_path=str(config_path))\n"
    "    if config_path is None:\n"
    "        config_path = Path('hotdocs.toml')\n"
    "    path = Path(config_path)\n"
    "    if not path.is_file():\n"
    "        return None\n"
    "    try:\n"
    "        data = tomllib.loads(path.read_text(encoding='utf-8'))\n"
    "    except tomllib.TOMLDecodeError:\n"
    "        raise ValueError('invalid config')\n"
    "    llm = data.get('llm')\n"
    "    if llm is None:\n"
    "        return None\n"
    "    if not isinstance(llm, dict):\n"
    "        raise ValueError('invalid llm table')\n"
    "    return {\n"
    "        'provider': llm.get('provider'),\n"
    "        'model': llm.get('model'),\n"
    "        'base_url': llm.get('base_url'),\n"
    "        'api_key_env': llm.get('api_key_env'),\n"
    "        'timeout_seconds': llm.get('timeout_seconds'),\n"
    "        'auth': llm.get('auth'),\n"
    "    }\n"
)


def make_tool_root(base, log_path, with_endpoint=True):
    root = base
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        "[project]\n" + "name = " + json.dumps("hotdocs") + "\n" + "version = " + json.dumps("9.8.7a1") + "\n",
        encoding="utf-8",
    )
    (root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    example = root / "examples" / "slugify" / "specs" / "product" / "slugs.md"
    example.parent.mkdir(parents=True, exist_ok=True)
    example.write_text(SLUGS_EXAMPLE_TEXT, encoding="utf-8")
    other = root / "gen" / "some-tool"
    other.mkdir(parents=True, exist_ok=True)
    (other / "some_tool.py").write_text("VALUE = 1\n", encoding="utf-8")
    if with_endpoint:
        ep = root / "gen" / "llm-endpoint"
        ep.mkdir(parents=True, exist_ok=True)
        source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_ENDPOINT_BODY
        (ep / "llm_endpoint.py").write_text(source, encoding="utf-8")
    return root


def make_env():
    return {"PATH": os.environ.get("PATH", "")}


class Recorder:
    def __init__(self):
        self.lines = []
        self.questions = []

    def output(self, *args, **kwargs):
        self.lines.append(" ".join(str(a) for a in args))

    def input(self, prompt=""):
        self.questions.append(prompt)
        return ""

    @property
    def text(self):
        return "\n".join(self.lines)


def call_run(argv, tool_root, cwd):
    rec = Recorder()
    rc = hotdocs_init.run(
        argv,
        tool_root=tool_root,
        input_fn=rec.input,
        output_fn=rec.output,
        env=make_env(),
        cwd=cwd,
    )
    return rc, rec


def snapshot(directory):
    snap = {}
    for p in sorted(Path(directory).rglob("*")):
        rel = p.relative_to(directory).as_posix()
        if p.is_dir():
            snap[rel] = None
        else:
            snap[rel] = p.read_bytes()
    return snap


def read_log(log_path):
    if not log_path.is_file():
        return []
    return [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]


def setup_paths(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    log_path = logs / "calls.log"
    tool_real = make_tool_root(tmp_path / "toolroot", log_path)
    # pass the tool root un-normalised, to check it is echoed exactly as given
    (tmp_path / "x").mkdir()
    tool_given = str(tmp_path / "x" / ".." / "toolroot")
    project = tmp_path / "proj"
    project.mkdir()
    return log_path, tool_real, tool_given, project


def test_example_copies_slugs_and_prints_next_steps(tmp_path):
    log_path, tool_real, tool_given, project = setup_paths(tmp_path)

    rc, rec = call_run([str(project), "--example", "--yes"], tool_given, project)
    assert rc in (0, 3), rec.text

    copied = project / "specs" / "product" / "slugs.md"
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == SLUGS_EXAMPLE_TEXT
    assert not (project / "examples").exists()

    # tool root example untouched
    assert (tool_real / "examples" / "slugify" / "specs" / "product" / "slugs.md").read_text(
        encoding="utf-8"
    ) == SLUGS_EXAMPLE_TEXT

    text = rec.text
    quickstart = str(Path(tool_given) / "QUICKSTART.md")
    assert "hotdocs lint" in text
    tail = text[text.rindex("hotdocs lint"):]
    assert "hotdocs generate comp-slugify" in tail
    assert "hotdocs verify" in tail
    assert quickstart in tail
    nonempty = [l for l in rec.lines if l.strip()]
    last_block = "\n".join(nonempty[-8:])
    assert quickstart in last_block


def test_example_never_overwrites_existing_file(tmp_path):
    log_path, tool_real, tool_given, project = setup_paths(tmp_path)
    existing = project / "specs" / "product" / "slugs.md"
    existing.parent.mkdir(parents=True)
    own = "# My own slugs\n\nDo not touch.\n"
    existing.write_text(own, encoding="utf-8")

    call_run([str(project), "--example", "--yes"], tool_given, project)

    assert existing.read_text(encoding="utf-8") == own
    assert not (project / "examples").exists()


def test_no_example_next_steps_omit_comp_slugify(tmp_path):
    log_path, tool_real, tool_given, project = setup_paths(tmp_path)

    rc, rec = call_run([str(project), "--yes"], tool_given, project)
    assert rc in (0, 3), rec.text
    assert "comp-slugify" not in rec.text
    assert "hotdocs lint" in rec.text
    assert "hotdocs verify" in rec.text


def test_reconfigure_changes_only_hotdocs_toml(tmp_path):
    log_path, tool_real, tool_given, project = setup_paths(tmp_path)

    rc0, rec0 = call_run(
        [str(project), "--yes", "--provider", "ollama", "--model", "llama3.2", "--no-test"],
        tool_given,
        project,
    )
    assert rc0 in (0, 3), rec0.text
    assert (project / ".hotdocs-tool.json").is_file()
    assert (project / "hotdocs.toml").is_file()

    before = snapshot(project)
    log_count = len(read_log(log_path))

    rc, rec = call_run(
        [str(project), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_given,
        project,
    )
    assert rc in (0, 3), rec.text

    after = snapshot(project)
    assert set(after) == set(before)
    for rel, content in before.items():
        if rel == "hotdocs.toml":
            continue
        assert after[rel] == content, rel

    new_calls = read_log(log_path)[log_count:]
    saves = [c for c in new_calls if c["call"] == "save_config"]
    assert saves
    assert saves[-1]["provider"] == "openai"
    assert saves[-1]["model"] == "m"
    assert Path(saves[-1]["config_path"]).resolve() == (project / "hotdocs.toml").resolve()

    toml_text = (project / "hotdocs.toml").read_text(encoding="utf-8")
    assert '"openai"' in toml_text
    assert after["hotdocs.toml"] != before["hotdocs.toml"]

    # now with a tool root holding no llm-endpoint module
    bare_root = make_tool_root(tmp_path / "bare-toolroot", log_path, with_endpoint=False)
    assert not (bare_root / "gen" / "llm-endpoint" / "llm_endpoint.py").exists()
    before2 = snapshot(project)
    rc2, rec2 = call_run(
        [str(project), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        str(bare_root),
        project,
    )
    assert rc2 == 1
    assert snapshot(project) == before2


def test_reconfigure_on_uninitialised_dir_returns_1_and_writes_nothing(tmp_path):
    log_path, tool_real, tool_given, project = setup_paths(tmp_path)
    spec_file = project / "specs" / "product" / "thing.md"
    spec_file.parent.mkdir(parents=True)
    spec_file.write_text("# Thing\n\nA product spec.\n", encoding="utf-8")

    before = snapshot(project)
    rc, rec = call_run(
        [str(project), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_given,
        project,
    )
    assert rc == 1
    assert snapshot(project) == before
    assert not (project / "hotdocs.toml").exists()
    assert not (project / ".hotdocs-tool.json").exists()
    assert not [c for c in read_log(log_path) if c["call"] == "save_config"]