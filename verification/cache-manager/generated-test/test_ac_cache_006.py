# hotdocs-criterion: sha256:526877abdb617edbd2abf23613731d2ae9a47fb1f1aa965408b4cdb6983d76dd
import json

import pytest

import cache_manager


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _last_json_line(text):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines, "expected one line of JSON on stdout, got nothing"
    return json.loads(lines[-1])


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    return root


def _put_entry(repo_root):
    key = cache_manager.CacheKey(
        spec_bundle_hash="sha256:a",
        gate_inputs_hash="sha256:b",
        gate_version="generator@1.0.0",
        model_pin="m",
    )
    result = cache_manager.CachedResult(
        gate_type="generator",
        payload={
            "component_id": "comp-example",
            "model": "m",
            "prompt_version": "1",
            "files": {"example.py": "print('hi')\n"},
        },
        stored_at="2026-01-01T00:00:00Z",
    )
    cache_manager.put(key, result, repo_root=repo_root)
    return key


def _inspect_argv(repo_root, model_pin):
    return [
        "inspect",
        "--spec-bundle-hash=sha256:a",
        "--gate-inputs-hash=sha256:b",
        "--gate-version=generator@1.0.0",
        "--model-pin=" + model_pin,
        "--repo-root=" + str(repo_root),
    ]


def test_inspect_hit_reports_provenance_fields_without_payload(repo_root, capsys):
    _put_entry(repo_root)
    capsys.readouterr()

    rc = cache_manager.main(_inspect_argv(repo_root, "m"))
    out = capsys.readouterr().out

    assert rc == 0
    data = _last_json_line(out)
    assert data == {
        "result": "hit",
        "gate_type": "generator",
        "stored_at": "2026-01-01T00:00:00Z",
    }
    assert "payload" not in data


def test_inspect_miss_on_different_model_pin(repo_root, capsys):
    _put_entry(repo_root)
    capsys.readouterr()

    rc = cache_manager.main(_inspect_argv(repo_root, "other"))
    out = capsys.readouterr().out

    assert rc == 0
    data = _last_json_line(out)
    assert data == {"result": "miss"}


@pytest.mark.parametrize(
    "argv",
    [
        ["inspect", "--spec-bundle-hash=sha256:a"],
        [],
        ["purge"],
    ],
)
def test_usage_errors_return_2(repo_root, argv):
    rc = cache_manager.main(argv)
    assert rc == 2