# hotdocs-criterion: sha256:e9cbfb0817834814dd5083b7781efaa8e3662cb79b762407d2cde256e2780984
import importlib.metadata
import os
from pathlib import Path

import hotdocs_init


FAKE_ENDPOINT_HEAD = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
)

FAKE_ENDPOINT_BODY = (
    "PROVIDERS = {\n"
    "    'claude-cli': {'default_base_url': None, 'default_api_key_env': None, 'needs_base_url': False, 'suggested_model': 'claude-sonnet-5'},\n"
    "    'anthropic': {'default_base_url': 'https://api.anthropic.com', 'default_api_key_env': 'ANTHROPIC_API_KEY', 'needs_base_url': False, 'suggested_model': 'claude-sonnet-5'},\n"
    "    'openai': {'default_base_url': 'https://api.openai.com/v1', 'default_api_key_env': 'OPENAI_API_KEY', 'needs_base_url': False, 'suggested_model': 'gpt-6-astra'},\n"
    "    'openai-compatible': {'default_base_url': None, 'default_api_key_env': None, 'needs_base_url': True, 'suggested_model': ''},\n"
    "    'gemini': {'default_base_url': 'https://generativelanguage.googleapis.com', 'default_api_key_env': 'GEMINI_API_KEY', 'needs_base_url': False, 'suggested_model': 'gemini-4-argon'},\n"
    "    'ollama': {'default_base_url': 'http://localhost:11434', 'default_api_key_env': None, 'needs_base_url': False, 'suggested_model': 'llama3.2'},\n"
    "}\n"
    "\n"
    "def _log(name, **kwargs):\n"
    "    Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(name + ' ' + repr(sorted((k, str(v)) for k, v in kwargs.items())) + '\\n')\n"
    "\n"
    "def detect_providers(env=None, probe_ollama=True):\n"
    "    _log('detect_providers', probe_ollama=probe_ollama)\n"
    "    out = []\n"
    "    for name, info in PROVIDERS.items():\n"
    "        out.append({\n"
    "            'provider': name,\n"
    "            'available': name == 'openai',\n"
    "            'reason': 'fake',\n"
    "            'suggested_model': info['suggested_model'],\n"
    "            'api_key_env': info['default_api_key_env'],\n"
    "        })\n"
    "    return out\n"
    "\n"
    "def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30, auth=None):\n"
    "    _log('check_connection', provider=provider, model=model)\n"
    "    if provider not in PROVIDERS:\n"
    "        raise ValueError('unknown provider')\n"
    "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
    "        raise ValueError('base_url required')\n"
    "    return {'ok': True, 'error': None}\n"
    "\n"
    "def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None, auth=None):\n"
    "    _log('save_config', provider=provider, model=model)\n"
    "    if provider not in PROVIDERS or not model:\n"
    "        raise ValueError('invalid')\n"
    "    p = Path(config_path)\n"
    "    p.parent.mkdir(parents=True, exist_ok=True)\n"
    "    kept = []\n"
    "    if p.exists():\n"
    "        skipping = False\n"
    "        for line in p.read_text(encoding='utf-8').splitlines():\n"
    "            s = line.strip()\n"
    "            if s.startswith('[') and s.endswith(']'):\n"
    "                skipping = (s == '[llm]')\n"
    "            if not skipping:\n"
    "                kept.append(line)\n"
    "    lines = ['[llm]', 'provider = ' + json.dumps(provider), 'model = ' + json.dumps(model)]\n"
    "    if base_url is not None:\n"
    "        lines.append('base_url = ' + json.dumps(base_url))\n"
    "    if api_key_env is not None:\n"
    "        lines.append('api_key_env = ' + json.dumps(api_key_env))\n"
    "    if timeout_seconds is not None:\n"
    "        lines.append('timeout_seconds = ' + str(int(timeout_seconds)))\n"
    "    if auth is not None:\n"
    "        lines.append('auth = ' + json.dumps(auth))\n"
    "    text = '\\n'.join(kept + lines) + '\\n'\n"
    "    p.write_text(text, encoding='utf-8')\n"
    "\n"
    "def load_config(config_path=None):\n"
    "    _log('load_config')\n"
    "    if config_path is None:\n"
    "        return None\n"
    "    p = Path(config_path)\n"
    "    if not p.exists():\n"
    "        return None\n"
    "    result = {'provider': None, 'model': None, 'base_url': None, 'api_key_env': None, 'timeout_seconds': None, 'auth': None}\n"
    "    in_llm = False\n"
    "    found = False\n"
    "    for line in p.read_text(encoding='utf-8').splitlines():\n"
    "        s = line.strip()\n"
    "        if s.startswith('[') and s.endswith(']'):\n"
    "            in_llm = (s == '[llm]')\n"
    "            found = found or in_llm\n"
    "            continue\n"
    "        if in_llm and '=' in s:\n"
    "            k, v = s.split('=', 1)\n"
    "            k = k.strip()\n"
    "            v = v.strip()\n"
    "            if k == 'timeout_seconds':\n"
    "                result[k] = int(v)\n"
    "            elif k in result:\n"
    "                result[k] = json.loads(v)\n"
    "    if not found:\n"
    "        return None\n"
    "    return result\n"
)

