import hashlib
import json
import os
import tempfile
from pathlib import Path

import license_scanner


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
    payload: dict
    stored_at: str


def get(cache_key, *, repo_root=None):
    return None


def put(cache_key, result, *, repo_root=None):
    return None
'''


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _window_hash(tokens):
    joined = "\x1f".join(tokens)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def test_below_block_threshold_high_risk_entry_notifies_without_blocking():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        cache_manager_dir = repo_root / "gen" / "cache-manager"
        cache_manager_dir.mkdir(parents=True)
        (cache_manager_dir / "cache_manager.py").write_text(CACHE_MANAGER_SOURCE)

        component_id = "comp-sample-widget"
        component_slug = component_id.replace("comp-", "", 1)

        tokens = [f"token{i}" for i in range(18)]
        source_text = " ".join(tokens) + "\n"

        windows = [tokens[i:i + 9] for i in range(len(tokens) - 8)]
        window_hashes = [_window_hash(w) for w in windows]
        assert len(window_hashes) == 10
        assert len(set(window_hashes)) == 10

        matched_hashes = window_hashes[:3]

        # license-scanner compares against the component's own generated
        # source, which per the glossary's gen/<slug>/ convention lives here.
        target_dir = repo_root / "gen" / component_slug
        target_dir.mkdir(parents=True)
        (target_dir / "main.py").write_text(source_text)

        corpus = {
            "corpus_version": 1,
            "block_threshold": 0.7,
            "entries": [
                {
                    "reference_id": "ref-high-1",
                    "license_family": "gpl-3.0",
                    "risk_tier": "high",
                    "hashes": matched_hashes,
                }
            ],
        }
        corpus_path = repo_root / "license-corpus.json"
        corpus_path.write_text(json.dumps(corpus))

        env_backup = {
            "VAR_LICENSE_CORPUS_PATH": os.environ.get("VAR_LICENSE_CORPUS_PATH"),
            "VAR_COMPLIANCE_WEBHOOK_URL": os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL"),
        }
        os.environ["VAR_LICENSE_CORPUS_PATH"] = str(corpus_path)
        os.environ["VAR_COMPLIANCE_WEBHOOK_URL"] = "http://127.0.0.1:1/webhook"

        try:
            result = license_scanner.scan(component_id, repo_root)
        finally:
            for key, value in env_backup.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        evaluated = _field(result, "evaluated")
        reason = _field(result, "reason")
        similarity_score = _field(result, "similarity_score")
        block_threshold = _field(result, "block_threshold")
        blocked = _field(result, "blocked")
        notified = _field(result, "notified")
        matches = _field(result, "matches")

        assert evaluated is True
        assert reason is None
        assert block_threshold == 0.7
        assert similarity_score is not None
        assert abs(similarity_score - 0.3) < 1e-9
        assert similarity_score < block_threshold

        assert blocked is False
        assert notified is True

        high_risk_match_present = False
        for match in matches or []:
            if _field(match, "risk_tier") == "high":
                high_risk_match_present = True
        assert high_risk_match_present