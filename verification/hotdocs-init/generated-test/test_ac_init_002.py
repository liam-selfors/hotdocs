# hotdocs-criterion: sha256:114e61c1c6554564f662617b1e86632cb1e923ea58e721b974e8091f1dd84030
import importlib.metadata
import json
import os
import time
from pathlib import Path

import pytest

import hotdocs_init


PYPROJECT_TEXT = '[project]\nname = "hotdocs"\nversion = "9.8.7a1"\n'


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_llm_endpoint_source(log_path):
    src = ""
    src += "import json\n"
    src += "import tomllib\n"
    src += "from pathlib import Path\n"
    src += "\n"
    src += "_LOG_PATH = " + repr(str(log_path)) + "\n"
    src += "\n"
    src += "def _log(name):\n"
    src += "    with open(_LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    src += "        fh.write(name + '\\n')\n"
    src += "\n"
    src += "PROVIDERS = {\n"
    src += "    'claude-cli': {'default_base_url': None, 'default_api_key_env': None, 'needs_base_url': False, 'suggested_model': 'claude-sonnet-5'},\n"
    src += "    'anthropic': {'default_base_url': 'https://api.anthropic.com', 'default_api_key_env': 'ANTHROPIC_API_KEY', 'needs_base_url': False, 'suggested_model': 'claude-sonnet-5'},\n"
    src += "    'openai': {'default_base_url': 'https://api.openai.com/v1', 'default_api_key_env': 'OPENAI_API_KEY', 'needs_base_url': False, 'suggested_model': 'gpt-6-astra'},\n"
    src += "    'openai-compatible': {'default_base_url': None, 'default_api_key_env': None, 'needs_base_url': True, 'suggested_model': ''},\n"
    src += "    'gemini': {'default_base_url': 'https://generativelanguage.googleapis.com', 'default_api_key_env': 'GEMINI_API_KEY', 'needs_base_url': False, 'suggested_model': 'gemini-4-argon'},\n"
    src += "    'ollama': {'default_base_url': 'http://localhost:11434', 'default_api_key_env': None, 'needs_base_url': False, 'suggested_model': 'llama3.2'},\n"
    src += "}\n"
    src += "\n"
    src += "def detect_providers(env=None, probe_ollama=True):\n"
    src += "    _log('detect_providers')\n"
    src += "    out = []\n"
    src += "    for name, info in PROVIDERS.items():\n"
    src += "        available = name == 'ollama'\n"
    src += "        out.append({'provider': name, 'available': available,\n"
    src += "                    'reason': 'fake' if available else 'fake: unavailable',\n"
    src += "                    'suggested_model': info['suggested_model'],\n"
    src += "                    'api_key_env': info['default_api_key_env']})\n"
    src += "    return out\n"
    src += "\n"
    src += "def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30, auth=None):\n"
    src += "    _log('check_connection')\n"
    src += "    if provider not in PROVIDERS:\n"
    src += "        raise ValueError('unknown provider')\n"
    src += "    if PROVIDERS[provider]['needs_base_url'] and not base_url:\n"
    src += "        raise ValueError('base_url required')\n"
    src += "    return {'ok': True, 'error': None}\n"
    src += "\n"
    src += "def _strip_llm(text):\n"
    src += "    lines = text.splitlines()\n"
    src += "    kept = []\n"
    src += "    in_llm = False\n"
    src += "    for line in lines:\n"
    src += "        s = line.strip()\n"
    src += "        if s.startswith('[') and s.endswith(']'):\n"
    src += "            in_llm = s == '[llm]'\n"
    src += "            if in_llm:\n"
    src += "                continue\n"
    src += "        if not in_llm:\n"
    src += "            kept.append(line)\n"
    src += "    return '\\n'.join(kept).rstrip()\n"
    src += "\n"
    src += "def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None, auth=None):\n"
    src += "    _log('save_config')\n"
    src += "    if provider not in PROVIDERS or not model:\n"
    src += "        raise ValueError('invalid config')\n"
    src += "    path = Path(config_path)\n"
    src += "    path.parent.mkdir(parents=True, exist_ok=True)\n"
    src += "    existing = path.read_text(encoding='utf-8') if path.exists() else ''\n"
    src += "    head = _strip_llm(existing)\n"
    src += "    body = '[llm]\\n'\n"
    src += "    body += 'provider = ' + json.dumps(provider) + '\\n'\n"
    src += "    body += 'model = ' + json.dumps(model) + '\\n'\n"
    src += "    if base_url is not None:\n"
    src += "        body += 'base_url = ' + json.dumps(base_url) + '\\n'\n"
    src += "    if api_key_env is not None:\n"
    src += "        body += 'api_key_env = ' + json.dumps(api_key_env) + '\\n'\n"
    src += "    if timeout_seconds is not None:\n"
    src += "        body += 'timeout_seconds = ' + str(int(timeout_seconds)) + '\\n'\n"
    src += "    if auth is not None:\n"
    src += "        body += 'auth = ' + json.dumps(auth) + '\\n'\n"
    src += "    text = (head + '\\n\\n' + body) if head else body\n"
    src += "    path.write_text(text, encoding='utf-8')\n"
    src += "\n"
    src += "def load_config(config_path=None):\n"
    src += "    _log('load_config')\n"
    src += "    path = Path(config_path) if config_path is not None else Path('hotdocs.toml')\n"
    src += "    if not path.exists():\n"
    src += "        return None\n"
    src += "    try:\n"
    src += "        data = tomllib.loads(path.read_text(encoding='utf-8'))\n"
    src += "    except Exception as exc:\n"
    src += "        raise ValueError('invalid config') from exc\n"
    src += "    llm = data.get('llm')\n"
    src += "    if llm is None:\n"
    src += "        return None\n"
    src += "    return {'provider': llm.get('provider'), 'model': llm.get('model'),\n"
    src += "            'base_url': llm.get('base_url'), 'api_key_env': llm.get('api_key_env'),\n"
    src += "            'timeout_seconds': llm.get('timeout_seconds'), 'auth': llm.get('auth')}\n"
    return src


