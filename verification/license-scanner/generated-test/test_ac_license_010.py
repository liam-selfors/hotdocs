# hotdocs-criterion: sha256:719c723074ae2cdb5d6cf9d15a16ae9ea87b4b36eaf6dd26a5d65b6092f41110
import hashlib
import json
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-foo"
COMPONENT_SLUG = "foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_cache_manager_source(log_path):
    lines = [
        "import dataclasses",
        "",
        "LOG = " + repr(str(log_path)),
        "",
        "",
        "def _log(name):",
        "    with open(LOG, 'a') as f:",
        "        f.write(name + '\\n')",
        "",
        "",
        "@dataclasses.dataclass",
        "class CacheKey:",
        "    spec_bundle_hash: str",
        "    gate_inputs_hash: str",
        "    gate_version: str",
        "    model_pin: str",
        "",
        "    def __post_init__(self):",
        "        _log('CacheKey')",
        "",
        "",
        "@dataclasses.dataclass",
        "class CachedResult:",
        "    gate_type: str",
        "    payload: dict",
        "    stored_at: str",
        "",
        "    def __post_init__(self):",
        "        _log('CachedResult')",
        "",
        "",
        "class Miss:",
        "    def __eq__(self, other):",
        "        return isinstance(other, Miss)",
        "",
        "    def __hash__(self):",
        "        return 0",
        "",
        "",
        "class SchemaValidationError(ValueError):",
        "    pass",
        "",
        "",
        "def get(cache_key, *, repo_root=None):",
        "    _log('get')",
        "    return Miss()",
        "",
        "",
        "def put(cache_key, result, *, repo_root=None):",
        "    _log('put')",
        "    return None",
        "",
        "",
        "def now_iso():",
        "    _log('now_iso')",
        "    import datetime",
        "    return datetime.datetime.now(datetime.timezone.utc).strftime("
        + repr("%Y-%m-%dT%H:%M:%SZ")
        + ")",
        "",
        "",
        "def stats(*, repo_root=None):",
        "    _log('stats')",
        "    return " + repr({"entry_count": 0}),
        "",
        "",
        "def main(argv=None):",
        "    _log('main')",
        "    return 0",
        "",
    ]
    return "\n".join(lines)


def _write_fake_cache_manager(repo_root, log_path):
    d = repo_root / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cache_manager.py").write_text(_fake_cache_manager_source(log_path))


def _write_component(repo_root):
    d = repo_root / "gen" / COMPONENT_SLUG
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "def compute_total(items, factor):\n"
        "    total = 0\n"
        "    for item in items:\n"
        "        total = total + item * factor + 1\n"
        "    return total\n"
    )
    (d / "foo.py").write_text(src)


def _corpus(version, n_entries=1):
    entries = []
    for i in range(n_entries):
        entries.append(
            {
                "reference_id": "ref-" + str(i + 1).zfill(3),
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": [hashlib.sha256(("x" + str(i)).encode("utf-8")).hexdigest()],
            }
        )
    return {"corpus_version": version, "block_threshold": 0.7, "entries": entries}


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text().splitlines() if line.strip()]


def _snapshot(root):
    snap = {}
    if not root.exists():
        return snap
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if "__pycache__" in rel:
            continue
        if p.is_file():
            snap[rel] = p.read_bytes()
        else:
            snap[rel] = None
    return snap


@pytest.fixture
def env(monkeypatch):
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    return monkeypatch


@pytest.fixture
def setup(tmp_path, env):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "cache_calls.log"
    _write_fake_cache_manager(repo_root, log_path)
    _write_component(repo_root)
    corpus_path = tmp_path / "corpus.json"
    return repo_root, log_path, corpus_path


def _gate_version_no_cache_calls(repo_root, log_path):
    before = len(_read_log(log_path))
    gv = license_scanner.gate_version(repo_root)
    after = len(_read_log(log_path))
    assert after == before, "gate_version must not call cache-manager"
    assert isinstance(gv, str)
    return gv


def test_gate_version_matches_scan_for_usable_corpus(setup, env):
    repo_root, log_path, corpus_path = setup
    corpus_path.write_text(json.dumps(_corpus(4)))
    env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    gv = _gate_version_no_cache_calls(repo_root, log_path)
    result = license_scanner.scan(COMPONENT_ID, repo_root)

    assert gv == field(result, "gate_version")
    assert gv.startswith("license_scanner@4.0.4+")


def test_gate_version_changes_on_version_bump_and_on_entry_added(setup, env):
    repo_root, log_path, corpus_path = setup
    corpus_path.write_text(json.dumps(_corpus(4)))
    env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    gv1 = _gate_version_no_cache_calls(repo_root, log_path)

    corpus_path.write_text(json.dumps(_corpus(5)))
    gv2 = _gate_version_no_cache_calls(repo_root, log_path)
    assert gv2 != gv1

    corpus_path.write_text(json.dumps(_corpus(5, n_entries=2)))
    gv3 = _gate_version_no_cache_calls(repo_root, log_path)
    assert gv3 != gv2
    assert gv3 != gv1

    result = license_scanner.scan(COMPONENT_ID, repo_root)
    assert field(result, "gate_version") == gv3


def test_gate_version_matches_scan_without_usable_corpus(setup, env, tmp_path):
    repo_root, log_path, corpus_path = setup

    versions = []

    # Unset
    env.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    gv = _gate_version_no_cache_calls(repo_root, log_path)
    result = license_scanner.scan(COMPONENT_ID, repo_root)
    assert gv == field(result, "gate_version")
    versions.append(gv)

    # Missing file
    missing = tmp_path / "does-not-exist.json"
    assert not missing.exists()
    env.setenv("VAR_LICENSE_CORPUS_PATH", str(missing))
    gv = _gate_version_no_cache_calls(repo_root, log_path)
    result = license_scanner.scan(COMPONENT_ID, repo_root)
    assert gv == field(result, "gate_version")
    versions.append(gv)

    # Invalid corpus (no entries list)
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps({"corpus_version": 4, "block_threshold": 0.7}))
    env.setenv("VAR_LICENSE_CORPUS_PATH", str(invalid))
    gv = _gate_version_no_cache_calls(repo_root, log_path)
    result = license_scanner.scan(COMPONENT_ID, repo_root)
    assert gv == field(result, "gate_version")
    versions.append(gv)

    assert len(set(versions)) == 3, versions


def test_gate_version_never_calls_cache_manager_or_writes(tmp_path, env):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "cache_calls.log"
    # Only the faked cache-manager lives under gen/; no component files.
    _write_fake_cache_manager(repo_root, log_path)
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps(_corpus(4)))
    env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    before = _snapshot(repo_root)
    gv = license_scanner.gate_version(repo_root)
    after = _snapshot(repo_root)

    assert isinstance(gv, str)
    assert _read_log(log_path) == []
    assert not log_path.exists()
    assert before == after


def test_gate_version_with_no_gen_directory_at_all(tmp_path, env):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    assert not (repo_root / "gen").exists()

    before = _snapshot(repo_root)
    gv = license_scanner.gate_version(repo_root)
    after = _snapshot(repo_root)

    assert isinstance(gv, str)
    assert before == after
    assert not (repo_root / "gen").exists()