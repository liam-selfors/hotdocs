"""Acceptance test for AC-INIT-001 / R-INIT-001."""
import json
import os
import time
from importlib.metadata import version as _pkg_version
from pathlib import Path

import pytest

import hotdocs_init


def _no_input(prompt):
    raise AssertionError(f"unexpected prompt: {prompt!r}")


def _write_fake_llm_endpoint(gen_dir: Path, log_path: Path) -> None:
    module_dir = gen_dir / "llm-endpoint"
    module_dir.mkdir(parents=True, exist_ok=True)
    log_path_literal = json.dumps(str(log_path))
    code = (
        "import json\n"
        "\n"
        "LOG_PATH = " + log_path_literal + "\n"
        "\n"
        "PROVIDERS = {\n"
        "    'anthropic': {\n"
        "        'default_base_url': None,\n"
        "        'default_api_key_env': 'ANTHROPIC_API_KEY',\n"
        "        'needs_base_url': False,\n"
        "        'suggested_model': 'claude-sonnet-5',\n"
        "    },\n"
        "}\n"
        "\n"
        "\n"
        "def _log(call):\n"
        "    with open(LOG_PATH, 'a') as f:\n"
        "        f.write(json.dumps({'call': call}) + chr(10))\n"
        "\n"
        "\n"
        "def detect_providers(env=None, probe_ollama=True):\n"
        "    _log('detect_providers')\n"
        "    return [{\n"
        "        'provider': 'anthropic',\n"
        "        'available': True,\n"
        "        'reason': None,\n"
        "        'suggested_model': 'claude-sonnet-5',\n"
        "        'api_key_env': 'ANTHROPIC_API_KEY',\n"
        "    }]\n"
        "\n"
        "\n"
        "def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):\n"
        "    _log('check_connection')\n"
        "    return {'ok': True, 'error': None}\n"
        "\n"
        "\n"
        "def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):\n"
        "    _log('save_config')\n"
        "    with open(config_path, 'a') as f:\n"
        "        f.write(chr(10) + '[llm]' + chr(10) + 'provider = ' + repr(provider) + chr(10))\n"
        "\n"
        "\n"
        "def load_config(config_path=None):\n"
        "    _log('load_config')\n"
        "    return None\n"
    )
    (module_dir / "llm_endpoint.py").write_text(code)


def _write_fake_tool_root(root: Path, log_path: Path) -> None:
    _write_fake_llm_endpoint(root / "gen", log_path)

    cc_path = root / "pipeline" / "criterion-compiler" / "criterion_compiler.py"
    cc_path.parent.mkdir(parents=True, exist_ok=True)
    cc_path.write_text("def compile(*args, **kwargs):\n    pass\n")

    slugs_path = root / "examples" / "slugify" / "specs" / "product" / "slugs.md"
    slugs_path.parent.mkdir(parents=True, exist_ok=True)
    slugs_path.write_text("# Slugs\n\nExample product spec for the slugify example.\n")

    pytest_version = _pkg_version("pytest")
    (root / "requirements.txt").write_text(f"pytest=={pytest_version}\n")


EXPECTED_DIRS = [
    "specs/product",
    "specs/components",
    "specs/decisions",
    "gen",
    "pipeline",
    "verification",
]

EXPECTED_GITKEEP_DIRS = [
    "specs/product",
    "specs/components",
    "specs/decisions",
    "verification",
]

GITIGNORE_LINES = ["/.hotdocs/", "__pycache__/", "*.pyc", ".venv/"]


def test_init_creates_structure_and_is_idempotent(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tool_root = tmp_path / "tool_root"
    tool_root.mkdir()
    log_path = tmp_path / "calls.log"
    _write_fake_tool_root(tool_root, log_path)

    lines = []
    exit_code = hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=lines.append,
        env={},
    )
    assert exit_code not in (1, 2)

    for d in EXPECTED_DIRS:
        assert (project_dir / d).is_dir()

    gitkeep_paths = []
    for d in EXPECTED_GITKEEP_DIRS:
        gitkeep = project_dir / d / ".gitkeep"
        assert gitkeep.is_file()
        assert gitkeep.read_bytes() == b""
        gitkeep_paths.append(f"{d}/.gitkeep")

    glossary_path = project_dir / "specs" / "glossary.md"
    assert glossary_path.is_file()
    assert glossary_path.read_text().startswith("# Glossary")

    allowlist_path = project_dir / ".secret-allowlist.json"
    assert allowlist_path.is_file()

    gitignore_path = project_dir / ".gitignore"
    assert gitignore_path.is_file()
    gitignore_lines = gitignore_path.read_text().splitlines()
    for required in GITIGNORE_LINES:
        assert gitignore_lines.count(required) == 1

    expected_paths = (
        EXPECTED_DIRS
        + gitkeep_paths
        + ["specs/glossary.md", ".secret-allowlist.json", ".gitignore"]
    )
    for path in expected_paths:
        assert f"{path}: created" in lines

    before_files = {}
    for root, _dirs, files in os.walk(project_dir):
        for name in files:
            p = Path(root) / name
            st = p.stat()
            before_files[p] = (p.read_bytes(), st.st_mtime)

    time.sleep(1.1)

    lines2 = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=lines2.append,
        env={},
    )

    after_files = set()
    for root, _dirs, files in os.walk(project_dir):
        for name in files:
            after_files.add(Path(root) / name)
    assert after_files == set(before_files.keys())

    for p, (content, mtime) in before_files.items():
        assert p.read_bytes() == content
        assert p.stat().st_mtime == mtime

    for path in expected_paths:
        assert f"{path}: skipped (exists)" in lines2


def test_init_preserves_existing_glossary_and_gitignore(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tool_root = tmp_path / "tool_root"
    tool_root.mkdir()
    log_path = tmp_path / "calls.log"
    _write_fake_tool_root(tool_root, log_path)

    specs_dir = project_dir / "specs"
    specs_dir.mkdir()
    glossary_path = specs_dir / "glossary.md"
    glossary_path.write_text("mine")

    gitignore_path = project_dir / ".gitignore"
    gitignore_path.write_text("/.hotdocs/\n")

    lines = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=lines.append,
        env={},
    )

    assert glossary_path.read_text() == "mine"

    gitignore_lines = gitignore_path.read_text().splitlines()
    assert gitignore_lines.count("/.hotdocs/") == 1
    for required in ["__pycache__/", "*.pyc", ".venv/"]:
        assert gitignore_lines.count(required) == 1

    assert "specs/glossary.md: skipped (exists)" in lines
    assert ".gitignore: skipped (exists)" in lines