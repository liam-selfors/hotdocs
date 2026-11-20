# hotdocs-criterion: sha256:843e3dbbae6f12805825af393f4b5de2509b7f21b5cd28e51add772ad6368991
import hashlib
import json
from pathlib import Path

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_SOURCE = (
    "from dataclasses import dataclass\n"
    "from datetime import datetime, timezone\n"
    "from typing import Any\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: Any\n"
    "    stored_at: str\n"
    "\n"
    "\n"
    "class Miss:\n"
    "    def __eq__(self, other):\n"
    "        return isinstance(other, Miss)\n"
    "\n"
    "    def __hash__(self):\n"
    "        return 0\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return " + repr({"entry_count": 0}) + "\n"
)


SHARED_RUN = [
    "shared_alpha", "shared_bravo", "shared_charlie", "shared_delta",
    "shared_echo", "shared_foxtrot", "shared_golf", "shared_hotel",
]
assert len(SHARED_RUN) == 8

COMPONENT_TOKENS = (
    ["comp_head_one", "comp_head_two", "comp_head_three", "comp_head_four",
     "comp_head_five"]
    + SHARED_RUN
    + ["comp_tail_one", "comp_tail_two", "comp_tail_three", "comp_tail_four",
       "comp_tail_five"]
)

REFERENCE_TOKENS = (
    ["ref_head_one", "ref_head_two", "ref_head_three", "ref_head_four",
     "ref_head_five"]
    + SHARED_RUN
    + ["ref_tail_one", "ref_tail_two", "ref_tail_three", "ref_tail_four",
       "ref_tail_five"]
)


def window_hashes(tokens, k):
    out = []
    for i in range(len(tokens) - k + 1):
        joined = "\x1f".join(tokens[i:i + k])
        out.append(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return out


def make_repo(tmp_path, name, entry_hashes, monkeypatch):
    repo_root = tmp_path / name
    comp_dir = repo_root / "gen" / "sample"
    comp_dir.mkdir(parents=True)
    # One token per whitespace-separated word, no comments, all lowercase.
    (comp_dir / "sample.py").write_text(" ".join(COMPONENT_TOKENS) + "\n")

    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE)

    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-shared-8",
                "license_family": "GPL",
                "risk_tier": "low",
                "hashes": list(entry_hashes),
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus))

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    return repo_root


def test_ac_license_008_shared_8_token_run_contributes_no_match(tmp_path, monkeypatch):
    # The reference entry's real 9-token window hashes: the reference text
    # shares only an 8-token run with the component, so no 9-token window
    # is common to both.
    ref_9 = window_hashes(REFERENCE_TOKENS, 9)
    assert not set(ref_9) & set(window_hashes(COMPONENT_TOKENS, 9))

    # Also include hashes of the shared run (and the component's content)
    # at nearby window sizes; a scanner using any size other than 9 would
    # find matches among these.
    nearby = []
    for k in (7, 8, 10, 11):
        nearby.extend(window_hashes(COMPONENT_TOKENS, k))
    nearby.extend(window_hashes(SHARED_RUN, 8))

    repo_root = make_repo(tmp_path, "negative", ref_9 + nearby, monkeypatch)
    result = license_scanner.scan("comp-sample", repo_root)

    assert field(result, "evaluated") is True
    assert field(result, "reason") is None
    assert field(result, "similarity_score") == 0
    assert field(result, "blocked") is False
    for match in field(result, "matches"):
        assert field(match, "score") == 0


def test_ac_license_008_positive_control_9_token_window_matches(tmp_path, monkeypatch):
    # Control: the same component content does match when the corpus holds
    # one of its own 9-token window hashes, proving the negative case's zero
    # is due to the window size rather than an unscanned or mis-tokenized file.
    comp_9 = window_hashes(COMPONENT_TOKENS, 9)
    repo_root = make_repo(tmp_path, "positive", [comp_9[0]], monkeypatch)
    result = license_scanner.scan("comp-sample", repo_root)

    assert field(result, "evaluated") is True
    score = field(result, "similarity_score")
    assert score is not None and score > 0
    expected = 1 / len(set(comp_9))
    assert abs(score - expected) < 1e-9