import json

import pytest

import provenance_tracker_ui


FAKE_PROVENANCE_TRACKER_TEMPLATE = '''
import json as _json
from pathlib import Path as _Path


class UsageError(Exception):
    pass


_LOG_PATH = _Path({log_path!r})
_RAISE_USAGE_ERROR = {raise_usage_error!r}


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _LOG_PATH.write_text(_json.dumps({{
        "changed_ids": changed_ids,
        "model": model,
        "seed": seed,
    }}))
    if _RAISE_USAGE_ERROR:
        raise UsageError("fake capability miss, no model given")
    ids = changed_ids if changed_ids else ["comp-foo", "comp-bar"]
    components = {{}}
    for cid in ids:
        components[cid] = {{
            "hit": True,
            "verification_report": {{
                "component_id": cid,
                "criteria": [],
                "requirement_results": {{}},
                "interface_drift": False,
                "mutation_score": 1.0,
                "overall": "pass",
            }},
            "license_scan": {{"blocked": False}},
            "secret_scan": {{"flagged": False}},
        }}
    return {{
        "scope": "blast-radius" if changed_ids else "whole-corpus",
        "ready": True,
        "components": components,
        "capabilities": {{}},
        "not_ready_reasons": [],
    }}


def last_requirement_failures(component_id, repo_root):
    return []
'''


CORPUS_GRAPH = {
    "nodes": {
        "comp-foo": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
        },
        "comp-bar": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
        },
    },
    "edges": [],
    "aggregates": {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    },
}


def _write_fake_provenance_tracker(repo_root, log_path, raise_usage_error=False):
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True, exist_ok=True)
    content = FAKE_PROVENANCE_TRACKER_TEMPLATE.format(
        log_path=str(log_path),
        raise_usage_error=raise_usage_error,
    )
    (dep_dir / "provenance_tracker.py").write_text(content)


def _make_repo_root(
    tmp_path,
    name,
    log_path,
    raise_usage_error=False,
    write_corpus_graph=True,
    corpus_graph_text=None,
):
    repo_root = tmp_path / name
    repo_root.mkdir(parents=True, exist_ok=True)
    if write_corpus_graph:
        verification_dir = repo_root / "verification"
        verification_dir.mkdir(parents=True, exist_ok=True)
        if corpus_graph_text is None:
            corpus_graph_text = json.dumps(CORPUS_GRAPH)
        (verification_dir / "corpus-graph.json").write_text(corpus_graph_text)
    _write_fake_provenance_tracker(repo_root, log_path, raise_usage_error=raise_usage_error)
    return repo_root


def test_build_with_comma_separated_changed_prints_index_and_passes_changed_ids(tmp_path, capsys):
    log_path = tmp_path / "log1.json"
    repo_root = _make_repo_root(tmp_path, "repo1", log_path)
    out_dir = tmp_path / "out1"

    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        f"--repo-root={repo_root}",
        f"--out={out_dir}",
        "--changed=comp-foo,comp-bar",
    ])

    captured = capsys.readouterr()
    expected_index = out_dir / "index.html"
    assert rc == 0
    assert str(expected_index) in captured.out
    assert expected_index.exists()
    log_data = json.loads(log_path.read_text())
    assert log_data["changed_ids"] == ["comp-foo", "comp-bar"]


def test_build_with_space_separated_flags_passes_model_and_seed(tmp_path):
    log_path = tmp_path / "log2.json"
    repo_root = _make_repo_root(tmp_path, "repo2", log_path)
    out_dir = tmp_path / "out2"

    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root", str(repo_root),
        "--out", str(out_dir),
        "--changed", "comp-foo",
        "--model", "fake-model",
        "--seed", "3",
    ])

    assert rc == 0
    index_path = out_dir / "index.html"
    assert index_path.exists()
    log_data = json.loads(log_path.read_text())
    assert log_data["changed_ids"] == ["comp-foo"]
    assert log_data["model"] == "fake-model"
    assert log_data["seed"] == 3


def test_build_without_out_defaults_to_hotdocs_ui_directory(tmp_path):
    log_path = tmp_path / "log3.json"
    repo_root = _make_repo_root(tmp_path, "repo3", log_path)

    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        f"--repo-root={repo_root}",
        "--changed=comp-foo",
    ])

    assert rc == 0
    default_index = repo_root / ".hotdocs" / "ui" / "index.html"
    assert default_index.exists()


def test_build_invalid_corpus_graph_json_returns_1(tmp_path):
    log_path = tmp_path / "log4.json"
    repo_root = _make_repo_root(
        tmp_path, "repo4", log_path, corpus_graph_text="{not valid json"
    )
    out_dir = tmp_path / "out4"

    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        f"--repo-root={repo_root}",
        f"--out={out_dir}",
    ])

    assert rc == 1


def test_build_missing_corpus_graph_returns_2(tmp_path):
    log_path = tmp_path / "log5a.json"
    repo_root = _make_repo_root(tmp_path, "repo5a", log_path, write_corpus_graph=False)
    out_dir = tmp_path / "out5a"

    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        f"--repo-root={repo_root}",
        f"--out={out_dir}",
    ])

    assert rc == 2


def test_build_dependency_usage_error_returns_2(tmp_path):
    log_path = tmp_path / "log5b.json"
    repo_root = _make_repo_root(tmp_path, "repo5b", log_path, raise_usage_error=True)
    out_dir = tmp_path / "out5b"

    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        f"--repo-root={repo_root}",
        f"--out={out_dir}",
    ])

    assert rc == 2


def test_build_unknown_argument_returns_2(tmp_path):
    log_path = tmp_path / "log5c.json"
    repo_root = _make_repo_root(tmp_path, "repo5c", log_path)
    out_dir = tmp_path / "out5c"

    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        f"--repo-root={repo_root}",
        f"--out={out_dir}",
        "--bogus-flag=1",
    ])

    assert rc == 2


def test_serve_subcommand_returns_2():
    rc = provenance_tracker_ui.main(["track", "ui", "serve"])
    assert rc == 2


@pytest.mark.parametrize("flag", ["--changed", "--repo-root", "--out", "--model", "--seed"])
def test_flag_as_last_argument_with_no_value_returns_2(flag):
    rc = provenance_tracker_ui.main(["track", "ui", "build", flag])
    assert rc == 2