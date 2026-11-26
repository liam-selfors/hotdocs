# hotdocs-criterion: sha256:657ff584d51400c2ddf1d6dda3af2e9047898a96faa7bdc222f3a83f46067741
"""AC-CACHE-005: gate_version is part of the lookup key itself (R-CACHE-005).

Given an entry stored under gate_version "license_scanner@1.0.0",
when get is called with the same spec_bundle_hash/gate_inputs_hash/model_pin
but gate_version "license_scanner@2.0.0",
then it returns Miss, not the entry stored under the old gate_version.
"""

import json

import pytest

import cache_manager


SPEC_BUNDLE_HASH = "sha256:" + "a" * 64
GATE_INPUTS_HASH = "sha256:" + "b" * 64
MODEL_PIN = "claude-sonnet-5"
OLD_GATE_VERSION = "license_scanner@1.0.0"
NEW_GATE_VERSION = "license_scanner@2.0.0"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(autouse=True)
def _local_store(monkeypatch, tmp_path):
    # Force the local fallback store under a fresh repo_root.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)


def make_key(gate_version):
    return cache_manager.CacheKey(
        spec_bundle_hash=SPEC_BUNDLE_HASH,
        gate_inputs_hash=GATE_INPUTS_HASH,
        gate_version=gate_version,
        model_pin=MODEL_PIN,
    )


def make_result():
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload={
            "component_id": "comp-example",
            "gate_version": OLD_GATE_VERSION,
            "similarity_score": 0.0,
            "blocked": False,
            "matches": [],
        },
        stored_at=cache_manager.now_iso(),
    )


def test_get_with_new_gate_version_returns_miss(tmp_path):
    repo_root = tmp_path
    result = make_result()
    cache_manager.put(make_key(OLD_GATE_VERSION), result, repo_root=repo_root)

    # Sanity: the entry really is stored and retrievable under the old key.
    hit = cache_manager.get(make_key(OLD_GATE_VERSION), repo_root=repo_root)
    assert not isinstance(hit, cache_manager.Miss)
    assert field(hit, "gate_type") == "license_scanner"

    # The criterion: a different gate_version, everything else equal, misses.
    got = cache_manager.get(make_key(NEW_GATE_VERSION), repo_root=repo_root)
    assert got is not None
    assert isinstance(got, cache_manager.Miss)
    assert got == cache_manager.Miss()


def test_cli_inspect_with_new_gate_version_reports_miss(tmp_path, capsys):
    repo_root = tmp_path
    cache_manager.put(make_key(OLD_GATE_VERSION), make_result(), repo_root=repo_root)

    def inspect(gate_version):
        capsys.readouterr()
        code = cache_manager.main(
            [
                "inspect",
                "--spec-bundle-hash=" + SPEC_BUNDLE_HASH,
                "--gate-inputs-hash=" + GATE_INPUTS_HASH,
                "--gate-version=" + gate_version,
                "--model-pin=" + MODEL_PIN,
                "--repo-root=" + str(repo_root),
            ]
        )
        out = capsys.readouterr().out.strip()
        return code, json.loads(out.splitlines()[-1])

    code, doc = inspect(OLD_GATE_VERSION)
    assert code == 0
    assert doc["result"] == "hit"

    code, doc = inspect(NEW_GATE_VERSION)
    assert code == 0
    assert doc == {"result": "miss"}