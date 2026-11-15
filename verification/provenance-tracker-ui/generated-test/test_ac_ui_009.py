import json
from pathlib import Path

import pytest

import provenance_tracker_ui


FAKE_TRACKER_TEMPLATE = '''
import json
from pathlib import Path

_LOG_PATH = {log_path!r}
_RAISE = {raise_value_error!r}


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def _passing_result(component_id):
    return {{
        "hit": True,
        "verification_report": {{
            "component_id": component_id,
            "criteria": [],
            "requirement_results": {{}},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": "pass",
        }},
        "license_scan": {{"blocked": False, "findings": []}},
        "secret_scan": {{"flagged": False, "findings": []}},
    }}


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({{
        "fn": "check_readiness",
        "repo_root": str(repo_root),
        "changed_ids": None if changed_ids is None else list(changed_ids),
        "model": model,
        "seed": seed,
    }})
    if _RAISE:
        raise ValueError("P-FAKE: capability needs a fresh run but no model was given")
    return {{
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": True,
        "components": {{
            "comp-bar": _passing_result("comp-bar"),
            "comp-foo": _passing_result("comp-foo"),
        }},
        "capabilities": {{}},
        "not_ready_reasons": [],
    }}


def last_requirement_failures(component_id, repo_root):
    _log({{
        "fn": "last_requirement_failures",
        "component_id": component_id,
        "repo_root": str(repo_root),
    }})
    return []
'''


def _component_node(slug):
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "ok",
        "sealed": True,
        "pinned_overrides": [],
        "owners": ["test-team"],
        "documents": {"component.md": "---\nid: comp-%s\n---\n" % slug},
    }


def _corpus_graph():
    return {
        "nodes": {
            "comp-bar": _component_node("bar"),
            "comp-foo": _component_node("foo"),
        },
        "edges": [
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


def _make_repo(tmp_path, name="repo", raise_value_error=False, corpus="valid"):
    repo_root = tmp_path / name
    repo_root.mkdir(parents=True)
    log_path = tmp_path / (name + "-tracker-log.jsonl")
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        FAKE_TRACKER_TEMPLATE.format(
            log_path=str(log_path), raise_value_error=bool(raise_value_error)
        ),
        encoding="utf-8",
    )
    if corpus is not None:
        verification = repo_root / "verification"
        verification.mkdir(parents=True)
        graph_path = verification / "corpus-graph.json"
        if corpus == "valid":
            graph_path.write_text(
                json.dumps(_corpus_graph(), sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
        elif corpus == "invalid":
            graph_path.write_text("{ this is not: valid json ,,, ", encoding="utf-8")
    return repo_root, log_path


def _readiness_calls(log_path):
    if not log_path.exists():
        return []
    calls = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("fn") == "check_readiness":
            calls.append(rec)
    return calls


def _printed_paths(out_text):
    paths = []
    for line in out_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            paths.append(Path(line).resolve())
        except Exception:
            continue
    return paths


def test_build_equals_form_comma_separated_changed(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path)
    out_dir = tmp_path / "out1"
    rc = provenance_tracker_ui.main(
        [
            "track",
            "ui",
            "build",
            "--repo-root=%s" % repo_root,
            "--out=%s" % out_dir,
            "--changed=comp-foo,comp-bar",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    index = out_dir / "index.html"
    assert index.is_file()
    assert index.resolve() in _printed_paths(captured.out), captured.out
    calls = _readiness_calls(log_path)
    assert calls, "faked check_readiness was never called"
    assert calls[-1]["changed_ids"] == ["comp-foo", "comp-bar"]


def test_build_space_form_with_model_and_seed(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path)
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
    capsys.readouterr()
    assert rc == 0
    assert (out_dir / "index.html").is_file()
    calls = _readiness_calls(log_path)
    assert calls, "faked check_readiness was never called"
    last = calls[-1]
    assert last["changed_ids"] == ["comp-foo"]
    assert last["model"] == "fake-model"
    assert last["seed"] == 3


def test_build_default_out_dir(tmp_path, capsys):
    repo_root, _log_path = _make_repo(tmp_path)
    rc = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=%s" % repo_root]
    )
    capsys.readouterr()
    assert rc == 0
    assert (repo_root / ".hotdocs" / "ui" / "index.html").is_file()


def test_build_invalid_corpus_graph_json_returns_1(tmp_path, capsys):
    repo_root, _log_path = _make_repo(tmp_path, corpus="invalid")
    out_dir = tmp_path / "out-invalid"
    rc = provenance_tracker_ui.main(
        [
            "track",
            "ui",
            "build",
            "--repo-root=%s" % repo_root,
            "--out=%s" % out_dir,
        ]
    )
    capsys.readouterr()
    assert rc == 1


def test_build_missing_corpus_graph_returns_2(tmp_path, capsys):
    repo_root, _log_path = _make_repo(tmp_path, corpus=None)
    out_dir = tmp_path / "out-missing"
    rc = provenance_tracker_ui.main(
        [
            "track",
            "ui",
            "build",
            "--repo-root=%s" % repo_root,
            "--out=%s" % out_dir,
        ]
    )
    capsys.readouterr()
    assert rc == 2


def test_build_check_readiness_value_error_returns_2(tmp_path, capsys):
    repo_root, _log_path = _make_repo(tmp_path, raise_value_error=True)
    out_dir = tmp_path / "out-valueerror"
    rc = provenance_tracker_ui.main(
        [
            "track",
            "ui",
            "build",
            "--repo-root=%s" % repo_root,
            "--out=%s" % out_dir,
        ]
    )
    capsys.readouterr()
    assert rc == 2


def test_build_unknown_argument_returns_2(tmp_path, capsys):
    repo_root, _log_path = _make_repo(tmp_path)
    out_dir = tmp_path / "out-unknown"
    rc = provenance_tracker_ui.main(
        [
            "track",
            "ui",
            "build",
            "--repo-root=%s" % repo_root,
            "--out=%s" % out_dir,
            "--no-such-flag=1",
        ]
    )
    capsys.readouterr()
    assert rc == 2


def test_serve_returns_2(tmp_path, capsys):
    repo_root, _log_path = _make_repo(tmp_path)
    rc = provenance_tracker_ui.main(["track", "ui", "serve"])
    capsys.readouterr()
    assert rc == 2


@pytest.mark.parametrize(
    "flag", ["--changed", "--repo-root", "--out", "--model", "--seed"]
)
def test_flag_last_with_no_value_returns_2(tmp_path, capsys, flag):
    repo_root, _log_path = _make_repo(tmp_path)
    out_dir = tmp_path / "out-novalue"
    argv = ["track", "ui", "build"]
    if flag != "--repo-root":
        argv.append("--repo-root=%s" % repo_root)
    if flag != "--out":
        argv.append("--out=%s" % out_dir)
    argv.append(flag)
    rc = provenance_tracker_ui.main(argv)
    capsys.readouterr()
    assert rc == 2