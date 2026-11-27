# hotdocs-criterion: sha256:796e9682a8aafa0770e1a806f5924ebb6accb860d1a1ade1ba0491d6f47b6e3b
import hashlib
import json
import os
from pathlib import Path

import license_scanner


COMPONENT_ID = "comp-sample"
COMPONENT_SLUG = "sample"
ENV = "VAR_LICENSE_CORPUS_PATH"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_fake_cache_manager(repo_root, log_path):
    base = Path(repo_root) / "gen" / "cache-manager"
    base.mkdir(parents=True, exist_ok=True)
    src = (
        "import dataclasses\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(name):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(name + '\\n')\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "    def __post_init__(self):\n"
        "        _log('CacheKey')\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: dict\n"
        "    stored_at: str\n"
        "\n"
        "    def __post_init__(self):\n"
        "        _log('CachedResult')\n"
        "\n"
        "\n"
        "class Miss:\n"
        "    def __eq__(self, other):\n"
        "        return isinstance(other, Miss)\n"
        "\n"
        "    def __hash__(self):\n"
        "        return hash('Miss')\n"
        "\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log('get')\n"
        "    return Miss()\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log('put')\n"
        "    return None\n"
        "\n"
        "\n"
        "def now_iso():\n"
        "    _log('now_iso')\n"
        "    return '2026-01-01T00:00:00Z'\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    _log('stats')\n"
        "    return {'entry_count': 0}\n"
    )
    (base / "cache_manager.py").write_text(src, encoding="utf-8")


def write_component(repo_root):
    comp_dir = Path(repo_root) / "gen" / COMPONENT_SLUG
    comp_dir.mkdir(parents=True, exist_ok=True)
    src = (
        "def compute_total(items, factor):\n"
        "    total = 0\n"
        "    for item in items:\n"
        "        total = total + item * factor\n"
        "    return total\n"
        "\n"
        "\n"
        "def describe(name, count):\n"
        "    return name + ' has ' + str(count) + ' entries in total now'\n"
    )
    (comp_dir / "sample.py").write_text(src, encoding="utf-8")


def make_corpus(version, n_entries=1):
    entries = []
    for i in range(n_entries):
        entries.append(
            {
                "reference_id": "ref-" + str(i + 1).zfill(3),
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": [hashlib.sha256(("window-" + str(i)).encode("utf-8")).hexdigest()],
            }
        )
    return {"corpus_version": version, "block_threshold": 0.70, "entries": entries}


def write_corpus(path, corpus):
    Path(path).write_text(json.dumps(corpus, indent=2), encoding="utf-8")


def expected_usable_version(path, version):
    h = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]
    return "license_scanner@4.0." + str(version) + "+" + h


def setup_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "cache_calls.log"
    write_fake_cache_manager(repo_root, log_path)
    write_component(repo_root)
    return repo_root, log_path


def test_gate_version_matches_scan_for_usable_corpus(tmp_path, monkeypatch):
    repo_root, _ = setup_repo(tmp_path)
    corpus_path = tmp_path / "corpus.json"
    write_corpus(corpus_path, make_corpus(4))
    monkeypatch.setenv(ENV, str(corpus_path))

    gv = license_scanner.gate_version(repo_root)
    result = license_scanner.scan(COMPONENT_ID, repo_root)

    assert isinstance(gv, str)
    assert gv == field(result, "gate_version")
    assert gv == expected_usable_version(corpus_path, 4)


def test_gate_version_changes_with_corpus_version_and_content(tmp_path, monkeypatch):
    repo_root, _ = setup_repo(tmp_path)
    corpus_path = tmp_path / "corpus.json"
    write_corpus(corpus_path, make_corpus(4))
    monkeypatch.setenv(ENV, str(corpus_path))

    before = license_scanner.gate_version(repo_root)

    # corpus_version changed to 5
    write_corpus(corpus_path, make_corpus(5))
    after_version_bump = license_scanner.gate_version(repo_root)
    assert isinstance(after_version_bump, str)
    assert after_version_bump != before
    assert after_version_bump == field(license_scanner.scan(COMPONENT_ID, repo_root), "gate_version")

    # separately: restore version 4, then add an entry with corpus_version unchanged
    write_corpus(corpus_path, make_corpus(4))
    baseline = license_scanner.gate_version(repo_root)
    assert baseline == before
    write_corpus(corpus_path, make_corpus(4, n_entries=2))
    after_entry_added = license_scanner.gate_version(repo_root)
    assert isinstance(after_entry_added, str)
    assert after_entry_added != baseline
    assert after_entry_added == field(license_scanner.scan(COMPONENT_ID, repo_root), "gate_version")


def test_gate_version_matches_scan_when_no_usable_corpus(tmp_path, monkeypatch):
    repo_root, _ = setup_repo(tmp_path)

    observed = []

    # unset
    monkeypatch.delenv(ENV, raising=False)
    gv_unset = license_scanner.gate_version(repo_root)
    res_unset = license_scanner.scan(COMPONENT_ID, repo_root)
    assert gv_unset == field(res_unset, "gate_version")
    assert gv_unset == "license_scanner@4.0.0-no-reference-corpus"
    observed.append(gv_unset)

    # set to a missing file
    missing = tmp_path / "does-not-exist.json"
    assert not missing.exists()
    monkeypatch.setenv(ENV, str(missing))
    gv_missing = license_scanner.gate_version(repo_root)
    res_missing = license_scanner.scan(COMPONENT_ID, repo_root)
    assert gv_missing == field(res_missing, "gate_version")
    assert gv_missing == "license_scanner@4.0.0-corpus-unreadable"
    observed.append(gv_missing)

    # set to an invalid corpus
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps({"corpus_version": 4, "entries": "not-a-list"}), encoding="utf-8")
    monkeypatch.setenv(ENV, str(invalid))
    gv_invalid = license_scanner.gate_version(repo_root)
    res_invalid = license_scanner.scan(COMPONENT_ID, repo_root)
    assert gv_invalid == field(res_invalid, "gate_version")
    assert gv_invalid == "license_scanner@4.0.0-corpus-invalid"
    observed.append(gv_invalid)

    assert all(isinstance(v, str) for v in observed)
    assert len(set(observed)) == 3


def _snapshot(root):
    out = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            p = Path(dirpath) / name
            out[str(p)] = p.read_bytes()
    return out


def test_gate_version_without_gen_dir_never_touches_cache_manager(tmp_path, monkeypatch):
    corpus_path = tmp_path / "corpus.json"
    write_corpus(corpus_path, make_corpus(4))
    monkeypatch.setenv(ENV, str(corpus_path))

    # Literal case: repo_root with no gen/ directory at all.
    bare_root = tmp_path / "bare"
    bare_root.mkdir()
    before_bare = _snapshot(bare_root)
    gv_bare = license_scanner.gate_version(bare_root)
    assert isinstance(gv_bare, str)
    assert not (bare_root / "gen").exists()
    assert _snapshot(bare_root) == before_bare

    # Recording fake cache-manager present, but no component files under gen/.
    faked_root = tmp_path / "faked"
    faked_root.mkdir()
    log_path = tmp_path / "faked_calls.log"
    write_fake_cache_manager(faked_root, log_path)
    before_faked = _snapshot(faked_root)
    gv_faked = license_scanner.gate_version(faked_root)
    assert isinstance(gv_faked, str)
    assert not log_path.exists() or log_path.read_text(encoding="utf-8") == ""
    assert _snapshot(faked_root) == before_faked