import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "docs-site-renderer"))
import docs_site_renderer  # noqa: E402

SAMPLE_GRAPH = {
    "nodes": {
        "P-ZERO-EDIT": {"type": "capability"},
        "comp-foo": {
            "type": "component",
            # CorpusGraph.md's shape (D286): verification is the manifest's
            # verification_report, documents the component's spec files.
            "verification": {
                "criteria": [{"id": "AC-FOO-001", "covers": "R-FOO-001",
                              "kind": "generated-test", "result": "pass"}],
                "requirement_results": {"R-FOO-001": "pass"},
                "overall": "pass",
            },
            "provenance": {"model_pin": "claude-sonnet-5", "prompt_version": "v3"},
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {"component.md": "# Foo\n\nFoo does a thing."},
        },
        "VAR-FOO-URL": {"type": "var"},
    },
    "edges": [
        {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
        {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
    ],
    "aggregates": {
        "orphan_capability_rate": 0.25,
        "orphan_component_rate": 0.0,
    },
}


@pytest.fixture
def out_dir(tmp_path):
    return tmp_path / "dist"
