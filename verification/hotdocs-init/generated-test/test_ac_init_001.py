# hotdocs-criterion: sha256:884087d989672f5d617615d08f6e40c96f02280d03d22876961058df11cc5b7e
import importlib.metadata
import os
from pathlib import Path

import pytest

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
GITIGNORE_LINES = ["/.hotdocs/", "__pycache__/", "*.pyc", ".venv/", "/dist/"]


FAKE_BODY = (
    "import json\n"
    "import tomllib\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def _log(name, **kw):\n"
    "    rec = {'call': name}\n"
    "    for k, v in kw.items():\n"
    "        rec[k] = repr(v)\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(rec) + '\\n')\n"
    "\n"
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
    "def detect_providers(env=None, probe_ollama=True):\n"
    "    _log('detect_providers', env=env is not None, probe_ollama=probe_ollama)\n"
    "    out = []\n"
    "    for name, info in PROVIDERS.items():\n"
    "        avail = name == 'ollama'\n"
    "        out.append({\n"
    "            'provider': name,\n"
    "            'available': avail,\n"
    "            'reason': 'running' if avail else 'not configured',\n"
    "            'suggested_model': info['suggested_model'],\n"
    "            'api_key_env': info['default_api_key_env'],\n"
    "        })\n"
    "    return out\n"
    "\n"
    "\n"
    "def check_connection(provider, model, base_url=None, api_key_env=None,\n"
    "                     timeout_seconds=30, auth=None):\n"
    "    _log('check_connection', provider=provider, model=model)\n"
    "    if provider not in PROVIDERS:\n"
    "        raise ValueError('unknown provider')\n"
    "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
    "        raise ValueError('base_url required')\n"
    "    return {'ok': True, 'error': None}\n"
    "\n"
    "\n"
    "def _q(v):\n"
    "    return json.dumps(v)\n"
    "\n"
    "\n"
    "def save_config(config_path, provider, model, base_url=None,\n"
    "                api_key_env=None, timeout_seconds=None, auth=None):\n"
    "    _log('save_config', provider=provider, model=model)\n"
    "    if provider not in PROVIDERS:\n"
    "        raise ValueError('unknown provider')\n"
    "    if not isinstance(model, str):\n"
    "        raise ValueError('bad model')\n"
    "    path = Path(config_path)\n"
    "    path.parent.mkdir(parents=True, exist_ok=True)\n"
    "    kept = []\n"
    "    if path.exists():\n"
    "        in_llm = False\n"
    "        for line in path.read_text(encoding='utf-8').splitlines():\n"
    "            s = line.strip()\n"
    "            if s.startswith('['):\n"
    "                in_llm = s == '[llm]'\n"
    "            if not in_llm:\n"
    "                kept.append(line)\n"
    "    lines = list(kept)\n"
    "    lines.append('[llm]')\n"
    "    lines.append('provider = ' + _q(provider))\n"
    "    lines.append('model = ' + _q(model))\n"
    "    if base_url is not None:\n"
    "        lines.append('base_url = ' + _q(base_url))\n"
    "    if api_key_env is not None:\n"
    "        lines.append('api_key_env = ' + _q(api_key_env))\n"
    "    if timeout_seconds is not None:\n"
    "        lines.append('timeout_seconds = ' + str(int(timeout_seconds)))\n"
    "    if auth is not None:\n"
    "        lines.append('auth = ' + _q(auth))\n"
    "    path.write_text('\\n'.join(lines) + '\\n', encoding='utf-8')\n"
    "\n"
    "\n"
    "def load_config(config_path=None):\n"
    "    _log('load_config', config_path=config_path)\n"
    "    path = Path(config_path) if config_path is not None else Path('hotdocs.toml')\n"
    "    if not path.is_file():\n"
    "        return None\n"
    "    try:\n"
    "        data = tomllib.loads(path.read_text(encoding='utf-8'))\n"
    "    except Exception as exc:\n"
    "        raise ValueError('invalid config') from exc\n"
    "    llm = data.get('llm')\n"
    "    if not isinstance(llm, dict):\n"
    "        return None\n"
    "    return {\n"
    "        'provider': llm.get('provider'),\n"
    "        'model': llm.get('model'),\n"
    "        'base_url': llm.get('base_url'),\n"
    "        'api_key_env': llm.get('api_key_env'),\n"
    "        'timeout_seconds': llm.get('timeout_seconds'),\n"
    "        'auth': llm.get('auth'),\n"
    "    }\n"
)


