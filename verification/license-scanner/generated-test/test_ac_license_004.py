import json
import tempfile
from pathlib import Path

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _match_tuple(m):
    return (
        _get(m, "reference_id"),
        _get(m, "license_family"),
        _get(m, "risk_tier"),
        _get(m, "score"),
    )


def test_cache_hit_is_reused_and_no_rescan_is_performed():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        component_id = "comp-foo"
        slug = "foo"

        gen_dir = repo_root / "gen" / slug
        gen_dir.mkdir(parents=True)
        (gen_dir / f"{slug}.py").write_text(
            "\n".join(f"placeholder_{i} = {i}" for i in range(20)),
            encoding="utf-8",
        )

        expected_gate_version = license_scanner.gate_version(repo_root)

        log_path = repo_root / "cache_manager_calls.jsonl"

        hit_payload = {
            "component_id": component_id,
            "gate_version": expected_gate_version,
            "similarity_score": 0.91,
            "block_threshold": 0.70,
            "blocked": True,
            "matches": [
                {
                    "reference_id": "ref-999",
                    "license_family": "gpl-3.0",
                    "risk_tier": "high",
                    "score": 0.91,
                }
            ],
            "notified": True,
            "notification_delivery_error": None,
            "cache_hit": True,
        }

        fake_module_src = f'''
import dataclasses
import json

LOG_PATH = {str(log_path)!r}


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


_HIT_PAYLOAD = {hit_payload!r}


def _record(fn, cache_key):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{
            "fn": fn,
            "spec_bundle_hash": cache_key.spec_bundle_hash,
            "gate_inputs_hash": cache_key.gate_inputs_hash,
            "gate_version": cache_key.gate_version,
            "model_pin": cache_key.model_pin,
        }}) + "\\n")


def get(cache_key, *, repo_root=None):
    _record("get", cache_key)
    return CachedResult(
        gate_type="license_scanner",
        payload=dict(_HIT_PAYLOAD),
        stored_at="2026-01-01T00:00:00Z",
    )


def put(cache_key, result, *, repo_root=None):
    _record("put", cache_key)
'''

        cache_manager_dir = repo_root / "gen" / "cache-manager"
        cache_manager_dir.mkdir(parents=True)
        (cache_manager_dir / "cache_manager.py").write_text(
            fake_module_src, encoding="utf-8"
        )

        result = license_scanner.scan(component_id, repo_root)

        assert log_path.exists(), "cache-manager.get was never invoked"
        records = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line
        ]

        get_records = [r for r in records if r["fn"] == "get"]
        put_records = [r for r in records if r["fn"] == "put"]

        assert len(get_records) == 1, "expected exactly one cache-manager.get lookup"
        assert len(put_records) == 0, (
            "a fresh scan was performed (cache-manager.put was called) "
            "despite an existing cache hit"
        )

        logged_key = get_records[0]
        for field in ("spec_bundle_hash", "gate_inputs_hash", "gate_version", "model_pin"):
            assert field in logged_key
        assert logged_key["gate_version"] == expected_gate_version

        assert _get(result, "component_id") == hit_payload["component_id"]
        assert _get(result, "gate_version") == hit_payload["gate_version"]
        assert _get(result, "similarity_score") == hit_payload["similarity_score"]
        assert _get(result, "block_threshold") == hit_payload["block_threshold"]
        assert _get(result, "blocked") == hit_payload["blocked"]
        assert _get(result, "notified") == hit_payload["notified"]
        assert _get(result, "notification_delivery_error") == hit_payload[
            "notification_delivery_error"
        ]
        assert _get(result, "cache_hit") == hit_payload["cache_hit"]

        result_matches = _get(result, "matches")
        assert [_match_tuple(m) for m in result_matches] == [
            _match_tuple(m) for m in hit_payload["matches"]
        ]