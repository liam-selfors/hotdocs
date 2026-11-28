# hotdocs-criterion: sha256:ecdef5d8ec7c9a60f18b3dd5c352a79cc98fd20cac21ff8757d6244714ae47e0
import json
from pathlib import Path

import pytest

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_fake_tracker(repo_root, log_path, raise_value_error=False):
    d = repo_root / "gen" / "provenance-tracker"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "RAISE = " + repr(bool(raise_value_error)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'changed_ids': None if changed_ids is None else list(changed_ids),"
        " 'model': model, 'seed': seed}) + '\\n')\n"
        "    if RAISE:\n"
        "        raise ValueError('P-X: capability provenance miss and no model given')\n"
        "    return {\n"
        "        'scope': 'whole-corpus' if changed_ids is None else 'blast-radius',\n"
        "        'ready': True,\n"
        "        'components': {},\n"
        "        'capabilities': {},\n"
        "        'secret_scan': None,\n"
        "        'not_ready_reasons': [],\n"
        "    }\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (d / "provenance_tracker.py").write_text(src, encoding="utf-8")


def write_corpus_graph(repo_root, text=None):
    v = repo_root / "verification"
    v.mkdir(parents=True, exist_ok=True)
    if text is None:
        text = json.dumps(
            {
                "nodes": {},
                "edges": [],
                "aggregates": {
                    "orphan_capability_rate": 0.0,
                    "orphan_component_rate": 0.0,
                    "orphan_var_rate": 0.0,
                },
            },
            sort_keys=True,
            indent=2,
        ) + "\n"
    (v / "corpus-graph.json").write_text(text, encoding="utf-8")


def make_repo(tmp_path, raise_value_error=False, graph_text=None, with_graph=True):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "check_readiness.log"
    write_fake_tracker(repo_root, log_path, raise_value_error)
    if with_graph:
        write_corpus_graph(repo_root, graph_text)
    return repo_root, log_path


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_equals_form_comma_separated_changed(tmp_path, capsys):
    repo_root, log_path = make_repo(tmp_path)
    out_dir = tmp_path / "out"
    code = provenance_tracker_ui.main(
        [
            "track", "ui", "build",
            "--repo-root=" + str(repo_root),
            "--out=" + str(out_dir),
            "--changed=comp-foo,comp-bar",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    index = out_dir / "index.html"
    assert index.is_file()
    lines = [l for l in captured.out.splitlines() if l.strip()]
    assert lines, "nothing printed to stdout"
    assert Path(lines[-1].strip()).resolve() == index.resolve()
    calls = read_log(log_path)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo", "comp-bar"]


def test_space_form_with_model_and_seed(tmp_path, capsys):
    repo_root, log_path = make_repo(tmp_path)
    out_dir = tmp_path / "out"
    code = provenance_tracker_ui.main(
        [
            "track", "ui", "build",
            "--repo-root", str(repo_root),
            "--out", str(out_dir),
            "--changed", "comp-foo",
            "--model", "fake-model",
            "--seed", "3",
        ]
    )
    capsys.readouterr()
    assert code == 0
    assert (out_dir / "index.html").is_file()
    calls = read_log(log_path)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo"]
    assert calls[0]["model"] == "fake-model"
    assert calls[0]["seed"] == 3


def test_default_out_dir(tmp_path, capsys):
    repo_root, _ = make_repo(tmp_path)
    code = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(repo_root)]
    )
    capsys.readouterr()
    assert code == 0
    assert (repo_root / ".hotdocs" / "ui" / "index.html").is_file()


def test_invalid_corpus_graph_json_returns_1(tmp_path, capsys):
    repo_root, _ = make_repo(tmp_path, graph_text="{not valid json")
    out_dir = tmp_path / "out"
    code = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(repo_root), "--out=" + str(out_dir)]
    )
    capsys.readouterr()
    assert code == 1


def test_check_readiness_value_error_returns_2(tmp_path, capsys):
    repo_root, _ = make_repo(tmp_path, raise_value_error=True)
    out_dir = tmp_path / "out"
    code = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(repo_root), "--out=" + str(out_dir)]
    )
    capsys.readouterr()
    assert code == 2


def test_unknown_argument_returns_2(tmp_path, capsys):
    repo_root, _ = make_repo(tmp_path)
    out_dir = tmp_path / "out"
    code = provenance_tracker_ui.main(
        [
            "track", "ui", "build",
            "--repo-root=" + str(repo_root),
            "--out=" + str(out_dir),
            "--hotdocs-smoke-unknown",
        ]
    )
    capsys.readouterr()
    assert code == 2


def test_missing_corpus_graph_returns_2_with_message(tmp_path, capsys):
    repo_root, _ = make_repo(tmp_path, with_graph=False)
    out_dir = tmp_path / "out"
    code = provenance_tracker_ui.main(
        ["track", "ui", "build", "--repo-root=" + str(repo_root), "--out=" + str(out_dir)]
    )
    captured = capsys.readouterr()
    assert code == 2
    err_lines = captured.err.splitlines()
    assert err_lines, "nothing printed to stderr"
    first = err_lines[0]
    assert first.startswith("usage error: missing ")
    assert first.endswith("verification/corpus-graph.json; run hotdocs corpus-graph build first")
    assert "  " not in first


@pytest.mark.parametrize(
    "tail",
    [
        "serve",
        "--changed",
        "--repo-root",
        "--out",
        "--model",
        "--seed",
    ],
)
def test_usage_errors_return_2(tmp_path, capsys, tail):
    repo_root, _ = make_repo(tmp_path)
    out_dir = tmp_path / "out"
    if tail == "serve":
        argv = ["track", "ui", "serve"]
    else:
        argv = [
            "track", "ui", "build",
            "--repo-root=" + str(repo_root),
            "--out=" + str(out_dir),
            tail,
        ]
    code = provenance_tracker_ui.main(argv)
    capsys.readouterr()
    assert code == 2