# hotdocs-criterion: sha256:4b358f15ded50d822f02e7eb0c6ab32c77ed970e1dd16a606fb8ba4dd1e02257
import json
from pathlib import Path

import pytest

import provenance_tracker_ui


FAKE_TRACKER_SOURCE = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def _log(repo_root, entry):\n"
    "    with open(Path(repo_root) / " + repr("fake-log.jsonl") + ", " + repr("a") + ") as f:\n"
    "        f.write(json.dumps(entry) + " + repr("\n") + ")\n"
    "\n"
    "\n"
    "def _verification_report(component_id):\n"
    "    return {\n"
    "        " + repr("component_id") + ": component_id,\n"
    "        " + repr("criteria") + ": [],\n"
    "        " + repr("requirement_results") + ": {},\n"
    "        " + repr("interface_drift") + ": False,\n"
    "        " + repr("mutation_score") + ": None,\n"
    "        " + repr("mutation_error") + ": None,\n"
    "        " + repr("assets") + ": [],\n"
    "        " + repr("overall") + ": " + repr("pass") + ",\n"
    "    }\n"
    "\n"
    "\n"
    "def _hit(component_id):\n"
    "    return {\n"
    "        " + repr("hit") + ": True,\n"
    "        " + repr("reason") + ": None,\n"
    "        " + repr("verification_report") + ": _verification_report(component_id),\n"
    "        " + repr("license_scan") + ": {" + repr("blocked") + ": False},\n"
    "        " + repr("secret_scan") + ": {" + repr("flagged") + ": False},\n"
    "    }\n"
    "\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log(repo_root, {\n"
    "        " + repr("call") + ": " + repr("check_readiness") + ",\n"
    "        " + repr("changed_ids") + ": None if changed_ids is None else list(changed_ids),\n"
    "        " + repr("model") + ": model,\n"
    "        " + repr("seed") + ": seed,\n"
    "    })\n"
    "    if (Path(repo_root) / " + repr("fake-mode-raise") + ").exists():\n"
    "        raise ValueError(" + repr("P-X: capability provenance miss with no model") + ")\n"
    "    return {\n"
    "        " + repr("scope") + ": " + repr("blast-radius") + " if changed_ids is not None else " + repr("whole-corpus") + ",\n"
    "        " + repr("ready") + ": True,\n"
    "        " + repr("components") + ": {\n"
    "            " + repr("comp-foo") + ": _hit(" + repr("comp-foo") + "),\n"
    "            " + repr("comp-bar") + ": _hit(" + repr("comp-bar") + "),\n"
    "        },\n"
    "        " + repr("capabilities") + ": {},\n"
    "        " + repr("not_ready_reasons") + ": [],\n"
    "    }\n"
    "\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log(repo_root, {" + repr("call") + ": " + repr("last_requirement_failures") + ", "
    + repr("component_id") + ": component_id})\n"
    "    return []\n"
)


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


def make_repo(tmp_path, graph=True, graph_text=None, raise_value_error=False):
    repo_root = tmp_path / "repo"
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(FAKE_TRACKER_SOURCE, encoding="utf-8")
    if graph:
        ver = repo_root / "verification"
        ver.mkdir(parents=True)
        text = graph_text if graph_text is not None else json.dumps(_corpus_graph(), indent=2)
        (ver / "corpus-graph.json").write_text(text, encoding="utf-8")
    if raise_value_error:
        (repo_root / "fake-mode-raise").write_text("1", encoding="utf-8")
    return repo_root


def read_log(repo_root):
    path = repo_root / "fake-log.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def readiness_calls(repo_root):
    return [e for e in read_log(repo_root) if e.get("call") == "check_readiness"]


def printed_path(out, path):
    return str(path) in out or str(path.resolve()) in out


def test_build_equals_form_comma_separated_changed(tmp_path, capsys, monkeypatch):
    repo_root = make_repo(tmp_path)
    monkeypatch.chdir(repo_root)
    out_dir = tmp_path / "out"
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo_root),
        "--out=" + str(out_dir),
        "--changed=comp-foo,comp-bar",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    index = out_dir / "index.html"
    assert index.is_file()
    assert printed_path(captured.out, index)
    calls = readiness_calls(repo_root)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo", "comp-bar"]


def test_build_space_form_with_model_and_seed(tmp_path, capsys, monkeypatch):
    repo_root = make_repo(tmp_path)
    monkeypatch.chdir(repo_root)
    out_dir = tmp_path / "out2"
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
    assert printed_path(captured.out, index)
    calls = readiness_calls(repo_root)
    assert len(calls) == 1
    assert calls[0]["changed_ids"] == ["comp-foo"]
    assert calls[0]["model"] == "fake-model"
    assert calls[0]["seed"] == 3
    assert isinstance(calls[0]["seed"], int)


def test_build_default_out_dir(tmp_path, capsys, monkeypatch):
    repo_root = make_repo(tmp_path)
    monkeypatch.chdir(repo_root)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo_root),
        "--changed=comp-foo",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    index = repo_root / ".hotdocs" / "ui" / "index.html"
    assert index.is_file()
    assert printed_path(captured.out, index)


def test_build_invalid_corpus_graph_json_returns_1(tmp_path, capsys, monkeypatch):
    repo_root = make_repo(tmp_path, graph_text="{ this is not json")
    monkeypatch.chdir(repo_root)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo_root),
        "--out=" + str(tmp_path / "out"),
        "--changed=comp-foo",
    ])
    capsys.readouterr()
    assert rc == 1


def test_build_missing_corpus_graph_returns_2(tmp_path, capsys, monkeypatch):
    repo_root = make_repo(tmp_path, graph=False)
    monkeypatch.chdir(repo_root)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo_root),
        "--out=" + str(tmp_path / "out"),
        "--changed=comp-foo",
    ])
    capsys.readouterr()
    assert rc == 2


def test_build_check_readiness_value_error_returns_2(tmp_path, capsys, monkeypatch):
    repo_root = make_repo(tmp_path, raise_value_error=True)
    monkeypatch.chdir(repo_root)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo_root),
        "--out=" + str(tmp_path / "out"),
        "--changed=comp-foo",
    ])
    capsys.readouterr()
    assert rc == 2
    assert len(readiness_calls(repo_root)) == 1


def test_build_unknown_argument_returns_2(tmp_path, capsys, monkeypatch):
    repo_root = make_repo(tmp_path)
    monkeypatch.chdir(repo_root)
    rc = provenance_tracker_ui.main([
        "track", "ui", "build",
        "--repo-root=" + str(repo_root),
        "--out=" + str(tmp_path / "out"),
        "--hotdocs-smoke-unknown",
    ])
    capsys.readouterr()
    assert rc == 2


def test_serve_returns_2(tmp_path, capsys, monkeypatch):
    repo_root = make_repo(tmp_path)
    monkeypatch.chdir(repo_root)
    rc = provenance_tracker_ui.main(["track", "ui", "serve"])
    capsys.readouterr()
    assert rc == 2


@pytest.mark.parametrize("flag", ["--changed", "--repo-root", "--out", "--model", "--seed"])
def test_flag_last_without_value_returns_2(tmp_path, capsys, monkeypatch, flag):
    repo_root = make_repo(tmp_path)
    monkeypatch.chdir(repo_root)
    argv = ["track", "ui", "build"]
    if flag != "--repo-root":
        argv.append("--repo-root=" + str(repo_root))
    if flag != "--out":
        argv.append("--out=" + str(tmp_path / "out"))
    argv.append(flag)
    rc = provenance_tracker_ui.main(argv)
    capsys.readouterr()
    assert rc == 2