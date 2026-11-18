# hotdocs-criterion: sha256:b07eaa22d2ca2726d21d285d3fd69cd5dbb4fecbc563631baae9edb421d34408
import importlib.metadata
import os
import time
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


FAKE_LLM_ENDPOINT_BODY = (
    "import json\n"
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
    "    'ollama': {'default_base_url': 'http://localhost:11434', 'default_api_key_env': None,\n"
    "               'needs_base_url': False, 'suggested_model': 'llama3.2'},\n"
    "}\n"
    "\n"
    "_KEYS = ['provider', 'model', 'base_url', 'api_key_env', 'timeout_seconds', 'auth']\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
    "\n"
    "def detect_providers(env=None, probe_ollama=True):\n"
    "    _log('detect_providers')\n"
    "    out = []\n"
    "    for name, info in PROVIDERS.items():\n"
    "        available = name == 'ollama'\n"
    "        out.append({\n"
    "            'provider': name,\n"
    "            'available': available,\n"
    "            'reason': 'running' if available else 'not found',\n"
    "            'suggested_model': info['suggested_model'],\n"
    "            'api_key_env': info['default_api_key_env'],\n"
    "        })\n"
    "    return out\n"
    "\n"
    "\n"
    "def check_connection(provider, model, base_url=None, api_key_env=None,\n"
    "                     timeout_seconds=30, auth=None):\n"
    "    _log('check_connection')\n"
    "    if provider not in PROVIDERS:\n"
    "        raise ValueError('unknown provider')\n"
    "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
    "        raise ValueError('base_url required')\n"
    "    return {'ok': True, 'error': None}\n"
    "\n"
    "\n"
    "def _strip_llm(text):\n"
    "    kept = []\n"
    "    in_llm = False\n"
    "    for line in text.splitlines():\n"
    "        s = line.strip()\n"
    "        if s.startswith('[') and s.endswith(']'):\n"
    "            in_llm = s == '[llm]'\n"
    "            if in_llm:\n"
    "                continue\n"
    "        if not in_llm:\n"
    "            kept.append(line)\n"
    "    return kept\n"
    "\n"
    "\n"
    "def save_config(config_path, provider, model, base_url=None, api_key_env=None,\n"
    "                timeout_seconds=None, auth=None):\n"
    "    _log('save_config')\n"
    "    if provider not in PROVIDERS:\n"
    "        raise ValueError('unknown provider')\n"
    "    p = Path(config_path)\n"
    "    p.parent.mkdir(parents=True, exist_ok=True)\n"
    "    old = p.read_text(encoding='utf-8') if p.exists() else ''\n"
    "    lines = _strip_llm(old)\n"
    "    while lines and not lines[-1].strip():\n"
    "        lines.pop()\n"
    "    if lines:\n"
    "        lines.append('')\n"
    "    lines.append('[llm]')\n"
    "    vals = {'provider': provider, 'model': model, 'base_url': base_url,\n"
    "            'api_key_env': api_key_env, 'timeout_seconds': timeout_seconds, 'auth': auth}\n"
    "    for k in _KEYS:\n"
    "        if vals[k] is not None:\n"
    "            lines.append(k + ' = ' + json.dumps(vals[k]))\n"
    "    new = '\\n'.join(lines) + '\\n'\n"
    "    if new != old:\n"
    "        p.write_text(new, encoding='utf-8')\n"
    "\n"
    "\n"
    "def load_config(config_path=None):\n"
    "    _log('load_config')\n"
    "    if config_path is None:\n"
    "        return None\n"
    "    p = Path(config_path)\n"
    "    if not p.is_file():\n"
    "        return None\n"
    "    result = None\n"
    "    in_llm = False\n"
    "    for line in p.read_text(encoding='utf-8').splitlines():\n"
    "        s = line.strip()\n"
    "        if s.startswith('[') and s.endswith(']'):\n"
    "            in_llm = s == '[llm]'\n"
    "            if in_llm and result is None:\n"
    "                result = {k: None for k in _KEYS}\n"
    "            continue\n"
    "        if in_llm and '=' in s:\n"
    "            k, v = s.split('=', 1)\n"
    "            k = k.strip()\n"
    "            if k in _KEYS:\n"
    "                result[k] = json.loads(v.strip())\n"
    "    return result\n"
)


