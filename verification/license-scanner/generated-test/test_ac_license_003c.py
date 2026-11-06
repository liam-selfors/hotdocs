import hashlib
import json
import re

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")


def _tokenize(text):
    return [tok.lower() for tok in _TOKEN_RE.findall(text)]


def _window_hashes(tokens, size=9):
    hashes = []
    for i in range(len(tokens) - size + 1):
        window = tokens[i:i + size]
        joined = "\x1f".join(window)
        hashes.append(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return hashes


_CACHE_MANAGER_SOURCE = '''import dataclasses
import os


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


class _Miss:
    payload = None


def _log(entry):
    log_path = os.environ.get("FAKE_CACHE_LOG_PATH")
    if not log_path:
        return
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry + "\\n")


def get(cache_key, *, repo_root=None):
    _log("get")
    return _Miss()


def put(cache_key, result, *, repo_root=None):
    _log("put")
    return None
'''


def test_ac_license_003c_blocked_low_risk_no_webhook_notified_false_but_recorded(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    (cache_manager_dir / "cache_manager.py").write_text(_CACHE_MANAGER_SOURCE, encoding="utf-8")

    component_slug = "sample-widget"
    component_id = "comp-" + component_slug
    component_dir = repo_root / "gen" / component_slug
    component_dir.mkdir(parents=True)

    source_code = "def quick_brown_fox(jumps, over, lazy, dog, river, bank, moon):\n"
    (component_dir / "sample_widget.py").write_text(source_code, encoding="utf-8")

    tokens = _tokenize(source_code)
    assert len(tokens) == 9
    hashes = _window_hashes(tokens)
    assert len(hashes) == 1

    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.5,
        "entries": [
            {
                "reference_id": "ref-low-001",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": [hashes[0]],
            }
        ],
    }
    corpus_path = repo_root / "reference_corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    log_path = tmp_path / "cache_calls.log"
    monkeypatch.setenv("FAKE_CACHE_LOG_PATH", str(log_path))
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    result = license_scanner.scan(component_id, repo_root)

    assert _get(result, "evaluated") is True

    similarity_score = _get(result, "similarity_score")
    block_threshold = _get(result, "block_threshold")
    assert similarity_score is not None
    assert block_threshold is not None
    assert similarity_score >= block_threshold

    matches = _get(result, "matches") or []
    assert any(_get(m, "risk_tier") == "low" for m in matches)
    assert not any(_get(m, "risk_tier") == "high" for m in matches)

    assert _get(result, "blocked") is True
    assert _get(result, "notified") is False
    assert _get(result, "notification_delivery_error") is None

    log_contents = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    assert "put" in log_contents.splitlines()