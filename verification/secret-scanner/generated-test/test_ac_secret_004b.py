import json
import urllib.request

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_low_risk_tier_blocking_match_still_notifies(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)
    (repo_root / "gen" / "cache-manager").mkdir(parents=True)
    (repo_root / "verification").mkdir(parents=True)

    secret_value = "HIGHENTROPYSECRETVALUE1234567890"

    patterns = {
        "version": "1.0.0",
        "rules": [
            {
                "rule_id": "generic-high-entropy",
                "risk_tier": "low",
                "pattern": secret_value,
            }
        ],
    }
    patterns_path = repo_root / "secret-patterns.json"
    patterns_path.write_text(json.dumps(patterns), encoding="utf-8")

    leaky_file = repo_root / "specs" / "leaky.txt"
    leaky_file.write_text("token = " + secret_value + "\n", encoding="utf-8")

    cache_manager_src = (
        "class CacheKey:\n"
        "    def __init__(self, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_inputs_hash = gate_inputs_hash\n"
        "        self.gate_version = gate_version\n"
        "        self.model_pin = model_pin\n"
        "\n"
        "class CachedResult:\n"
        "    def __init__(self, gate_type, payload, stored_at):\n"
        "        self.gate_type = gate_type\n"
        "        self.payload = payload\n"
        "        self.stored_at = stored_at\n"
        "\n"
        "def get(cache_key, repo_root=None):\n"
        "    return CachedResult(gate_type='secret_scanner', payload=None, stored_at='1970-01-01T00:00:00Z')\n"
        "\n"
        "def put(cache_key, result, repo_root=None):\n"
        "    pass\n"
    )
    (repo_root / "gen" / "cache-manager" / "cache_manager.py").write_text(
        cache_manager_src, encoding="utf-8"
    )

    webhook_calls_log = tmp_path / "webhook_calls.log"

    def fake_urlopen(request, *args, **kwargs):
        with open(webhook_calls_log, "a", encoding="utf-8") as fh:
            fh.write("called\n")

        class _Resp:
            status = 200

            def read(self):
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("VAR_SECRET_PATTERNS_PATH", str(patterns_path))
    monkeypatch.setenv(
        "VAR_COMPLIANCE_WEBHOOK_URL", "https://compliance.example.invalid/webhook"
    )

    result = secret_scanner.scan(repo_root)

    matches = _get(result, "matches", [])
    assert len(matches) == 1
    assert _get(matches[0], "risk_tier") == "low"
    assert _get(matches[0], "file") == "specs/leaky.txt"

    assert _get(result, "flagged") is True
    assert _get(result, "notified") is True
    assert _get(result, "notification_delivery_error") is None

    assert webhook_calls_log.exists()
    assert webhook_calls_log.read_text(encoding="utf-8").count("called") == 1