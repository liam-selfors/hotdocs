# hotdocs-criterion: sha256:d79ae6801dbe93d0e87bb4188a89e7ffa302dfdf4143b44195e4271a6587dcd7
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


def _fake_llm_endpoint_source(log_path):
    return (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(name, **kw):\n"
        "    Path(LOG).parent.mkdir(parents=True, exist_ok=True)\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'call': name, 'args': dict((k, str(v)) for k, v in kw.items())}) + '\\n')\n"
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
        "_KEYS = ['provider', 'model', 'base_url', 'api_key_env', 'timeout_seconds', 'auth']\n"
        "\n"
        "def detect_providers(env=None, probe_ollama=True):\n"
        "    _log('detect_providers', env_given=env is not None, probe_ollama=probe_ollama)\n"
        "    out = []\n"
        "    for name, p in PROVIDERS.items():\n"
        "        available = name == 'ollama'\n"
        "        out.append({\n"
        "            'provider': name,\n"
        "            'available': available,\n"
        "            'reason': 'fake: reachable' if available else 'fake: not configured',\n"
        "            'suggested_model': p['suggested_model'],\n"
        "            'api_key_env': p['default_api_key_env'],\n"
        "        })\n"
        "    return out\n"
        "\n"
        "def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30, auth=None):\n"
        "    _log('check_connection', provider=provider, model=model, base_url=base_url)\n"
        "    if provider not in PROVIDERS:\n"
        "        raise ValueError('unknown provider')\n"
        "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
        "        raise ValueError('base_url required')\n"
        "    return {'ok': True, 'error': None}\n"
        "\n"
        "def _toml_value(v):\n"
        "    if isinstance(v, bool):\n"
        "        return 'true' if v else 'false'\n"
        "    if isinstance(v, int):\n"
        "        return str(v)\n"
        "    return json.dumps(str(v))\n"
        "\n"
        "def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None, auth=None):\n"
        "    _log('save_config', config_path=config_path, provider=provider, model=model)\n"
        "    if provider not in PROVIDERS:\n"
        "        raise ValueError('unknown provider')\n"
        "    if not isinstance(model, str):\n"
        "        raise ValueError('invalid model')\n"
        "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
        "        raise ValueError('base_url required')\n"
        "    path = Path(config_path)\n"
        "    path.parent.mkdir(parents=True, exist_ok=True)\n"
        "    existing = path.read_text(encoding='utf-8') if path.is_file() else ''\n"
        "    kept = []\n"
        "    in_llm = False\n"
        "    for line in existing.splitlines():\n"
        "        s = line.strip()\n"
        "        if s.startswith('[') and s.endswith(']'):\n"
        "            in_llm = s == '[llm]'\n"
        "        if not in_llm:\n"
        "            kept.append(line)\n"
        "    values = {'provider': provider, 'model': model, 'base_url': base_url, 'api_key_env': api_key_env, 'timeout_seconds': timeout_seconds, 'auth': auth}\n"
        "    block = ['[llm]']\n"
        "    for k in _KEYS:\n"
        "        if values[k] is not None:\n"
        "            block.append(k + ' = ' + _toml_value(values[k]))\n"
        "    while kept and not kept[-1].strip():\n"
        "        kept.pop()\n"
        "    parts = kept + ([''] if kept else []) + block\n"
        "    text = '\\n'.join(parts) + '\\n'\n"
        "    if text != existing:\n"
        "        path.write_text(text, encoding='utf-8')\n"
        "\n"
        "def load_config(config_path=None):\n"
        "    _log('load_config', config_path=config_path)\n"
        "    import tomllib\n"
        "    path = Path(config_path) if config_path is not None else Path('hotdocs.toml')\n"
        "    if not path.is_file():\n"
        "        return None\n"
        "    try:\n"
        "        data = tomllib.loads(path.read_text(encoding='utf-8'))\n"
        "    except Exception as exc:\n"
        "        raise ValueError('invalid config') from exc\n"
        "    llm = data.get('llm')\n"
        "    if llm is None:\n"
        "        return None\n"
        "    if not isinstance(llm, dict) or llm.get('provider') not in PROVIDERS:\n"
        "        raise ValueError('invalid llm table')\n"
        "    return dict((k, llm.get(k)) for k in _KEYS)\n"
    )


