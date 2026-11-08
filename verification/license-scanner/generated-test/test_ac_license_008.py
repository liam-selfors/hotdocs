import hashlib
import json
import os
import tempfile
from pathlib import Path

import license_scanner


UNIT_SEP = "\x1f"


def _window_hash(tokens):
    joined = UNIT_SEP.join(tokens)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


CACHE_MANAGER_FAKE = '''
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
    pass


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    return None
'''


def test_ac_license_008_shared_eight_token_run_yields_no_match():
    with tempfile.TemporaryDirectory() as repo_root_str:
        repo_root = Path(repo_root_str)

        cache_manager_dir = repo_root / "gen" / "cache-manager"
        cache_manager_dir.mkdir(parents=True)
        (cache_manager_dir / "cache_manager.py").write_text(CACHE_MANAGER_FAKE)

        # The 8-token run shared between the reference corpus entry and the
        # scanned component's content. H8 is the hash a window-size-8
        # implementation would produce for this exact run; a correct
        # window-size-9 implementation never produces this hash at all,
        # since it always hashes 9 tokens, never 8.
        shared_eight_run = ["t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9"]
        h8 = _window_hash(shared_eight_run)

        corpus = {
            "corpus_version": 1,
            "block_threshold": 0.7,
            "entries": [
                {
                    "reference_id": "ref-test-1",
                    "license_family": "TestLicense",
                    "risk_tier": "high",
                    "hashes": [h8],
                }
            ],
        }
        corpus_path = repo_root / "license-corpus.json"
        corpus_path.write_text(json.dumps(corpus))

        component_id = "comp-widget"
        component_dir = repo_root / "gen" / "widget"
        component_dir.mkdir(parents=True)
        # Tokens: zzz1 (prefix differs from any reference token), the
        # shared 8-token run, then zzz2 (suffix differs too) -- so every
        # true 9-token window straddling the shared run includes a token
        # that is not part of any corpus hash.
        source_text = "zzz1 t2 t3 t4 t5 t6 t7 t8 t9 zzz2\n"
        (component_dir / "source.txt").write_text(source_text)

        old_env = os.environ.get("VAR_LICENSE_CORPUS_PATH")
        os.environ["VAR_LICENSE_CORPUS_PATH"] = str(corpus_path)
        try:
            result = license_scanner.scan(component_id, repo_root)
        finally:
            if old_env is None:
                os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
            else:
                os.environ["VAR_LICENSE_CORPUS_PATH"] = old_env

        assert _field(result, "evaluated") is True, (
            "expected a usable corpus to produce an evaluated result"
        )
        assert _field(result, "reason") is None

        similarity_score = _field(result, "similarity_score")
        assert similarity_score == 0.0, (
            "an 8-token shared run must not contribute a matching "
            "window-hash under a true 9-token window size; a nonzero "
            "score here indicates the window size is not exactly 9"
        )

        matches = _field(result, "matches")
        assert matches == []

        assert _field(result, "blocked") is False