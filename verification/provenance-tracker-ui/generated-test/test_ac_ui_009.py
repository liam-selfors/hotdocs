# hotdocs-criterion: sha256:5a77427b2c4ac67efc1ee9c4848b68a136014005cb7c6b02f654c609267a2056
import json
from pathlib import Path

import pytest

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_tracker_source(log_path, raise_value_error):
    return (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "RAISE_VALUE_ERROR = " + repr(bool(raise_value_error)) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'changed_ids': list(changed_ids) if changed_ids is not None else None,\n"
        "                             'model': model, 'seed': seed}) + '\\n')\n"
        "    if RAISE_VALUE_ERROR:\n"
        "        raise ValueError('P-FAKE: capability provenance miss and no model given')\n"
        "    return {\n"
        "        'scope': 'blast-radius' if changed_ids else 'whole-corpus',\n"
        "        'ready': False,\n"
        "        'components': {\n"
        "            'comp-foo': {\n"
        "                'hit': False,\n"
        "                'reason': 'no manifest',\n"
        "                'verification_report': None,\n"
        "                'license_scan': None,\n"
        "                'secret_scan': None,\n"
        "            },\n"
        "        },\n"
        "        'capabilities': {},\n"
        "        'secret_scan': None,\n"
        "        'not_ready_reasons': ['comp-foo: no provenance for current spec state \\u2014 run hotdocs generate comp-foo'],\n"
        "    }\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


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
                "owners": ["pipeline-team"],
                "documents": {},
            },
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
        },
        "edges": [{"from": "comp-bar", "to": "comp-foo", "kind": "depends_on"}],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


def _make_repo(tmp_path, raise_value_error=False, graph=True, graph_text=None):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "check_readiness.log"
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        _fake_tracker_source(log_path, raise_value_error), encoding="utf-8"
    )
    if graph:
        vdir = repo_root / "verification"
        vdir.mkdir()
        text = graph_text if graph_text is not None else json.dumps(_corpus_graph(), indent=2)
        (vdir / "corpus-graph.json").write_text(text, encoding="utf-8")
    return repo_root, log_path


def _calls(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _printed_paths(stdout):
    return [Path(line.strip()).resolve() for line in stdout.splitlines() if line.strip()]


def test_build_equals_form_comma_separated_changed(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path)
    out = tmp_path / "out"
    code = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(repo_root), "--out=" + str(out),
         "--changed=comp-foo,comp-bar"]
    )
    captured = capsys.readouterr()
    assert code == 0
    index = out / "index.html"
    assert index.is_file()
    assert index.resolve() in _printed_paths(captured.out)
    calls = _calls(log_path)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo", "comp-bar"]


def test_build_space_form_with_model_and_seed(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path)
    out = tmp_path / "out2"
    code = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root", str(repo_root), "--out", str(out),
         "--changed", "comp-foo", "--model", "fake-model", "--seed", "3"]
    )
    captured = capsys.readouterr()
    assert code == 0
    index = out / "index.html"
    assert index.is_file()
    assert index.resolve() in _printed_paths(captured.out)
    calls = _calls(log_path)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo"]
    assert calls[0]["model"] == "fake-model"
    assert calls[0]["seed"] == 3


def test_build_default_out_dir(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path)
    code = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(repo_root)]
    )
    captured = capsys.readouterr()
    assert code == 0
    index = repo_root / ".hotdocs" / "ui" / "index.html"
    assert index.is_file()
    assert index.resolve() in _printed_paths(captured.out)


def test_build_invalid_corpus_graph_json_returns_1(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path, graph_text="{not valid json")
    out = tmp_path / "out"
    code = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(repo_root), "--out=" + str(out)]
    )
    capsys.readouterr()
    assert code == 1


def test_build_check_readiness_value_error_returns_2(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path, raise_value_error=True)
    out = tmp_path / "out"
    code = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(repo_root), "--out=" + str(out),
         "--changed=comp-foo"]
    )
    capsys.readouterr()
    assert code == 2


def test_build_unknown_argument_returns_2(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path)
    out = tmp_path / "out"
    code = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(repo_root), "--out=" + str(out),
         "--hotdocs-smoke-unknown"]
    )
    capsys.readouterr()
    assert code == 2


def test_build_missing_corpus_graph_returns_2_with_message(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path, graph=False)
    out = tmp_path / "out"
    code = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(repo_root), "--out=" + str(out)]
    )
    captured = capsys.readouterr()
    assert code == 2
    lines = captured.err.splitlines()
    assert lines, "expected a usage error on stderr"
    first = lines[0]
    assert first.startswith("usage error: missing ")
    assert first.endswith(
        "verification/corpus-graph.json; run hotdocs corpus-graph build first"
    )
    assert "  " not in first


def test_serve_is_usage_error(tmp_path, capsys):
    repo_root, log_path = _make_repo(tmp_path)
    code = provenance_tracker_ui.main(["track", "ui", "serve"])
    capsys.readouterr()
    assert code == 2


@pytest.mark.parametrize("flag", ["--changed", "--repo-root", "--out", "--model", "--seed"])
def test_flag_last_with_no_value_is_usage_error(tmp_path, capsys, flag):
    repo_root, log_path = _make_repo(tmp_path)
    out = tmp_path / "out"
    argv = ["track", "ui", "build"]
    if flag != "--repo-root":
        argv.append("--repo-root=" + str(repo_root))
    if flag != "--out":
        argv.append("--out=" + str(out))
    argv.append(flag)
    code = provenance_tracker_ui.main(argv)
    capsys.readouterr()
    assert code == 2