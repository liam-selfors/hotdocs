# hotdocs-criterion: sha256:71b50c855d1690ddb8e881d7e756040fa7721f2610db22dd9df3d945ab68c1de
import json

import pytest

import cache_manager


SBH = "sha256:a"
GIH = "sha256:b"
GV = "generator@1.0.0"
PIN = "m"
STORED_AT = "2026-01-01T00:00:00Z"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    key = cache_manager.CacheKey(
        spec_bundle_hash=SBH,
        gate_inputs_hash=GIH,
        gate_version=GV,
        model_pin=PIN,
    )
    result = cache_manager.CachedResult(
        gate_type="generator",
        payload={
            "component_id": "comp-foo",
            "model": "anthropic:claude-sonnet-5",
            "prompt_version": "1",
            "files": {"foo.py": "x = 1\n"},
        },
        stored_at=STORED_AT,
    )
    cache_manager.put(key, result, repo_root=root)
    got = cache_manager.get(key, repo_root=root)
    assert not isinstance(got, cache_manager.Miss)
    assert field(got, "gate_type") == "generator"
    return root


def _parse_stdout(out):
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1, out
    return json.loads(lines[0])


def _full_args(repo_root):
    return [
        "--spec-bundle-hash=" + SBH,
        "--gate-inputs-hash=" + GIH,
        "--gate-version=" + GV,
        "--model-pin=" + PIN,
        "--repo-root=" + str(repo_root),
    ]


def test_inspect_hit_reports_provenance_without_payload(repo_root, capsys):
    capsys.readouterr()
    code = cache_manager.main(["inspect"] + _full_args(repo_root))
    out = capsys.readouterr().out
    assert code == 0
    doc = _parse_stdout(out)
    assert doc == {
        "result": "hit",
        "gate_type": "generator",
        "stored_at": STORED_AT,
    }
    assert "payload" not in doc


def test_inspect_miss_on_other_model_pin(repo_root, capsys):
    capsys.readouterr()
    args = [
        "inspect",
        "--spec-bundle-hash=" + SBH,
        "--gate-inputs-hash=" + GIH,
        "--gate-version=" + GV,
        "--model-pin=other",
        "--repo-root=" + str(repo_root),
    ]
    code = cache_manager.main(args)
    out = capsys.readouterr().out
    assert code == 0
    assert _parse_stdout(out) == {"result": "miss"}


@pytest.mark.parametrize(
    "argv",
    [
        ["inspect", "--spec-bundle-hash=sha256:a"],
        [],
        ["purge"],
    ],
)
def test_usage_errors_return_2(repo_root, argv):
    assert cache_manager.main(list(argv)) == 2


@pytest.mark.parametrize("drop_index", [0, 1, 2, 3])
def test_inspect_missing_required_flag_returns_2(repo_root, drop_index):
    args = _full_args(repo_root)
    del args[drop_index]
    assert cache_manager.main(["inspect"] + args) == 2


def test_inspect_abbreviated_model_flag_returns_2(repo_root):
    args = _full_args(repo_root)
    args[3] = "--model=" + PIN
    assert cache_manager.main(["inspect"] + args) == 2