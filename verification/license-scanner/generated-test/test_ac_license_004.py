# hotdocs-criterion: sha256:55708a254d0800e3ec29bc2c702f1c4a86dcad1161581f5aa81ea150e2507975
import hashlib
import json
import re
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-foo"
COMPONENT_SLUG = "foo"

SOURCE_TEXT = """def accumulate_values(first_value, second_value, third_value):
    running_total = first_value + second_value
    running_total = running_total * third_value
    return running_total


class LedgerKeeper:
    def __init__(self, opening_balance):
        self.balance = opening_balance

    def deposit(self, amount):
        self.balance = self.balance + amount
        return self.balance

    def withdraw(self, amount):
        self.balance = self.balance - amount
        return self.balance
"""


FAKE_CACHE_MANAGER_TEMPLATE = '''
import json
import os
from dataclasses import dataclass, asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

_LOG_PATH = __LOG_PATH__
_STORE_PATH = __STORE_PATH__
_MODE = __MODE__
_HIT_PAYLOAD = json.loads(__HIT_PAYLOAD_JSON__)

_KEY_FIELDS = ("spec_bundle_hash", "gate_inputs_hash", "gate_version", "model_pin")

_REQUIRED = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0

    def __repr__(self):
        return "Miss()"


class SchemaValidationError(ValueError):
    pass


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _key_dict(cache_key):
    return {f: _field(cache_key, f) for f in _KEY_FIELDS}


def _key_str(cache_key):
    return json.dumps(_key_dict(cache_key), sort_keys=True, default=str)


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, default=str) + "\\n")


def _load_store():
    if not os.path.exists(_STORE_PATH):
        return {}
    with open(_STORE_PATH, "r", encoding="utf-8") as fh:
        text = fh.read()
    if not text.strip():
        return {}
    return json.loads(text)


def _save_store(store):
    tmp = _STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(store, fh, sort_keys=True, default=str)
    os.replace(tmp, _STORE_PATH)


def _payload_as_dict(payload):
    if isinstance(payload, dict):
        return payload
    if is_dataclass(payload) and not isinstance(payload, type):
        return asdict(payload)
    return payload


def get(cache_key, *, repo_root=None):
    _log({
        "op": "get",
        "key": _key_dict(cache_key),
        "is_cache_key": isinstance(cache_key, CacheKey),
        "repo_root": str(repo_root) if repo_root is not None else None,
    })
    if _MODE == "always_hit":
        return CachedResult(
            gate_type="license_scanner",
            payload=dict(_HIT_PAYLOAD),
            stored_at="2026-01-01T00:00:00Z",
        )
    try:
        store = _load_store()
    except Exception:
        return Miss()
    entry = store.get(_key_str(cache_key))
    if entry is None:
        return Miss()
    return CachedResult(
        gate_type=entry["gate_type"],
        payload=entry["payload"],
        stored_at=entry["stored_at"],
    )


def put(cache_key, result, *, repo_root=None):
    gate_type = _field(result, "gate_type")
    payload = _payload_as_dict(_field(result, "payload"))
    stored_at = _field(result, "stored_at")
    key = _key_dict(cache_key)
    _log({
        "op": "put",
        "key": key,
        "is_cache_key": isinstance(cache_key, CacheKey),
        "is_cached_result": isinstance(result, CachedResult),
        "gate_type": gate_type,
        "stored_at": stored_at,
        "repo_root": str(repo_root) if repo_root is not None else None,
    })
    gv = key.get("gate_version") or ""
    expected_type = str(gv).split("@", 1)[0]
    if gate_type != expected_type or gate_type not in _REQUIRED:
        raise SchemaValidationError("gate_type mismatch: %r vs %r" % (gate_type, expected_type))
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload is not a mapping")
    missing = [k for k in _REQUIRED[gate_type] if k not in payload]
    if missing:
        raise SchemaValidationError("payload missing keys: %r" % (missing,))
    store = _load_store()
    store[_key_str(cache_key)] = {
        "gate_type": gate_type,
        "payload": json.loads(json.dumps(payload, default=str)),
        "stored_at": str(stored_at),
    }
    _save_store(store)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    try:
        return {"entry_count": len(_load_store())}
    except Exception:
        return {"entry_count": 0}


def main(argv=None):
    return 0
'''


def _f(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _tokens(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    return [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]


def _window_hashes(text):
    toks = _tokens(text)
    out = set()
    for i in range(len(toks) - 9 + 1):
        window = "\x1f".join(toks[i:i + 9])
        out.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(out)


def _write_fake_cache_manager(repo_root, log_path, store_path, mode, hit_payload):
    src = FAKE_CACHE_MANAGER_TEMPLATE
    src = src.replace("__LOG_PATH__", repr(str(log_path)))
    src = src.replace("__STORE_PATH__", repr(str(store_path)))
    src = src.replace("__MODE__", repr(mode))
    src = src.replace("__HIT_PAYLOAD_JSON__", repr(json.dumps(hit_payload)))
    target_dir = repo_root / "gen" / "cache-manager"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "cache_manager.py").write_text(src, encoding="utf-8")


def _build_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Synthetic spec fixture for the scanned component.
    comp_dir = repo_root / "specs" / "components" / COMPONENT_SLUG
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)
    (comp_dir / "interface").mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo\n"
        "---\n"
        "# Foo\n\nA small synthetic component used as a license-scan subject.\n",
        encoding="utf-8",
    )
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST accumulate values.\n",
        encoding="utf-8",
    )
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
        encoding="utf-8",
    )
    (comp_dir / "interface" / "library.md").write_text(
        "# Library\n\n```\naccumulate_values(a, b, c)\n```\n",
        encoding="utf-8",
    )

    # The component's code, both under gen/ and at the sealed source_path,
    # so whichever the scanner reads, it reads the same content.
    gen_dir = repo_root / "gen" / COMPONENT_SLUG
    gen_dir.mkdir(parents=True)
    (gen_dir / "foo.py").write_text(SOURCE_TEXT, encoding="utf-8")
    legacy_dir = repo_root / "legacy" / COMPONENT_SLUG
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "foo.py").write_text(SOURCE_TEXT, encoding="utf-8")

    # A usable corpus whose single entry matches every window of the source,
    # so a genuine fresh scan would score 1.0 and be blocked.
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-real-001",
                "license_family": "GPL",
                "risk_tier": "medium",
                "hashes": _window_hashes(SOURCE_TEXT),
            }
        ],
    }
    assert corpus["entries"][0]["hashes"], "fixture must yield at least one window"
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)
    return repo_root


