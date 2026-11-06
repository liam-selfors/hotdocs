import hashlib
import json

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_high_risk_tier_match_below_block_threshold_notifies_without_blocking(tmp_path, monkeypatch):
    repo_root = tmp_path

    (repo_root / "gen" / "cache-manager").mkdir(parents=True)
    (repo_root / "gen" / "cache-manager" / "cache_manager.py").write_text(
        '''
class CacheKey:
    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None,
                 gate_version=None, model_pin=None):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


class CachedResult:
    def __init__(self, gate_type=None, payload=None, stored_at=None):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


class Miss:
    payload = None


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    pass
'''
    )

    # Ten tokens produce exactly two overlapping 9-token windows; sharing
    # only one of them with the reference entry gives a 0.5 score, well
    # above any reporting floor and comfortably below the 0.9 threshold
    # set on the corpus below.
    tokens = ["alpha", "beta", "gamma", "delta", "epsilon",
              "zeta", "eta", "theta", "iota", "kappa"]
    (repo_root / "gen" / "widget").mkdir(parents=True)
    (repo_root / "gen" / "widget" / "widget.py").write_text(" ".join(tokens) + "\n")

    matched_window = tokens[0:9]
    matched_hash = hashlib.sha256(
        "\x1f".join(matched_window).encode("utf-8")
    ).hexdigest()

    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.9,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL-3.0",
                "risk_tier": "high",
                "hashes": [matched_hash],
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus))

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    # Loopback port 1 refuses connections immediately, so a single
    # unretried webhook attempt fails fast instead of hanging the test.
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "http://127.0.0.1:1/webhook")

    result = license_scanner.scan("comp-widget", repo_root)

    assert _get(result, "evaluated") is True

    score = _get(result, "similarity_score")
    threshold = _get(result, "block_threshold")
    assert score < threshold
    assert _get(result, "blocked") is False

    matches = _get(result, "matches")
    assert any(_get(m, "risk_tier") == "high" for m in matches)

    assert _get(result, "notified") is True