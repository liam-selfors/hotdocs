import json
from pathlib import Path

import pytest

import provenance_tracker_ui


NORMAL_FAKE_MODULE_TEMPLATE = r'''
import json

class UsageError(Exception):
    pass

CALL_LOG_PATH = "__CALL_LOG_PATH__"

def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    record = {
        "changed_ids": changed_ids,
        "model": model,
        "seed": seed,
    }
    with open(CALL_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")
    return {
        "scope": "blast-radius" if changed_ids else "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }

def last_requirement_failures(component_id, repo_root):
    return []
'''

RAISING_FAKE_MODULE = r'''
class UsageError(Exception):
    pass

def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    raise UsageError("capability provenance miss with no model")

def last_requirement_failures(component_id, repo_root):
    return []
'''


def _write_fake_provenance_tracker(repo_root, call_log_path, raising=False):
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True, exist_ok=True)
    if raising:
        source = RAISING_FAKE_MODULE
    else:
        source = NORMAL_FAKE_MODULE_TEMPLATE.replace(
            "__CALL_LOG_PATH__", str(call_log_path)
        )
    (dep_dir / "provenance_tracker.py").write_text(source)


def _write_corpus_graph(repo_root, content=None):
    verification_dir = repo_root / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    if content is None:
        content = json.dumps(
            {
                "nodes": {},
                "edges": [],
                "aggregates": {
                    "orphan_capability_rate": 0.0,
                    "orphan_component_rate": 0.0,
                    "orphan_var_rate": 0.0,
                },
            }
        )
    (verification_dir / "corpus-graph.json").write_text(content)


def _build_repo_root(
    tmp_path,
    name,
    call_log_path,
    raising=False,
    corpus_graph_content=None,
    write_corpus_graph=True,
):
    repo_root = tmp_path / name
    repo_root.mkdir()
    _write_fake_provenance_tracker(repo_root, call_log_path, raising=raising)
    if write_corpus_graph:
        _write_corpus_graph(repo_root, content=corpus_graph_content)
    return repo_root


def _read_call_log(call_log_path):
    if not call_log_path.exists():
        return []
    lines = call_log_path.read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_build_with_comma_separated_changed_returns_0_and_passes_changed_ids(
    tmp_path, capsys
):
    call_log = tmp_path / "calls1.jsonl"
    repo_root = _build_repo_root(tmp_path, "repo1", call_log)
    out_dir = tmp_path / "out1"

    rc = provenance_tracker_ui.main(
        [
            "track",
            "ui",
            "build",
            f"--repo-root={repo_root}",
            f"--out={out_dir}",
            "--changed=comp-foo,comp-bar",
        ]
    )

    assert rc == 0
    expected_index = out_dir / "index.html"
    assert expected_index.exists()

    captured = capsys.readouterr()
    assert str(expected_index) in captured.out

    calls = _read_call_log(call_log)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo", "comp-bar"]


def test_build_with_space_separated_flags_passes_model_and_seed(tmp_path):
    call_log = tmp_path / "calls2.jsonl"
    repo_root = _build_repo_root(tmp_path, "repo2", call_log)
    out_dir = tmp_path / "out2"

    rc = provenance_tracker_ui.main(
        [
            "track",
            "ui",
            "build",
            "--repo-root",
            str(repo_root),
            "--out",
            str(out_dir),
            "--changed",
            "comp-foo",
            "--model",
            "fake-model",
            "--seed",
            "3",
        ]
    )

    assert rc == 0
    expected_index = out_dir / "index.html"
    assert expected_index.exists()

    calls = _read_call_log(call_log)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo"]
    assert calls[0]["model"] == "fake-model"
    assert calls[0]["seed"] == 3


def test_build_with_no_out_defaults_to_hotdocs_ui(tmp_path):
    call_log = tmp_path / "calls3.jsonl"
    repo_root = _build_repo_root(tmp_path, "repo3", call_log)

    rc = provenance_tracker_ui.main(
        [
            "track",
            "ui",
            "build",
            f"--repo-root={repo_root}",
            "--changed=comp-foo",
        ]
    )

    assert rc == 0
    expected_index = repo_root / ".hotdocs" / "ui" / "index.html"
    assert expected_index.exists()


def test_build_invalid_corpus_graph_json_returns_1(tmp_path):
    call_log = tmp_path / "calls4.jsonl"
    repo_root = _build_repo_root(
        tmp_path,
        "repo4",
        call_log,
        corpus_graph_content="{not valid json",
    )
    out_dir = tmp_path / "out4"

    rc = provenance_tracker_ui.main(
        [
            "track",
            "ui",
            "build",
            f"--repo-root={repo_root}",
            f"--out={out_dir}",
        ]
    )

    assert rc == 1


def test_build_missing_corpus_graph_returns_2(tmp_path):
    call_log = tmp_path / "calls5.jsonl"
    repo_root = _build_repo_root(
        tmp_path, "repo5", call_log, write_corpus_graph=False
    )
    out_dir = tmp_path / "out5"

    rc = provenance_tracker_ui.main(
        [
            "track",
            "ui",
            "build",
            f"--repo-root={repo_root}",
            f"--out={out_dir}",
        ]
    )

    assert rc == 2


def test_build_usage_error_from_check_readiness_returns_2(tmp_path):
    call_log = tmp_path / "calls6.jsonl"
    repo_root = _build_repo_root(tmp_path, "repo6", call_log, raising=True)
    out_dir = tmp_path / "out6"

    rc = provenance_tracker_ui.main(
        [
            "track",
            "ui",
            "build",
            f"--repo-root={repo_root}",
            f"--out={out_dir}",
            "--changed=comp-foo",
        ]
    )

    assert rc == 2


def test_build_unknown_argument_returns_2(tmp_path):
    call_log = tmp_path / "calls7.jsonl"
    repo_root = _build_repo_root(tmp_path, "repo7", call_log)
    out_dir = tmp_path / "out7"

    rc = provenance_tracker_ui.main(
        [
            "track",
            "ui",
            "build",
            f"--repo-root={repo_root}",
            f"--out={out_dir}",
            "--not-a-real-flag=foo",
        ]
    )

    assert rc == 2


def test_serve_subcommand_returns_2(tmp_path):
    call_log = tmp_path / "calls8.jsonl"
    _build_repo_root(tmp_path, "repo8", call_log)

    rc = provenance_tracker_ui.main(["track", "ui", "serve"])

    assert rc == 2


@pytest.mark.parametrize(
    "flag", ["--changed", "--repo-root", "--out", "--model", "--seed"]
)
def test_flag_as_last_argument_with_no_value_returns_2(tmp_path, flag):
    suffix = flag.strip("-")
    call_log = tmp_path / f"calls_flag_{suffix}.jsonl"
    repo_root = _build_repo_root(tmp_path, f"repo_flag_{suffix}", call_log)
    out_dir = tmp_path / f"out_flag_{suffix}"

    argv = [
        "track",
        "ui",
        "build",
        f"--repo-root={repo_root}",
        f"--out={out_dir}",
        "--changed=comp-foo",
        flag,
    ]

    rc = provenance_tracker_ui.main(argv)

    assert rc == 2