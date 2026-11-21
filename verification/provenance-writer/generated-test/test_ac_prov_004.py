# hotdocs-criterion: sha256:43a36729d5dc916518b22123f34eb3527b2646ec8530d6ab06dd74a6e3f4c5e5
import json
from pathlib import Path

import provenance_writer


def _minimal_inputs(provenance_hit):
    # A valid minimal call per provenance-writer-fixtures.md, with every
    # per-gate cache_hit set false so a recomputed value would disagree.
    return {
        "component_id": "comp-foo",
        "generation_result": {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification_report": None,
        "license_scan_result": {"cache_hit": False},
        "secret_scan_result": {"cache_hit": False},
        "provenance_hit": provenance_hit,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {},
    }


def _read_manifests(repo_root, slug):
    paths = [
        repo_root / "gen" / slug / ".provenance.json",
        repo_root / "verification" / slug / ".provenance.json",
    ]
    manifests = []
    for path in paths:
        assert path.is_file(), "manifest missing at " + str(path)
        manifests.append(json.loads(path.read_text(encoding="utf-8")))
    return manifests


def test_ac_prov_004_provenance_hit_true_is_copied(tmp_path):
    repo_root = Path(tmp_path)
    inputs = _minimal_inputs(True)

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    for manifest in _read_manifests(repo_root, "foo"):
        assert "provenance_hit" in manifest
        assert manifest["provenance_hit"] is True