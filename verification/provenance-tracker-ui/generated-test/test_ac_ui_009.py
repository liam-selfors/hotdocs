import json
import os
from pathlib import Path

import pytest

import provenance_tracker_ui


FAKE_TRACKER_TEMPLATE = '''
import json

_LOG_PATH = {log_path!r}
_RAISE = {raise_value_error!r}


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def _passing_result(cid):
    return {{
        "hit": True,
        "verification_report": {{
            "component_id": cid,
            "criteria": [],
            "requirement_results": {{}},
            "interface_drift": False,
            "mutation_score": None,
            "overall": "pass",
        }},
        "license_scan": {{"blocked": False}},
        "secret_scan": {{"flagged": False}},
    }}


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({{
        "fn": "check_readiness",
        "repo_root": str(repo_root),
        "changed_ids": list(changed_ids) if changed_ids is not None else None,
        "model": model,
        "seed": seed,
    }})
    if _RAISE:
        raise ValueError("P-FAKE: capability needs a fresh run but no model was given")
    ids = list(changed_ids) if changed_ids else ["comp-foo"]
    return {{
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": True,
        "components": {{cid: _passing_result(cid) for cid in ids}},
        "capabilities": {{}},
        "not_ready_reasons": [],
    }}


def last_requirement_failures(component_id, repo_root):
    _log({{"fn": "last_requirement_failures", "component_id": component_id}})
    return []
'''


def _corpus_graph():
    return {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["test-team"],
                "documents": {},
            },
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["test-team"],
                "documents": {},
            },
        },
        "edges": [
            {"from": "comp-bar", "to": "comp-foo", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


def _make_repo(base, *, raise_value_error=False, graph="valid"):
    repo_root = base / "repo"
    repo_root.mkdir(parents=True)
    log_path = base / "tracker_calls.jsonl"
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        FAKE_TRACKER_TEMPLATE.format(
            log_path=str(log_path), raise_value_error=raise_value_error
        ),
        encoding="utf-8",
    )
    if graph is not None:
        ver = repo_root / "verification"
        ver.mkdir(parents=True)
        if graph == "valid":
            (ver / "corpus-graph.json").write_text(
                json.dumps(_corpus_graph(), sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
        elif graph == "invalid":
            (ver / "corpus-graph.json").write_text(
                "{ this is not: valid json ,,, ", encoding="utf-8"
            )
    return repo_root, log_path


def _calls(log_path, fn="check_readiness"):
    if not log_path.exists():
        return []
    out = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("fn") == fn:
            out.append(rec)
    return out


def _path_printed(stdout, path):
    candidates = {str(path), str(Path(path).resolve()), os.path.realpath(str(path))}
    return any(c in stdout for c in candidates)


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)


def test_build_equals_form_comma_separated_changed(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path / "a")
    out_dir = tmp_path / "a" / "out"
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        f"--repo-root={repo_root}",
        f"--out={out_dir}",
        "--changed=comp-foo,comp-bar",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    index = out_dir / "index.html"
    assert index.is_file()
    assert _path_printed(captured.out, index), captured.out
    calls = _calls(log_path)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo", "comp-bar"]


def test_build_space_form_with_model_and_seed(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path / "b")
    out_dir = tmp_path / "b" / "out"
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root", str(repo_root),
        "--out", str(out_dir),
        "--changed", "comp-foo",
        "--model", "fake-model",
        "--seed", "3",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    index = out_dir / "index.html"
    assert index.is_file()
    assert _path_printed(captured.out, index), captured.out
    calls = _calls(log_path)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo"]
    assert calls[0]["model"] == "fake-model"
    assert calls[0]["seed"] == 3
    assert isinstance(calls[0]["seed"], int)


def test_build_default_out_dir(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path / "c")
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        f"--repo-root={repo_root}",
        "--changed=comp-foo",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    index = repo_root / ".hotdocs" / "ui" / "index.html"
    assert index.is_file()
    assert _path_printed(captured.out, index), captured.out


def test_build_invalid_corpus_graph_json_returns_1(tmp_path):
    repo_root, _ = _make_repo(tmp_path / "d", graph="invalid")
    out_dir = tmp_path / "d" / "out"
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        f"--repo-root={repo_root}",
        f"--out={out_dir}",
        "--changed=comp-foo",
    ])
    assert rc == 1


def test_build_missing_corpus_graph_returns_2(tmp_path):
    repo_root, _ = _make_repo(tmp_path / "e", graph=None)
    out_dir = tmp_path / "e" / "out"
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        f"--repo-root={repo_root}",
        f"--out={out_dir}",
        "--changed=comp-foo",
    ])
    assert rc == 2


def test_build_check_readiness_value_error_returns_2(tmp_path):
    repo_root, log_path = _make_repo(tmp_path / "f", raise_value_error=True)
    out_dir = tmp_path / "f" / "out"
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        f"--repo-root={repo_root}",
        f"--out={out_dir}",
        "--changed=comp-foo",
    ])
    assert rc == 2
    assert len(_calls(log_path)) == 1


def test_build_unknown_argument_returns_2(tmp_path):
    repo_root, _ = _make_repo(tmp_path / "g")
    out_dir = tmp_path / "g" / "out"
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        f"--repo-root={repo_root}",
        f"--out={out_dir}",
        "--bogus-flag=1",
    ])
    assert rc == 2


def test_serve_subcommand_returns_2(tmp_path):
    repo_root, _ = _make_repo(tmp_path / "h")
    rc = provenance_tracker_ui.main(["track", "ui", "serve"])
    assert rc == 2
    rc = provenance_tracker_ui.main(
        ["track", "ui", "serve", f"--repo-root={repo_root}"]
    )
    assert rc == 2


@pytest.mark.parametrize(
    "flag", ["--changed", "--repo-root", "--out", "--model", "--seed"]
)
def test_flag_last_without_value_returns_2(tmp_path, flag):
    repo_root, _ = _make_repo(tmp_path / "i")
    out_dir = tmp_path / "i" / "out"
    argv = ["track", "ui", "build"]
    if flag != "--repo-root":
        argv.append(f"--repo-root={repo_root}")
    if flag != "--out":
        argv.append(f"--out={out_dir}")
    argv.append(flag)
    rc = provenance_tracker_ui.main(argv)
    assert rc == 2