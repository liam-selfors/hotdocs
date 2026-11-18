# hotdocs-criterion: sha256:9984d474fcac052209bb6c699e5657a69c7b35d598f95d3ca0a543a46848fb67
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

import license_scanner


NOT_EVALUATED_GV = "license_scanner@4.0.0-no-reference-corpus"
SEEDED_EVALUATED_SCORE = 0.987
SEEDED_REFERENCE_ID = "ref-seeded-only-never-in-real-corpus"


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


FAKE_CACHE_MANAGER_TEMPLATE = r'''
import dataclasses
import datetime
import json
import os

SEED_PATH = __SEED_PATH__
LOG_PATH = __LOG_PATH__
STORE_PATH = __STORE_PATH__


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return hash("Miss")


class SchemaValidationError(ValueError):
    pass


_KNOWN = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


def _acc(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _log(record):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def _load(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _key_dict(cache_key):
    return {
        "spec_bundle_hash": _acc(cache_key, "spec_bundle_hash"),
        "gate_inputs_hash": _acc(cache_key, "gate_inputs_hash"),
        "gate_version": _acc(cache_key, "gate_version"),
        "model_pin": _acc(cache_key, "model_pin"),
    }


def get(cache_key, *, repo_root=None):
    kd = _key_dict(cache_key)
    _log({"op": "get", "key": kd})
    # Seeded entries stand for "a result stored for gen/foo/'s content" under
    # a given gate_version: they match any key carrying that gate_version.
    for seed in _load(SEED_PATH):
        if seed["gate_version"] == kd["gate_version"]:
            _log({"op": "hit", "key": kd, "source": "seed"})
            return CachedResult(
                gate_type="license_scanner",
                payload=dict(seed["payload"]),
                stored_at=seed["stored_at"],
            )
    for entry in _load(STORE_PATH):
        if entry["key"] == kd:
            _log({"op": "hit", "key": kd, "source": "store"})
            return CachedResult(
                gate_type=entry["gate_type"],
                payload=dict(entry["payload"]),
                stored_at=entry["stored_at"],
            )
    _log({"op": "miss", "key": kd})
    return Miss()


def put(cache_key, result, *, repo_root=None):
    kd = _key_dict(cache_key)
    gate_type = _acc(result, "gate_type")
    payload = _acc(result, "payload")
    stored_at = _acc(result, "stored_at")
    _log({"op": "put", "key": kd, "gate_type": gate_type})
    key_type = (kd["gate_version"] or "").split("@", 1)[0]
    if gate_type not in _KNOWN or gate_type != key_type:
        raise SchemaValidationError("gate_type mismatch: %r vs %r" % (gate_type, key_type))
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload must be a dict")
    missing = [k for k in _KNOWN[gate_type] if k not in payload]
    if missing:
        raise SchemaValidationError("missing payload keys: %r" % (missing,))
    store = _load(STORE_PATH)
    store = [e for e in store if e["key"] != kd]
    store.append({
        "key": kd,
        "gate_type": gate_type,
        "payload": json.loads(json.dumps(payload, default=str)),
        "stored_at": stored_at,
    })
    with open(STORE_PATH, "w", encoding="utf-8") as fh:
        json.dump(store, fh)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": len(_load(STORE_PATH))}
'''


COMPONENT_SOURCE = '''\
def compute_widget_total(alpha_values, beta_scale, gamma_offset):
    running_total = 0
    for item_value in alpha_values:
        running_total = running_total + item_value * beta_scale + gamma_offset
    return running_total


class WidgetAccumulator:
    def __init__(self, initial_amount, step_size):
        self.current_amount = initial_amount
        self.step_size = step_size

    def advance_once(self, multiplier_value):
        self.current_amount = self.current_amount + self.step_size * multiplier_value
        return self.current_amount
'''


def _make_repo(tmp_path, seeds):
    repo_root = tmp_path / "repo"
    state_dir = tmp_path / "fake_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    seed_path = state_dir / "seeds.json"
    log_path = state_dir / "calls.log"
    store_path = state_dir / "store.json"
    seed_path.write_text(json.dumps(seeds), encoding="utf-8")

    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True, exist_ok=True)
    fake_src = (
        FAKE_CACHE_MANAGER_TEMPLATE
        .replace("__SEED_PATH__", repr(str(seed_path)))
        .replace("__LOG_PATH__", repr(str(log_path)))
        .replace("__STORE_PATH__", repr(str(store_path)))
    )
    (cm_dir / "cache_manager.py").write_text(fake_src, encoding="utf-8")

    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True, exist_ok=True)
    (foo_dir / "foo.py").write_text(COMPONENT_SOURCE, encoding="utf-8")

    spec_dir = repo_root / "specs" / "components" / "foo"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n\n"
        "# Foo\n\nA synthetic component used as license-scan input.\n",
        encoding="utf-8",
    )
    return repo_root, log_path


def _write_corpus(path, entries):
    corpus = {
        "corpus_version": 0,
        "block_threshold": 0.70,
        "entries": entries,
    }
    data = json.dumps(corpus, indent=2).encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()[:12]


def _entry(ref_id, digit):
    return {
        "reference_id": ref_id,
        "license_family": "MIT",
        "risk_tier": "low",
        "hashes": [digit * 64],
    }