def _make_tool_root(tmp_path):
    tool_root = tmp_path / "tool"
    log_path = tmp_path / "logs" / "llm_endpoint_calls.log"
    fake_dir = tool_root / "gen" / "llm-endpoint"
    fake_dir.mkdir(parents=True)
    (fake_dir / "llm_endpoint.py").write_text(
        _fake_llm_endpoint_source(log_path), encoding="utf-8"
    )
    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nAn example product spec.\n", encoding="utf-8")
    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    (tool_root / "pyproject.toml").write_text(
        '[project]\nname = "hotdocs"\nversion = "9.8.7a1"\n', encoding="utf-8"
    )
    return tool_root


def _run(project, tool_root, cwd):
    lines = []

    def output_fn(*args, **kwargs):
        text = " ".join(str(a) for a in args)
        lines.extend(text.splitlines())

    def input_fn(prompt=""):
        return ""

    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(cwd)}
    code = hotdocs_init.run(
        [str(project), "--yes"],
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=str(cwd),
    )
    return code, lines


def _snapshot(project):
    files = {}
    dirs = set()
    for p in sorted(project.rglob("*")):
        rel = p.relative_to(project).as_posix()
        if p.is_dir():
            dirs.add(rel)
        else:
            st = p.stat()
            files[rel] = (p.read_bytes(), st.st_mtime_ns)
    return files, dirs


def _gitignore_lines(project):
    return (project / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_first_run_creates_everything(tmp_path):
    tool_root = _make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()

    code, lines = _run(project, tool_root, tmp_path)
    assert code in (0, 3), lines

    for d in DIRS:
        assert (project / d).is_dir(), d
    for g in GITKEEPS:
        assert (project / g).is_file(), g
        assert (project / g).read_bytes() == b"", g
    glossary = (project / "specs" / "glossary.md").read_text(encoding="utf-8")
    assert glossary.startswith("# Glossary")
    assert (project / ".secret-allowlist.json").is_file()
    gi = _gitignore_lines(project)
    for line in GITIGNORE_LINES:
        assert gi.count(line) == 1, (line, gi)

    for path in ALL_PATHS:
        assert path + ": created" in lines, (path, lines)


def test_second_run_changes_nothing(tmp_path):
    tool_root = _make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()

    code, _ = _run(project, tool_root, tmp_path)
    assert code in (0, 3)
    assert (project / ".hotdocs-tool.json").is_file()

    before_files, before_dirs = _snapshot(project)

    code2, lines2 = _run(project, tool_root, tmp_path)
    assert code2 in (0, 3), lines2

    after_files, after_dirs = _snapshot(project)
    assert after_dirs == before_dirs
    assert set(after_files) == set(before_files)
    for rel, (data, mtime) in before_files.items():
        assert after_files[rel][0] == data, rel
        assert after_files[rel][1] == mtime, rel
    assert ".hotdocs-tool.json" in after_files
    assert after_files[".hotdocs-tool.json"] == before_files[".hotdocs-tool.json"]

    for path in ALL_PATHS:
        assert path + ": skipped (exists)" in lines2, (path, lines2)
        assert path + ": created" not in lines2, (path, lines2)


def test_existing_files_are_kept_and_gitignore_completed(tmp_path):
    tool_root = _make_tool_root(tmp_path)
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "glossary.md").write_text("mine", encoding="utf-8")
    (project / ".gitignore").write_text("/.hotdocs/\n", encoding="utf-8")

    code, lines = _run(project, tool_root, tmp_path)
    assert code in (0, 3), lines

    assert (project / "specs" / "glossary.md").read_text(encoding="utf-8") == "mine"
    gi = _gitignore_lines(project)
    assert gi.count("/.hotdocs/") == 1, gi
    for line in ["__pycache__/", "*.pyc", ".venv/"]:
        assert gi.count(line) == 1, (line, gi)