def make_tool_root(tmp_path):
    tool = tmp_path / "tool"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log = log_dir / "calls.log"
    fake_dir = tool / "gen" / "llm-endpoint"
    fake_dir.mkdir(parents=True)
    source = "LOG = " + repr(str(log)) + "\n" + FAKE_BODY
    (fake_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")
    ex = tool / "examples" / "slugify" / "specs" / "product"
    ex.mkdir(parents=True)
    (ex / "slugs.md").write_text("# Slugs\n", encoding="utf-8")
    (tool / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    (tool / "pyproject.toml").write_text(
        '[project]\nname = "hotdocs"\nversion = "9.8.7a1"\n', encoding="utf-8"
    )
    return tool


class Recorder:
    def __init__(self):
        self.lines = []

    def __call__(self, *args, **kwargs):
        text = " ".join(str(a) for a in args)
        self.lines.extend(text.splitlines() if text else [""])


def make_env(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {"PATH": os.environ.get("PATH", ""), "HOME": str(home)}


def do_run(project, tool, tmp_path):
    out = Recorder()
    rc = hotdocs_init.run(
        [str(project), "--yes"],
        tool_root=tool,
        input_fn=lambda prompt: "",
        output_fn=out,
        env=make_env(tmp_path),
        cwd=tmp_path,
    )
    return rc, out.lines


def snapshot(root):
    snap = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        st = p.stat()
        if p.is_file():
            snap[rel] = ("file", p.read_bytes(), st.st_mtime_ns)
        else:
            snap[rel] = ("dir",)
    return snap


def test_first_run_creates_everything(tmp_path):
    tool = make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()

    rc, lines = do_run(project, tool, tmp_path)
    assert rc in (0, 3)

    for d in DIRS:
        assert (project / d).is_dir(), d
    for g in GITKEEPS:
        assert (project / g).is_file(), g
        assert (project / g).read_bytes() == b"", g
    glossary = (project / "specs" / "glossary.md").read_text(encoding="utf-8")
    assert glossary.startswith("# Glossary")
    assert (project / ".secret-allowlist.json").is_file()
    gi_lines = (project / ".gitignore").read_text(encoding="utf-8").splitlines()
    for entry in GITIGNORE_LINES:
        assert gi_lines.count(entry) == 1, entry

    for path in ALL_PATHS:
        assert (path + ": created") in lines, path


def test_second_run_changes_nothing(tmp_path):
    tool = make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()

    rc1, _ = do_run(project, tool, tmp_path)
    assert rc1 in (0, 3)
    marker = project / ".hotdocs-tool.json"
    assert marker.is_file()
    before = snapshot(project)
    marker_bytes = marker.read_bytes()
    marker_mtime = marker.stat().st_mtime_ns

    rc2, lines = do_run(project, tool, tmp_path)
    assert rc2 in (0, 3)

    after = snapshot(project)
    assert after == before
    assert marker.read_bytes() == marker_bytes
    assert marker.stat().st_mtime_ns == marker_mtime

    for path in ALL_PATHS:
        assert (path + ": skipped (exists)") in lines, path
        assert (path + ": created") not in lines, path


def test_existing_files_are_kept(tmp_path):
    tool = make_tool_root(tmp_path)
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "glossary.md").write_text("mine", encoding="utf-8")
    (project / ".gitignore").write_text("/.hotdocs/\n", encoding="utf-8")

    rc, _ = do_run(project, tool, tmp_path)
    assert rc in (0, 3)

    assert (project / "specs" / "glossary.md").read_text(encoding="utf-8") == "mine"
    gi_lines = (project / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert gi_lines.count("/.hotdocs/") == 1
    for entry in GITIGNORE_LINES[1:]:
        assert gi_lines.count(entry) == 1, entry