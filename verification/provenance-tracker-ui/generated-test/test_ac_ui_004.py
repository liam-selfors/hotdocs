# hotdocs-criterion: sha256:c739cb0f4c7b76f13b3d5b363912ae1d54685cf3500ba890e0fea47b373494b0
import json
from pathlib import Path

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
        "mutation_score": 0.92,
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


def _report():
    return {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report("comp-foo"),
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            },
            "comp-bar": {
                "hit": False,
                "reason": "no manifest",
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            },
        },
        "capabilities": {
            "P-ZERO-EDIT": {
                "hit": True,
                "capability_scenario_report": {
                    "P-ZERO-EDIT": {"overall": "pass", "scenarios": []}
                },
            }
        },
        "not_ready_reasons": [
            "comp-bar: no provenance for current spec state — run hotdocs generate comp-bar"
        ],
    }


def _write_fake_tracker(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    src = (
        "REPORT = " + repr(_report()) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "VAR-FOO-URL": {"type": "var"},
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {"component.md": "bar"},
            },
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {"component.md": "foo"},
            },
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
    vdir = repo_root / "verification"
    vdir.mkdir(parents=True)
    (vdir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _snapshot(*roots):
    files = {}
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            rel = p.relative_to(root)
            if "__pycache__" in rel.parts:
                continue
            if p.is_file():
                files[p.resolve()] = p.read_bytes()
    return files


def test_ac_ui_004_edges_and_only_write(tmp_path):
    base = tmp_path.resolve()
    repo_root = base / "repo"
    out_dir = base / "out"
    repo_root.mkdir()
    out_dir.mkdir()
    log_path = base / "calls.log"

    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    before = _snapshot(repo_root, out_dir)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    after = _snapshot(repo_root, out_dir)

    # The fake was really used.
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines.count("check_readiness") == 1

    edges = field(snapshot, "edges")
    got = sorted(
        (field(e, "from"), field(e, "to"), field(e, "kind")) for e in edges
    )
    assert len(got) == len(list(edges))
    assert got == sorted(
        [
            ("comp-foo", "comp-bar", "depends_on"),
            ("comp-foo", "P-ZERO-EDIT", "realizes"),
        ]
    )
    assert all(kind != "uses_var" for _, _, kind in got)
    assert all(to != "VAR-FOO-URL" for _, to, _ in got)

    changed = set()
    for path in set(before) | set(after):
        if before.get(path) != after.get(path):
            changed.add(path)
    index = (out_dir / "index.html").resolve()
    assert changed == {index}
    assert index.is_file()