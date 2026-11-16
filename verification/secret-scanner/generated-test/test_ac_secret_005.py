import json
import sys
import textwrap
import urllib.request
from pathlib import Path


FAKE_CACHE_MANAGER_SOURCE = textwrap.dedent(
    '''
    import dataclasses
    import datetime
    import json
    import os
    from pathlib import Path


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


    class SchemaValidationError(ValueError):
        pass


    _FIELDS = ("spec_bundle_hash", "gate_inputs_hash", "gate_version", "model_pin")
    _REQUIRED = ("scope", "gate_version", "flagged", "matches")


    def _state_dir():
        return Path(os.environ["FAKE_CACHE_STATE_DIR"])


    def _read(obj, name):
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)


    def _fields_of(cache_key):
        return {f: _read(cache_key, f) for f in _FIELDS}


    def _log(record):
        d = _state_dir()
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "calls.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\\n")


    def get(cache_key, *, repo_root=None):
        fields = _fields_of(cache_key)
        _log({"op": "get", "fields": fields})
        cfg = _state_dir() / "hit.json"
        if cfg.exists():
            data = json.loads(cfg.read_text(encoding="utf-8"))
            if data.get("fields") == fields:
                return CachedResult(
                    gate_type=data["gate_type"],
                    payload=data["payload"],
                    stored_at=data["stored_at"],
                )
        return Miss()


    def put(cache_key, result, *, repo_root=None):
        fields = _fields_of(cache_key)
        gate_type = _read(result, "gate_type")
        payload = _read(result, "payload")
        _log({"op": "put", "fields": fields, "gate_type": gate_type, "payload": payload})
        expected_type = str(fields.get("gate_version") or "").split("@")[0]
        if gate_type != expected_type:
            raise SchemaValidationError("gate_type does not match gate_version")
        if not isinstance(payload, dict):
            raise SchemaValidationError("payload must be a mapping")
        for name in _REQUIRED:
            if name not in payload:
                raise SchemaValidationError("missing payload field: " + name)
        return None


    def now_iso():
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


    def stats(*, repo_root=None):
        return {"entry_count": 0}
    '''
).lstrip()


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _normalize_match(m):
    return {
        "rule_id": _get(m, "rule_id"),
        "risk_tier": _get(m, "risk_tier"),
        "file": _get(m, "file"),
        "line": _get(m, "line"),
    }


def _read_calls(state_dir):
    log = state_dir / "calls.jsonl"
    if not log.exists():
        return []
    out = []
    for line in log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _build_repo(repo_root):
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8")

    comp_dir = repo_root / "specs" / "components" / "demo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-demo\n"
        "title: Demo\n"
        "status: draft\n"
        "owners: [demo-owner]\n"
        "sealed: true\n"
        "source_path: legacy/demo\n"
        "---\n"
        "\n"
        "# Demo\n"
        "\n"
        "A harmless demo component.\n",
        encoding="utf-8",
    )

    app_dir = repo_root / "gen" / "demo"
    app_dir.mkdir(parents=True)
    (app_dir / "app.py").write_text(
        "def greet(name):\n"
        "    return 'hello ' + name\n",
        encoding="utf-8",
    )


def test_ac_secret_005_cache_hit_is_reused_without_rescan_or_put(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    state_dir = tmp_path / "cache-state"
    repo_root.mkdir()
    state_dir.mkdir()
    _build_repo(repo_root)

    monkeypatch.setenv("FAKE_CACHE_STATE_DIR", str(state_dir))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    # Keep the scanned file set identical between runs (no __pycache__ appearing).
    monkeypatch.setattr(sys, "dont_write_bytecode", True)

    webhook_calls = []

    def _fake_urlopen(*args, **kwargs):
        webhook_calls.append((args, kwargs))
        raise OSError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    import secret_scanner

    # Phase 1: cache miss -> fresh scan, which learns the exact full-scan key.
    first = secret_scanner.scan(repo_root)
    calls1 = _read_calls(state_dir)
    gets1 = [c for c in calls1 if c.get("op") == "get"]
    puts1 = [c for c in calls1 if c.get("op") == "put"]

    assert gets1, "full scan must consult cache-manager.get before scanning"
    assert _get(first, "cache_hit") is False
    assert puts1, "a fresh full scan on a miss is expected to call put"

    key_fields = gets1[-1]["fields"]
    assert str(key_fields["spec_bundle_hash"]).startswith("sha256:")
    assert str(key_fields["gate_inputs_hash"]).startswith("sha256:")
    assert str(key_fields["gate_version"]).startswith("secret_scanner@")
    assert key_fields["model_pin"] == "none"

    planted_matches = [
        {
            "rule_id": "AWS Access Key",
            "risk_tier": "high",
            "file": "gen/foo/config.py",
            "line": 12,
        }
    ]
    assert not (repo_root / "gen" / "foo" / "config.py").exists()

    first_matches = [_normalize_match(m) for m in (_get(first, "matches") or [])]
    for planted in planted_matches:
        assert planted not in first_matches, (
            "the planted cached match must differ from what a fresh scan finds"
        )

    # Phase 2: cache-manager now holds a result for that exact key.
    cached_payload = {
        "scope": "full",
        "gate_version": key_fields["gate_version"],
        "flagged": True,
        "matches": planted_matches,
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    (state_dir / "hit.json").write_text(
        json.dumps(
            {
                "fields": key_fields,
                "gate_type": "secret_scanner",
                "payload": cached_payload,
                "stored_at": "2026-10-02T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "calls.jsonl").unlink()

    second = secret_scanner.scan(repo_root)
    calls2 = _read_calls(state_dir)
    gets2 = [c for c in calls2 if c.get("op") == "get"]
    puts2 = [c for c in calls2 if c.get("op") == "put"]

    assert gets2, "full scan must consult cache-manager.get"
    assert gets2[-1]["fields"] == key_fields, (
        "matching inputs must yield the exact same full-scan cache key"
    )
    assert puts2 == [], "put must not be called on a cache hit"

    assert _get(second, "cache_hit") is True
    second_matches = [_normalize_match(m) for m in (_get(second, "matches") or [])]
    assert second_matches == planted_matches, (
        "a cache hit must return exactly the cached matches, not a fresh scan's"
    )