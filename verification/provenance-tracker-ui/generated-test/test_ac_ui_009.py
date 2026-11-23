# hotdocs-criterion: sha256:1d45c55138e24e2a778cbcdbb6eb852527c76a454d8e2781f7d51e48bb80c83e
import copy
import json
from pathlib import Path

import pytest

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:00",
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "pass",
    }


def _provenance_hit(component_id):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id),
        "license_scan": {"blocked": False},
        "secret_scan": {"flagged": False},
    }


def _verify_report():
    return {
        "scope": "whole-corpus",
        "ready": True,
        "components": {
            "comp-bar": _provenance_hit("comp-bar"),
            "comp-foo": _provenance_hit("comp-foo"),
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def _component_node():
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "ok",
        "sealed": True,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {},
    }


def _corpus_graph():
    return {
        "nodes": {
            "comp-bar": _component_node(),
            "comp-foo": _component_node(),
        },
        "edges": [{"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"}],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


def _fake_source(log_path, raise_error):
    lines = [
        "import copy",
        "import json",
        "LOG = " + repr(str(log_path)),
        "REPORT = " + repr(_verify_report()),
        "RAISE = " + repr(bool(raise_error)),
        "",
        "def _log(entry):",
        "    with open(LOG, 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps(entry) + '\\n')",
        "",
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):",
        "    _log({'call': 'check_readiness', 'changed_ids': None if changed_ids is None else list(changed_ids), 'model': model, 'seed': seed})",
        "    if RAISE:",
        "        raise ValueError('P-ZERO-EDIT: capability provenance miss with no model')",
        "    report = copy.deepcopy(REPORT)",
        "    report['scope'] = 'blast-radius' if changed_ids else 'whole-corpus'",
        "    return report",
        "",
        "def last_requirement_failures(component_id, repo_root):",
        "    _log({'call': 'last_requirement_failures', 'component_id': component_id})",
        "    return []",
        "",
    ]
    return "\n".join(lines)


def make_repo(root, log_path, raise_error=False, graph_text=None, write_graph=True):
    root.mkdir(parents=True, exist_ok=True)
    fake_dir = root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    (fake_dir / "provenance_tracker.py").write_text(
        _fake_source(log_path, raise_error), encoding="utf-8"
    )
    if write_graph:
        vdir = root / "verification"
        vdir.mkdir(parents=True, exist_ok=True)
        text = graph_text if graph_text is not None else json.dumps(_corpus_graph(), indent=2)
        (vdir / "corpus-graph.json").write_text(text, encoding="utf-8")
    return root


def readiness_calls(log_path):
    if not log_path.exists():
        return []
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [e for e in entries if e.get("call") == "check_readiness"]


def test_equals_form_comma_separated_changed(tmp_path, capsys):
    log = tmp_path / "log.jsonl"
    root = make_repo(tmp_path / "repo", log)
    out = tmp_path / "out"
    capsys.readouterr()
    rc = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(root), "--out=" + str(out),
         "--changed=comp-foo,comp-bar"]
    )
    captured = capsys.readouterr()
    assert rc == 0
    index = out / "index.html"
    assert index.is_file()
    assert str(index) in captured.out or str(index.resolve()) in captured.out
    calls = readiness_calls(log)
    assert len(calls) == 1
    assert calls[-1]["changed_ids"] == ["comp-foo", "comp-bar"]


def test_space_form_with_model_and_seed(tmp_path, capsys):
    log = tmp_path / "log.jsonl"
    root = make_repo(tmp_path / "repo", log)
    out = tmp_path / "out"
    rc = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root", str(root), "--out", str(out),
         "--changed", "comp-foo", "--model", "fake-model", "--seed", "3"]
    )
    assert rc == 0
    assert (out / "index.html").is_file()
    calls = readiness_calls(log)
    assert len(calls) == 1
    assert calls[-1]["changed_ids"] == ["comp-foo"]
    assert calls[-1]["model"] == "fake-model"
    assert calls[-1]["seed"] == 3


def test_default_out_dir(tmp_path, capsys):
    log = tmp_path / "log.jsonl"
    root = make_repo(tmp_path / "repo", log)
    rc = provenance_tracker_ui.main(["track", "ui", "build", "--repo-root=" + str(root)])
    assert rc == 0
    assert (root / ".hotdocs" / "ui" / "index.html").is_file()


def test_invalid_corpus_graph_json_returns_1(tmp_path, capsys):
    log = tmp_path / "log.jsonl"
    root = make_repo(tmp_path / "repo", log, graph_text="{ this is not json")
    out = tmp_path / "out"
    rc = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(root), "--out=" + str(out)]
    )
    assert rc == 1


def test_check_readiness_value_error_returns_2(tmp_path, capsys):
    log = tmp_path / "log.jsonl"
    root = make_repo(tmp_path / "repo", log, raise_error=True)
    out = tmp_path / "out"
    rc = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(root), "--out=" + str(out)]
    )
    assert rc == 2


def test_unknown_argument_returns_2(tmp_path, capsys):
    log = tmp_path / "log.jsonl"
    root = make_repo(tmp_path / "repo", log)
    out = tmp_path / "out"
    rc = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(root), "--out=" + str(out),
         "--hotdocs-smoke-unknown"]
    )
    assert rc == 2


def test_missing_corpus_graph_usage_error(tmp_path, capsys):
    log = tmp_path / "log.jsonl"
    root = make_repo(tmp_path / "repo", log, write_graph=False)
    out = tmp_path / "out"
    capsys.readouterr()
    rc = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(root), "--out=" + str(out)]
    )
    captured = capsys.readouterr()
    assert rc == 2
    lines = captured.err.splitlines()
    assert lines, "expected a usage error on stderr"
    first = lines[0]
    assert first.startswith("usage error: missing ")
    assert first.endswith(
        "verification/corpus-graph.json; run hotdocs corpus-graph build first"
    )
    assert "  " not in first


def test_serve_returns_2(tmp_path, capsys, monkeypatch):
    log = tmp_path / "log.jsonl"
    make_repo(tmp_path / "repo", log)
    monkeypatch.chdir(tmp_path / "repo")
    rc = provenance_tracker_ui.main(["track", "ui", "serve"])
    assert rc == 2


@pytest.mark.parametrize("flag", ["--changed", "--repo-root", "--out", "--model", "--seed"])
def test_flag_last_without_value_returns_2(tmp_path, capsys, monkeypatch, flag):
    log = tmp_path / "log.jsonl"
    root = make_repo(tmp_path / "repo", log)
    monkeypatch.chdir(root)
    out = tmp_path / "out"
    argv = ["track", "ui", "build"]
    if flag != "--repo-root":
        argv += ["--repo-root", str(root)]
    if flag != "--out":
        argv += ["--out", str(out)]
    argv.append(flag)
    rc = provenance_tracker_ui.main(argv)
    assert rc == 2