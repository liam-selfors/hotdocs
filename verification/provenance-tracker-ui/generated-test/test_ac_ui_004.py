# hotdocs-criterion: sha256:ed6a5fa728217bc2c2af8b01333376dbb827b88bb03e45060e05dee341bc4c0e
import hashlib
import json
import os
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-X-001", "covers": "R-X-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-X-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "overall": "pass",
    }


def _provenance_check_result(component_id):
    return {
        "hit": True,
        "verification_report": _verification_report(component_id),
        "license_scan": {"blocked": False, "findings": []},
        "secret_scan": {"flagged": False, "findings": []},
    }


def _component_node():
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "unknown",
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["test-team"],
        "documents": {},
    }


def _write_fake_tracker(repo_root, log_path):
    components = {
        "comp-foo": _provenance_check_result("comp-foo"),
        "comp-bar": _provenance_check_result("comp-bar"),
    }
    capabilities = {
        "P-ZERO-EDIT": {
            "hit": True,
            "capability_scenario_report": {
                "P-ZERO-EDIT": {"overall": "pass", "scenarios": []}
            },
        }
    }
    src = (
        "import copy\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_COMPONENTS = " + repr(components) + "\n"
        "_CAPABILITIES = " + repr(capabilities) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return {\n"
        "        'scope': 'whole-corpus' if changed_ids is None else 'blast-radius',\n"
        "        'ready': True,\n"
        "        'components': copy.deepcopy(_COMPONENTS),\n"
        "        'capabilities': copy.deepcopy(_CAPABILITIES),\n"
        "        'not_ready_reasons': [],\n"
        "    }\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
    )
    d = repo_root / "gen" / "provenance-tracker"
    d.mkdir(parents=True)
    (d / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "VAR-FOO-URL": {"type": "var"},
            "comp-bar": _component_node(),
            "comp-foo": _component_node(),
        },
        "edges": [
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
            {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    v = repo_root / "verification"
    v.mkdir(parents=True)
    (v / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _snapshot(root, label):
    result = {}
    root = Path(root)
    if not root.exists():
        return result
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            p = Path(dirpath) / name
            if "__pycache__" in p.relative_to(root).parts:
                continue
            st = p.stat()
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            result[(label, p.relative_to(root).as_posix())] = (st.st_mtime_ns, st.st_size, digest)
    return result


def test_ac_ui_004_edges_and_only_index_html_written(tmp_path):
    repo_root = tmp_path / "repo"
    out_dir = tmp_path / "out"
    log_dir = tmp_path / "logs"
    repo_root.mkdir()
    log_dir.mkdir()
    log_path = log_dir / "calls.log"

    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    before = {}
    before.update(_snapshot(repo_root, "repo"))
    before.update(_snapshot(out_dir, "out"))

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    after = {}
    after.update(_snapshot(repo_root, "repo"))
    after.update(_snapshot(out_dir, "out"))

    # The fake tracker was actually used.
    assert log_path.is_file()
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    # Edges: exactly depends_on and realizes, never the uses_var edge.
    edges = field(snapshot, "edges")
    got = sorted(
        (field(e, "from"), field(e, "to"), field(e, "kind")) for e in edges
    )
    assert len(edges) == 2
    assert got == sorted([
        ("comp-foo", "comp-bar", "depends_on"),
        ("comp-foo", "P-ZERO-EDIT", "realizes"),
    ])
    assert all(t[1] != "VAR-FOO-URL" and t[2] != "uses_var" for t in got)

    # Only out_dir/index.html created or changed.
    created = set(after) - set(before)
    removed = set(before) - set(after)
    changed = {k for k in set(before) & set(after) if before[k] != after[k]}
    assert (out_dir / "index.html").is_file()
    assert created | changed == {("out", "index.html")}
    assert removed == set()