EXAMPLE_TEXT = "# Slugs\n\nexample slugs spec from the tool root\n"


def make_tool_root(base, log_path, with_endpoint=True):
    root = Path(base)
    root.mkdir(parents=True, exist_ok=True)
    if with_endpoint:
        ep = root / "gen" / "llm-endpoint"
        ep.mkdir(parents=True, exist_ok=True)
        src = FAKE_ENDPOINT_HEAD + "LOG_PATH = " + repr(str(log_path)) + "\n\n" + FAKE_ENDPOINT_BODY
        (ep / "llm_endpoint.py").write_text(src, encoding="utf-8")
    other = root / "gen" / "slugify"
    other.mkdir(parents=True, exist_ok=True)
    (other / "slugify.py").write_text("def slugify(text):\n    return text.lower()\n", encoding="utf-8")
    ex = root / "examples" / "slugify" / "specs" / "product"
    ex.mkdir(parents=True, exist_ok=True)
    (ex / "slugs.md").write_text(EXAMPLE_TEXT, encoding="utf-8")
    (root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    return root


def snapshot(root):
    root = Path(root)
    files = {}
    dirs = set()
    if not root.exists():
        return files, dirs
    for p in root.rglob("*"):
        rel = p.relative_to(root).as_posix()
        if p.is_dir():
            dirs.add(rel)
        else:
            files[rel] = p.read_bytes()
    return files, dirs


class Capture:
    def __init__(self):
        self.chunks = []

    def __call__(self, *args, **kwargs):
        sep = kwargs.get("sep", " ")
        self.chunks.append(sep.join(str(a) for a in args))

    def text(self):
        return "\n".join(self.chunks)

    def lines(self):
        return [ln for ln in self.text().splitlines() if ln.strip()]


def run(argv, tool_root, cwd):
    out = Capture()
    rc = hotdocs_init.main(
        argv,
        tool_root=tool_root,
        input_fn=lambda prompt: "",
        output_fn=out,
        env={"PATH": os.environ.get("PATH", "")},
        cwd=cwd,
    )
    return rc, out


def test_example_copies_slugs_and_prints_next_steps(tmp_path):
    log = tmp_path / "logs" / "llm.log"
    tool = make_tool_root(tmp_path / "tool", log)
    proj = tmp_path / "proj"
    proj.mkdir()

    rc, out = run([str(proj), "--example", "--yes"], tool, tmp_path)
    assert rc in (0, 3), out.text()

    copied = proj / "specs" / "product" / "slugs.md"
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == EXAMPLE_TEXT
    assert not (proj / "examples").exists()

    lines = out.lines()
    idx = max(i for i, ln in enumerate(lines) if "hotdocs lint" in ln)
    tail = "\n".join(lines[idx:])
    for needle in ("hotdocs lint", "hotdocs generate comp-slugify", "hotdocs verify", "QUICKSTART.md"):
        assert needle in tail, out.text()
    assert "QUICKSTART.md" in "\n".join(lines[-3:]) or lines[-1].find("hotdocs") >= 0 or "QUICKSTART.md" in tail


def test_example_never_overwrites_existing_file(tmp_path):
    log = tmp_path / "logs" / "llm.log"
    tool = make_tool_root(tmp_path / "tool", log)
    proj = tmp_path / "proj"
    existing = proj / "specs" / "product" / "slugs.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("my own slugs\n", encoding="utf-8")

    run([str(proj), "--example", "--yes"], tool, tmp_path)

    assert existing.read_text(encoding="utf-8") == "my own slugs\n"
    assert not (proj / "examples").exists()


def test_no_example_does_not_mention_comp_slugify(tmp_path):
    log = tmp_path / "logs" / "llm.log"
    tool = make_tool_root(tmp_path / "tool", log)
    proj = tmp_path / "proj"
    proj.mkdir()

    rc, out = run([str(proj), "--yes"], tool, tmp_path)
    assert rc in (0, 3), out.text()
    text = out.text()
    assert "comp-slugify" not in text
    assert "hotdocs lint" in text
    assert "hotdocs verify" in text
    assert "QUICKSTART.md" in text


def test_reconfigure_changes_only_hotdocs_toml(tmp_path):
    log = tmp_path / "logs" / "llm.log"
    tool = make_tool_root(tmp_path / "tool", log)
    proj = tmp_path / "proj"
    proj.mkdir()

    rc, out = run(
        [str(proj), "--yes", "--provider", "openai", "--model", "first-model", "--no-test"],
        tool,
        tmp_path,
    )
    assert rc in (0, 3), out.text()
    assert (proj / ".hotdocs-tool.json").is_file()
    assert (proj / "hotdocs.toml").is_file()

    before_files, before_dirs = snapshot(proj)
    tool_before = snapshot(tool)
    log_before = log.read_text(encoding="utf-8") if log.exists() else ""

    rc, out = run(
        [str(proj), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool,
        tmp_path,
    )
    assert rc == 0, out.text()

    after_files, after_dirs = snapshot(proj)
    assert after_dirs == before_dirs
    assert set(after_files) == set(before_files)
    changed = sorted(k for k in after_files if after_files[k] != before_files[k])
    assert changed == ["hotdocs.toml"]
    assert snapshot(tool) == tool_before

    new_log = (log.read_text(encoding="utf-8") if log.exists() else "")[len(log_before):]
    assert any(
        ln.startswith("save_config ") and "'m'" in ln for ln in new_log.splitlines()
    ), new_log


def test_reconfigure_without_endpoint_file_returns_1(tmp_path):
    log = tmp_path / "logs" / "llm.log"
    tool = make_tool_root(tmp_path / "tool", log)
    proj = tmp_path / "proj"
    proj.mkdir()

    rc, out = run(
        [str(proj), "--yes", "--provider", "openai", "--model", "first-model", "--no-test"],
        tool,
        tmp_path,
    )
    assert rc in (0, 3), out.text()
    assert (proj / ".hotdocs-tool.json").is_file()
    assert (proj / "hotdocs.toml").is_file()

    bare_tool = make_tool_root(tmp_path / "bare-tool", log, with_endpoint=False)
    assert not (bare_tool / "gen" / "llm-endpoint" / "llm_endpoint.py").exists()

    rc, out = run(
        [str(proj), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        bare_tool,
        tmp_path,
    )
    assert rc == 1


def test_reconfigure_on_uninitialised_dir_returns_1_and_writes_nothing(tmp_path, capsys):
    log = tmp_path / "logs" / "llm.log"
    tool = make_tool_root(tmp_path / "tool", log)
    proj = tmp_path / "proj"
    spec = proj / "specs" / "product" / "thing.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Thing\n", encoding="utf-8")

    before = snapshot(proj)
    tool_before = snapshot(tool)

    rc, out = run(
        [str(proj), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool,
        tmp_path,
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert snapshot(proj) == before
    assert snapshot(tool) == tool_before
    assert not (proj / "hotdocs.toml").exists()
    assert not (proj / ".hotdocs-tool.json").exists()
    assert (captured.err + out.text()).strip()