def _not_evaluated_payload():
    return {
        "component_id": "comp-foo",
        "gate_version": NOT_EVALUATED_GV,
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _evaluated_payload(gv):
    return {
        "component_id": "comp-foo",
        "gate_version": gv,
        "evaluated": True,
        "reason": None,
        "similarity_score": SEEDED_EVALUATED_SCORE,
        "block_threshold": 0.70,
        "blocked": True,
        "matches": [
            {
                "reference_id": SEEDED_REFERENCE_ID,
                "license_family": "gpl-3.0",
                "risk_tier": "high",
                "score": SEEDED_EVALUATED_SCORE,
            }
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _match_ref_ids(result):
    matches = _field(result, "matches") or []
    return [_field(m, "reference_id") for m in matches]


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for name in (
        "VAR_LICENSE_CORPUS_PATH",
        "VAR_COMPLIANCE_WEBHOOK_URL",
        "VAR_CACHE_STORE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return monkeypatch


def test_not_evaluated_cache_entry_not_reused_once_corpus_configured(tmp_path, clean_env):
    seeds = [
        {
            "gate_version": NOT_EVALUATED_GV,
            "payload": _not_evaluated_payload(),
            "stored_at": "2026-01-01T00:00:00Z",
        }
    ]
    repo_root, log_path = _make_repo(tmp_path, seeds)

    corpus_path = tmp_path / "corpus.json"
    h = _write_corpus(corpus_path, [_entry("ref-001", "a")])
    clean_env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    expected_gv = "license_scanner@4.0.0+" + h

    assert license_scanner.gate_version(repo_root) == expected_gv

    result = license_scanner.scan("comp-foo", repo_root)

    assert _field(result, "evaluated") is True
    assert _field(result, "gate_version") == expected_gv
    assert _field(result, "reason") is None
    assert not _field(result, "cache_hit")
    assert _field(result, "similarity_score") is not None
    assert _field(result, "block_threshold") is not None

    log = _read_log(log_path)
    gets = [r for r in log if r["op"] == "get"]
    hits = [r for r in log if r["op"] == "hit"]
    puts = [r for r in log if r["op"] == "put"]
    assert gets, "scan never consulted the stand-in cache-manager"
    assert any(g["key"]["gate_version"] == expected_gv for g in gets)
    assert all(g["key"]["gate_version"] != NOT_EVALUATED_GV for g in gets)
    assert not hits
    assert all(p["key"]["gate_version"] == expected_gv for p in puts)


def test_evaluated_cache_entry_not_reused_once_corpus_unset(tmp_path, clean_env):
    corpus_path = tmp_path / "corpus.json"
    h = _write_corpus(corpus_path, [_entry("ref-001", "a")])
    evaluated_gv = "license_scanner@4.0.0+" + h

    seeds = [
        {
            "gate_version": evaluated_gv,
            "payload": _evaluated_payload(evaluated_gv),
            "stored_at": "2026-01-01T00:00:00Z",
        }
    ]
    repo_root, log_path = _make_repo(tmp_path, seeds)

    clean_env.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)

    assert license_scanner.gate_version(repo_root) == NOT_EVALUATED_GV

    result = license_scanner.scan("comp-foo", repo_root)

    assert _field(result, "evaluated") is False
    assert _field(result, "reason") == "no-reference-corpus"
    assert _field(result, "gate_version") == NOT_EVALUATED_GV
    assert not _field(result, "cache_hit")
    assert _field(result, "similarity_score") is None
    assert _field(result, "block_threshold") is None
    assert list(_field(result, "matches") or []) == []
    assert _field(result, "blocked") is False
    assert SEEDED_REFERENCE_ID not in _match_ref_ids(result)

    log = _read_log(log_path)
    gets = [r for r in log if r["op"] == "get"]
    hits = [r for r in log if r["op"] == "hit"]
    puts = [r for r in log if r["op"] == "put"]
    assert all(g["key"]["gate_version"] != evaluated_gv for g in gets)
    assert not hits
    assert all(p["key"]["gate_version"] != evaluated_gv for p in puts)


def test_corpus_entry_added_without_version_bump_invalidates_cache(tmp_path, clean_env):
    corpus_path = tmp_path / "corpus.json"
    h_old = _write_corpus(corpus_path, [_entry("ref-001", "a")])
    old_gv = "license_scanner@4.0.0+" + h_old

    seeds = [
        {
            "gate_version": old_gv,
            "payload": _evaluated_payload(old_gv),
            "stored_at": "2026-01-01T00:00:00Z",
        }
    ]
    repo_root, log_path = _make_repo(tmp_path, seeds)

    h_new = _write_corpus(corpus_path, [_entry("ref-001", "a"), _entry("ref-002", "b")])
    assert h_new != h_old
    new_gv = "license_scanner@4.0.0+" + h_new
    clean_env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    assert license_scanner.gate_version(repo_root) == new_gv

    result = license_scanner.scan("comp-foo", repo_root)

    assert _field(result, "evaluated") is True
    assert _field(result, "gate_version") == new_gv
    assert not _field(result, "cache_hit")
    assert _field(result, "similarity_score") != SEEDED_EVALUATED_SCORE
    assert SEEDED_REFERENCE_ID not in _match_ref_ids(result)

    log = _read_log(log_path)
    gets = [r for r in log if r["op"] == "get"]
    hits = [r for r in log if r["op"] == "hit"]
    puts = [r for r in log if r["op"] == "put"]
    assert gets, "scan never consulted the stand-in cache-manager"
    assert any(g["key"]["gate_version"] == new_gv for g in gets)
    assert all(g["key"]["gate_version"] != old_gv for g in gets)
    assert not hits
    assert all(p["key"]["gate_version"] == new_gv for p in puts)