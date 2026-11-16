import hashlib
import json
import re
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-sample-widget"
COMPONENT_SLUG = "sample-widget"


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _snapshot(result):
    names = [
        "component_id",
        "gate_version",
        "evaluated",
        "reason",
        "similarity_score",
        "block_threshold",
        "blocked",
        "matches",
        "notified",
        "notification_delivery_error",
        "cache_hit",
    ]
    snap = {}
    for n in names:
        v = _field(result, n)
        if n == "matches" and v is not None:
            normalized = []
            for m in v:
                normalized.append(
                    {
                        "reference_id": _field(m, "reference_id"),
                        "license_family": _field(m, "license_family"),
                        "risk_tier": _field(m, "risk_tier"),
                        "score": _field(m, "score"),
                    }
                )
            v = normalized
        snap[n] = v
    return snap


def _tokens(text):
    return [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]


def _window_hashes(text):
    toks = _tokens(text)
    out = []
    for i in range(len(toks) - 8):
        window = "\x1f".join(toks[i : i + 9])
        out.append(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return out


# Comment-free, docstring-free source so the stripping rules never matter.
FLAGGED_SOURCE = (
    "def alpha_reticulate(bravo_items, charlie_limit):\n"
    "    delta_total = 0\n"
    "    for echo_item in bravo_items:\n"
    "        foxtrot_weight = echo_item.golf_value * 17\n"
    "        if foxtrot_weight > charlie_limit:\n"
    "            hotel_overflow = foxtrot_weight - charlie_limit\n"
    "            delta_total = delta_total + hotel_overflow\n"
    "        else:\n"
    "            delta_total = delta_total + india_baseline(foxtrot_weight, 42)\n"
    "    return juliet_finalize(delta_total, kilo_mode=3)\n"
    "\n"
    "def india_baseline(lima_value, mike_factor):\n"
    "    november_result = lima_value * mike_factor + 99\n"
    "    return oscar_clamp(november_result, papa_low=1, quebec_high=1000)\n"
)

CLEAN_SOURCE = (
    "def zebra_compose(yak_parts, xylo_sep):\n"
    "    wombat_buffer = []\n"
    "    for vulture_piece in yak_parts:\n"
    "        wombat_buffer.append(umbra_render(vulture_piece))\n"
    "    return xylo_sep.join(wombat_buffer)\n"
    "\n"
    "def umbra_render(tapir_node):\n"
    "    if tapir_node is None:\n"
    "        return sable_default\n"
    "    return raven_format(tapir_node, quill_width=8, pelican_pad=5)\n"
)


FAKE_CACHE_MANAGER = r'''
import json
from dataclasses import dataclass
from pathlib import Path

_LOG_PATH = Path(__LOG_PATH__)
_STORE_PATH = Path(__STORE_PATH__)

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


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def _key_str(cache_key):
    return json.dumps(
        [
            cache_key.spec_bundle_hash,
            cache_key.gate_inputs_hash,
            cache_key.gate_version,
            cache_key.model_pin,
        ],
        default=str,
    )


def _load_store():
    if _STORE_PATH.exists():
        return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_store(store):
    tmp = _STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, default=str), encoding="utf-8")
    tmp.replace(_STORE_PATH)


def get(cache_key, *, repo_root=None):
    k = _key_str(cache_key)
    store = _load_store()
    hit = k in store
    _log({"op": "get", "key": k, "hit": hit})
    if hit:
        entry = store[k]
        return CachedResult(
            gate_type=entry["gate_type"],
            payload=entry["payload"],
            stored_at=entry["stored_at"],
        )
    return Miss()


def put(cache_key, result, *, repo_root=None):
    gate_type = str(cache_key.gate_version).split("@", 1)[0]
    if result.gate_type != gate_type:
        raise SchemaValidationError("gate_type mismatch")
    if gate_type not in _REQUIRED:
        raise SchemaValidationError("unknown gate type")
    payload = result.payload
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload not a dict")
    for req in _REQUIRED[gate_type]:
        if req not in payload:
            raise SchemaValidationError("missing key " + req)
    payload_copy = json.loads(json.dumps(payload, default=str))
    k = _key_str(cache_key)
    store = _load_store()
    store[k] = {
        "gate_type": result.gate_type,
        "payload": payload_copy,
        "stored_at": result.stored_at,
    }
    _save_store(store)
    _log({"op": "put", "key": k, "payload": payload_copy})


def now_iso():
    _log({"op": "now_iso"})
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": len(_load_store())}
'''


def _write_fake_cache_manager(repo_root, log_path, store_path):
    dep_dir = repo_root / "gen" / "cache-manager"
    dep_dir.mkdir(parents=True, exist_ok=True)
    content = FAKE_CACHE_MANAGER.replace("__LOG_PATH__", repr(str(log_path))).replace(
        "__STORE_PATH__", repr(str(store_path))
    )
    (dep_dir / "cache_manager.py").write_text(content, encoding="utf-8")


def _read_log(log_path):
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _write_component_source(repo_root, text):
    comp_dir = repo_root / "gen" / COMPONENT_SLUG
    comp_dir.mkdir(parents=True, exist_ok=True)
    for existing in comp_dir.glob("*.py"):
        existing.unlink()
    (comp_dir / "sample_widget.py").write_text(text, encoding="utf-8")


def test_ac_license_007_flagged_result_survives_clean_retry(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    log_path = logs_dir / "cache_calls.jsonl"
    store_path = logs_dir / "cache_store.json"

    _write_fake_cache_manager(repo_root, log_path, store_path)

    flagged_hashes = sorted(set(_window_hashes(FLAGGED_SOURCE)))
    clean_hashes = set(_window_hashes(CLEAN_SOURCE))
    assert len(flagged_hashes) > 0
    assert len(clean_hashes) > 0
    assert clean_hashes.isdisjoint(flagged_hashes)

    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": flagged_hashes,
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)

    # First generation sample: scans flagged.
    _write_component_source(repo_root, FLAGGED_SOURCE)
    flagged = license_scanner.scan(COMPONENT_ID, repo_root)

    assert _field(flagged, "evaluated") is True
    assert _field(flagged, "blocked") is True
    assert _field(flagged, "similarity_score") >= _field(flagged, "block_threshold")
    assert len(_field(flagged, "matches") or []) >= 1
    flagged_snapshot = _snapshot(flagged)

    # Retried sample: scans clean.
    _write_component_source(repo_root, CLEAN_SOURCE)
    clean = license_scanner.scan(COMPONENT_ID, repo_root)

    assert _field(clean, "evaluated") is True
    assert _field(clean, "blocked") is False
    assert _field(clean, "similarity_score") < _field(clean, "block_threshold")

    # Retry is not a re-read of the flagged entry: it was a fresh scan.
    assert _field(clean, "cache_hit") is False

    # The original flagged result is still intact after the clean retry —
    # never overwritten or mutated into the clean one.
    assert _snapshot(flagged) == flagged_snapshot
    assert _field(flagged, "blocked") is True
    assert clean is not flagged

    # Both results are present side by side in the record the scanner wrote.
    records = _read_log(log_path)
    puts = [r for r in records if r.get("op") == "put"]
    assert len(puts) >= 2, records
    put_blocked_values = [r["payload"].get("blocked") for r in puts]
    assert True in put_blocked_values
    assert False in put_blocked_values

    store = json.loads(store_path.read_text(encoding="utf-8"))
    stored_blocked = [entry["payload"].get("blocked") for entry in store.values()]
    assert True in stored_blocked, store
    assert False in stored_blocked, store

    flagged_keys = [k for k, e in store.items() if e["payload"].get("blocked") is True]
    clean_keys = [k for k, e in store.items() if e["payload"].get("blocked") is False]
    assert set(flagged_keys).isdisjoint(clean_keys)

    for entry in store.values():
        assert entry["gate_type"] == "license_scanner"
        assert entry["payload"].get("component_id") == COMPONENT_ID