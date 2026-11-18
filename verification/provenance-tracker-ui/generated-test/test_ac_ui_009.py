# hotdocs-criterion: sha256:25814814167f193d38c8e88f0595e9e32d051413dc2367f337ef46cd51cdcc88
import json
from pathlib import Path

import pytest

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_tracker_source(log_path, raise_value_error=False):
    src = ""
    src += "import json\n"
    src += "LOG = " + repr(str(log_path)) + "\n"
    src += "RAISE = " + repr(bool(raise_value_error)) + "\n"
    src += "\n"
    src += "def _passing():\n"
    src += "    return {\n"
    src += "        'hit': True,\n"
    src += "        'verification_report': {\n"
    src += "            'component_id': 'x',\n"
    src += "            'criteria': [],\n"
    src += "            'requirement_results': {},\n"
    src += "            'interface_drift': False,\n"
    src += "            'mutation_score': None,\n"
    src += "            'mutation_error': None,\n"
    src += "            'overall': 'pass',\n"
    src += "        },\n"
    src += "        'license_scan': {'blocked': False, 'findings': []},\n"
    src += "        'secret_scan': {'flagged': False, 'findings': []},\n"
    src += "    }\n"
    src += "\n"
    src += "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    src += "    with open(LOG, 'a') as f:\n"
    src += "        f.write(json.dumps({'changed_ids': None if changed_ids is None else list(changed_ids), 'model': model, 'seed': seed}) + '\\n')\n"
    src += "    if RAISE:\n"
    src += "        raise ValueError('P-X: capability provenance miss and no model given')\n"
    src += "    ids = list(changed_ids) if changed_ids else ['comp-foo', 'comp-bar']\n"
    src += "    components = {}\n"
    src += "    for i in ids:\n"
    src += "        r = _passing()\n"
    src += "        r['verification_report']['component_id'] = i\n"
    src += "        components[i] = r\n"
    src += "    return {\n"
    src += "        'scope': 'blast-radius' if changed_ids is not None else 'whole-corpus',\n"
    src += "        'ready': True,\n"
    src += "        'components': components,\n"
    src += "        'capabilities': {},\n"
    src += "        'not_ready_reasons': [],\n"
    src += "    }\n"
    src += "\n"
    src += "def last_requirement_failures(component_id, repo_root):\n"
    src += "    return []\n"
    return src


def _corpus_graph():
    def comp():
        return {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["team"],
            "documents": {"component.md": "text"},
        }

    return {
        "nodes": {"comp-foo": comp(), "comp-bar": comp()},
        "edges": [{"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"}],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


def _make_repo(root, raise_value_error=False, graph="valid"):
    root.mkdir(parents=True, exist_ok=True)
    log = root.parent / (root.name + "-calls.log")
    fake_dir = root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        _fake_tracker_source(log, raise_value_error), encoding="utf-8"
    )
    if graph == "valid":
        (root / "verification").mkdir(parents=True)
        (root / "verification" / "corpus-graph.json").write_text(
            json.dumps(_corpus_graph(), indent=2), encoding="utf-8"
        )
    elif graph == "invalid":
        (root / "verification").mkdir(parents=True)
        (root / "verification" / "corpus-graph.json").write_text(
            "{ this is not json", encoding="utf-8"
        )
    return root, log


def _calls(log):
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def _run(argv):
    try:
        return provenance_tracker_ui.main(argv)
    except SystemExit as e:
        code = e.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 2


def _printed_path(out_text, expected):
    expected_resolved = expected.resolve()
    for line in out_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line == str(expected):
            return True
        try:
            if Path(line).resolve() == expected_resolved:
                return True
        except (OSError, ValueError):
            pass
    return False


