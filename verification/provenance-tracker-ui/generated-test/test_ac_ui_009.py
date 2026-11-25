# hotdocs-criterion: sha256:3b40b6835e498d9782f09e3333462f87e84a0f15be17a182a8fe81840a55d83b
import json
from pathlib import Path

import pytest

import provenance_tracker_ui


GRAPH_SUFFIX = "verification/corpus-graph.json; run hotdocs corpus-graph build first"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_source(log_path, raise_value_error):
    src = ""
    src += "import json\n"
    src += "\n"
    src += "LOG = " + repr(str(log_path)) + "\n"
    src += "RAISE = " + repr(bool(raise_value_error)) + "\n"
    src += "\n"
    src += "\n"
    src += "def _verification_report(component_id):\n"
    src += "    return {\n"
    src += "        'component_id': component_id,\n"
    src += "        'criteria': [],\n"
    src += "        'requirement_results': {},\n"
    src += "        'interface_drift': False,\n"
    src += "        'mutation_score': None,\n"
    src += "        'mutation_error': None,\n"
    src += "        'assets': [],\n"
    src += "        'overall': 'pass',\n"
    src += "    }\n"
    src += "\n"
    src += "\n"
    src += "def _secret_scan():\n"
    src += "    return {\n"
    src += "        'scope': 'full',\n"
    src += "        'gate_version': 'secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
    src += "        'flagged': False,\n"
    src += "        'matches': [],\n"
    src += "        'allowed': [],\n"
    src += "        'unused_allowlist_entries': [],\n"
    src += "        'notified': False,\n"
    src += "        'notification_delivery_error': None,\n"
    src += "        'cache_hit': False,\n"
    src += "    }\n"
    src += "\n"
    src += "\n"
    src += "def _hit(component_id):\n"
    src += "    return {\n"
    src += "        'hit': True,\n"
    src += "        'reason': None,\n"
    src += "        'verification_report': _verification_report(component_id),\n"
    src += "        'license_scan': {'blocked': False},\n"
    src += "        'secret_scan': _secret_scan(),\n"
    src += "    }\n"
    src += "\n"
    src += "\n"
    src += "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    src += "    entry = {\n"
    src += "        'changed_ids': list(changed_ids) if changed_ids is not None else None,\n"
    src += "        'model': model,\n"
    src += "        'seed': seed,\n"
    src += "    }\n"
    src += "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    src += "        fh.write(json.dumps(entry) + '\\n')\n"
    src += "    if RAISE:\n"
    src += "        raise ValueError('P-X: capability provenance miss and no model given')\n"
    src += "    return {\n"
    src += "        'scope': 'blast-radius' if changed_ids is not None else 'whole-corpus',\n"
    src += "        'ready': True,\n"
    src += "        'components': {'comp-foo': _hit('comp-foo'), 'comp-bar': _hit('comp-bar')},\n"
    src += "        'capabilities': {},\n"
    src += "        'secret_scan': _secret_scan(),\n"
    src += "        'not_ready_reasons': [],\n"
    src += "    }\n"
    src += "\n"
    src += "\n"
    src += "def last_requirement_failures(component_id, repo_root):\n"
    src += "    return []\n"
    return src


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
        "edges": [
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


def _make_repo(tmp_path, name, raise_value_error=False, graph="valid"):
    repo = tmp_path / name
    repo.mkdir()
    log_path = tmp_path / (name + "-calls.log")
    fake_dir = repo / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        _fake_source(log_path, raise_value_error), encoding="utf-8"
    )
    if graph is not None:
        ver = repo / "verification"
        ver.mkdir()
        if graph == "valid":
            text = json.dumps(_corpus_graph(), sort_keys=True, indent=2) + "\n"
        else:
            text = "{ this is not json"
        (ver / "corpus-graph.json").write_text(text, encoding="utf-8")
    return repo, log_path


def _calls(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _printed_path(stdout, expected):
    target = Path(expected).resolve()
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            if Path(line).resolve() == target:
                return True
        except (OSError, ValueError):
            continue
    return False


def test_build_equals_form_comma_separated_changed(tmp_path, capsys, monkeypatch):
    repo, log = _make_repo(tmp_path, "repo1")
    out = tmp_path / "out1"
    monkeypatch.chdir(tmp_path)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo),
        "--out=" + str(out),
        "--changed=comp-foo,comp-bar",
    ])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    index = out / "index.html"
    assert index.is_file()
    assert _printed_path(captured.out, index), captured.out
    calls = _calls(log)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo", "comp-bar"]


