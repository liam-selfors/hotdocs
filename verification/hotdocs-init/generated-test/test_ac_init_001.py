import json
from pathlib import Path

import hotdocs_init


LLM_ENDPOINT_FAKE_TEMPLATE = '''\
import json as _json

_LOG_PATH = __LOG_PATH_LITERAL__


def _log(name, args, kwargs):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps({"name": name, "args": list(args), "kwargs": kwargs}) + "\\n")


PROVIDERS = {
    "anthropic": {
        "default_base_url": None,
        "default_api_key_env": "ANTHROPIC_API_KEY",
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "openai-compatible": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": True,
        "suggested_model": "",
    },
}


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", (), {"env": env, "probe_ollama": probe_ollama})
    return [
        {
            "provider": "anthropic",
            "available": False,
            "reason": "no key configured",
            "suggested_model": "claude-sonnet-5",
            "api_key_env": "ANTHROPIC_API_KEY",
        }
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log(
        "check_connection",
        (provider, model),
        {"base_url": base_url, "api_key_env": api_key_env, "timeout_seconds": timeout_seconds},
    )
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: %s" % provider)
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required for %s" % provider)
    return {"ok": False, "error": {"category": "network", "message": "fake backend: no network in tests"}}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log(
        "save_config",
        (str(config_path), provider, model),
        {"base_url": base_url, "api_key_env": api_key_env, "timeout_seconds": timeout_seconds},
    )
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: %s" % provider)


def load_config(config_path=None):
    _log("load_config", (), {"config_path": str(config_path) if config_path else None})
    return None
'''


def make_fake_tool_root(base_dir: Path, log_path: Path) -> Path:
    tool_root = base_dir / "tool_root"
    tool_root.mkdir()

    llm_dir = tool_root / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    content = LLM_ENDPOINT_FAKE_TEMPLATE.replace(
        "__LOG_PATH_LITERAL__", json.dumps(str(log_path))
    )
    (llm_dir / "llm_endpoint.py").write_text(content, encoding="utf-8")

    cc_dir = tool_root / "pipeline" / "criterion-compiler"
    cc_dir.mkdir(parents=True)
    (cc_dir / "criterion_compiler.py").write_text(
        "def compile_criterion(*args, **kwargs):\n    raise NotImplementedError\n",
        encoding="utf-8",
    )

    slugify_dir = tool_root / "examples" / "slugify" / "specs" / "product"
    slugify_dir.mkdir(parents=True)
    (slugify_dir / "slugs.md").write_text(
        "# Slugs\n\nExample product spec for the slugify example.\n",
        encoding="utf-8",
    )

    (tool_root / "requirements.txt").write_text("pytest\n", encoding="utf-8")

    return tool_root


def _snapshot(root: Path):
    snap = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            st = p.stat()
            snap[rel] = (p.read_bytes(), st.st_mtime_ns)
    return snap


DIRS = [
    "specs/product",
    "specs/components",
    "specs/decisions",
    "gen",
    "pipeline",
    "verification",
]

GITKEEPS = [
    "specs/product/.gitkeep",
    "specs/components/.gitkeep",
    "specs/decisions/.gitkeep",
    "verification/.gitkeep",
]

SINGLES = [
    "specs/glossary.md",
    ".secret-allowlist.json",
    ".gitignore",
]

ALL_CREATED = DIRS + GITKEEPS + SINGLES

GITIGNORE_LINES = ["/.hotdocs/", "__pycache__/", "*.pyc", ".venv/"]


def test_init_creates_structure_then_is_idempotent(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    log_path = tmp_path / "llm_calls.log"
    tool_root = make_fake_tool_root(tmp_path, log_path)

    lines_first = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        output_fn=lines_first.append,
    )

    for rel in DIRS:
        assert (project_dir / rel).is_dir()

    for rel in GITKEEPS:
        p = project_dir / rel
        assert p.is_file()
        assert p.read_bytes() == b""

    glossary_text = (project_dir / "specs" / "glossary.md").read_text(encoding="utf-8")
    assert glossary_text.startswith("# Glossary")

    allowlist = json.loads((project_dir / ".secret-allowlist.json").read_text(encoding="utf-8"))
    assert allowlist == {"version": 1, "entries": []}

    gitignore_text_lines = (project_dir / ".gitignore").read_text(encoding="utf-8").splitlines()
    for expected in GITIGNORE_LINES:
        assert gitignore_text_lines.count(expected) == 1

    for rel in ALL_CREATED:
        assert lines_first.count(f"{rel}: created") == 1

    snapshot_before = _snapshot(project_dir)

    lines_second = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        output_fn=lines_second.append,
    )

    snapshot_after = _snapshot(project_dir)
    assert snapshot_after == snapshot_before

    for rel in ALL_CREATED:
        assert lines_second.count(f"{rel}: skipped (exists)") == 1


def test_init_does_not_clobber_existing_glossary_or_duplicate_gitignore_line(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "specs").mkdir()
    (project_dir / "specs" / "glossary.md").write_text("mine", encoding="utf-8")
    (project_dir / ".gitignore").write_text("/.hotdocs/\n", encoding="utf-8")

    log_path = tmp_path / "llm_calls.log"
    tool_root = make_fake_tool_root(tmp_path, log_path)

    lines = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        output_fn=lines.append,
    )

    assert (project_dir / "specs" / "glossary.md").read_text(encoding="utf-8") == "mine"

    gitignore_text_lines = (project_dir / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert gitignore_text_lines.count("/.hotdocs/") == 1
    for expected in ["__pycache__/", "*.pyc", ".venv/"]:
        assert gitignore_text_lines.count(expected) == 1