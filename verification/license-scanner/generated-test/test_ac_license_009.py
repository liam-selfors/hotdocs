import hashlib
import json
import socket

import pytest

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _closed_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _write_cache_manager_fake(repo_root):
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "cache_manager.py").write_text(
        "class CacheKey:\n"
        "    def __init__(self, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_inputs_hash = gate_inputs_hash\n"
        "        self.gate_version = gate_version\n"
        "        self.model_pin = model_pin\n"
        "\n"
        "\n"
        "class CachedResult:\n"
        "    def __init__(self, gate_type, payload, stored_at):\n"
        "        self.gate_type = gate_type\n"
        "        self.payload = payload\n"
        "        self.stored_at = stored_at\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    return None\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    return None\n"
    )


def test_ac_license_009_network_failure_during_high_risk_notification(tmp_path, monkeypatch):
    repo_root = tmp_path
    _write_cache_manager_fake(repo_root)

    # Ten distinct tokens produce exactly two overlapping 9-token windows
    # (window A = tokens[0:9], window B = tokens[1:10]); only window A's
    # hash is seeded into the corpus, giving a similarity_score of 1/2,
    # which stays below the 0.70 block threshold while still surfacing a
    # high-risk match.
    tokens = [
        "alpha_one", "bravo_two", "charlie_three", "delta_four", "echo_five",
        "foxtrot_six", "golf_seven", "hotel_eight", "india_nine", "juliet_ten",
    ]
    window_a = tokens[0:9]
    hash_a = hashlib.sha256("\x1f".join(window_a).encode("utf-8")).hexdigest()

    target_dir = repo_root / "gen" / "fixture-target"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "fixture_target.py").write_text(" ".join(tokens) + "\n")

    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL-3.0",
                "risk_tier": "high",
                "hashes": [hash_a],
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus))

    # A port nobody is listening on, guaranteeing the webhook call itself
    # raises a real network error (connection refused) rather than relying
    # on any particular HTTP library being mocked.
    port = _closed_port()
    webhook_url = "http://127.0.0.1:%d/compliance-hook" % port

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", "corpus.json")
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", webhook_url)

    result = license_scanner.scan("comp-fixture-target", repo_root)

    assert _get(result, "evaluated") is True
    assert _get(result, "similarity_score") == pytest.approx(0.5)
    assert _get(result, "block_threshold") == pytest.approx(0.70)

    blocked = _get(result, "blocked")
    assert blocked is False

    matches = _get(result, "matches")
    assert any(_get(m, "risk_tier") == "high" for m in matches)

    # notified is due purely to the high-risk match, independent of the
    # (false) blocked outcome, and independent of webhook delivery success.
    assert _get(result, "notified") is True

    delivery_error = _get(result, "notification_delivery_error")
    assert delivery_error is not None
    assert _get(delivery_error, "category") == "network"
    assert _get(delivery_error, "message")

    # blocked must remain exactly what similarity_score/block_threshold
    # dictate, unaffected by the webhook delivery failure.
    assert _get(result, "blocked") is False