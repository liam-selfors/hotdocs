# hotdocs-criterion: sha256:9cafaf73733ad8725bdcaad46e9e05f8e209f4aebc2e8f3586f3cb91038eacc2
import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


PYPROJECT = '[project]\nname = "hotdocs"\nversion = "9.8.7a1"\n'


def _fake_llm_endpoint_source(log_path):
    lines = [
        "import json",
        "import tomllib",
        "from pathlib import Path",
        "",
        "_LOG = " + repr(str(log_path)),
        "",
        "def _log(name, **kwargs):",
        "    with open(_LOG, 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps({'call': name, 'args': {k: str(v) for k, v in kwargs.items()}}) + '\\n')",
        "",
        "PROVIDERS = {",
        "    'claude-cli': {'default_base_url': None, 'default_api_key_env': None, 'needs_base_url': False, 'suggested_model': 'claude-sonnet-5'},",
        "    'anthropic': {'default_base_url': 'https://api.anthropic.com', 'default_api_key_env': 'ANTHROPIC_API_KEY', 'needs_base_url': False, 'suggested_model': 'claude-sonnet-5'},",
        "    'openai': {'default_base_url': 'https://api.openai.com/v1', 'default_api_key_env': 'OPENAI_API_KEY', 'needs_base_url': False, 'suggested_model': 'gpt-6-astra'},",
        "    'openai-compatible': {'default_base_url': None, 'default_api_key_env': None, 'needs_base_url': True, 'suggested_model': ''},",
        "    'gemini': {'default_base_url': 'https://generativelanguage.googleapis.com', 'default_api_key_env': 'GEMINI_API_KEY', 'needs_base_url': False, 'suggested_model': 'gemini-4-argon'},",
        "    'ollama': {'default_base_url': 'http://localhost:11434', 'default_api_key_env': None, 'needs_base_url': False, 'suggested_model': 'llama3.2'},",
        "}",
        "",
        "def detect_providers(env=None, probe_ollama=True):",
        "    _log('detect_providers', env=env is not None, probe_ollama=probe_ollama)",
        "    out = []",
        "    for name, info in PROVIDERS.items():",
        "        out.append({",
        "            'provider': name,",
        "            'available': name == 'ollama',",
        "            'reason': 'fake' if name == 'ollama' else 'not available (fake)',",
        "            'suggested_model': info['suggested_model'],",
        "            'api_key_env': info['default_api_key_env'],",
        "        })",
        "    return out",
        "",
        "def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30, auth=None):",
        "    _log('check_connection', provider=provider, model=model)",
        "    if provider not in PROVIDERS:",
        "        raise ValueError('unknown provider')",
        "    if PROVIDERS[provider]['needs_base_url'] and not base_url:",
        "        raise ValueError('base_url required')",
        "    return {'ok': True, 'error': None}",
        "",
        "def _q(value):",
        "    return json.dumps(value)",
        "",
        "def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None, auth=None):",
        "    _log('save_config', config_path=config_path, provider=provider, model=model)",
        "    if provider not in PROVIDERS:",
        "        raise ValueError('unknown provider')",
        "    path = Path(config_path)",
        "    path.parent.mkdir(parents=True, exist_ok=True)",
        "    kept = []",
        "    if path.exists():",
        "        for line in path.read_text(encoding='utf-8').splitlines():",
        "            if line.strip() == '[llm]':",
        "                break",
        "            kept.append(line)",
        "    body = ['[llm]', 'provider = ' + _q(provider), 'model = ' + _q(model)]",
        "    if base_url is not None:",
        "        body.append('base_url = ' + _q(base_url))",
        "    if api_key_env is not None:",
        "        body.append('api_key_env = ' + _q(api_key_env))",
        "    if timeout_seconds is not None:",
        "        body.append('timeout_seconds = ' + str(int(timeout_seconds)))",
        "    if auth is not None:",
        "        body.append('auth = ' + _q(auth))",
        "    path.write_text('\\n'.join(kept + body) + '\\n', encoding='utf-8')",
        "",
        "def load_config(config_path=None):",
        "    _log('load_config', config_path=config_path)",
        "    path = Path(config_path) if config_path is not None else Path('hotdocs.toml')",
        "    if not path.is_file():",
        "        return None",
        "    try:",
        "        data = tomllib.loads(path.read_text(encoding='utf-8'))",
        "    except Exception as exc:",
        "        raise ValueError('invalid config') from exc",
        "    llm = data.get('llm')",
        "    if llm is None:",
        "        return None",
        "    return {",
        "        'provider': llm.get('provider'),",
        "        'model': llm.get('model'),",
        "        'base_url': llm.get('base_url'),",
        "        'api_key_env': llm.get('api_key_env'),",
        "        'timeout_seconds': llm.get('timeout_seconds'),",
        "        'auth': llm.get('auth'),",
        "    }",
        "",
    ]
    return "\n".join(lines)


