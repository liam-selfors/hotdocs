# hotdocs-criterion: sha256:72ebde31ea5f609a094806d73f34e612b693878f02e2d4deb85c492a5ebde653
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_TRACKER_SOURCE = (
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    verification_report = {\n"
    "        'component_id': 'comp-foo',\n"
    "        'criteria': [\n"
    "            {'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'},\n"
    "        ],\n"
    "        'requirement_results': {'R-FOO-001': 'pass'},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': 1.0,\n"
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
    "    license_scan = {'blocked': False, 'matches': []}\n"
    "    return {\n"
    "        'scope': 'blast-radius' if changed_ids is not None else 'whole-corpus',\n"
    "        'ready': True,\n"
    "        'components': {\n"
    "            'comp-foo': {\n"
    "                'hit': True,\n"
    "                'reason': None,\n"
    "                'verification_report': verification_report,\n"
    "                'license_scan': license_scan,\n"
    "                'secret_scan': dict(secret_scan),\n"
    "            },\n"
    "        },\n"
    "        'capabilities': {},\n"
    "        'secret_scan': secret_scan,\n"
    "        'not_ready_reasons': [],\n"
    "    }\n"
    "\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)


def _build_repo(repo_root):
    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    (tracker_dir / "provenance_tracker.py").write_text(FAKE_TRACKER_SOURCE, encoding="utf-8")

    graph = {
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
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    verification = repo_root / "verification"
    verification.mkdir(parents=True)
    (verification / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def test_ac_ui_011_app_js_inlined_once_as_module_script(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    index = out_dir / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")

    module_open = '<script type="module">'
    assert html.count(module_open) == 1
    assert html.count("<script") == 2
    assert html.count('<script type="application/json" id="tracker-snapshot">') == 1

    asset_path = Path(provenance_tracker_ui.__file__).parent / "static" / "app.js"
    asset_text = asset_path.read_text(encoding="utf-8")

    start = html.index(module_open) + len(module_open)
    end = html.index("</script>", start)
    module_text = html[start:end]
    assert module_text == asset_text + "\ninit(document);\n"

    assert html.count(asset_text) == 1