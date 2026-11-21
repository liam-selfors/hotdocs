# hotdocs-criterion: sha256:138f291ce3e191007e96fced80166969279376e0e7aa96895b5880fdc86fd06a
import importlib.metadata
import json
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


def _fake_llm_endpoint_source(log_path):
    return (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(name, **kw):\n"
        "    p = Path(_LOG)\n"
        "    p.parent.mkdir(parents=True, exist_ok=True)\n"
        "    with open(p, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'call': name, 'args': {k: repr(v) for k, v in kw.items()}}) + '\\n')\n"
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
        "def detect_providers(env=None, probe_ollama=True):\n"
        "    _log('detect_providers', env=env is not None, probe_ollama=probe_ollama)\n"
        "    out = []\n"
        "    for name, info in PROVIDERS.items():\n"
        "        available = name == 'claude-cli'\n"
        "        out.append({\n"
        "            'provider': name,\n"
        "            'available': available,\n"
        "            'reason': 'found' if available else 'not found',\n"
        "            'suggested_model': info['suggested_model'],\n"
        "            'api_key_env': info['default_api_key_env'],\n"
        "        })\n"
        "    return out\n"
        "\n"
        "def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30, auth=None):\n"
        "    _log('check_connection', provider=provider, model=model, base_url=base_url, api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)\n"
        "    if provider not in PROVIDERS:\n"
        "        raise ValueError('unknown provider')\n"
        "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
        "        raise ValueError('base_url required')\n"
        "    return {'ok': True, 'error': None}\n"
        "\n"
        "_KEYS = ['provider', 'model', 'base_url', 'api_key_env', 'timeout_seconds', 'auth']\n"
        "\n"
        "def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None, auth=None):\n"
        "    _log('save_config', config_path=str(config_path), provider=provider, model=model, base_url=base_url, api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)\n"
        "    if provider not in PROVIDERS or not model:\n"
        "        raise ValueError('invalid config')\n"
        "    path = Path(config_path)\n"
        "    path.parent.mkdir(parents=True, exist_ok=True)\n"
        "    existing = path.read_text(encoding='utf-8') if path.is_file() else ''\n"
        "    head = existing.split('[llm]')[0]\n"
        "    values = {'provider': provider, 'model': model, 'base_url': base_url, 'api_key_env': api_key_env, 'timeout_seconds': timeout_seconds, 'auth': auth}\n"
        "    body = '[llm]\\n'\n"
        "    for k in _KEYS:\n"
        "        if values[k] is not None:\n"
        "            body += k + ' = ' + json.dumps(values[k]) + '\\n'\n"
        "    new = head + body\n"
        "    if new != existing:\n"
        "        path.write_text(new, encoding='utf-8')\n"
        "\n"
        "def load_config(config_path=None):\n"
        "    _log('load_config', config_path=None if config_path is None else str(config_path))\n"
        "    if config_path is None:\n"
        "        return None\n"
        "    path = Path(config_path)\n"
        "    if not path.is_file():\n"
        "        return None\n"
        "    text = path.read_text(encoding='utf-8')\n"
        "    if '[llm]' not in text:\n"
        "        return None\n"
        "    result = {k: None for k in _KEYS}\n"
        "    for line in text.split('[llm]', 1)[1].splitlines():\n"
        "        line = line.strip()\n"
        "        if line.startswith('['):\n"
        "            break\n"
        "        if '=' not in line:\n"
        "            continue\n"
        "        key, _, val = line.partition('=')\n"
        "        key = key.strip()\n"
        "        if key in result:\n"
        "            try:\n"
        "                result[key] = json.loads(val.strip())\n"
        "            except Exception:\n"
        "                raise ValueError('invalid config')\n"
        "    if result['provider'] is None or result['model'] is None:\n"
        "        raise ValueError('invalid config')\n"
        "    return result\n"
    )


def _make_tool_root(base):
    tool_root = base / "toolroot"
    log_path = base / "logs" / "llm_endpoint.log"
    ep = tool_root / "gen" / "llm-endpoint"
    ep.mkdir(parents=True)
    (ep / "llm_endpoint.py").write_text(_fake_llm_endpoint_source(log_path), encoding="utf-8")
    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nTurn titles into slugs.\n", encoding="utf-8")
    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    return tool_root


def _invoke(project, tool_root, cwd):
    lines = []

    def output_fn(*args, **kwargs):
        text = " ".join(str(a) for a in args)
        lines.extend(text.split("\n"))

    def input_fn(prompt=""):
        return ""

    env = {"PATH": os.environ.get("PATH", "")}
    rc = hotdocs_init.run(
        [str(project), "--yes"],
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=cwd,
    )
    return rc, lines


def _snapshot(root):
    snap = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file():
            st = p.stat()
            snap[rel] = ("file", p.read_bytes(), st.st_mtime_ns)
        elif p.is_dir():
            snap[rel] = ("dir",)
    return snap


def _gitignore_lines(project):
    return (project / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_ac_init_001_fresh_run_creates_everything(tmp_path):
    tool_root = _make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()

    rc, lines = _invoke(project, tool_root, tmp_path)
    assert rc in (0, 3), lines

    for d in DIRS:
        assert (project / d).is_dir(), d
    for g in GITKEEPS:
        assert (project / g).is_file(), g
        assert (project / g).stat().st_size == 0, g
    assert (project / "specs" / "glossary.md").read_text(encoding="utf-8").startswith("# Glossary")
    assert (project / ".secret-allowlist.json").is_file()
    gi = _gitignore_lines(project)
    for line in GITIGNORE_LINES:
        assert gi.count(line) == 1, (line, gi)

    for path in ALL_PATHS:
        assert (path + ": created") in lines, (path, lines)


def test_ac_init_001_second_run_changes_nothing(tmp_path):
    tool_root = _make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()

    rc1, _ = _invoke(project, tool_root, tmp_path)
    assert rc1 in (0, 3)

    tool_json = project / ".hotdocs-tool.json"
    tool_json_existed = tool_json.is_file()
    if tool_json_existed:
        tj_bytes = tool_json.read_bytes()
        tj_mtime = tool_json.stat().st_mtime_ns

    before = _snapshot(project)
    rc2, lines = _invoke(project, tool_root, tmp_path)
    assert rc2 in (0, 3), lines
    after = _snapshot(project)

    assert after == before
    assert tool_json.is_file() == tool_json_existed
    if tool_json_existed:
        assert tool_json.read_bytes() == tj_bytes
        assert tool_json.stat().st_mtime_ns == tj_mtime

    for path in ALL_PATHS:
        assert (path + ": skipped (exists)") in lines, (path, lines)
        assert (path + ": created") not in lines, (path, lines)


def test_ac_init_001_existing_files_preserved(tmp_path):
    tool_root = _make_tool_root(tmp_path)
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "glossary.md").write_text("mine", encoding="utf-8")
    (project / ".gitignore").write_text("/.hotdocs/\n", encoding="utf-8")

    rc, lines = _invoke(project, tool_root, tmp_path)
    assert rc in (0, 3), lines

    assert (project / "specs" / "glossary.md").read_text(encoding="utf-8") == "mine"
    gi = _gitignore_lines(project)
    assert gi.count("/.hotdocs/") == 1, gi
    for line in ["__pycache__/", "*.pyc", ".venv/"]:
        assert gi.count(line) == 1, (line, gi)
    assert "specs/glossary.md: skipped (exists)" in lines, lines