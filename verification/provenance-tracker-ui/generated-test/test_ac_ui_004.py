# hotdocs-criterion: sha256:2478a168a8d3117e78e15f5a7bb999b39e701144db2d1da10382d36b53424795
import hashlib
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _snapshot_files(roots):
    state = {}
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if "__pycache__" in p.parts:
                continue
            if p.is_file():
                state[str(p.resolve())] = hashlib.sha256(p.read_bytes()).hexdigest()
    return state


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
                "adapter_sha256": "sha256:abc",
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "pass",
    }


def _secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _verify_report():
    return {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report("comp-foo"),
                "license_scan": {"blocked": False},
                "secret_scan": _secret_scan(),
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
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [
            "comp-bar: no provenance for current spec state — run hotdocs generate comp-bar"
        ],
    }


def _write_fake_tracker(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    src = (
        "import copy\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(_verify_report()) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    report = copy.deepcopy(_REPORT)\n"
        "    report['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return report\n"
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
                "documents": {},
            },
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
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
            "orphan_var_rate": 1.0,
        },
    }
    vdir = repo_root / "verification"
    vdir.mkdir(parents=True)
    (vdir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def test_ac_ui_004_edges_and_only_index_written(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "fake_calls.log"

    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    before = _snapshot_files([repo_root, out_dir])

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    after = _snapshot_files([repo_root, out_dir])

    # The fake ran.
    assert log_path.is_file()
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    # Edges are exactly depends_on and realizes, never uses_var.
    edges = field(snapshot, "edges")
    got = sorted(
        (field(e, "from"), field(e, "to"), field(e, "kind")) for e in edges
    )
    assert got == sorted(
        [
            ("comp-foo", "comp-bar", "depends_on"),
            ("comp-foo", "P-ZERO-EDIT", "realizes"),
        ]
    )
    assert len(edges) == 2
    for e in edges:
        assert field(e, "kind") != "uses_var"
        assert field(e, "to") != "VAR-FOO-URL"

    # The only file created or changed is out_dir/index.html.
    index_path = str((out_dir / "index.html").resolve())
    created = set(after) - set(before)
    removed = set(before) - set(after)
    changed = {p for p in set(before) & set(after) if before[p] != after[p]}
    assert created == {index_path}
    assert changed == set()
    assert removed == set()
    assert (out_dir / "index.html").is_file()