# hotdocs-criterion: sha256:8842b9a62cb53daa06508732f1048ce4ae97d16d721ec1ce37608238ac050d19
import importlib.metadata
import os
from pathlib import Path

import hotdocs_init


DIRS = [
    "specs/product",
    "specs/components",
    "specs/decisions",
    "gen",
    "verification",
]
GITKEEPS = [
    "specs/product/.gitkeep",
    "specs/components/.gitkeep",
    "specs/decisions/.gitkeep",
    "verification/.gitkeep",
]
FILES = ["specs/glossary.md", ".secret-allowlist.json", ".gitignore"]
ALL_PATHS = DIRS + GITKEEPS + FILES
GITIGNORE_LINES = ["/.hotdocs/", "__pycache__/", "*.pyc", ".venv/"]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_BODY = (
    "import os\n"
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
    "    'ollama': {'default_base_url': 'http://localhost:11434',\n"
    "               'default_api_key_env': None,\n"
    "               'needs_base_url': False, 'suggested_model': 'llama3.2'},\n"
    "}\n"
    "\n"
    "def _log(text):\n"
    "    p = Path(LOG_PATH)\n"
    "    p.parent.mkdir(parents=True, exist_ok=True)\n"
    "    with open(p, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(text + '\\n')\n"
    "\n"
    "def detect_providers(env=None, probe_ollama=True):\n"
    "    _log('detect_providers')\n"
    "    out = []\n"
    "    for name, info in PROVIDERS.items():\n"
    "        out.append({\n"
    "            'provider': name,\n"
    "            'available': name == 'claude-cli',\n"
    "            'reason': 'found' if name == 'claude-cli' else 'not configured',\n"
    "            'suggested_model': info['suggested_model'],\n"
    "            'api_key_env': info['default_api_key_env'],\n"
    "        })\n"
    "    return out\n"
    "\n"
    "def check_connection(provider, model, base_url=None, api_key_env=None,\n"
    "                     timeout_seconds=30, auth=None):\n"
    "    _log('check_connection ' + str(provider))\n"
    "    if provider not in PROVIDERS:\n"
    "        raise ValueError('unknown provider')\n"
    "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
    "        raise ValueError('base_url required')\n"
    "    return {'ok': True, 'error': None}\n"
    "\n"
    "def _render(provider, model, base_url, api_key_env, timeout_seconds, auth):\n"
    "    lines = ['[llm]', 'provider = ' + _q(provider), 'model = ' + _q(model)]\n"
    "    if base_url is not None:\n"
    "        lines.append('base_url = ' + _q(base_url))\n"
    "    if api_key_env is not None:\n"
    "        lines.append('api_key_env = ' + _q(api_key_env))\n"
    "    if timeout_seconds is not None:\n"
    "        lines.append('timeout_seconds = ' + str(int(timeout_seconds)))\n"
    "    if auth is not None:\n"
    "        lines.append('auth = ' + _q(auth))\n"
    "    return '\\n'.join(lines) + '\\n'\n"
    "\n"
    "def _q(s):\n"
    "    return '\"' + str(s).replace('\\\\', '\\\\\\\\').replace('\"', '\\\\\"') + '\"'\n"
    "\n"
    "def save_config(config_path, provider, model, base_url=None,\n"
    "                api_key_env=None, timeout_seconds=None, auth=None):\n"
    "    _log('save_config')\n"
    "    if provider not in PROVIDERS:\n"
    "        raise ValueError('unknown provider')\n"
    "    if not isinstance(model, str):\n"
    "        raise ValueError('invalid model')\n"
    "    path = Path(config_path)\n"
    "    path.parent.mkdir(parents=True, exist_ok=True)\n"
    "    old = path.read_text(encoding='utf-8') if path.exists() else ''\n"
    "    kept = []\n"
    "    in_llm = False\n"
    "    for line in old.splitlines():\n"
    "        s = line.strip()\n"
    "        if s.startswith('[') and s.endswith(']'):\n"
    "            in_llm = (s == '[llm]')\n"
    "            if in_llm:\n"
    "                continue\n"
    "        if not in_llm:\n"
    "            kept.append(line)\n"
    "    rest = '\\n'.join(kept).strip()\n"
    "    new = _render(provider, model, base_url, api_key_env, timeout_seconds, auth)\n"
    "    if rest:\n"
    "        new = rest + '\\n\\n' + new\n"
    "    if new != old:\n"
    "        path.write_text(new, encoding='utf-8')\n"
    "\n"
    "def load_config(config_path=None):\n"
    "    _log('load_config')\n"
    "    path = Path(config_path) if config_path is not None else Path('hotdocs.toml')\n"
    "    if not path.exists():\n"
    "        return None\n"
    "    result = None\n"
    "    in_llm = False\n"
    "    for line in path.read_text(encoding='utf-8').splitlines():\n"
    "        s = line.strip()\n"
    "        if s.startswith('[') and s.endswith(']'):\n"
    "            in_llm = (s == '[llm]')\n"
    "            if in_llm:\n"
    "                result = {'provider': None, 'model': None, 'base_url': None,\n"
    "                          'api_key_env': None, 'timeout_seconds': None, 'auth': None}\n"
    "            continue\n"
    "        if in_llm and '=' in s:\n"
    "            key, _, val = s.partition('=')\n"
    "            key = key.strip()\n"
    "            val = val.strip()\n"
    "            if val.startswith('\"') and val.endswith('\"'):\n"
    "                val = val[1:-1]\n"
    "            elif key == 'timeout_seconds':\n"
    "                val = int(val)\n"
    "            if key in result:\n"
    "                result[key] = val\n"
    "    return result\n"
)


