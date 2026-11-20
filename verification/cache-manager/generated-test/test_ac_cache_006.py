# hotdocs-criterion: sha256:b3b189c12ad3403c03acc8d1a9202d5d129b1d2b1715b0870196414a98ce3b27
import json

import pytest

import cache_manager


SBH = "sha256:a"
GIH = "sha256:b"
GV = "generator@1.0.0"
PIN = "m"
STORED_AT = "2026-01-01T00:00:00Z"


@pytest.fixture(autouse=True)
def _no_remote_store(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def _put_entry(repo_root):
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
            "model": "m",
            "prompt_version": "1",
            "files": {"foo.py": "x = 1\n"},
        },
        stored_at=STORED_AT,
    )
    cache_manager.put(key, result, repo_root=repo_root)


def _inspect_argv(repo_root, model_pin=PIN):
    return [
        "inspect",
        "--spec-bundle-hash=" + SBH,
        "--gate-inputs-hash=" + GIH,
        "--gate-version=" + GV,
        "--model-pin=" + model_pin,
        "--repo-root=" + str(repo_root),
    ]


def _stdout_json(capsys):
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1, out
    return json.loads(lines[0])


def test_inspect_hit_reports_provenance_fields_without_payload(tmp_path, capsys):
    _put_entry(tmp_path)
    capsys.readouterr()

    code = cache_manager.main(_inspect_argv(tmp_path))

    assert code == 0
    doc = _stdout_json(capsys)
    assert "payload" not in doc
    assert doc == {
        "result": "hit",
        "gate_type": "generator",
        "stored_at": STORED_AT,
    }


def test_inspect_miss_for_other_model_pin(tmp_path, capsys):
    _put_entry(tmp_path)
    capsys.readouterr()

    code = cache_manager.main(_inspect_argv(tmp_path, model_pin="other"))

    assert code == 0
    doc = _stdout_json(capsys)
    assert doc == {"result": "miss"}


@pytest.mark.parametrize(
    "argv",
    [
        ["inspect", "--spec-bundle-hash=sha256:a"],
        [],
        ["purge"],
    ],
)
def test_usage_errors_return_2(argv, capsys):
    code = cache_manager.main(argv)
    assert code == 2


@pytest.mark.parametrize(
    "drop_prefix",
    [
        "--spec-bundle-hash=",
        "--gate-inputs-hash=",
        "--gate-version=",
        "--model-pin=",
    ],
)
def test_inspect_missing_required_flag_returns_2(tmp_path, capsys, drop_prefix):
    _put_entry(tmp_path)
    capsys.readouterr()
    argv = [a for a in _inspect_argv(tmp_path) if not a.startswith(drop_prefix)]
    assert len(argv) == 5

    code = cache_manager.main(argv)

    assert code == 2


def test_inspect_abbreviated_model_flag_returns_2(tmp_path, capsys):
    _put_entry(tmp_path)
    capsys.readouterr()
    argv = [
        ("--model=" + PIN) if a == "--model-pin=" + PIN else a
        for a in _inspect_argv(tmp_path)
    ]
    assert "--model=m" in argv

    code = cache_manager.main(argv)

    assert code == 2