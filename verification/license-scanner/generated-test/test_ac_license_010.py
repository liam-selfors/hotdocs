"""AC-LICENSE-010 (covers R-LICENSE-008).

gate_version(repo_root) MUST return exactly the gate_version that
scan(component_id, repo_root) reports, under the same repo_root and the
same VAR_LICENSE_CORPUS_PATH value (including no usable corpus), and MUST
NOT scan gen/, call cache-manager, or write anything.
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-foo"
COMPONENT_SLUG = "foo"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


FAKE_CACHE_MANAGER_TEMPLATE = '''\
import json
import time


_LOG_PATH = {log_path!r}


def _record(name):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"call": name}}) + "\\n")


from dataclasses import dataclass


class SchemaValidationError(ValueError):
    pass


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return hash("Miss")

    def __repr__(self):
        return "Miss()"


@dataclass
class CacheKey:
    spec_bundle_hash: object
    gate_inputs_hash: object
    gate_version: object
    model_pin: object

    def __post_init__(self):
        _record("CacheKey")


@dataclass
class CachedResult:
    gate_type: object
    payload: object
    stored_at: object

    def __post_init__(self):
        _record("CachedResult")


def get(cache_key, *, repo_root=None):
    _record("get")
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _record("put")
    return None


def now_iso():
    _record("now_iso")
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stats(*, repo_root=None):
    _record("stats")
    return {{"entry_count": 0}}


def main(argv=None):
    _record("main")
    return 0
'''


COMPONENT_SOURCE = '''\
def compute_total(items, multiplier, offset):
    total = 0
    for item in items:
        total = total + item * multiplier + offset
    return total


class Accumulator:
    def __init__(self, start_value):
        self.value = start_value

    def add(self, amount):
        self.value = self.value + amount
        return self.value
'''


def _hex(seed):
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _usable_corpus(corpus_version, extra_entry=False):
    entries = [
        {
            "reference_id": "ref-001",
            "license_family": "gpl-3.0",
            "risk_tier": "high",
            "hashes": [_hex("window-a"), _hex("window-b")],
        }
    ]
    if extra_entry:
        entries.append(
            {
                "reference_id": "ref-002",
                "license_family": "mit",
                "risk_tier": "low",
                "hashes": [_hex("window-c")],
            }
        )
    return {
        "corpus_version": corpus_version,
        "block_threshold": 0.70,
        "entries": entries,
    }


def _write_corpus(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _expected_usable_gate_version(corpus_path, corpus_version):
    digest = hashlib.sha256(corpus_path.read_bytes()).hexdigest()[:12]
    return "license_scanner@4.0.%d+%s" % (corpus_version, digest)


def _make_repo(tmp_path, with_gen=True, with_fake_cache_manager=True):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "cache_manager_calls.log"
    if with_gen:
        comp_dir = repo_root / "gen" / COMPONENT_SLUG
        comp_dir.mkdir(parents=True)
        (comp_dir / "foo.py").write_text(COMPONENT_SOURCE, encoding="utf-8")
        if with_fake_cache_manager:
            cm_dir = repo_root / "gen" / "cache-manager"
            cm_dir.mkdir(parents=True)
            (cm_dir / "cache_manager.py").write_text(
                FAKE_CACHE_MANAGER_TEMPLATE.format(log_path=str(log_path)),
                encoding="utf-8",
            )
    return repo_root, log_path


def _read_log(log_path):
    if not log_path.exists():
        return []
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def _snapshot(root):
    snap = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if "__pycache__" in rel.parts:
            continue
        if p.is_dir():
            snap[str(rel)] = ("dir", None)
        elif p.is_file():
            snap[str(rel)] = ("file", p.read_bytes())
        else:
            snap[str(rel)] = ("other", None)
    return snap


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    yield


def _gate_and_scan(repo_root):
    gv = license_scanner.gate_version(repo_root)
    result = license_scanner.scan(COMPONENT_ID, repo_root)
    scan_gv = _field(result, "gate_version")
    return gv, scan_gv


# ---------------------------------------------------------------------------
# Scenario 1: usable corpus with corpus_version 4
# ---------------------------------------------------------------------------


def test_gate_version_matches_scan_with_usable_corpus_version_4(tmp_path, monkeypatch):
    repo_root, _log = _make_repo(tmp_path)
    corpus_path = tmp_path / "corpus" / "corpus.json"
    _write_corpus(corpus_path, _usable_corpus(4))
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    gv, scan_gv = _gate_and_scan(repo_root)

    assert isinstance(gv, str)
    assert gv == scan_gv
    assert gv == _expected_usable_gate_version(corpus_path, 4)

    # Calling gate_version again after the scan still agrees.
    assert license_scanner.gate_version(repo_root) == scan_gv


# ---------------------------------------------------------------------------
# Scenario 2: version bump, and separately an added entry, each change it
# ---------------------------------------------------------------------------


def test_gate_version_changes_on_version_bump_and_on_entry_added(tmp_path, monkeypatch):
    repo_root, _log = _make_repo(tmp_path)
    corpus_path = tmp_path / "corpus" / "corpus.json"
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    # Baseline: corpus_version 4.
    _write_corpus(corpus_path, _usable_corpus(4))
    baseline = license_scanner.gate_version(repo_root)
    assert isinstance(baseline, str)

    # corpus_version changed to 5.
    _write_corpus(corpus_path, _usable_corpus(5))
    bumped = license_scanner.gate_version(repo_root)
    assert isinstance(bumped, str)
    assert bumped != baseline
    bumped_scan = _field(license_scanner.scan(COMPONENT_ID, repo_root), "gate_version")
    assert bumped == bumped_scan

    # Separately: back to the version-4 baseline, then an entry added with
    # corpus_version unchanged.
    _write_corpus(corpus_path, _usable_corpus(4))
    restored = license_scanner.gate_version(repo_root)
    assert restored == baseline

    _write_corpus(corpus_path, _usable_corpus(4, extra_entry=True))
    added = license_scanner.gate_version(repo_root)
    assert isinstance(added, str)
    assert added != restored
    assert added != baseline
    added_scan = _field(license_scanner.scan(COMPONENT_ID, repo_root), "gate_version")
    assert added == added_scan


# ---------------------------------------------------------------------------
# Scenario 3: unset, missing file, invalid corpus
# ---------------------------------------------------------------------------


def test_gate_version_matches_scan_for_unset_missing_and_invalid_corpus(tmp_path, monkeypatch):
    repo_root, _log = _make_repo(tmp_path)

    # Unset.
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    gv_unset, scan_unset = _gate_and_scan(repo_root)
    assert isinstance(gv_unset, str)
    assert gv_unset == scan_unset

    # Set to a missing file.
    missing = tmp_path / "corpus" / "does-not-exist.json"
    assert not missing.exists()
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(missing))
    gv_missing, scan_missing = _gate_and_scan(repo_root)
    assert isinstance(gv_missing, str)
    assert gv_missing == scan_missing

    # Set to an invalid corpus (JSON object with no entries list).
    invalid = tmp_path / "corpus" / "invalid.json"
    invalid.parent.mkdir(parents=True, exist_ok=True)
    invalid.write_text(json.dumps({"corpus_version": 1}), encoding="utf-8")
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(invalid))
    gv_invalid, scan_invalid = _gate_and_scan(repo_root)
    assert isinstance(gv_invalid, str)
    assert gv_invalid == scan_invalid

    # The three differ from one another.
    assert len({gv_unset, gv_missing, gv_invalid}) == 3

    # And match the documented not-evaluated forms.
    assert gv_unset == "license_scanner@4.0.0-no-reference-corpus"
    assert gv_missing == "license_scanner@4.0.0-corpus-unreadable"
    assert gv_invalid == "license_scanner@4.0.0-corpus-invalid"


# ---------------------------------------------------------------------------
# Scenario 4: no gen/ directory; no cache-manager calls; no writes
# ---------------------------------------------------------------------------


def test_gate_version_without_gen_dir_returns_string_and_writes_nothing(tmp_path, monkeypatch):
    repo_root, log_path = _make_repo(tmp_path, with_gen=False)
    assert not (repo_root / "gen").exists()

    # No corpus configured.
    before = _snapshot(repo_root)
    gv = license_scanner.gate_version(repo_root)
    assert isinstance(gv, str)
    assert _snapshot(repo_root) == before
    assert not (repo_root / "gen").exists()
    assert not (repo_root / ".hotdocs").exists()

    # Usable corpus configured.
    corpus_path = tmp_path / "corpus" / "corpus.json"
    _write_corpus(corpus_path, _usable_corpus(4))
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    corpus_bytes = corpus_path.read_bytes()
    before = _snapshot(repo_root)
    gv_usable = license_scanner.gate_version(repo_root)
    assert isinstance(gv_usable, str)
    assert _snapshot(repo_root) == before
    assert corpus_path.read_bytes() == corpus_bytes
    assert not (repo_root / ".hotdocs").exists()

    assert _read_log(log_path) == []


def test_gate_version_never_calls_faked_cache_manager(tmp_path, monkeypatch):
    repo_root, log_path = _make_repo(tmp_path, with_gen=True, with_fake_cache_manager=True)
    assert (repo_root / "gen" / "cache-manager" / "cache_manager.py").is_file()

    for setting in ("unset", "usable", "missing", "invalid"):
        if setting == "unset":
            monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
        elif setting == "usable":
            corpus_path = tmp_path / "corpus" / "corpus.json"
            _write_corpus(corpus_path, _usable_corpus(4))
            monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
        elif setting == "missing":
            monkeypatch.setenv(
                "VAR_LICENSE_CORPUS_PATH", str(tmp_path / "corpus" / "nope.json")
            )
        else:
            invalid = tmp_path / "corpus" / "invalid.json"
            invalid.parent.mkdir(parents=True, exist_ok=True)
            invalid.write_text(json.dumps({"entries": []}), encoding="utf-8")
            monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(invalid))

        before = _snapshot(repo_root)
        gv = license_scanner.gate_version(repo_root)
        assert isinstance(gv, str), setting
        assert _snapshot(repo_root) == before, setting
        assert _read_log(log_path) == [], setting

    assert not log_path.exists()