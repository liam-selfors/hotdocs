import importlib.metadata
import json

import hotdocs_init


FAKE_LLM_ENDPOINT_TEMPLATE = r'''
import json as _json

_LOG_PATH = __LOG_PATH_LITERAL__

def _log(name, data):
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(_json.dumps({"name": name, "data": data}, default=str) + "\n")

PROVIDERS = {
    "anthropic": {
        "default_base_url": None,
        "default_api_key_env": "ANTHROPIC_API_KEY",
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
}

def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", {"has_env": env is not None, "probe_ollama": probe_ollama})
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
    _log("check_connection", {"provider": provider, "model": model})
    return {"ok": False, "error": {"category": "auth", "message": "no credentials"}}

def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log("save_config", {"config_path": str(config_path), "provider": provider, "model": model})
    with open(config_path, "a", encoding="utf-8") as f:
        f.write("[llm]\n")
        f.write("provider = " + str(provider) + "\n")
        f.write("model = " + str(model) + "\n")

def load_config(config_path=None):
    _log("load_config", {"config_path": str(config_path) if config_path else None})
    return None
'''


def _build_fake_tool_root(tool_root, log_path):
    tool_root.mkdir(parents=True, exist_ok=True)

    llm_endpoint_dir = tool_root / "gen" / "llm-endpoint"
    llm_endpoint_dir.mkdir(parents=True, exist_ok=True)
    content = FAKE_LLM_ENDPOINT_TEMPLATE.replace(
        "__LOG_PATH_LITERAL__", json.dumps(str(log_path))
    )
    (llm_endpoint_dir / "llm_endpoint.py").write_text(content, encoding="utf-8")

    slugify_product_dir = tool_root / "examples" / "slugify" / "specs" / "product"
    slugify_product_dir.mkdir(parents=True, exist_ok=True)
    (slugify_product_dir / "slugs.md").write_text(
        "---\n"
        "id: comp-slugify\n"
        "title: Slugify example\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n\n"
        "Example product spec for the slugify example used by `init --example`.\n",
        encoding="utf-8",
    )

    pytest_version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text(
        "pytest==" + pytest_version + "\n", encoding="utf-8"
    )

    return tool_root


def test_empty_directory_creates_sealed_allowlist_and_only_gitkeep_in_decisions(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    log_path = tmp_path / "calls.log"
    tool_root = _build_fake_tool_root(tmp_path / "tool_root", log_path)

    messages = []

    def output_fn(msg):
        messages.append(msg)

    def input_fn(prompt):
        raise AssertionError("unexpected prompt with --yes: " + prompt)

    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env={},
        cwd=project_dir,
    )

    allowlist_path = project_dir / ".secret-allowlist.json"
    expected_bytes = (
        json.dumps({"version": 1, "entries": []}, indent=2) + "\n"
    ).encode("utf-8")
    assert allowlist_path.read_bytes() == expected_bytes

    decisions_dir = project_dir / "specs" / "decisions"
    assert decisions_dir.is_dir()
    entry_names = sorted(p.name for p in decisions_dir.iterdir())
    assert entry_names == [".gitkeep"]


def test_existing_allowlist_is_skipped_and_unchanged(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    log_path = tmp_path / "calls.log"
    tool_root = _build_fake_tool_root(tmp_path / "tool_root", log_path)

    allowlist_path = project_dir / ".secret-allowlist.json"
    existing_bytes = (
        json.dumps({"version": 1, "entries": ["FAKE-ALLOWLIST-ENTRY-PLACEHOLDER"]}, indent=2)
        + "\n"
    ).encode("utf-8")
    allowlist_path.write_bytes(existing_bytes)

    messages = []

    def output_fn(msg):
        messages.append(msg)

    def input_fn(prompt):
        raise AssertionError("unexpected prompt with --yes: " + prompt)

    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env={},
        cwd=project_dir,
    )

    assert allowlist_path.read_bytes() == existing_bytes
    assert ".secret-allowlist.json: skipped (exists)" in messages