def _read_log(log_path):
    if not Path(log_path).exists():
        return []
    lines = Path(log_path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _sentinel_payload(gate_version):
    return {
        "component_id": COMPONENT_ID,
        "gate_version": gate_version,
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.0123,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [
            {
                "reference_id": "ref-cached-sentinel",
                "license_family": "mit",
                "risk_tier": "low",
                "score": 0.0123,
            }
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _assert_is_sentinel(result):
    assert _f(result, "component_id") == COMPONENT_ID
    assert _f(result, "similarity_score") == pytest.approx(0.0123)
    assert _f(result, "blocked") is False
    matches = _f(result, "matches")
    assert matches is not None
    matches = list(matches)
    assert len(matches) == 1
    assert _f(matches[0], "reference_id") == "ref-cached-sentinel"


def test_cache_hit_returns_cached_result_without_rescan(tmp_path, monkeypatch):
    repo_root = _build_repo(tmp_path, monkeypatch)
    expected_gate_version = license_scanner.gate_version(repo_root)

    log_path = tmp_path / "cache_calls.log"
    store_path = tmp_path / "cache_store.json"
    _write_fake_cache_manager(
        repo_root,
        log_path,
        store_path,
        "always_hit",
        _sentinel_payload(expected_gate_version),
    )

    result = license_scanner.scan(COMPONENT_ID, repo_root)

    calls = _read_log(log_path)
    gets = [c for c in calls if c.get("op") == "get"]
    puts = [c for c in calls if c.get("op") == "put"]

    assert gets, "scan must consult cache-manager.get before scanning"
    assert gets[0]["is_cache_key"] is True
    assert set(gets[0]["key"].keys()) == {
        "spec_bundle_hash",
        "gate_inputs_hash",
        "gate_version",
        "model_pin",
    }
    assert gets[0]["key"]["gate_version"] == expected_gate_version

    # The cached result is what is returned; a fresh scan of this fixture
    # would have scored 1.0 against the corpus and been blocked.
    _assert_is_sentinel(result)
    # No rescan: nothing fresh was produced to store.
    assert puts == []


def test_matching_inputs_hit_the_exact_key_stored_by_a_prior_scan(tmp_path, monkeypatch):
    repo_root = _build_repo(tmp_path, monkeypatch)
    expected_gate_version = license_scanner.gate_version(repo_root)

    log_path = tmp_path / "cache_calls.log"
    store_path = tmp_path / "cache_store.json"
    _write_fake_cache_manager(repo_root, log_path, store_path, "store", {})

    # First run: a miss, so a fresh scan happens and is stored under its key.
    first = license_scanner.scan(COMPONENT_ID, repo_root)
    assert _f(first, "component_id") == COMPONENT_ID

    calls_after_first = _read_log(log_path)
    first_gets = [c for c in calls_after_first if c.get("op") == "get"]
    first_puts = [c for c in calls_after_first if c.get("op") == "put"]
    assert len(first_gets) >= 1
    assert len(first_puts) == 1, "a fresh scan after a miss must be stored once"
    stored_key = first_puts[0]["key"]
    assert first_puts[0]["is_cache_key"] is True
    assert first_puts[0]["is_cached_result"] is True
    assert first_puts[0]["gate_type"] == "license_scanner"
    assert stored_key["gate_version"] == expected_gate_version
    assert stored_key["spec_bundle_hash"] is not None
    assert stored_key["gate_inputs_hash"] is not None
    assert first_gets[0]["key"] == stored_key

    store = json.loads(store_path.read_text(encoding="utf-8"))
    assert len(store) == 1
    (entry_key,) = list(store.keys())

    # Replace the stored payload with a recognizable sentinel under the very
    # same key, so only a genuine cache reuse can produce it.
    stored_gate_version = store[entry_key]["payload"].get("gate_version", expected_gate_version)
    store[entry_key]["payload"] = _sentinel_payload(stored_gate_version)
    store_path.write_text(json.dumps(store), encoding="utf-8")

    # Second run with identical inputs.
    second = license_scanner.scan(COMPONENT_ID, repo_root)

    calls_after_second = _read_log(log_path)
    new_calls = calls_after_second[len(calls_after_first):]
    new_gets = [c for c in new_calls if c.get("op") == "get"]
    new_puts = [c for c in new_calls if c.get("op") == "put"]

    assert new_gets, "second scan must consult the cache"
    assert new_gets[0]["key"] == stored_key, "matching inputs must yield the exact same key"
    _assert_is_sentinel(second)
    assert new_puts == [], "a cache hit must not trigger a rescan/store"