def make_tool_root(tmp_path):
    tool = tmp_path / "tool"
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "llm_endpoint_calls.log"

    ep_dir = tool / "gen" / "llm-endpoint"
    ep_dir.mkdir(parents=True)
    src = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_LLM_ENDPOINT_BODY
    (ep_dir / "llm_endpoint.py").write_text(src, encoding="utf-8")

    ex = tool / "examples" / "slugify" / "specs" / "product"
    ex.mkdir(parents=True)
    (ex / "slugs.md").write_text("# Slugs\n\nExample product spec.\n", encoding="utf-8")

    version = importlib.metadata.version("pytest")
    (tool / "requirements.txt").write_text("pytest==" + version + "\n", encoding="utf-8")
    return tool


def run_init(project, tool, cwd):
    lines = []

    def out(*args, **kwargs):
        text = " ".join(str(a) for a in args)
        lines.extend(text.splitlines())

    def inp(prompt=""):
        return ""

    rc = hotdocs_init.main(
        [str(project), "--yes"],
        tool_root=tool,
        input_fn=inp,
        output_fn=out,
        env=dict(os.environ),
        cwd=cwd,
    )
    return rc, lines


def snapshot(root):
    snap = {}
    for p in sorted(Path(root).rglob("*")):
        rel = p.relative_to(root).as_posix()
        st = p.stat()
        if p.is_file():
            snap[rel] = ("file", p.read_bytes(), st.st_mtime_ns)
        elif p.is_dir():
            snap[rel] = ("dir",)
    return snap


def test_init_creates_skips_and_preserves(tmp_path):
    tool = make_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()

    # First run on an empty directory
    rc, lines = run_init(project, tool, tmp_path)
    assert rc in (0, 3), lines

    for d in DIRS:
        assert (project / d).is_dir(), d
    for g in GITKEEPS:
        assert (project / g).is_file(), g
        assert (project / g).read_bytes() == b"", g
    glossary = (project / "specs" / "glossary.md").read_text(encoding="utf-8")
    assert glossary.startswith("# Glossary")
    assert (project / ".secret-allowlist.json").is_file()
    gi_lines = (project / ".gitignore").read_text(encoding="utf-8").splitlines()
    for line in GITIGNORE_LINES:
        assert gi_lines.count(line) == 1, (line, gi_lines)

    for path in ALL_PATHS:
        assert (path + ": created") in lines, (path, lines)

    # Second run: nothing changes
    before = snapshot(project)
    assert ".hotdocs-tool.json" in before
    time.sleep(0.05)
    rc2, lines2 = run_init(project, tool, tmp_path)
    assert rc2 in (0, 3), lines2
    after = snapshot(project)
    assert after == before

    for path in ALL_PATHS:
        assert (path + ": skipped (exists)") in lines2, (path, lines2)
        assert (path + ": created") not in lines2, (path, lines2)

    # Existing glossary and partial .gitignore are preserved
    project2 = tmp_path / "proj2"
    (project2 / "specs").mkdir(parents=True)
    (project2 / "specs" / "glossary.md").write_text("mine", encoding="utf-8")
    (project2 / ".gitignore").write_text("/.hotdocs/\n", encoding="utf-8")

    rc3, lines3 = run_init(project2, tool, tmp_path)
    assert rc3 in (0, 3), lines3
    assert (project2 / "specs" / "glossary.md").read_text(encoding="utf-8") == "mine"
    gi2 = (project2 / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert gi2.count("/.hotdocs/") == 1, gi2
    for line in ["__pycache__/", "*.pyc", ".venv/"]:
        assert gi2.count(line) == 1, (line, gi2)