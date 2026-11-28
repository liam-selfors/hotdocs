# hotdocs-criterion: sha256:9c3dc881e24ac535a25c3ea60a9aabc77466c213c407cac9a5e8c7e24ae358c7
import json
from pathlib import Path

import pytest

import provenance_tracker_ui


GRAPH_SUFFIX = "verification/corpus-graph.json; run hotdocs corpus-graph build first"


def _report():
    return {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": False,
                "reason": "no manifest",
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            }
        },
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": [
            "comp-foo: no provenance for current spec state \u2014 run hotdocs generate comp-foo"
        ],
    }


def _graph():
    return {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": False,
                "pinned_overrides": [],
                "owners": [],
                "documents": {},
            }
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


def _fake_source(log_path, raise_value_error):
    lines = [
        "import copy",
        "import json",
        "",
        "LOG = " + repr(str(log_path)),
        "REPORT = " + repr(_report()),
        "RAISE = " + repr(bool(raise_value_error)),
        "",
        "",
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):",
        "    with open(LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps({",
        "            'changed_ids': None if changed_ids is None else list(changed_ids),",
        "            'model': model,",
        "            'seed': seed,",
        "        }) + '\\n')",
        "    if RAISE:",
        "        raise ValueError('P-X: capability provenance miss and no model given')",
        "    report = copy.deepcopy(REPORT)",
        "    report['scope'] = 'whole-corpus' if changed_ids is None else 'blast-radius'",
        "    return report",
        "",
        "",
        "def last_requirement_failures(component_id, repo_root):",
        "    return []",
        "",
    ]
    return "\n".join(lines)


def make_repo(tmp_path, graph="valid", raise_value_error=False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        _fake_source(log_path, raise_value_error), encoding="utf-8"
    )
    if graph is not None:
        vdir = repo_root / "verification"
        vdir.mkdir()
        if graph == "valid":
            text = json.dumps(_graph(), indent=2)
        else:
            text = "{not valid json"
        (vdir / "corpus-graph.json").write_text(text, encoding="utf-8")
    return repo_root, log_path


def read_calls(log_path):
    if not log_path.is_file():
        return []
    return [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _printed(path, stdout):
    candidates = {str(path), str(path.resolve())}
    return any(c in stdout for c in candidates)


def test_build_equals_form_comma_separated_changed(tmp_path, capsys):
    repo_root, log_path = make_repo(tmp_path)
    out_dir = tmp_path / "out"
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo_root),
        "--out=" + str(out_dir),
        "--changed=comp-foo,comp-bar",
    ])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    index = out_dir / "index.html"
    assert index.is_file()
    assert _printed(index, captured.out)
    calls = read_calls(log_path)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo", "comp-bar"]


def test_build_space_form_with_model_and_seed(tmp_path, capsys):
    repo_root, log_path = make_repo(tmp_path)
    out_dir = tmp_path / "out"
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root", str(repo_root),
        "--out", str(out_dir),
        "--changed", "comp-foo",
        "--model", "fake-model",
        "--seed", "3",
    ])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    assert (out_dir / "index.html").is_file()
    calls = read_calls(log_path)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo"]
    assert calls[0]["model"] == "fake-model"
    assert calls[0]["seed"] == 3


def test_build_default_out_dir(tmp_path, capsys):
    repo_root, log_path = make_repo(tmp_path)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build", "--repo-root=" + str(repo_root),
    ])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    index = repo_root / ".hotdocs" / "ui" / "index.html"
    assert index.is_file()
    assert _printed(index, captured.out)


def test_build_invalid_corpus_graph_json_returns_1(tmp_path, capsys):
    repo_root, _ = make_repo(tmp_path, graph="invalid")
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo_root),
        "--out=" + str(tmp_path / "out"),
    ])
    capsys.readouterr()
    assert rc == 1


def test_build_check_readiness_value_error_returns_2(tmp_path, capsys):
    repo_root, log_path = make_repo(tmp_path, raise_value_error=True)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo_root),
        "--out=" + str(tmp_path / "out"),
    ])
    capsys.readouterr()
    assert rc == 2
    assert len(read_calls(log_path)) == 1


def test_build_unknown_argument_returns_2(tmp_path, capsys):
    repo_root, _ = make_repo(tmp_path)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo_root),
        "--out=" + str(tmp_path / "out"),
        "--hotdocs-smoke-unknown",
    ])
    capsys.readouterr()
    assert rc == 2


def test_build_missing_corpus_graph_usage_error(tmp_path, capsys):
    repo_root, _ = make_repo(tmp_path, graph=None)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo_root),
        "--out=" + str(tmp_path / "out"),
    ])
    captured = capsys.readouterr()
    assert rc == 2
    lines = captured.err.splitlines()
    assert lines, "expected a usage error on stderr"
    first = lines[0]
    assert first.startswith("usage error: missing "), first
    assert first.endswith(GRAPH_SUFFIX), first
    assert "  " not in first, first


def test_serve_is_usage_error(tmp_path, capsys):
    repo_root, _ = make_repo(tmp_path)
    rc = provenance_tracker_ui.main(["track", "ui", "serve"])
    capsys.readouterr()
    assert rc == 2


@pytest.mark.parametrize(
    "flag", ["--changed", "--repo-root", "--out", "--model", "--seed"]
)
def test_flag_last_without_value_is_usage_error(tmp_path, capsys, flag):
    repo_root, _ = make_repo(tmp_path)
    argv = ["track", "ui", "build"]
    if flag != "--repo-root":
        argv.append("--repo-root=" + str(repo_root))
    if flag != "--out":
        argv.append("--out=" + str(tmp_path / "out"))
    argv.append(flag)
    rc = provenance_tracker_ui.main(argv)
    capsys.readouterr()
    assert rc == 2