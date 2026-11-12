import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-sample-widget"
COMPONENT_SLUG = "sample-widget"
SEP = "\x1f"


FAKE_CACHE_MANAGER = '''
import datetime
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: Any
    stored_at: str


class Miss:
    payload = None

    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


class SchemaValidationError(ValueError):
    pass


_REQUIRED = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    gate_type = result.get("gate_type") if isinstance(result, dict) else getattr(result, "gate_type", None)
    payload = result.get("payload") if isinstance(result, dict) else getattr(result, "payload", None)
    gv = cache_key.get("gate_version") if isinstance(cache_key, dict) else getattr(cache_key, "gate_version", None)
    if gate_type not in _REQUIRED:
        raise SchemaValidationError("unknown gate_type")
    if not isinstance(gv, str) or gv.split("@", 1)[0] != gate_type:
        raise SchemaValidationError("gate_type mismatch")
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload not a dict")
    for key in _REQUIRED[gate_type]:
        if key not in payload:
            raise SchemaValidationError("missing key " + key)
    return None


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": 0}
'''


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _hash_window(tokens):
    return hashlib.sha256(SEP.join(tokens).encode("utf-8")).hexdigest()


def _windows(tokens, k):
    return [tokens[i:i + k] for i in range(len(tokens) - k + 1)]


def _window_hashes(tokens, k):
    return {_hash_window(w) for w in _windows(tokens, k)}


def _make_repo(root: Path, component_tokens, corpus_hashes):
    root.mkdir(parents=True, exist_ok=True)
    gen_dir = root / "gen" / COMPONENT_SLUG
    gen_dir.mkdir(parents=True, exist_ok=True)
    # one token per line, plain identifiers only (no comments, no strings)
    (gen_dir / "sample_widget.py").write_text("\n".join(component_tokens) + "\n", encoding="utf-8")

    cm_dir = root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True, exist_ok=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    corpus_dir = root / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = corpus_dir / "reference.json"
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-window-probe",
                "license_family": "GPL",
                "risk_tier": "low",
                "hashes": sorted(corpus_hashes),
            }
        ],
    }
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    return corpus_path


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    return monkeypatch


def test_shared_8_token_run_contributes_no_matching_window(tmp_path, clean_env):
    monkeypatch = clean_env

    pre = [f"compprefix{chr(97 + i)}" for i in range(6)]
    shared8 = [f"sharedrun{chr(97 + i)}" for i in range(8)]
    post = [f"compsuffix{chr(97 + i)}" for i in range(6)]
    component_tokens = pre + shared8 + post

    ref_pre = [f"refprefix{chr(97 + i)}" for i in range(5)]
    ref_post = [f"refsuffix{chr(97 + i)}" for i in range(5)]
    reference_tokens = ref_pre + shared8 + ref_post

    # Corpus carries the reference's hashes for every window size around 9,
    # including all sub-9 sizes (so an 8- or 7-token window would match),
    # plus its real 9- and 10-token windows.
    corpus_hashes = set()
    for k in range(1, 11):
        corpus_hashes |= _window_hashes(reference_tokens, k)

    # Self-check the fixture: an 8-token (or smaller) window size WOULD match,
    # a 9-token window size would NOT.
    assert _window_hashes(component_tokens, 8) & corpus_hashes
    assert _window_hashes(component_tokens, 7) & corpus_hashes
    assert not (_window_hashes(component_tokens, 9) & corpus_hashes)
    assert not (_window_hashes(component_tokens, 10) & corpus_hashes)

    repo_root = tmp_path / "repo_negative"
    corpus_path = _make_repo(repo_root, component_tokens, corpus_hashes)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.chdir(repo_root)

    result = license_scanner.scan(COMPONENT_ID, repo_root)

    assert _field(result, "evaluated") is True
    assert _field(result, "reason") is None
    score = _field(result, "similarity_score")
    assert score is not None
    assert float(score) == pytest.approx(0.0, abs=1e-9), (
        f"an 8-token shared run produced a nonzero similarity score {score!r}; "
        "window size is not exactly 9"
    )
    assert _field(result, "blocked") is False
    matches = _field(result, "matches") or []
    for m in matches:
        m_score = _field(m, "score")
        assert m_score is None or float(m_score) == pytest.approx(0.0, abs=1e-9)


def test_shared_9_token_run_does_contribute_matching_window(tmp_path, clean_env):
    # Positive control: same shape, but the shared run is exactly 9 tokens,
    # and the corpus holds only the reference's 9-token window hashes.
    monkeypatch = clean_env

    pre = [f"compprefix{chr(97 + i)}" for i in range(6)]
    shared9 = [f"sharedrun{chr(97 + i)}" for i in range(9)]
    post = [f"compsuffix{chr(97 + i)}" for i in range(6)]
    component_tokens = pre + shared9 + post

    ref_pre = [f"refprefix{chr(97 + i)}" for i in range(5)]
    ref_post = [f"refsuffix{chr(97 + i)}" for i in range(5)]
    reference_tokens = ref_pre + shared9 + ref_post

    corpus_hashes = _window_hashes(reference_tokens, 9)

    comp9 = _window_hashes(component_tokens, 9)
    shared_count = len(comp9 & corpus_hashes)
    assert shared_count == 1
    # A 10-token window size would find nothing here.
    assert not (_window_hashes(component_tokens, 10) & _window_hashes(reference_tokens, 10))
    expected = shared_count / len(comp9)

    repo_root = tmp_path / "repo_positive"
    corpus_path = _make_repo(repo_root, component_tokens, corpus_hashes)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.chdir(repo_root)

    result = license_scanner.scan(COMPONENT_ID, repo_root)

    assert _field(result, "evaluated") is True
    score = _field(result, "similarity_score")
    assert score is not None
    assert float(score) > 0.0, "a shared 9-token run produced no matching window-hash"
    assert float(score) == pytest.approx(expected, abs=1e-3)
    assert _field(result, "blocked") is False