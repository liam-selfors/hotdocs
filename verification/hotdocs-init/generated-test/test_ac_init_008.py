import hashlib
import importlib.metadata
import json
from pathlib import Path

import pytest

import hotdocs_init


EXPECTED_ENTRY = {
    "file": "gen/review-packet-builder/review_packet_builder.py",
    "type": "Hex High Entropy String",
    "hashed_secret": "sha1:2c74b2b5a39b54beae7d7c0e994feb84693a3466",
    "reason": "public-constant",
}

_LLM_ENDPOINT_TEMPLATE = '''
import json
from pathlib import Path

LOG_PATH = __LOG_PATH__

def _log(name, kwargs):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"call": name, "kwargs": {k: str(v) for k, v in kwargs.items()}}) + "\\n")

PROVIDERS = {
    "anthropic": {
        "default_base_url": None,
        "default_api_key_env": "ANTHROPIC_API_KEY",
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
}

def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", {"env": env, "probe_ollama": probe_ollama})
    return [
        {
            "provider": "anthropic",
            "available": False,
            "reason": "no-key",
            "suggested_model": "claude-sonnet-5",
            "api_key_env": "ANTHROPIC_API_KEY",
        }
    ]

def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log("check_connection", {"provider": provider, "model": model})
    return {"ok": False, "error": {"category": "auth", "message": "no key configured"}}

def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log("save_config", {"provider": provider, "model": model})
    Path(config_path).write_text(
        "[llm]\\nprovider = \\"" + provider + "\\"\\nmodel = \\"" + model + "\\"\\n",
        encoding="utf-8",
    )

def load_config(config_path=None):
    _log("load_config", {"config_path": config_path})
    return None
'''


def _no_input(prompt):
    raise AssertionError("unexpected interactive prompt: " + repr(prompt))


def _make_fake_tool_root(tmp_path, name="tool_root"):
    tool_root = tmp_path / name
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "llm_calls.log"

    llm_dir = tool_root / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True, exist_ok=True)
    source = _LLM_ENDPOINT_TEMPLATE.replace("__LOG_PATH__", repr(str(log_path)))
    (llm_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")

    cc_dir = tool_root / "pipeline" / "criterion-compiler"
    cc_dir.mkdir(parents=True, exist_ok=True)
    (cc_dir / "criterion_compiler.py").write_text(
        "def compile_criteria(*args, **kwargs):\n    raise NotImplementedError\n",
        encoding="utf-8",
    )

    slugify_dir = tool_root / "examples" / "slugify" / "specs" / "product"
    slugify_dir.mkdir(parents=True, exist_ok=True)
    (slugify_dir / "slugs.md").write_text("# Slugs\n\nExample product spec.\n", encoding="utf-8")

    pytest_version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text("pytest==" + pytest_version + "\n", encoding="utf-8")

    return tool_root


def _parse_frontmatter(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.index("\n---", 4)
    raw = text[4:end]
    frontmatter = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        frontmatter[key.strip()] = value.strip()
    body = text[end + 4:]
    return frontmatter, body


def _write_decision(path, decision_id, title, last_ratified_commit="abc123"):
    path.write_text(
        "---\n"
        "id: " + decision_id + "\n"
        "title: " + title + "\n"
        "status: ratified\n"
        "owners: [project]\n"
        "last_ratified_commit: " + last_ratified_commit + "\n"
        "---\n"
        "# " + decision_id + "\n"
        "\n"
        "Body of " + decision_id + ".\n",
        encoding="utf-8",
    )


def test_fresh_init_writes_allowlist_and_seals_with_d1(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tool_root = _make_fake_tool_root(tmp_path)

    outputs = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=outputs.append,
    )

    allowlist_path = project_dir / ".secret-allowlist.json"
    assert allowlist_path.exists()

    expected_doc = {"version": 1, "entries": [EXPECTED_ENTRY]}
    expected_bytes = (json.dumps(expected_doc, indent=2) + "\n").encode("utf-8")
    actual_bytes = allowlist_path.read_bytes()
    assert actual_bytes == expected_bytes

    data = json.loads(actual_bytes.decode("utf-8"))
    assert data["version"] == 1
    assert len(data["entries"]) == 1
    assert data["entries"][0] == EXPECTED_ENTRY

    decision_path = project_dir / "specs" / "decisions" / "D1.md"
    assert decision_path.exists()
    frontmatter, _body = _parse_frontmatter(decision_path)
    assert frontmatter["status"] == "ratified"

    expected_hash = "sha256:" + hashlib.sha256(actual_bytes).hexdigest()
    assert frontmatter["allowlist_sha256"] == expected_hash

    assert "specs/decisions/D1.md: created" in outputs


def test_sealing_decision_numbers_above_existing_decisions(tmp_path):
    project_dir = tmp_path / "project"
    decisions_dir = project_dir / "specs" / "decisions"
    decisions_dir.mkdir(parents=True)

    d3_path = decisions_dir / "D3.md"
    d12_path = decisions_dir / "D12.md"
    _write_decision(d3_path, "D3", "An earlier decision")
    _write_decision(d12_path, "D12", "Another earlier decision")

    d3_before = d3_path.read_bytes()
    d12_before = d12_path.read_bytes()

    tool_root = _make_fake_tool_root(tmp_path)
    outputs = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=outputs.append,
    )

    d3_after = d3_path.read_bytes()
    d12_after = d12_path.read_bytes()
    assert d3_after == d3_before
    assert d12_after == d12_before

    d13_path = decisions_dir / "D13.md"
    assert d13_path.exists()
    frontmatter, _body = _parse_frontmatter(d13_path)
    assert frontmatter["id"] == "D13"
    assert frontmatter["title"] == "Seal the initial secret allowlist"
    assert frontmatter["status"] == "ratified"
    assert frontmatter["last_ratified_commit"] == "hotdocs-init"

    allowlist_path = project_dir / ".secret-allowlist.json"
    assert allowlist_path.exists()
    expected_hash = "sha256:" + hashlib.sha256(allowlist_path.read_bytes()).hexdigest()
    assert frontmatter["allowlist_sha256"] == expected_hash

    assert "specs/decisions/D13.md: created" in outputs


def test_existing_allowlist_is_skipped_and_no_decision_written(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    allowlist_path = project_dir / ".secret-allowlist.json"
    original_bytes = json.dumps({"version": 1, "entries": []}, indent=2).encode("utf-8") + b"\n"
    allowlist_path.write_bytes(original_bytes)

    tool_root = _make_fake_tool_root(tmp_path)
    outputs = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=outputs.append,
    )

    assert allowlist_path.read_bytes() == original_bytes

    decisions_dir = project_dir / "specs" / "decisions"
    if decisions_dir.exists():
        decision_md_files = [p for p in decisions_dir.iterdir() if p.name.startswith("D") and p.name.endswith(".md")]
        assert decision_md_files == []

    for line in outputs:
        assert "specs/decisions/D" not in line

    assert any(
        "specs/decisions" in line and ".gitkeep" in line
        for line in outputs
    )