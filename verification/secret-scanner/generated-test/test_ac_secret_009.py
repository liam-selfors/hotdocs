# hotdocs-criterion: sha256:3046d392a7efc0437b6b25e37a330b6e0423da326a0835a61319b55cd5392044
"""AC-SECRET-009 (covers R-SECRET-009).

A flagged SecretScanResult stays recorded in cache-manager under its own
key after the files are cleaned and the scan runs again; the clean result
is written under a different key and never overwrites the flagged one.
"""

import json
import os
import textwrap
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


# The planted key is assembled here so that this test file itself carries
# no contiguous credential-shaped literal; the fixture file gets the full
# literal exactly as the criterion describes.
PLANTED_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"

STORE_ENV = "AC009_STORE_PATH"
LOG_ENV = "AC009_LOG_PATH"


# The stand-in cache-manager. It is scanned along with the rest of the
# repo, so it embeds no long random-looking literal and no temp path: it
# reads its store and log locations from environment variables, and both
# files live OUTSIDE repo_root so they never change what a scan sees.
FAKE_CACHE_MANAGER = textwrap.dedent(
    '''
    import dataclasses
    import json
    import os
    from datetime import datetime, timezone


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
            return 0

        def __repr__(self):
            return "Miss()"


    class SchemaValidationError(ValueError):
        pass


    REQUIRED_KEYS = ("scope", "gate_version", "flagged", "matches")


    def _store_path():
        return os.environ["AC009_STORE_PATH"]


    def _log_path():
        return os.environ["AC009_LOG_PATH"]


    def _field(obj, name):
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)


    def _key_text(cache_key):
        return json.dumps(
            {
                "spec_bundle_hash": _field(cache_key, "spec_bundle_hash"),
                "gate_inputs_hash": _field(cache_key, "gate_inputs_hash"),
                "gate_version": _field(cache_key, "gate_version"),
                "model_pin": _field(cache_key, "model_pin"),
            },
            sort_keys=True,
        )


    def _plain(value):
        if isinstance(value, dict):
            return value
        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            return to_dict()
        if dataclasses.is_dataclass(value):
            return dataclasses.asdict(value)
        return dict(vars(value))


    def _load():
        path = _store_path()
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)


    def _save(store):
        with open(_store_path(), "w", encoding="utf-8") as fh:
            json.dump(store, fh, default=str)


    def _record(entry):
        with open(_log_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\\n")


    def now_iso():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


    def get(cache_key, *, repo_root=None):
        key = _key_text(cache_key)
        _record({"op": "get", "key": key})
        entry = _load().get(key)
        if entry is None:
            return Miss()
        return CachedResult(
            gate_type=entry["gate_type"],
            payload=entry["payload"],
            stored_at=entry["stored_at"],
        )


    def put(cache_key, result, *, repo_root=None):
        gate_type = _field(result, "gate_type")
        gate_version = _field(cache_key, "gate_version") or ""
        if gate_version.split("@")[0] != gate_type:
            raise SchemaValidationError("gate_type does not match gate_version")
        payload = _plain(_field(result, "payload"))
        for name in REQUIRED_KEYS:
            if name not in payload:
                raise SchemaValidationError("missing payload key: " + name)
        key = _key_text(cache_key)
        store = _load()
        store[key] = {
            "gate_type": gate_type,
            "payload": json.loads(json.dumps(payload, default=str)),
            "stored_at": _field(result, "stored_at"),
        }
        _save(store)
        _record({"op": "put", "key": key, "flagged": payload.get("flagged")})
        return None


    def stats(*, repo_root=None):
        return {"entry_count": len(_load())}
    '''
).lstrip()


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _read_log(path):
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def test_ac_secret_009_flagged_result_survives_clean_rescan(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    records_dir = tmp_path / "records"
    repo_root.mkdir()
    records_dir.mkdir()

    store_path = records_dir / "store.json"
    log_path = records_dir / "calls.jsonl"
    monkeypatch.setenv(STORE_ENV, str(store_path))
    monkeypatch.setenv(LOG_ENV, str(log_path))

    # No webhook configured, and the one delivery function replaced so no
    # real network call can ever happen.
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    webhook_calls = []

    def _fake_urlopen(*args, **kwargs):
        webhook_calls.append((args, kwargs))
        raise AssertionError("urlopen must not be called without a webhook URL")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    # Stand-in cache-manager, flat-module shape.
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    # Planted secret.
    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True)
    target = foo_dir / "c.py"
    target.write_text('K = "' + PLANTED_KEY + '"\n', encoding="utf-8")

    # First scan: flagged.
    first = secret_scanner.scan(repo_root)
    assert _get(first, "flagged") is True, first
    first_matches = _get(first, "matches") or []
    assert len(first_matches) >= 1
    assert any(
        (_get(m, "file") == "gen/foo/c.py") for m in first_matches
    ), first_matches
    assert _get(first, "cache_hit") is False

    puts_after_first = [r for r in _read_log(log_path) if r.get("op") == "put"]
    assert len(puts_after_first) == 1, puts_after_first
    flagged_key = puts_after_first[0]["key"]

    # Clean the file: the key is removed.
    target.write_text("K = None\n", encoding="utf-8")

    # Second scan: clean.
    second = secret_scanner.scan(repo_root)
    assert _get(second, "flagged") is False, second
    assert (_get(second, "matches") or []) == []
    assert _get(second, "cache_hit") is False

    # put was called exactly twice, under two different keys.
    puts = [r for r in _read_log(log_path) if r.get("op") == "put"]
    assert len(puts) == 2, puts
    assert puts[0]["key"] == flagged_key
    clean_key = puts[1]["key"]
    assert flagged_key != clean_key

    # Both results are stored, and the flagged one was never overwritten.
    store = json.loads(store_path.read_text(encoding="utf-8"))
    assert flagged_key in store, list(store)
    assert clean_key in store, list(store)

    flagged_entry = store[flagged_key]
    assert flagged_entry["gate_type"] == "secret_scanner"
    assert flagged_entry["payload"].get("flagged") is True
    assert len(flagged_entry["payload"].get("matches") or []) >= 1

    clean_entry = store[clean_key]
    assert clean_entry["gate_type"] == "secret_scanner"
    assert clean_entry["payload"].get("flagged") is False

    # Each key's gate_version names the secret_scanner gate type.
    assert json.loads(flagged_key)["gate_version"].startswith("secret_scanner@")
    assert json.loads(clean_key)["gate_version"].startswith("secret_scanner@")

    assert webhook_calls == []