def make_tool_root(base, with_pyproject):
    tool_root = base / "tool"
    log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "llm_endpoint_calls.log"

    llm_dir = tool_root / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    (llm_dir / "llm_endpoint.py").write_text(_fake_llm_endpoint_source(log_path), encoding="utf-8")

    ab_dir = tool_root / "gen" / "a-b"
    ab_dir.mkdir(parents=True)
    (ab_dir / "a_b.py").write_text("VALUE = " + repr("a-b") + "\n", encoding="utf-8")

    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nA fake example product spec.\n", encoding="utf-8")

    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    if with_pyproject:
        (tool_root / "pyproject.toml").write_text(PYPROJECT_TEXT, encoding="utf-8")
    return tool_root, log_path


def make_env(base):
    home = base / "home"
    home.mkdir(exist_ok=True)
    return {"PATH": os.environ.get("PATH", ""), "HOME": str(home)}


def make_input_fn():
    calls = []

    def input_fn(prompt=""):
        calls.append(prompt)
        if len(calls) > 50:
            raise RuntimeError("too many questions asked")
        return ""

    return input_fn


def invoke(target, tool_root, base):
    outputs = []

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    argv = [
        str(target),
        "--provider", "ollama",
        "--model", "llama3.2",
        "--no-test",
        "--yes",
    ]
    code = hotdocs_init.run(
        argv,
        tool_root=tool_root,
        input_fn=make_input_fn(),
        output_fn=output_fn,
        env=make_env(base),
        cwd=str(target),
    )
    return code, outputs


def snapshot(root):
    root = Path(root)
    result = {}
    st = root.stat()
    result["."] = ("dir", None, st.st_mtime_ns)
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            p = Path(dirpath) / d
            result[str(p.relative_to(root))] = ("dir", None, p.stat().st_mtime_ns)
        for f in filenames:
            p = Path(dirpath) / f
            result[str(p.relative_to(root))] = ("file", p.read_bytes(), p.stat().st_mtime_ns)
    return result


def read_marker(target):
    return json.loads((target / ".hotdocs-tool.json").read_text(encoding="utf-8"))


def test_init_writes_empty_gen_and_version_marker(tmp_path):
    tool_root, _ = make_tool_root(tmp_path, with_pyproject=True)
    target = tmp_path / "project"
    target.mkdir()

    code, _ = invoke(target, tool_root, tmp_path)
    assert code in (0, 3)

    gen = target / "gen"
    assert gen.is_dir()
    assert list(gen.iterdir()) == []
    others = {p.name for p in target.iterdir()} - {"gen", ".hotdocs-tool.json"}
    assert others, "expected R-INIT-001's other entries beside gen/"
    assert not (target / "pipeline").exists()
    assert not (target / "gen" / "a-b").exists()
    assert not (target / "gen" / "llm-endpoint").exists()

    assert read_marker(target) == {"tool_version": "9.8.7a1"}


def test_init_without_pyproject_writes_unknown(tmp_path):
    tool_root, _ = make_tool_root(tmp_path, with_pyproject=False)
    target = tmp_path / "project"
    target.mkdir()

    code, _ = invoke(target, tool_root, tmp_path)
    assert code in (0, 3)

    assert read_marker(target) == {"tool_version": "unknown"}


def test_second_run_leaves_marker_untouched(tmp_path):
    tool_root, _ = make_tool_root(tmp_path, with_pyproject=True)
    target = tmp_path / "project"
    target.mkdir()

    code, _ = invoke(target, tool_root, tmp_path)
    assert code in (0, 3)
    marker = target / ".hotdocs-tool.json"
    before_bytes = marker.read_bytes()
    before_mtime = marker.stat().st_mtime_ns

    time.sleep(0.05)
    code2, _ = invoke(target, tool_root, tmp_path)
    assert code2 in (0, 3)

    assert marker.read_bytes() == before_bytes
    assert marker.stat().st_mtime_ns == before_mtime


def test_collision_with_tool_component_refuses(tmp_path, capsys):
    tool_root, log_path = make_tool_root(tmp_path, with_pyproject=True)
    target = tmp_path / "project"
    (target / "gen" / "a-b").mkdir(parents=True)
    (target / "gen" / "mine").mkdir(parents=True)

    target_before = snapshot(target)
    tool_before = snapshot(tool_root)
    capsys.readouterr()

    code, outputs = invoke(target, tool_root, tmp_path)
    captured = capsys.readouterr()
    assert code == 1

    text = captured.err + "\n" + captured.out + "\n" + "\n".join(outputs)
    assert "gen/a-b" in text
    assert "gen/mine" not in text

    assert snapshot(target) == target_before
    assert snapshot(tool_root) == tool_before
    assert not log_path.exists()


def test_target_is_tool_root_refuses(tmp_path, capsys):
    tool_root, log_path = make_tool_root(tmp_path, with_pyproject=True)
    tool_before = snapshot(tool_root)
    capsys.readouterr()

    code, _ = invoke(tool_root, tool_root, tmp_path)
    capsys.readouterr()
    assert code == 1

    assert snapshot(tool_root) == tool_before
    assert not (tool_root / ".hotdocs-tool.json").exists()
    assert not log_path.exists()