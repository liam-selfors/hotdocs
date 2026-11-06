import hashlib
import json
import textwrap

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _window_hash(tokens):
    joined = "\x1f".join(tokens)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _write_fake_cache_manager(repo_root):
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "cache_manager.py").write_text(
        textwrap.dedent(
            """
            class CacheKey:
                def __init__(self, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):
                    self.spec_bundle_hash = spec_bundle_hash
                    self.gate_inputs_hash = gate_inputs_hash
                    self.gate_version = gate_version
                    self.model_pin = model_pin

            class CachedResult:
                def __init__(self, gate_type, payload, stored_at):
                    self.gate_type = gate_type
                    self.payload = payload
                    self.stored_at = stored_at

            def get(cache_key, *, repo_root=None):
                return None

            def put(cache_key, result, *, repo_root=None):
                return None
            """
        ),
        encoding="utf-8",
    )


def test_eight_token_run_does_not_match_nine_token_window(tmp_path, monkeypatch):
    repo_root = tmp_path
    _write_fake_cache_manager(repo_root)

    reference_tokens = [
        "alpha", "bravo", "charlie", "delta", "echo",
        "foxtrot", "golf", "hotel", "india",
    ]
    assert len(reference_tokens) == 9
    reference_hash = _window_hash(reference_tokens)

    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": [reference_hash],
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    # Negative case: "zulu alpha bravo charlie delta echo foxtrot golf
    # hotel yankee" shares the 8-token run "alpha..hotel" with the
    # reference's 9-token window ("alpha..india"), but its own two
    # 9-token windows each substitute a different 9th token (zulu at the
    # front, yankee at the back) for the reference's "india" -- so
    # neither window hash can equal the corpus entry's hash.
    neg_dir = repo_root / "gen" / "license-neg"
    neg_dir.mkdir(parents=True)
    (neg_dir / "sample.py").write_text(
        "zulu alpha bravo charlie delta echo foxtrot golf hotel yankee",
        encoding="utf-8",
    )

    neg_result = license_scanner.scan("comp-license-neg", repo_root)

    assert _get(neg_result, "evaluated") is True
    assert _get(neg_result, "similarity_score") == 0.0
    assert _get(neg_result, "blocked") is False
    assert _get(neg_result, "matches") == []

    # Positive control: exactly the 9 reference tokens and nothing else,
    # forming exactly one 9-token window identical to the corpus entry's
    # hashed window. Together with the negative case above, this shows
    # the window size is exactly 9 -- an 8-token overlap alone never
    # matches, but the full 9-token run does.
    pos_dir = repo_root / "gen" / "license-pos"
    pos_dir.mkdir(parents=True)
    (pos_dir / "sample.py").write_text(
        " ".join(reference_tokens),
        encoding="utf-8",
    )

    pos_result = license_scanner.scan("comp-license-pos", repo_root)

    assert _get(pos_result, "evaluated") is True
    assert _get(pos_result, "similarity_score") == 1.0
    assert _get(pos_result, "blocked") is True
    matches = _get(pos_result, "matches")
    assert any(_get(m, "reference_id") == "ref-001" for m in matches)