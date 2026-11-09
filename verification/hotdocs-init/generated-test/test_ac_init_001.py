import json
import os
import importlib.metadata
from pathlib import Path

import hotdocs_init


def _build_tool_root(base_dir: Path, log_path: Path) -> Path:
    tool_root = base_dir / "tool_root"
    tool_root.mkdir(parents=True)

    llm_endpoint_dir = tool_root / "gen" / "llm-endpoint"
    llm_endpoint_dir.mkdir(parents=True)

    fake_module = """
import json
from pathlib import Path

LOG_PATH = __LOG_PATH__


def _log(name):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(name + "\\n")


PROVIDERS = {
    "anthropic": {
        "default_base_url": None,
        "default_api_key_env": "ANTHROPIC_API_KEY",
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "openai": {
        "default_base_url": None,
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-4o",
    },
    "openai-compatible": {
        "default_base_url": None,
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": True,
        "suggested_model": "",
    },
    "gemini": {
        "default_base_url": None,
        "default_api_key_env": "GEMINI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gemini-2.0-flash",
    },
    "ollama": {
        "default_base_url": "http://localhost:11434",
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "llama3.1:8b",
    },
    "claude-cli": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
}


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers")
    return [
        {
            "provider": "anthropic",
            "available": False,
            "reason": "no api key set",
            "suggested_model": "claude-sonnet-5",
            "api_key_env": "ANTHROPIC_API_KEY",
        }
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log("check_connection")
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required for provider: " + str(provider))
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log("save_config")
    path = Path(config_path)
    kept_lines = []
    if path.exists():
        skip = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped == "[llm]":
                skip = True
                continue
            if skip and stripped.startswith("["):
                skip = False
            if not skip:
                kept_lines.append(line)
    kept_lines.append("[llm]")
    kept_lines.append("provider = " + json.dumps(provider))
    kept_lines.append("model = " + json.dumps(model))
    path.write_text("\\n".join(kept_lines) + "\\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config")
    return None
"""
    fake_module = fake_module.replace("__LOG_PATH__", json.dumps(str(log_path)))
    (llm_endpoint_dir / "llm_endpoint.py").write_text(fake_module, encoding="utf-8")

    slugify_dir = tool_root / "examples" / "slugify" / "specs" / "product"
    slugify_dir.mkdir(parents=True)
    (slugify_dir / "slugs.md").write_text("# Slugs\n\nExample slug list.\n", encoding="utf-8")

    pytest_version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text(
        "pytest==" + pytest_version + "\n", encoding="utf-8"
    )

    return tool_root


def _snapshot(root: Path):
    snap = {}
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        snap[("dir", rel_dir)] = os.stat(dirpath).st_mtime_ns
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            snap[("file", rel)] = (Path(full).read_bytes(), os.stat(full).st_mtime_ns)
    return snap


def _yes_input(prompt):
    return "y"


_EXPECTED_DIRS = ["specs/product", "specs/components", "specs/decisions", "gen", "verification"]
_EXPECTED_GITKEEPS = [
    "specs/product/.gitkeep",
    "specs/components/.gitkeep",
    "specs/decisions/.gitkeep",
    "verification/.gitkeep",
]
_EXPECTED_OTHERS = ["specs/glossary.md", ".secret-allowlist.json", ".gitignore"]
_EXPECTED_CREATED_PATHS = _EXPECTED_DIRS + _EXPECTED_GITKEEPS + _EXPECTED_OTHERS

_GITIGNORE_LINES = ["/.hotdocs/", "__pycache__/", "*.pyc", ".venv/"]


def test_init_creates_structure_and_second_run_is_noop(tmp_path):
    log_path = tmp_path / "logs" / "llm_endpoint_calls.log"
    log_path.parent.mkdir(parents=True)
    tool_root = _build_tool_root(tmp_path, log_path)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    env = {"PATH": os.environ.get("PATH", "")}

    outputs_first = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=str(tool_root),
        input_fn=_yes_input,
        output_fn=outputs_first.append,
        env=env,
    )

    for rel in _EXPECTED_DIRS:
        assert (project_dir / rel).is_dir()

    for rel in _EXPECTED_GITKEEPS:
        gitkeep_path = project_dir / rel
        assert gitkeep_path.is_file()
        assert gitkeep_path.read_text(encoding="utf-8") == ""

    glossary_text = (project_dir / "specs" / "glossary.md").read_text(encoding="utf-8")
    assert glossary_text.startswith("# Glossary")

    assert (project_dir / ".secret-allowlist.json").is_file()

    gitignore_lines = (project_dir / ".gitignore").read_text(encoding="utf-8").splitlines()
    for line in _GITIGNORE_LINES:
        assert gitignore_lines.count(line) == 1

    for rel in _EXPECTED_CREATED_PATHS:
        assert (rel + ": created") in outputs_first

    snapshot_before_second_run = _snapshot(project_dir)

    outputs_second = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=str(tool_root),
        input_fn=_yes_input,
        output_fn=outputs_second.append,
        env=env,
    )

    snapshot_after_second_run = _snapshot(project_dir)
    assert snapshot_after_second_run == snapshot_before_second_run

    for rel in _EXPECTED_CREATED_PATHS:
        assert (rel + ": skipped (exists)") in outputs_second


def test_init_preserves_existing_files_and_dedupes_gitignore(tmp_path):
    log_path = tmp_path / "logs" / "llm_endpoint_calls.log"
    log_path.parent.mkdir(parents=True)
    tool_root = _build_tool_root(tmp_path, log_path)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    specs_dir = project_dir / "specs"
    specs_dir.mkdir()
    (specs_dir / "glossary.md").write_text("mine", encoding="utf-8")
    (project_dir / ".gitignore").write_text("/.hotdocs/\n", encoding="utf-8")

    env = {"PATH": os.environ.get("PATH", "")}

    outputs = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=str(tool_root),
        input_fn=_yes_input,
        output_fn=outputs.append,
        env=env,
    )

    assert (specs_dir / "glossary.md").read_text(encoding="utf-8") == "mine"

    gitignore_lines = (project_dir / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert gitignore_lines.count("/.hotdocs/") == 1
    for line in ["__pycache__/", "*.pyc", ".venv/"]:
        assert gitignore_lines.count(line) == 1