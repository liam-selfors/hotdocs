import importlib.metadata
import json
from pathlib import Path

import hotdocs_init


def _write_fake_llm_endpoint(gen_dir: Path, log_path: Path) -> None:
    module_path = gen_dir / "llm-endpoint" / "llm_endpoint.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    content = '''
import json as _json

_LOG_PATH = __LOG_PATH__


def _log(call):
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(_json.dumps(call) + "\\n")


PROVIDERS = {
    "anthropic": {
        "default_base_url": None,
        "default_api_key_env": "ANTHROPIC_API_KEY",
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
}


def detect_providers(env=None, probe_ollama=True):
    _log({"fn": "detect_providers"})
    return [
        {
            "provider": "anthropic",
            "available": False,
            "reason": "no api key",
            "suggested_model": "claude-sonnet-5",
            "api_key_env": "ANTHROPIC_API_KEY",
        }
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log({"fn": "check_connection"})
    return {"ok": False, "error": {"category": "auth", "message": "no credentials"}}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log({"fn": "save_config"})
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            existing = f.read()
    except OSError:
        existing = ""
    kept = [line for line in existing.splitlines() if line.strip() != "[llm]"]
    kept.append("[llm]")
    kept.append("provider = " + _json.dumps(provider))
    kept.append("model = " + _json.dumps(model))
    if base_url is not None:
        kept.append("base_url = " + _json.dumps(base_url))
    if api_key_env is not None:
        kept.append("api_key_env = " + _json.dumps(api_key_env))
    if timeout_seconds is not None:
        kept.append("timeout_seconds = " + str(timeout_seconds))
    with open(config_path, "w", encoding="utf-8") as f:
        f.write("\\n".join(kept) + "\\n")


def load_config(config_path=None):
    _log({"fn": "load_config"})
    return None
'''
    content = content.replace("__LOG_PATH__", json.dumps(str(log_path)))
    module_path.write_text(content, encoding="utf-8")


def _make_fake_tool_root(base: Path, log_path: Path) -> Path:
    tool_root = base / "tool_root"
    gen_dir = tool_root / "gen"
    _write_fake_llm_endpoint(gen_dir, log_path)

    example_dir = tool_root / "examples" / "slugify" / "specs" / "product"
    example_dir.mkdir(parents=True, exist_ok=True)
    (example_dir / "slugs.md").write_text(
        "A tiny fixture product doc for the slugify example.\n",
        encoding="utf-8",
    )

    pytest_version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text(
        "pytest==" + pytest_version + "\n", encoding="utf-8"
    )

    return tool_root


def _capture(outputs):
    def _fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    return _fn


def test_empty_allowlist_written_and_no_decision_file(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    log_path = tmp_path / "llm_endpoint_calls.log"
    tool_root = _make_fake_tool_root(tmp_path, log_path)

    outputs = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        output_fn=_capture(outputs),
        env={},
        cwd=str(project_dir),
    )

    allowlist_path = project_dir / ".secret-allowlist.json"
    assert allowlist_path.exists()
    expected_bytes = (
        json.dumps({"version": 1, "entries": []}, indent=2) + "\n"
    ).encode("utf-8")
    assert allowlist_path.read_bytes() == expected_bytes

    decisions_dir = project_dir / "specs" / "decisions"
    assert decisions_dir.is_dir()
    entries = sorted(p.name for p in decisions_dir.iterdir())
    assert entries == [".gitkeep"]


def test_existing_allowlist_is_skipped(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    log_path = tmp_path / "llm_endpoint_calls.log"
    tool_root = _make_fake_tool_root(tmp_path, log_path)

    allowlist_path = project_dir / ".secret-allowlist.json"
    existing_bytes = b'{"version": 1, "entries": ["unchanged"]}'
    allowlist_path.write_bytes(existing_bytes)

    outputs = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        output_fn=_capture(outputs),
        env={},
        cwd=str(project_dir),
    )

    assert allowlist_path.read_bytes() == existing_bytes
    assert ".secret-allowlist.json: skipped (exists)" in outputs