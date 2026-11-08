import json
import os
import tempfile
from pathlib import Path

import license_scanner


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def test_ac_license_004_cache_hit_returns_cached_result_without_rescan():
    with tempfile.TemporaryDirectory() as repo_root_str:
        repo_root = Path(repo_root_str)
        cache_manager_dir = repo_root / "gen" / "cache-manager"
        cache_manager_dir.mkdir(parents=True)
        log_path = repo_root / "fake_cache_manager.log"

        saved_corpus_var = os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
        os.environ["FAKE_CACHE_MANAGER_LOG"] = str(log_path)
        try:
            component_id = "comp-license-scanner-ac004-fixture"

            # No corpus configured -> deterministic, documented gate_version
            # string, computed without touching cache-manager or scanning
            # anything (per interface/library.md's gate_version contract).
            expected_gate_version = license_scanner.gate_version(repo_root)
            assert expected_gate_version == "license_scanner@4.0.0-no-reference-corpus"

            # A payload that a fresh "no-reference-corpus" scan could never
            # produce (evaluated=True, a concrete similarity_score, a match)
            # so that returning it verbatim proves the cached result was
            # reused rather than recomputed.
            cached_payload = {
                "component_id": component_id,
                "gate_version": expected_gate_version,
                "evaluated": True,
                "reason": None,
                "similarity_score": 0.9999,
                "block_threshold": 0.70,
                "blocked": True,
                "matches": [
                    {
                        "reference_id": "ref-ac004-impossible",
                        "license_family": "gpl-3.0",
                        "risk_tier": "high",
                        "score": 0.9999,
                    }
                ],
                "notified": True,
                "notification_delivery_error": None,
                "cache_hit": False,
            }

            fake_module_source = (
                "import dataclasses\n"
                "import json\n"
                "import os\n"
                "\n"
                "@dataclasses.dataclass\n"
                "class CacheKey:\n"
                "    spec_bundle_hash: str\n"
                "    gate_inputs_hash: str\n"
                "    gate_version: str\n"
                "    model_pin: str\n"
                "\n"
                "@dataclasses.dataclass\n"
                "class CachedResult:\n"
                "    gate_type: str\n"
                "    payload: object\n"
                "    stored_at: str\n"
                "\n"
                "_LOG_PATH = os.environ['FAKE_CACHE_MANAGER_LOG']\n"
                "_CACHED_PAYLOAD = " + repr(cached_payload) + "\n"
                "\n"
                "def _append_log(record):\n"
                "    with open(_LOG_PATH, 'a', encoding='utf-8') as fh:\n"
                "        fh.write(json.dumps(record) + chr(10))\n"
                "\n"
                "def get(cache_key, *, repo_root=None):\n"
                "    _append_log({'op': 'get', 'key': dataclasses.asdict(cache_key)})\n"
                "    return CachedResult(\n"
                "        gate_type='license_scanner',\n"
                "        payload=dict(_CACHED_PAYLOAD),\n"
                "        stored_at='2026-01-01T00:00:00Z',\n"
                "    )\n"
                "\n"
                "def put(cache_key, result, *, repo_root=None):\n"
                "    _append_log({'op': 'put', 'key': dataclasses.asdict(cache_key)})\n"
            )

            (cache_manager_dir / "cache_manager.py").write_text(
                fake_module_source, encoding="utf-8"
            )

            result = license_scanner.scan(component_id, repo_root)

            assert result is not None

            assert log_path.exists(), "cache-manager's get() was never invoked"
            log_lines = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            get_calls = [entry for entry in log_lines if entry["op"] == "get"]
            put_calls = [entry for entry in log_lines if entry["op"] == "put"]

            assert len(get_calls) == 1, "expected exactly one cache-manager lookup"
            assert put_calls == [], (
                "a cache hit must not be followed by a put (no rescan was performed)"
            )

            used_key = get_calls[0]["key"]
            assert set(used_key.keys()) == {
                "spec_bundle_hash",
                "gate_inputs_hash",
                "gate_version",
                "model_pin",
            }, "cache key must use cache-manager's own canonical field names"
            assert used_key["gate_version"] == expected_gate_version
            assert isinstance(used_key["spec_bundle_hash"], str) and used_key["spec_bundle_hash"]
            assert isinstance(used_key["gate_inputs_hash"], str) and used_key["gate_inputs_hash"]
            assert isinstance(used_key["model_pin"], str) and used_key["model_pin"]

            assert _field(result, "cache_hit") is True
            assert _field(result, "component_id") == component_id
            assert _field(result, "gate_version") == expected_gate_version
            assert _field(result, "evaluated") is True
            assert _field(result, "reason") is None
            assert _field(result, "similarity_score") == 0.9999
            assert _field(result, "block_threshold") == 0.70
            assert _field(result, "blocked") is True

            matches = _field(result, "matches")
            assert matches is not None and len(matches) == 1
            match = matches[0]
            assert _field(match, "reference_id") == "ref-ac004-impossible"
            assert _field(match, "license_family") == "gpl-3.0"
            assert _field(match, "risk_tier") == "high"
            assert _field(match, "score") == 0.9999

            assert _field(result, "notified") is True
            assert _field(result, "notification_delivery_error") is None
        finally:
            os.environ.pop("FAKE_CACHE_MANAGER_LOG", None)
            if saved_corpus_var is not None:
                os.environ["VAR_LICENSE_CORPUS_PATH"] = saved_corpus_var