def make_tool_root(tmp_path, with_pyproject=True):
    root = tmp_path / "tool"
    log_path = tmp_path / "llm_calls.log"
    (root / "gen" / "llm-endpoint").mkdir(parents=True)
    (root / "gen" / "llm-endpoint" / "llm_endpoint.py").write_text(
        _fake_llm_endpoint_source(log_path), encoding="utf-8"
    )
    (root / "gen" / "a-b").mkdir(parents=True)
    (root / "gen" / "a-b" / "a_b.py").write_text("VALUE = 1\n", encoding="utf-8")
    slugs = root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nA fake product spec.\n", encoding="utf-8")
    (root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    if with_pyproject:
        (root / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    return root, log_path


def snapshot(root):
    root = Path(root)
    result = {}
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        rel = d.relative_to(root).as_posix()
        result[("dir", rel)] = d.stat().st_mtime_ns
        for name in filenames:
            p = d / name
            st = p.stat()
            result[("file", p.relative_to(root).as_posix())] = (p.read_bytes(), st.st_mtime_ns)
    return result


ARGS = ["--yes", "--no-test", "--provider", "ollama", "--model", "llama3.2"]


def run_init(target, tool_root, tmp_path, extra=None):
    messages = []
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(home)}
    argv = [str(target)] + ARGS + (extra or [])
    rc = hotdocs_init.run(
        argv,
        tool_root=tool_root,
        input_fn=lambda prompt: "",
        output_fn=lambda *a, **k: messages.append(" ".join(str(x) for x in a)),
        env=env,
        cwd=str(target),
    )
    return rc, "\n".join(messages)


def read_marker(target):
    return json.loads((target / ".hotdocs-tool.json").read_text(encoding="utf-8"))


def test_init_writes_empty_gen_and_version_marker(tmp_path):
    tool_root, _log = make_tool_root(tmp_path, with_pyproject=True)
    target = tmp_path / "proj"
    target.mkdir()

    rc, _out = run_init(target, tool_root, tmp_path)
    assert rc in (0, 3)

    gen = target / "gen"
    assert gen.is_dir()
    assert list(gen.iterdir()) == []
    others = {p.name for p in target.iterdir()} - {"gen", ".hotdocs-tool.json"}
    assert others, "expected R-INIT-001's other entries beside gen/"

    assert not (target / "pipeline").exists()
    assert not list(target.rglob("pipeline"))
    assert not list(target.rglob("a_b.py"))
    assert not list(target.rglob("llm_endpoint.py"))

    assert read_marker(target) == {"tool_version": "9.8.7a1"}


def test_init_without_pyproject_writes_unknown_version(tmp_path):
    tool_root, _log = make_tool_root(tmp_path, with_pyproject=False)
    target = tmp_path / "proj"
    target.mkdir()

    rc, _out = run_init(target, tool_root, tmp_path)
    assert rc in (0, 3)

    assert read_marker(target) == {"tool_version": "unknown"}


def test_second_run_leaves_marker_untouched(tmp_path):
    tool_root, _log = make_tool_root(tmp_path, with_pyproject=True)
    target = tmp_path / "proj"
    target.mkdir()

    rc, _out = run_init(target, tool_root, tmp_path)
    assert rc in (0, 3)
    marker = target / ".hotdocs-tool.json"
    before_bytes = marker.read_bytes()
    before_mtime = marker.stat().st_mtime_ns

    rc2, _out2 = run_init(target, tool_root, tmp_path)
    assert rc2 in (0, 3)

    assert marker.read_bytes() == before_bytes
    assert marker.stat().st_mtime_ns == before_mtime


def test_shadowing_component_refused_and_nothing_written(tmp_path, capsys):
    tool_root, log_path = make_tool_root(tmp_path, with_pyproject=True)
    target = tmp_path / "proj"
    (target / "gen" / "a-b").mkdir(parents=True)
    (target / "gen" / "mine").mkdir(parents=True)

    target_before = snapshot(target)
    tool_before = snapshot(tool_root)
    capsys.readouterr()

    rc, out = run_init(target, tool_root, tmp_path)
    captured = capsys.readouterr()
    text = out + "\n" + captured.out + "\n" + captured.err

    assert rc == 1
    assert "gen/a-b" in text
    assert "gen/mine" not in text

    assert snapshot(target) == target_before
    assert snapshot(tool_root) == tool_before
    assert not log_path.exists() or log_path.read_text(encoding="utf-8") == ""


def test_target_is_tool_root_refused_and_nothing_written(tmp_path, capsys):
    tool_root, log_path = make_tool_root(tmp_path, with_pyproject=True)

    tool_before = snapshot(tool_root)
    capsys.readouterr()

    rc, _out = run_init(tool_root, tool_root, tmp_path)
    capsys.readouterr()

    assert rc == 1
    assert snapshot(tool_root) == tool_before
    assert not log_path.exists() or log_path.read_text(encoding="utf-8") == ""