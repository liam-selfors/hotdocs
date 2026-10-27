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
            "verification": {
                "requirements": [{"id": "R-FOO-001", "status": "pass"}],
                "acceptance": [{"id": "AC-FOO-001", "kind": "generated-test", "result": "pass"}],
            },
            "provenance": {"model_pin": "claude-sonnet-5", "prompt_version": "v3"},
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team", "cross_model_divergence_check"],
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
