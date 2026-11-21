# hotdocs-criterion: sha256:c7a00fd17891e2427ab9bb167969af4da2d7e64a80cce556d650977da394c7c8
"""AC-PROV-003: gate_versions holds exactly the three reported values, unmodified.

Given reported versions from cache-manager, criterion-compiler and
license-scanner, when write_provenance runs, then the manifest's
gate_versions contains exactly those three reported values, unmodified.
"""

import copy
import json
from pathlib import Path

import pytest

import provenance_writer


COMPONENT_ID = "comp-prov-gate-fixture"
SLUG = "prov-gate-fixture"

# Deliberately unusual values, so nothing hardcoded in the writer can match.
REPORTED_GATE_VERSIONS = {
    "cache_manager": "cache-manager@7.13.29+zq81",
    "criterion_compiler": "criterion-compiler@0.42.917-rc.3+build.5x",
    "license_scanner": "license_scanner@4.0.11+a1b2c3d4e5f6",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _inputs(gate_versions):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": {"files": {}},
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": gate_versions,
    }


def _manifest_paths(repo_root):
    return [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]


def test_gate_versions_are_exactly_the_reported_values(tmp_path):
    repo_root = Path(tmp_path)
    gate_versions = copy.deepcopy(REPORTED_GATE_VERSIONS)
    inputs = _inputs(gate_versions)

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    for path in _manifest_paths(repo_root):
        assert path.is_file(), "manifest missing at " + str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        written = field(manifest, "gate_versions")
        assert isinstance(written, dict)
        # Exactly the three reported entries, no more, no fewer.
        assert set(written.keys()) == set(REPORTED_GATE_VERSIONS.keys())
        assert len(written) == 3
        # Each value unmodified, byte for byte.
        for key, value in REPORTED_GATE_VERSIONS.items():
            assert isinstance(written[key], str)
            assert written[key] == value
        assert written == REPORTED_GATE_VERSIONS

    # The caller's reported values were not altered in place either.
    assert gate_versions == REPORTED_GATE_VERSIONS


def test_gate_versions_follow_the_input_not_a_constant(tmp_path):
    """Different reported values yield different written values."""
    other = {
        "cache_manager": "cache-manager@99.0.1",
        "criterion_compiler": "criterion-compiler@3.3.3+zz",
        "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    }
    first_root = Path(tmp_path) / "first"
    second_root = Path(tmp_path) / "second"
    first_root.mkdir()
    second_root.mkdir()

    provenance_writer.write_provenance(
        COMPONENT_ID, _inputs(copy.deepcopy(REPORTED_GATE_VERSIONS)), first_root
    )
    provenance_writer.write_provenance(
        COMPONENT_ID, _inputs(copy.deepcopy(other)), second_root
    )

    for path in _manifest_paths(first_root):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert field(manifest, "gate_versions") == REPORTED_GATE_VERSIONS
    for path in _manifest_paths(second_root):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert field(manifest, "gate_versions") == other