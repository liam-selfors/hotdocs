# hotdocs-criterion: sha256:22ccb7d7a23ac5ae304aaa9dbfc99736d78cafc694f531f37713a0f59b7b9700
"""AC-PROV-018: write_sealed_provenance writes exactly one valid sealed
provenance manifest at <repo_root>/<source_path>/.sealed-provenance.json."""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import provenance_writer


EXPECTED_KEYS = [
    "kind",
    "version",
    "component_id",
    "owners",
    "source_path",
    "source_hash",
    "verifier_version",
    "characterization",
    "written_at",
]

OWNERS = ["pipeline-team", "alice"]
SOURCE_PATH = "pipeline/foo/"
SOURCE_HASH = "sha256:" + "0123456789abcdef" * 4
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"
WRITTEN_AT_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def _criteria_dicts(results):
    return [
        {
            "id": "AC-FOO-00" + str(i + 1),
            "covers": "R-FOO-00" + str(i + 1),
            "kind": "compiled",
            "result": r,
        }
        for i, r in enumerate(results)
    ]


def _report(results, overall):
    return {
        "component_id": "comp-foo",
        "criteria": _criteria_dicts(results),
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": overall,
    }


def _dataclass_inputs(report):
    return provenance_writer.SealedProvenanceInputs(
        component_id="comp-foo",
        owners=list(OWNERS),
        source_path=SOURCE_PATH,
        source_hash=SOURCE_HASH,
        verifier_version=VERIFIER_VERSION,
        verification_report=report,
    )


def _manifest_path(repo_root):
    return Path(repo_root) / "pipeline" / "foo" / ".sealed-provenance.json"


def _read_manifest(repo_root):
    path = _manifest_path(repo_root)
    assert path.is_file(), "manifest not written at " + str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_common(manifest):
    assert isinstance(manifest, dict)
    assert list(manifest.keys()) == EXPECTED_KEYS
    assert manifest["kind"] == "sealed-provenance"
    assert manifest["version"] == 1
    assert type(manifest["version"]) is int
    assert manifest["component_id"] == "comp-foo"
    assert manifest["owners"] == OWNERS
    assert manifest["source_path"] == SOURCE_PATH
    assert manifest["source_hash"] == SOURCE_HASH
    assert manifest["verifier_version"] == VERIFIER_VERSION
    assert isinstance(manifest["written_at"], str)
    assert WRITTEN_AT_RE.match(manifest["written_at"])


def _assert_no_gen_or_verification(repo_root):
    repo_root = Path(repo_root)
    assert not (repo_root / "gen").exists()
    assert not (repo_root / "verification").exists()


def test_all_pass_report_writes_manifest(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = _dataclass_inputs(_report(["pass", "pass", "pass"], "pass"))

    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    manifest = _read_manifest(repo_root)
    _assert_common(manifest)
    assert manifest["characterization"] == {
        "overall": "pass",
        "criteria_passed": 3,
        "criteria_total": 3,
    }
    assert list(manifest["characterization"].keys()) == [
        "overall",
        "criteria_passed",
        "criteria_total",
    ]
    _assert_no_gen_or_verification(repo_root)


def test_one_failing_criterion_characterization(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = _dataclass_inputs(_report(["pass", "fail", "pass"], "fail"))

    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    manifest = _read_manifest(repo_root)
    _assert_common(manifest)
    assert manifest["characterization"] == {
        "overall": "fail",
        "criteria_passed": 2,
        "criteria_total": 3,
    }
    _assert_no_gen_or_verification(repo_root)


def test_plain_dict_inputs_and_attribute_criteria(tmp_path):
    # Reference manifest from dataclass inputs with dict criteria.
    ref_root = tmp_path / "ref"
    ref_root.mkdir()
    provenance_writer.write_sealed_provenance(
        "comp-foo", _dataclass_inputs(_report(["pass", "pass", "pass"], "pass")), ref_root
    )
    reference = _read_manifest(ref_root)

    # Plain dict inputs; criteria entries are objects exposing `result`.
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    report = _report(["pass", "pass", "pass"], "pass")
    report["criteria"] = [SimpleNamespace(**entry) for entry in report["criteria"]]
    inputs = {
        "component_id": "comp-foo",
        "owners": list(OWNERS),
        "source_path": SOURCE_PATH,
        "source_hash": SOURCE_HASH,
        "verifier_version": VERIFIER_VERSION,
        "verification_report": report,
    }

    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    manifest = _read_manifest(repo_root)
    _assert_common(manifest)
    assert manifest["characterization"] == {
        "overall": "pass",
        "criteria_passed": 3,
        "criteria_total": 3,
    }
    without_time = {k: v for k, v in manifest.items() if k != "written_at"}
    ref_without_time = {k: v for k, v in reference.items() if k != "written_at"}
    assert without_time == ref_without_time
    assert list(manifest.keys()) == list(reference.keys())
    _assert_no_gen_or_verification(repo_root)