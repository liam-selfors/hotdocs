import hashlib
import json
from pathlib import Path

import license_scanner


WINDOW_TOKENS = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota"]


def _window_hash(tokens):
    joined = "\x1f".join(tokens)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


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


class Miss:
    pass


def get(cache_key, *, repo_root=None):
    with open(r"{log_path}", "a", encoding="utf-8") as f:
        f.write("get\\n")
    return Miss()


def put(cache_key, result, *, repo_root=None):
    with open(r"{log_path}", "a", encoding="utf-8") as f:
        f.write("put:" + result.gate_type + "\\n")
'''


def _install_fake_cache_manager(repo_root: Path, log_path: Path):
    dep_dir = repo_root / "gen" / "cache-manager"
    dep_dir.mkdir(parents=True, exist_ok=True)
    module_file = dep_dir / "cache_manager.py"
    module_file.write_text(
        CACHE_MANAGER_SOURCE.format(log_path=str(log_path)),
        encoding="utf-8",
    )


def test_ac_license_003_blocked_match_low_risk_tier_still_notifies(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    log_path = tmp_path / "cache_calls.log"
    _install_fake_cache_manager(repo_root, log_path)

    component_id = "comp-widgetizer"
    slug = "widgetizer"

    source_dir = repo_root / "gen" / slug
    source_dir.mkdir(parents=True, exist_ok=True)
    source_file = source_dir / "widgetizer.py"
    source_file.write_text(" ".join(WINDOW_TOKENS) + "\n", encoding="utf-8")

    window_hash = _window_hash(WINDOW_TOKENS)

    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-low-001",
                "license_family": "mit",
                "risk_tier": "low",
                "hashes": [window_hash],
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", "corpus.json")
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "http://127.0.0.1:1/compliance-webhook")

    result = license_scanner.scan(component_id, repo_root)

    similarity_score = _get(result, "similarity_score")
    block_threshold = _get(result, "block_threshold")
    blocked = _get(result, "blocked")
    matches = _get(result, "matches") or []
    notified = _get(result, "notified")

    assert similarity_score is not None
    assert block_threshold is not None
    assert similarity_score >= block_threshold
    assert blocked is True

    risk_tiers = {_get(m, "risk_tier") for m in matches}
    assert "low" in risk_tiers
    assert "high" not in risk_tiers

    assert notified is True

    assert log_path.exists()
    log_contents = log_path.read_text(encoding="utf-8")
    assert "get" in log_contents