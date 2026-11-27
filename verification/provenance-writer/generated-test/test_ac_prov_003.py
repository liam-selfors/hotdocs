# hotdocs-criterion: sha256:55663948d9bb4721a38c4421e51bb2de1bb10c4e78d4a3f5a87cd1f4424f1b04
import copy
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


REPORTED_GATE_VERSIONS = {
    "cache_manager": "cache-manager@1.7.2",
    "criterion_compiler": "compiler@2.3.0+5e1fa09c",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
}


def _minimal_inputs(gate_versions):
    return {
        "component_id": "comp-foo",
        "generation_result": {"files": {}},
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": gate_versions,
    }


def _read_manifest(path):
    assert path.is_file(), "manifest missing at " + str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def test_gate_versions_are_exactly_the_reported_values_unmodified(tmp_path):
    repo_root = Path(tmp_path)
    gate_versions = copy.deepcopy(REPORTED_GATE_VERSIONS)
    inputs = _minimal_inputs(gate_versions)

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    gen_manifest = _read_manifest(repo_root / "gen" / "foo" / ".provenance.json")
    ver_manifest = _read_manifest(
        repo_root / "verification" / "foo" / ".provenance.json"
    )

    for manifest in (gen_manifest, ver_manifest):
        written = field(manifest, "gate_versions")
        assert isinstance(written, dict)
        # Exactly the three reported values: no extra, no missing, none altered.
        assert written == REPORTED_GATE_VERSIONS
        assert set(written.keys()) == set(REPORTED_GATE_VERSIONS.keys())
        for key, value in REPORTED_GATE_VERSIONS.items():
            assert written[key] == value

    # The caller's reported values are not modified either.
    assert gate_versions == REPORTED_GATE_VERSIONS


def test_gate_versions_follow_the_reported_values_not_hardcoded(tmp_path):
    other_versions = {
        "cache_manager": "cache-manager@9.9.9-test",
        "criterion_compiler": "compiler@0.0.1+deadbeef",
        "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    }
    repo_root = Path(tmp_path)

    provenance_writer.write_provenance(
        "comp-foo", _minimal_inputs(copy.deepcopy(other_versions)), repo_root
    )

    for sub in ("gen", "verification"):
        manifest = _read_manifest(repo_root / sub / "foo" / ".provenance.json")
        assert field(manifest, "gate_versions") == other_versions