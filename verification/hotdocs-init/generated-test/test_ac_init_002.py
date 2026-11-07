import json
import os
from importlib.metadata import version as _pkg_version
from pathlib import Path

import hotdocs_init


LLM_ENDPOINT_TEMPLATE = '''
import os
from pathlib import Path

LOG_PATH = __LOG_PATH__


def _log(name):
    with open(LOG_PATH, "a") as f:
        f.write(name + "\\n")


PROVIDERS = {
    "anthropic": {"default_base_url": None, "default_api_key_env": "ANTHROPIC_API_KEY", "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "openai": {"default_base_url": "https://api.openai.com/v1", "default_api_key_env": "OPENAI_API_KEY", "needs_base_url": False, "suggested_model": "gpt-4o"},
    "openai-compatible": {"default_base_url": None, "default_api_key_env": None, "needs_base_url": True, "suggested_model": ""},
    "gemini": {"default_base_url": None, "default_api_key_env": "GEMINI_API_KEY", "needs_base_url": False, "suggested_model": "gemini-2.0-flash"},
    "ollama": {"default_base_url": "http://localhost:11434", "default_api_key_env": None, "needs_base_url": False, "suggested_model": "llama3.1:8b"},
    "claude-cli": {"default_base_url": None, "default_api_key_env": None, "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
}


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers")
    result = []
    for name, info in PROVIDERS.items():
        available = name == "ollama"
        result.append({
            "provider": name,
            "available": available,
            "reason": "fake-available" if available else "fake-unavailable",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return result


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log("check_connection")
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required for " + str(provider))
    return {"ok": True, "error": None}


def _parse_llm_section(text):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "[llm]":
            start = i
            break
    if start is None:
        return None, lines, None, None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].strip().startswith("["):
            end = i
            break
    data = {}
    for line in lines[start + 1:end]:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip().strip('"')
    return data, lines, start, end


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log("save_config")
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    path = Path(config_path)
    text = path.read_text() if path.exists() else ""
    _, lines, start, end = _parse_llm_section(text)
    section = ["[llm]", 'provider = "' + provider + '"', 'model = "' + model + '"']
    if base_url is not None:
        section.append('base_url = "' + base_url + '"')
    if api_key_env is not None:
        section.append('api_key_env = "' + api_key_env + '"')
    if timeout_seconds is not None:
        section.append("timeout_seconds = " + str(int(timeout_seconds)))
    if start is None:
        new_lines = lines + ([""] if lines else []) + section
    else:
        new_lines = lines[:start] + section + lines[end:]
    path.write_text("\\n".join(new_lines) + "\\n")


def load_config(config_path=None):
    _log("load_config")
    path = Path(config_path) if config_path is not None else Path("hotdocs.toml")
    if not path.exists():
        return None
    data, _lines, start, _end = _parse_llm_section(path.read_text())
    if start is None:
        return None
    timeout = data.get("timeout_seconds")
    return {
        "provider": data.get("provider"),
        "model": data.get("model"),
        "base_url": data.get("base_url"),
        "api_key_env": data.get("api_key_env"),
        "timeout_seconds": int(timeout) if timeout else None,
    }
'''


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _make_tool_root(base: Path, log_path: Path) -> Path:
    tool_root = base / "tool_root"
    tool_root.mkdir(parents=True)

    llm_endpoint_src = LLM_ENDPOINT_TEMPLATE.replace(
        "__LOG_PATH__", repr(str(log_path))
    )
    _write(tool_root / "gen" / "llm-endpoint" / "llm_endpoint.py", llm_endpoint_src)

    _write(tool_root / "gen" / "a-b" / "a_b.py", "MARKER = 'a-b'\n")

    pycache_dir = tool_root / "gen" / "c" / "__pycache__"
    pycache_dir.mkdir(parents=True)
    (pycache_dir / "x.pyc").write_bytes(b"\x00\x01fakebytecode")

    _write(
        tool_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "MARKER = 'criterion-compiler'\n",
    )

    pytest_version = _pkg_version("pytest")
    _write(tool_root / "requirements.txt", "pytest==%s\n" % pytest_version)

    return tool_root


def _walk_pycache_dirs(root: Path):
    found = []
    for dirpath, dirnames, _filenames in os.walk(root):
        if "__pycache__" in dirnames:
            found.append(os.path.join(dirpath, "__pycache__"))
    return found


def _snapshot(root: Path):
    dirs = set()
    files = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        if str(rel_dir) != ".":
            dirs.add(str(rel_dir))
        for name in filenames:
            p = Path(dirpath) / name
            rel = p.relative_to(root)
            files[str(rel)] = p.read_bytes()
    return dirs, files