def test_build_equals_form_comma_separated_changed(tmp_path, capsys):
    repo, log = _make_repo(tmp_path / "repo")
    out = tmp_path / "out"
    rc = _run([
        "track", "ui", "build",
        "--repo-root=" + str(repo),
        "--out=" + str(out),
        "--changed=comp-foo,comp-bar",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    assert (out / "index.html").is_file()
    assert _printed_path(captured.out, out / "index.html"), captured.out
    calls = _calls(log)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo", "comp-bar"]


def test_build_space_form_with_model_and_seed(tmp_path, capsys):
    repo, log = _make_repo(tmp_path / "repo")
    out = tmp_path / "out2"
    rc = _run([
        "track", "ui", "build",
        "--repo-root", str(repo),
        "--out", str(out),
        "--changed", "comp-foo",
        "--model", "fake-model",
        "--seed", "3",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    assert (out / "index.html").is_file()
    assert _printed_path(captured.out, out / "index.html"), captured.out
    calls = _calls(log)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo"]
    assert calls[0]["model"] == "fake-model"
    assert calls[0]["seed"] == 3
    assert isinstance(calls[0]["seed"], int)


def test_build_repeated_changed(tmp_path, capsys):
    repo, log = _make_repo(tmp_path / "repo")
    out = tmp_path / "out3"
    rc = _run([
        "track", "ui", "build",
        "--repo-root=" + str(repo),
        "--out=" + str(out),
        "--changed=comp-foo",
        "--changed", "comp-bar",
    ])
    capsys.readouterr()
    assert rc == 0
    calls = _calls(log)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo", "comp-bar"]


def test_build_default_out_dir(tmp_path, capsys):
    repo, log = _make_repo(tmp_path / "repo")
    rc = _run(["track", "ui", "build", "--repo-root=" + str(repo)])
    captured = capsys.readouterr()
    assert rc == 0
    expected = repo / ".hotdocs" / "ui" / "index.html"
    assert expected.is_file()
    assert _printed_path(captured.out, expected), captured.out
    assert len(_calls(log)) == 1


def test_build_invalid_corpus_graph_json_returns_1(tmp_path, capsys):
    repo, _log = _make_repo(tmp_path / "repo", graph="invalid")
    out = tmp_path / "out"
    rc = _run(["track", "ui", "build", "--repo-root=" + str(repo), "--out=" + str(out)])
    capsys.readouterr()
    assert rc == 1


def test_build_missing_corpus_graph_returns_2(tmp_path, capsys):
    repo, _log = _make_repo(tmp_path / "repo", graph=None)
    out = tmp_path / "out"
    rc = _run(["track", "ui", "build", "--repo-root=" + str(repo), "--out=" + str(out)])
    capsys.readouterr()
    assert rc == 2


def test_build_check_readiness_value_error_returns_2(tmp_path, capsys):
    repo, log = _make_repo(tmp_path / "repo", raise_value_error=True)
    out = tmp_path / "out"
    rc = _run([
        "track", "ui", "build",
        "--repo-root=" + str(repo),
        "--out=" + str(out),
        "--changed=comp-foo",
    ])
    capsys.readouterr()
    assert rc == 2
    assert len(_calls(log)) == 1


def test_build_unknown_argument_returns_2(tmp_path, capsys):
    repo, _log = _make_repo(tmp_path / "repo")
    out = tmp_path / "out"
    rc = _run([
        "track", "ui", "build",
        "--repo-root=" + str(repo),
        "--out=" + str(out),
        "--bogus-flag=1",
    ])
    capsys.readouterr()
    assert rc == 2


def test_serve_subcommand_returns_2(tmp_path, capsys):
    repo, _log = _make_repo(tmp_path / "repo")
    rc = _run(["track", "ui", "serve", "--repo-root=" + str(repo)])
    capsys.readouterr()
    assert rc == 2


def test_serve_bare_returns_2(tmp_path, capsys):
    _make_repo(tmp_path / "repo")
    rc = _run(["track", "ui", "serve"])
    capsys.readouterr()
    assert rc == 2


@pytest.mark.parametrize("flag", ["--changed", "--repo-root", "--out", "--model", "--seed"])
def test_flag_last_with_no_value_returns_2(tmp_path, capsys, flag):
    repo, _log = _make_repo(tmp_path / "repo")
    out = tmp_path / "out"
    argv = ["track", "ui", "build"]
    if flag != "--repo-root":
        argv.append("--repo-root=" + str(repo))
    if flag != "--out":
        argv.append("--out=" + str(out))
    argv.append(flag)
    rc = _run(argv)
    capsys.readouterr()
    assert rc == 2