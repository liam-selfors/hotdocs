# hotdocs-criterion: sha256:10e1f83e71bdf38e2c312e006a29efdee6b9aed40fda5e8c4ec529268f5ff7f8
import json
from pathlib import Path

import pytest

import cache_manager


STORE_URL = "redis://cache.internal:6379/0"

REQUIRED_KEYS = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": [
        "component_id",
        "gate_version",
        "similarity_score",
        "blocked",
        "matches",
    ],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def full_payload(gate_type):
    return {k: "x" for k in REQUIRED_KEYS[gate_type]}


def make_key(gate_type="license_scanner"):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_inputs_hash="sha256:" + "b" * 64,
        gate_version=gate_type + "@4.0.3+9f2c41ab07de",
        model_pin="claude-sonnet-5",
    )


def make_result(gate_type="license_scanner", payload=None):
    return cache_manager.CachedResult(
        gate_type=gate_type,
        payload=full_payload(gate_type) if payload is None else payload,
        stored_at=cache_manager.now_iso(),
    )


def files_under(path):
    path = Path(path)
    if not path.exists():
        return []
    return [p for p in path.rglob("*")]


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("VAR_CACHE_STORE_URL", STORE_URL)
    return root


def test_store_url_set_get_misses_nothing_stored_stats_zero(repo_root, capsys):
    key = make_key()
    result = make_result()

    cache_manager.put(key, result, repo_root=repo_root)
    got = cache_manager.get(key, repo_root=repo_root)

    assert isinstance(got, cache_manager.Miss)
    assert got == cache_manager.Miss()

    cache_dir = repo_root / ".hotdocs" / "cache"
    assert files_under(cache_dir) == []

    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 0

    capsys.readouterr()
    code = cache_manager.main(["stats", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 0
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"entry_count": 0}

    assert files_under(cache_dir) == []


@pytest.mark.parametrize(
    "gate_type,missing",
    [(g, k) for g, keys in REQUIRED_KEYS.items() for k in keys],
)
def test_store_url_set_put_still_validates_schema(repo_root, gate_type, missing):
    payload = full_payload(gate_type)
    del payload[missing]
    key = make_key(gate_type)
    result = make_result(gate_type, payload=payload)

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, result, repo_root=repo_root)

    assert issubclass(cache_manager.SchemaValidationError, ValueError)
    assert files_under(repo_root / ".hotdocs" / "cache") == []