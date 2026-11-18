# hotdocs-criterion: sha256:526877abdb617edbd2abf23613731d2ae9a47fb1f1aa965408b4cdb6983d76dd
import json

import pytest

import cache_manager


SPEC_HASH = "sha256:a"
INPUTS_HASH = "sha256:b"
GATE_VERSION = "generator@1.0.0"
MODEL_PIN = "m"
STORED_AT = "2026-01-01T00:00:00Z"


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


def _put_entry(repo_root):
    key = cache_manager.CacheKey(
        spec_bundle_hash=SPEC_HASH,
        gate_inputs_hash=INPUTS_HASH,
        gate_version=GATE_VERSION,
        model_pin=MODEL_PIN,
    )
    result = cache_manager.CachedResult(
        gate_type="generator",
        payload={
            "component_id": "comp-example",
            "model": "anthropic:claude-sonnet-5",
            "prompt_version": "1",
            "files": {"example.py": "print('hi')\n"},
        },
        stored_at=STORED_AT,
    )
    cache_manager.put(key, result, repo_root=repo_root)


def _run(argv):
    """Run main(argv); a SystemExit's code is treated as the exit code."""
    try:
        return cache_manager.main(argv)
    except SystemExit as exc:  # pragma: no cover - lenient on usage errors
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1


def _last_json_line(text):
    lines = [line for line in text.splitlines() if line.strip()]
    assert lines, "expected one line of JSON on stdout, got nothing"
    return json.loads(lines[-1])


def _full_args(repo_root, model_pin=MODEL_PIN):
    return [
        "inspect",
        "--spec-bundle-hash=" + SPEC_HASH,
        "--gate-inputs-hash=" + INPUTS_HASH,
        "--gate-version=" + GATE_VERSION,
        "--model-pin=" + model_pin,
        "--repo-root=" + str(repo_root),
    ]


def test_inspect_hit_reports_provenance_fields_without_payload(repo_root, capsys):
    _put_entry(repo_root)
    capsys.readouterr()

    code = cache_manager.main(_full_args(repo_root))
    out = capsys.readouterr().out

    assert code == 0
    parsed = _last_json_line(out)
    assert "payload" not in parsed
    assert parsed == {
        "result": "hit",
        "gate_type": "generator",
        "stored_at": STORED_AT,
    }


def test_inspect_miss_for_other_model_pin(repo_root, capsys):
    _put_entry(repo_root)
    capsys.readouterr()

    code = cache_manager.main(_full_args(repo_root, model_pin="other"))
    out = capsys.readouterr().out

    assert code == 0
    assert _last_json_line(out) == {"result": "miss"}


@pytest.mark.parametrize(
    "argv",
    [
        ["inspect", "--spec-bundle-hash=sha256:a"],
        [],
        ["purge"],
    ],
    ids=["inspect-missing-flags", "no-subcommand", "unknown-subcommand"],
)
def test_usage_errors_return_2(repo_root, capsys, argv):
    _put_entry(repo_root)
    capsys.readouterr()

    assert _run(argv) == 2


@pytest.mark.parametrize(
    "omit_prefix",
    [
        "--spec-bundle-hash=",
        "--gate-inputs-hash=",
        "--gate-version=",
        "--model-pin=",
    ],
)
def test_inspect_with_one_required_flag_left_out_returns_2(
    repo_root, capsys, omit_prefix
):
    _put_entry(repo_root)
    capsys.readouterr()

    argv = [a for a in _full_args(repo_root) if not a.startswith(omit_prefix)]
    assert len(argv) == len(_full_args(repo_root)) - 1

    assert _run(argv) == 2


def test_inspect_with_abbreviated_model_flag_returns_2(repo_root, capsys):
    _put_entry(repo_root)
    capsys.readouterr()

    argv = [
        "--model=m" if a == "--model-pin=" + MODEL_PIN else a
        for a in _full_args(repo_root)
    ]
    assert "--model=m" in argv
    assert not any(a.startswith("--model-pin") for a in argv)

    assert _run(argv) == 2