def _noop_input(_prompt):
    return ""


def test_ac_init_002_first_run_vendors_then_second_run_skips(tmp_path):
    log_path = tmp_path / "llm_endpoint_calls.log"
    tool_root = _make_tool_root(tmp_path / "tool", log_path)

    project = tmp_path / "project"
    project.mkdir()

    outputs1 = []
    ret1 = hotdocs_init.main(
        [str(project), "--yes"],
        tool_root=tool_root,
        input_fn=_noop_input,
        output_fn=outputs1.append,
        env={},
    )

    assert ret1 in (0, 3)

    copied_a_b = project / "gen" / "a-b" / "a_b.py"
    copied_cc = project / "pipeline" / "criterion-compiler" / "criterion_compiler.py"
    copied_llm = project / "gen" / "llm-endpoint" / "llm_endpoint.py"

    assert copied_a_b.is_file()
    assert not copied_a_b.is_symlink()
    assert copied_a_b.read_text() == (tool_root / "gen" / "a-b" / "a_b.py").read_text()

    assert copied_cc.is_file()
    assert not copied_cc.is_symlink()
    assert copied_cc.read_text() == (
        tool_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py"
    ).read_text()

    assert copied_llm.is_file()

    assert _walk_pycache_dirs(project) == []

    assert log_path.is_file()
    assert log_path.read_text() != ""

    stamp_path = project / ".hotdocs-tool.json"
    assert stamp_path.is_file()
    stamp = json.loads(stamp_path.read_text())

    assert stamp["tool_version"] == "0.1.0"
    assert stamp["vendored"] == [
        "gen/a-b",
        "gen/c",
        "gen/llm-endpoint",
        "pipeline/criterion-compiler",
    ]

    content_hash = stamp["content_hash"]
    assert content_hash.startswith("sha256:")
    assert len(content_hash) > len("sha256:")

    assert _walk_pycache_dirs(project) == []

    stamp_bytes_before = stamp_path.read_bytes()

    # corrupt a vendored file so a recopy on the next run would be detectable
    copied_a_b.write_text("CORRUPTED\n")

    outputs2 = []
    ret2 = hotdocs_init.main(
        [str(project), "--yes"],
        tool_root=tool_root,
        input_fn=_noop_input,
        output_fn=outputs2.append,
        env={},
    )

    assert ret2 in (0, 3)

    joined_output2 = "\n".join(str(o) for o in outputs2)
    assert "skip" in joined_output2.lower()
    assert "gen/a-b" in joined_output2
    assert "gen/c" in joined_output2
    assert "gen/llm-endpoint" in joined_output2
    assert "pipeline/criterion-compiler" in joined_output2

    # not recopied: the corruption survives
    assert copied_a_b.read_text() == "CORRUPTED\n"

    # existing stamp left untouched, byte for byte
    assert stamp_path.read_bytes() == stamp_bytes_before

    assert _walk_pycache_dirs(project) == []


def test_ac_init_002_collision_names_path_and_writes_nothing(tmp_path, capsys):
    log_path = tmp_path / "llm_endpoint_calls.log"
    tool_root = _make_tool_root(tmp_path / "tool", log_path)

    project = tmp_path / "project"
    (project / "gen" / "a-b").mkdir(parents=True)
    (project / "gen" / "a-b" / "preexisting.txt").write_text("already here\n")

    before = _snapshot(project)

    ret = hotdocs_init.main(
        [str(project), "--yes"],
        tool_root=tool_root,
        input_fn=_noop_input,
        output_fn=lambda *_a, **_k: None,
        env={},
    )

    captured = capsys.readouterr()

    assert ret == 1
    assert "gen/a-b" in captured.err

    after = _snapshot(project)
    assert after == before
    assert not (project / ".hotdocs-tool.json").exists()


def test_ac_init_002_target_is_tool_root_writes_nothing(tmp_path):
    log_path = tmp_path / "llm_endpoint_calls.log"
    tool_root = _make_tool_root(tmp_path / "tool", log_path)

    before = _snapshot(tool_root)

    ret = hotdocs_init.main(
        [str(tool_root), "--yes"],
        tool_root=tool_root,
        input_fn=_noop_input,
        output_fn=lambda *_a, **_k: None,
        env={},
    )

    assert ret == 1

    after = _snapshot(tool_root)
    assert after == before
    assert not (tool_root / ".hotdocs-tool.json").exists()