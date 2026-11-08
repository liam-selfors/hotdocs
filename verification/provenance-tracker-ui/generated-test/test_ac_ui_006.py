import json
from pathlib import Path

import provenance_tracker_ui


def _write_fixture(repo_root: Path) -> None:
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True, exist_ok=True)
    (dep_dir / "provenance_tracker.py").write_text(
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return {\n"
        "        \"scope\": \"blast-radius\" if changed_ids else \"whole-corpus\",\n"
        "        \"ready\": True,\n"
        "        \"components\": {\n"
        "            \"comp-foo\": {\n"
        "                \"hit\": True,\n"
        "                \"verification_report\": {\n"
        "                    \"component_id\": \"comp-foo\",\n"
        "                    \"criteria\": [],\n"
        "                    \"requirement_results\": {},\n"
        "                    \"interface_drift\": False,\n"
        "                    \"mutation_score\": 1.0,\n"
        "                    \"overall\": \"pass\",\n"
        "                },\n"
        "                \"license_scan\": {\"blocked\": False},\n"
        "                \"secret_scan\": {\"flagged\": False},\n"
        "            }\n"
        "        },\n"
        "        \"capabilities\": {},\n"
        "        \"not_ready_reasons\": [],\n"
        "    }\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )

    verification_dir = repo_root / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    corpus_graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": {
                    "component_id": "comp-foo",
                    "criteria": [],
                    "requirement_results": {},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "provenance": {},
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
            }
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    (verification_dir / "corpus-graph.json").write_text(json.dumps(corpus_graph))


def test_rendered_index_html_requires_no_server_and_serve_is_retired(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    index_html = out_dir / "index.html"
    assert index_html.is_file()
    html_text = index_html.read_text()

    assert "fetch(" not in html_text
    assert "XMLHttpRequest" not in html_text
    assert "http://" not in html_text
    assert "https://" not in html_text

    public_names = [
        name for name in dir(provenance_tracker_ui) if not name.startswith("_")
    ]
    assert not any("serve" in name.lower() for name in public_names)

    try:
        result = provenance_tracker_ui.main(["track", "ui", "serve"])
        exit_code = result
    except SystemExit as exc:
        exit_code = exc.code

    assert exit_code == 2