def make_tool_root(base):
    tool = base / "tool"
    log_path = base / "logs" / "llm_endpoint_calls.log"
    (tool / "gen" / "llm-endpoint").mkdir(parents=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_BODY
    (tool / "gen" / "llm-endpoint" / "llm_endpoint.py").write_text(source, encoding="utf-8")
    slugs = tool / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nTurn titles into slugs.\n", encoding="utf-8")
    version = importlib.metadata.version("pytest")
    (tool / "requirements.txt").write_text("pytest==" + version + "\n", encoding="utf-8")
    return tool


def run_init(project, tool, cwd, lines):
    def output_fn(*args, **kwargs):
        lines.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        return ""

    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(cwd)}
    return hotdocs_init.main(
        [str(project), "--yes"],
        tool_root=tool,
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=cwd,
    )


def snapshot(root):
    result = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file():
            st = p.stat()
            result[rel] = ("file", p.read_bytes(), st.st_mtime_ns)
        elif p.is_dir():
            result[rel] = ("dir", None, None)
    return result


def gitignore_lines(project):
    return (project / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_ac_init_001_fresh_then_rerun(tmp_path):
    tool = make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    workdir = tmp_path / "work"
    workdir.mkdir()

    lines = []
    rc = run_init(project, tool, workdir, lines)
    assert rc in (0, 3), lines

    for d in DIRS:
        assert (project / d).is_dir(), d
    for g in GITKEEPS:
        assert (project / g).is_file(), g
        assert (project / g).read_bytes() == b"", g
    glossary = (project / "specs" / "glossary.md").read_text(encoding="utf-8")
    assert glossary.startswith("# Glossary")
    assert (project / ".secret-allowlist.json").is_file()
    gi = gitignore_lines(project)
    for entry in GITIGNORE_LINES:
        assert gi.count(entry) == 1, (entry, gi)
    for path in ALL_PATHS:
        assert (path + ": created") in lines, (path, lines)

    before = snapshot(project)

    lines2 = []
    rc2 = run_init(project, tool, workdir, lines2)
    assert rc2 in (0, 3), lines2

    after = snapshot(project)
    assert set(after) == set(before)
    for rel, value in before.items():
        assert after[rel] == value, rel
    tool_json = project / ".hotdocs-tool.json"
    if ".hotdocs-tool.json" in before:
        assert tool_json.is_file()
        assert after[".hotdocs-tool.json"] == before[".hotdocs-tool.json"]

    for path in ALL_PATHS:
        assert (path + ": skipped (exists)") in lines2, (path, lines2)
        assert (path + ": created") not in lines2, (path, lines2)

    gi2 = gitignore_lines(project)
    for entry in GITIGNORE_LINES:
        assert gi2.count(entry) == 1, (entry, gi2)


def test_ac_init_001_existing_files_preserved(tmp_path):
    tool = make_tool_root(tmp_path)
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "glossary.md").write_text("mine", encoding="utf-8")
    (project / ".gitignore").write_text("/.hotdocs/\n", encoding="utf-8")
    workdir = tmp_path / "work"
    workdir.mkdir()

    lines = []
    rc = run_init(project, tool, workdir, lines)
    assert rc in (0, 3), lines

    assert (project / "specs" / "glossary.md").read_text(encoding="utf-8") == "mine"
    gi = gitignore_lines(project)
    assert gi.count("/.hotdocs/") == 1, gi
    for entry in ["__pycache__/", "*.pyc", ".venv/"]:
        assert gi.count(entry) == 1, (entry, gi)
    assert "specs/glossary.md: skipped (exists)" in lines, lines