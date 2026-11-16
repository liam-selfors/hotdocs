import importlib.util
import json
import sys
import textwrap
from pathlib import Path

import pytest

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SPEC_BUNDLE_HASH = "sha256:" + "a1" * 32
GATE_INPUTS_HASH = "sha256:" + "b2" * 32
GATE_VERSION = "license_scanner@4.0.3+9f2c41ab07de"
MODEL_PIN = "claude-sonnet-5"


CALLER_A_SRC = textwrap.dedent(
    '''
    """Simulated calling component A: builds its key from a dict of parts."""


    def make_key(cm, parts):
        return cm.CacheKey(
            spec_bundle_hash=parts["spec_bundle_hash"],
            gate_inputs_hash=parts["gate_inputs_hash"],
            gate_version=parts["gate_version"],
            model_pin=parts["model_pin"],
        )


    def store(cm, parts, payload, repo_root):
        key = make_key(cm, parts)
        result = cm.CachedResult(
            gate_type="license_scanner",
            payload=payload,
            stored_at=cm.now_iso(),
        )
        cm.put(key, result, repo_root=repo_root)
        return key
    '''
)

CALLER_B_SRC = textwrap.dedent(
    '''
    """Simulated calling component B: rebuilds each part as a fresh string
    object (distinct identity from caller A's) and passes keywords in a
    different order."""


    def make_key(cm, parts):
        fresh = {k: "".join(list(v)) for k, v in parts.items()}
        return cm.CacheKey(
            model_pin=fresh["model_pin"],
            gate_version=fresh["gate_version"],
            gate_inputs_hash=fresh["gate_inputs_hash"],
            spec_bundle_hash=fresh["spec_bundle_hash"],
        )


    def store(cm, parts, payload, repo_root):
        key = make_key(cm, parts)
        result = cm.CachedResult(
            gate_type="license_scanner",
            payload=payload,
            stored_at=cm.now_iso(),
        )
        cm.put(key, result, repo_root=repo_root)
        return key
    '''
)


def _load_module(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _payload(score):
    return {
        "component_id": "comp-example",
        "gate_version": GATE_VERSION,
        "similarity_score": score,
        "blocked": False,
        "matches": [],
    }


def _entry_count(repo_root):
    stats = cache_manager.stats(repo_root=repo_root)
    return field(stats, "entry_count")


def test_two_callers_produce_identical_cache_keys(tmp_path, monkeypatch, capsys):
    # Force the local fallback store under this test's own repo_root.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    callers_dir = tmp_path / "callers"
    callers_dir.mkdir()
    (callers_dir / "ac_cache_002_caller_a.py").write_text(CALLER_A_SRC)
    (callers_dir / "ac_cache_002_caller_b.py").write_text(CALLER_B_SRC)

    caller_a = _load_module(
        "ac_cache_002_caller_a", callers_dir / "ac_cache_002_caller_a.py"
    )
    caller_b = _load_module(
        "ac_cache_002_caller_b", callers_dir / "ac_cache_002_caller_b.py"
    )

    parts = {
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "gate_inputs_hash": GATE_INPUTS_HASH,
        "gate_version": GATE_VERSION,
        "model_pin": MODEL_PIN,
    }

    assert _entry_count(repo_root) == 0

    # Caller A puts first.
    key_a = caller_a.store(cache_manager, parts, _payload(0.1), repo_root)
    assert _entry_count(repo_root) == 1

    # Caller B can read A's entry with its independently-built key.
    hit_for_b = cache_manager.get(caller_b.make_key(cache_manager, parts), repo_root=repo_root)
    assert not isinstance(hit_for_b, cache_manager.Miss)
    assert field(hit_for_b, "gate_type") == "license_scanner"
    assert field(field(hit_for_b, "payload"), "similarity_score") == 0.1

    # Caller B puts under the same four components: it must land on the very
    # same serialized key (overwrite), not create a second entry.
    key_b = caller_b.store(cache_manager, parts, _payload(0.2), repo_root)
    assert _entry_count(repo_root) == 1

    # Both callers' keys now resolve to the one, identical entry.
    got_a = cache_manager.get(key_a, repo_root=repo_root)
    got_b = cache_manager.get(key_b, repo_root=repo_root)
    assert not isinstance(got_a, cache_manager.Miss)
    assert not isinstance(got_b, cache_manager.Miss)
    for name in ("gate_type", "payload", "stored_at"):
        assert field(got_a, name) == field(got_b, name)

    # A third caller (the CLI) forming the key from the same four strings
    # also hits that same entry.
    rc = cache_manager.main(
        [
            "inspect",
            f"--spec-bundle-hash={SPEC_BUNDLE_HASH}",
            f"--gate-inputs-hash={GATE_INPUTS_HASH}",
            f"--gate-version={GATE_VERSION}",
            f"--model-pin={MODEL_PIN}",
            f"--repo-root={repo_root}",
        ]
    )
    assert rc == 0
    out_lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert len(out_lines) == 1
    inspected = json.loads(out_lines[0])
    assert inspected["result"] == "hit"
    assert inspected["gate_type"] == "license_scanner"
    assert inspected["stored_at"] == field(got_a, "stored_at")
    assert "payload" not in inspected

    # Sanity: the key is not degenerate -- changing one component of the
    # 4-tuple yields a distinct key (miss, then a second entry).
    other_parts = dict(parts, model_pin="claude-opus-5")
    other_key = caller_a.make_key(cache_manager, other_parts)
    assert isinstance(cache_manager.get(other_key, repo_root=repo_root), cache_manager.Miss)
    caller_b.store(cache_manager, other_parts, _payload(0.3), repo_root)
    assert _entry_count(repo_root) == 2