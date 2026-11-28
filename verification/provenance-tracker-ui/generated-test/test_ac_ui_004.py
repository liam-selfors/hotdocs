# hotdocs-criterion: sha256:c8f3054ea6c6b023f44944d9e7c6d62a48806821e0b63b26c8e054879cf8965c
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_tracker_source(log_path):
    return (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    verification_report = {\n"
        "        'component_id': 'comp-foo',\n"
        "        'criteria': [\n"
        "            {'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'},\n"
        "        ],\n"
        "        'requirement_results': {'R-FOO-001': 'pass'},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': 0.92,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'drivers': [],\n"
        "        'overall': 'pass',\n"
        "    }\n"
        "    secret_scan = {\n"
        "        'scope': 'full',\n"
        "        'gate_version': 'secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
        "        'flagged': False,\n"
        "        'matches': [],\n"
        "        'allowed': [],\n"
        "        'unused_allowlist_entries': [],\n"
        "        'notified': False,\n"
        "        'notification_delivery_error': None,\n"
        "        'cache_hit': False,\n"
        "    }\n"
        "    license_scan = {'blocked': False, 'matches': [], 'notified': False}\n"
        "    return {\n"
        "        'scope': 'whole-corpus' if changed_ids is None else 'blast-radius',\n"
        "        'ready': False,\n"
        "        'components': {\n"
        "            'comp-foo': {\n"
        "                'hit': True,\n"
        "                'reason': None,\n"
        "                'verification_report': verification_report,\n"
        "                'license_scan': license_scan,\n"
        "                'secret_scan': secret_scan,\n"
        "            },\n"
        "            'comp-bar': {\n"
        "                'hit': False,\n"
        "                'reason': 'no manifest',\n"
        "                'verification_report': None,\n"
        "                'license_scan': None,\n"
        "                'secret_scan': None,\n"
        "            },\n"
        "        },\n"
        "        'capabilities': {\n"
        "            'P-ZERO-EDIT': {\n"
        "                'hit': True,\n"
        "                'capability_scenario_report': {\n"
        "                    'P-ZERO-EDIT': {'overall': 'pass', 'scenarios': []},\n"
        "                },\n"
        "            },\n"
        "        },\n"
        "        'secret_scan': None,\n"
        "        'not_ready_reasons': [\n"
        "            'comp-bar: no provenance for current spec state \\u2014 run hotdocs generate comp-bar',\n"
        "        ],\n"
        "    }\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
    )


def _corpus_graph():
    return {
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
            "orphan_var_rate": 0.0,
        },
    }


def _snapshot(*roots):
    state = {}
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if "__pycache__" in p.parts:
                continue
            if p.is_file():
                st = p.stat()
                state[str(p.resolve())] = (p.read_bytes(), st.st_mtime_ns, st.st_size)
    return state


def test_ac_ui_004_edges_limited_to_report_and_only_index_html_written(tmp_path):
    repo_root = tmp_path / "repo"
    out_dir = tmp_path / "out"
    log_path = tmp_path / "fake_log.txt"
    repo_root.mkdir()
    out_dir.mkdir()

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        _fake_tracker_source(log_path), encoding="utf-8"
    )

    (repo_root / "verification").mkdir()
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(_corpus_graph(), sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    before = _snapshot(repo_root, out_dir)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    after = _snapshot(repo_root, out_dir)

    # The fake ran, and check_readiness exactly once.
    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert log_lines.count("check_readiness") == 1

    # Edges are exactly depends_on and realizes, never the uses_var edge.
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
    assert all(field(e, "to") != "VAR-FOO-URL" for e in edges)
    assert all(field(e, "kind") != "uses_var" for e in edges)

    # The only file created or changed is out_dir/index.html.
    changed = set()
    for path, info in after.items():
        if path not in before or before[path] != info:
            changed.add(path)
    removed = set(before) - set(after)
    index_path = str((out_dir / "index.html").resolve())
    assert changed == {index_path}
    assert removed == set()