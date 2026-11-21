# hotdocs-criterion: sha256:952f89bad13a8fd5a6cbcfd087f822aa1fb686842f66ba2b6ea3f635ea037b43
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


REPORTED_VERSIONS = {
    "cache_manager": "cache-manager@2.4.1",
    "criterion_compiler": "compiler@1.7.0+sealed.3",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
}


def _inputs(component_id, gate_versions):
    return {
        "component_id": component_id,
        "generation_result": {"files": {}},
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": gate_versions,
    }


def _read_manifests(repo_root, slug):
    gen_path = Path(repo_root) / "gen" / slug / ".provenance.json"
    ver_path = Path(repo_root) / "verification" / slug / ".provenance.json"
    assert gen_path.is_file(), "missing manifest at " + str(gen_path)
    assert ver_path.is_file(), "missing manifest at " + str(ver_path)
    return [
        json.loads(gen_path.read_text(encoding="utf-8")),
        json.loads(ver_path.read_text(encoding="utf-8")),
    ]


def test_gate_versions_contains_exactly_the_three_reported_values_unmodified(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_id = "comp-prov-gate-sample"
    slug = "prov-gate-sample"

    gate_versions = dict(REPORTED_VERSIONS)
    result = provenance_writer.write_provenance(
        component_id, _inputs(component_id, gate_versions), repo_root
    )
    assert result is None

    # The input mapping itself is not altered by the writer.
    assert gate_versions == REPORTED_VERSIONS

    for manifest in _read_manifests(repo_root, slug):
        written = field(manifest, "gate_versions")
        assert isinstance(written, dict)
        # Exactly those three keys, no invented or hardcoded extras.
        assert set(written.keys()) == set(REPORTED_VERSIONS.keys())
        assert len(written) == 3
        # Each value is the gate's own reported version, unmodified.
        for key, value in REPORTED_VERSIONS.items():
            assert written[key] == value
            assert isinstance(written[key], str)
        assert written == REPORTED_VERSIONS


def test_gate_versions_follow_whatever_was_reported_not_a_hardcoded_table(tmp_path):
    # A second, different set of reported versions must appear verbatim too,
    # proving the values come from the inputs rather than from the writer.
    repo_root = tmp_path / "repo2"
    repo_root.mkdir()
    component_id = "comp-prov-gate-other"
    slug = "prov-gate-other"

    other_versions = {
        "cache_manager": "cache-manager@9.0.0-rc.1",
        "criterion_compiler": "compiler@0.0.1",
        "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    }

    provenance_writer.write_provenance(
        component_id, _inputs(component_id, dict(other_versions)), repo_root
    )

    for manifest in _read_manifests(repo_root, slug):
        written = field(manifest, "gate_versions")
        assert written == other_versions