def test_build_space_form_with_model_and_seed(tmp_path, capsys, monkeypatch):
    repo, log = _make_repo(tmp_path, "repo2")
    out = tmp_path / "out2"
    monkeypatch.chdir(tmp_path)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root", str(repo),
        "--out", str(out),
        "--changed", "comp-foo",
        "--model", "fake-model",
        "--seed", "3",
    ])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    assert (out / "index.html").is_file()
    calls = _calls(log)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo"]
    assert calls[0]["model"] == "fake-model"
    assert calls[0]["seed"] == 3
    assert not isinstance(calls[0]["seed"], bool)


def test_build_default_out_dir(tmp_path, capsys, monkeypatch):
    repo, log = _make_repo(tmp_path, "repo3")
    monkeypatch.chdir(tmp_path)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build", "--repo-root=" + str(repo),
    ])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    index = repo / ".hotdocs" / "ui" / "index.html"
    assert index.is_file()
    assert _printed_path(captured.out, index), captured.out


def test_build_invalid_corpus_graph_json_returns_1(tmp_path, capsys, monkeypatch):
    repo, log = _make_repo(tmp_path, "repo4", graph="invalid")
    out = tmp_path / "out4"
    monkeypatch.chdir(tmp_path)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo),
        "--out=" + str(out),
    ])
    capsys.readouterr()
    assert rc == 1


def test_build_check_readiness_value_error_returns_2(tmp_path, capsys, monkeypatch):
    repo, log = _make_repo(tmp_path, "repo5", raise_value_error=True)
    out = tmp_path / "out5"
    monkeypatch.chdir(tmp_path)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo),
        "--out=" + str(out),
    ])
    capsys.readouterr()
    assert rc == 2
    assert len(_calls(log)) == 1


def test_build_unknown_argument_returns_2(tmp_path, capsys, monkeypatch):
    repo, log = _make_repo(tmp_path, "repo6")
    out = tmp_path / "out6"
    monkeypatch.chdir(tmp_path)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo),
        "--out=" + str(out),
        "--hotdocs-smoke-unknown",
    ])
    capsys.readouterr()
    assert rc == 2


def test_build_missing_corpus_graph_usage_error(tmp_path, capsys, monkeypatch):
    repo, log = _make_repo(tmp_path, "repo7", graph=None)
    out = tmp_path / "out7"
    monkeypatch.chdir(tmp_path)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo),
        "--out=" + str(out),
    ])
    captured = capsys.readouterr()
    assert rc == 2
    lines = captured.err.splitlines()
    assert lines, "expected a usage error on stderr"
    first = lines[0]
    assert first.startswith("usage error: missing "), first
    assert first.endswith(GRAPH_SUFFIX), first
    assert "  " not in first, first


def test_serve_returns_2(tmp_path, capsys, monkeypatch):
    repo, log = _make_repo(tmp_path, "repo8")
    monkeypatch.chdir(repo)
    rc = provenance_tracker_ui.main(["track", "ui", "serve", "--repo-root=" + str(repo)])
    capsys.readouterr()
    assert rc == 2
    rc = provenance_tracker_ui.main(["track", "ui", "serve"])
    capsys.readouterr()
    assert rc == 2


@pytest.mark.parametrize("flag", ["--changed", "--repo-root", "--out", "--model", "--seed"])
def test_flag_last_with_no_value_returns_2(tmp_path, capsys, monkeypatch, flag):
    repo, log = _make_repo(tmp_path, "repo9")
    out = tmp_path / "out9"
    monkeypatch.chdir(repo)
    argv = ["track", "ui", "build"]
    if flag != "--repo-root":
        argv.append("--repo-root=" + str(repo))
    if flag != "--out":
        argv.append("--out=" + str(out))
    argv.append(flag)
    rc = provenance_tracker_ui.main(argv)
    capsys.readouterr()
    assert rc == 2