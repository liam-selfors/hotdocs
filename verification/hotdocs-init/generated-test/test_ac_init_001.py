import importlib.metadata
from pathlib import Path

import pytest

import hotdocs_init


FAKE_LLM_ENDPOINT_TEMPLATE = '''
import json as _json

_LOG_PATH = %(log_path)r


def _log(call):
    with open(_LOG_PATH, "a") as f:
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
            "available": True,
            "reason": None,
            "suggested_model": "claude-sonnet-5",
            "api_key_env": "ANTHROPIC_API_KEY",
        }
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log({"fn": "check_connection", "provider": provider, "model": model})
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log({"fn": "save_config", "provider": provider, "model": model})
    existing = ""
    try:
        with open(config_path, "r") as f:
            existing = f.read()
    except FileNotFoundError:
        pass
    with open(config_path, "w") as f:
        f.write(existing + "\\n[llm]\\n")


def load_config(config_path=None):
    _log({"fn": "load_config"})
    return None
'''


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _make_fake_tool_root(tmp_path: Path, log_path: Path) -> Path:
    tool_root = tmp_path / "fake_tool_root"
    tool_root.mkdir()

    pytest_version = importlib.metadata.version("pytest")
    _write(tool_root / "requirements.txt", "pytest==" + pytest_version + "\n")

    _write(
        tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md",
        "# Slugs\n\nExample slugify product spec.\n",
    )

    fake_module_content = FAKE_LLM_ENDPOINT_TEMPLATE % {"log_path": str(log_path)}
    _write(tool_root / "gen" / "llm-endpoint" / "llm_endpoint.py", fake_module_content)

    return tool_root


def _snapshot(root: Path):
    snap = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            snap[rel] = (p.read_bytes(), p.stat().st_mtime_ns)
    return snap


def _no_prompt_input_fn(prompt):
    return "y"


EXPECTED_DIRS = [
    "specs/product",
    "specs/components",
    "specs/decisions",
    "gen",
    "verification",
]

EXPECTED_GITKEEP_DIRS = [
    "specs/product",
    "specs/components",
    "specs/decisions",
    "verification",
]

EXPECTED_OTHER_FILES = [
    "specs/glossary.md",
    ".secret-allowlist.json",
    ".gitignore",
]

GITIGNORE_LINES = ["/.hotdocs/", "__pycache__/", "*.pyc", ".venv/"]


def test_init_creates_structure_then_is_idempotent(tmp_path):
    log_path = tmp_path / "fake_dep_log.jsonl"
    tool_root = _make_fake_tool_root(tmp_path, log_path)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    first_outputs = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        input_fn=_no_prompt_input_fn,
        output_fn=first_outputs.append,
        env={},
    )

    for d in EXPECTED_DIRS:
        assert (project_dir / d).is_dir()

    for d in EXPECTED_GITKEEP_DIRS:
        gitkeep = project_dir / d / ".gitkeep"
        assert gitkeep.is_file()
        assert gitkeep.read_bytes() == b""

    glossary_text = (project_dir / "specs" / "glossary.md").read_text()
    assert glossary_text.startswith("# Glossary")

    assert (project_dir / ".secret-allowlist.json").is_file()

    gitignore_lines = (project_dir / ".gitignore").read_text().splitlines()
    for line in GITIGNORE_LINES:
        assert gitignore_lines.count(line) == 1

    expected_created_paths = list(EXPECTED_DIRS)
    expected_created_paths += [f"{d}/.gitkeep" for d in EXPECTED_GITKEEP_DIRS]
    expected_created_paths += EXPECTED_OTHER_FILES

    for path in expected_created_paths:
        assert f"{path}: created" in first_outputs

    before = _snapshot(project_dir)

    second_outputs = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        input_fn=_no_prompt_input_fn,
        output_fn=second_outputs.append,
        env={},
    )

    after = _snapshot(project_dir)
    assert before == after

    for path in expected_created_paths:
        assert f"{path}: skipped (exists)" in second_outputs


def test_init_preserves_existing_glossary_and_merges_gitignore(tmp_path):
    log_path = tmp_path / "fake_dep_log_2.jsonl"
    tool_root = _make_fake_tool_root(tmp_path, log_path)

    project_dir = tmp_path / "project2"
    project_dir.mkdir()
    (project_dir / "specs").mkdir()
    _write(project_dir / "specs" / "glossary.md", "mine")
    _write(project_dir / ".gitignore", "/.hotdocs/\n")

    outputs = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        input_fn=_no_prompt_input_fn,
        output_fn=outputs.append,
        env={},
    )

    assert (project_dir / "specs" / "glossary.md").read_text() == "mine"

    gitignore_lines = (project_dir / ".gitignore").read_text().splitlines()
    assert gitignore_lines.count("/.hotdocs/") == 1
    for line in ["__pycache__/", "*.pyc", ".venv/"]:
        assert gitignore_lines.count(line) == 1