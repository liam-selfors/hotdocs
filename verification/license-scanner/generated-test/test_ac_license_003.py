import hashlib
import json
from pathlib import Path


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _window_hash(tokens):
    window = "\x1f".join(tokens)
    return hashlib.sha256(window.encode("utf-8")).hexdigest()


CACHE_MANAGER_SOURCE = '''
import dataclasses


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: object
    stored_at: str


_LOG_PATH = {log_path!r}


def _log(event):
    with open(_LOG_PATH, "a") as f:
        f.write(event + "\\n")


def get(cache_key, *, repo_root=None):
    _log("get")
    return None


def put(cache_key, result, *, repo_root=None):
    _log("put")
'''


def test_notified_true_when_blocked_against_low_risk_entry(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    log_path = tmp_path / "cache_manager_calls.log"
    (cache_manager_dir / "cache_manager.py").write_text(
        CACHE_MANAGER_SOURCE.format(log_path=str(log_path))
    )

    component_dir = repo_root / "gen" / "sample-app"
    component_dir.mkdir(parents=True)
    tokens = [
        "alpha", "beta", "gamma", "delta", "epsilon",
        "zeta", "eta", "theta", "iota",
    ]
    source_text = " = ".join(tokens) + "\n"
    (component_dir / "sample_app.py").write_text(source_text)

    window_hash = _window_hash(tokens)

    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.5,
        "entries": [
            {
                "reference_id": "ref-low-1",
                "license_family": "mit",
                "risk_tier": "low",
                "hashes": [window_hash],
            }
        ],
    }
    corpus_path = repo_root / "license-corpus.json"
    corpus_path.write_text(json.dumps(corpus))

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "http://127.0.0.1:1/webhook")

    import license_scanner

    result = license_scanner.scan("comp-sample-app", repo_root)

    assert _get(result, "evaluated") is True

    similarity_score = _get(result, "similarity_score")
    block_threshold = _get(result, "block_threshold")
    assert similarity_score is not None
    assert block_threshold is not None
    assert similarity_score >= block_threshold

    assert _get(result, "blocked") is True

    matches = _get(result, "matches")
    assert matches
    risk_tiers = {_get(m, "risk_tier") for m in matches}
    assert "low" in risk_tiers
    assert "high" not in risk_tiers

    assert _get(result, "notified") is True

    if log_path.exists():
        log_contents = log_path.read_text()
        assert "get" in log_contents