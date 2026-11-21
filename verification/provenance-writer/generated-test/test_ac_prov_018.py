# hotdocs-criterion: sha256:5a825abfba93884471f97ebd30a9e47bf409f5f358909fdaf6ee7bf03258610e
import json
import re
from datetime import datetime, timezone
from pathlib import Path

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

SOURCE_HASH = "sha256:" + "0123456789abcdef" * 4
OWNERS = ["pipeline-team", "alice"]
SOURCE_PATH = "pipeline/foo/"
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"
WRITTEN_AT_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_report(results, overall):
    criteria = []
    for i, result in enumerate(results, start=1):
        criteria.append({
            "id": "AC-FOO-00" + str(i),
            "covers": "R-FOO-00" + str(i),
            "kind": "generated-test",
            "result": result,
        })
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": {c["covers"]: c["result"] for c in criteria},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": overall,
    }


class CriterionEntry:
    def __init__(self, id, covers, kind, result):
        self.id = id
        self.covers = covers
        self.kind = kind
        self.result = result


def make_dataclass_inputs(report):
    return provenance_writer.SealedProvenanceInputs(
        component_id="comp-foo",
        owners=list(OWNERS),
        source_path=SOURCE_PATH,
        source_hash=SOURCE_HASH,
        verifier_version=VERIFIER_VERSION,
        verification_report=report,
    )


def read_manifest(repo_root):
    path = Path(repo_root) / "pipeline" / "foo" / ".sealed-provenance.json"
    assert path.is_file(), "manifest not written at " + str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def now_s():
    return datetime.now(timezone.utc).replace(microsecond=0)


def test_pass_report_writes_exact_manifest(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = make_dataclass_inputs(make_report(["pass", "pass", "pass"], "pass"))

    before = now_s()
    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)
    after = now_s()

    manifest = read_manifest(repo_root)
    assert isinstance(manifest, dict)
    assert list(manifest.keys()) == EXPECTED_KEYS
    assert manifest["kind"] == "sealed-provenance"
    assert manifest["version"] == 1 and type(manifest["version"]) is int
    assert manifest["characterization"] == {
        "overall": "pass",
        "criteria_passed": 3,
        "criteria_total": 3,
    }
    assert manifest["component_id"] == "comp-foo"
    assert manifest["owners"] == OWNERS
    assert manifest["source_path"] == SOURCE_PATH
    assert manifest["source_hash"] == SOURCE_HASH
    assert manifest["verifier_version"] == VERIFIER_VERSION

    written_at = manifest["written_at"]
    assert isinstance(written_at, str) and WRITTEN_AT_RE.match(written_at)
    ts = datetime.strptime(written_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert before <= ts <= after

    assert not (repo_root / "gen").exists()
    assert not (repo_root / "verification").exists()


def test_fail_report_characterization(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = make_dataclass_inputs(make_report(["pass", "fail", "pass"], "fail"))

    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    manifest = read_manifest(repo_root)
    assert manifest["characterization"] == {
        "overall": "fail",
        "criteria_passed": 2,
        "criteria_total": 3,
    }


def strip_time(manifest):
    return {k: v for k, v in manifest.items() if k != "written_at"}


def test_dict_inputs_and_attribute_entries_write_same_manifest(tmp_path):
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()

    dataclass_inputs = make_dataclass_inputs(make_report(["pass", "pass", "pass"], "pass"))
    provenance_writer.write_sealed_provenance("comp-foo", dataclass_inputs, root_a)
    reference = read_manifest(root_a)

    plain_report = make_report(["pass", "pass", "pass"], "pass")
    attr_report = dict(plain_report)
    attr_report["criteria"] = [
        CriterionEntry(c["id"], c["covers"], c["kind"], c["result"])
        for c in plain_report["criteria"]
    ]
    dict_inputs = {
        "component_id": "comp-foo",
        "owners": list(OWNERS),
        "source_path": SOURCE_PATH,
        "source_hash": SOURCE_HASH,
        "verifier_version": VERIFIER_VERSION,
        "verification_report": attr_report,
    }

    provenance_writer.write_sealed_provenance("comp-foo", dict_inputs, root_b)
    manifest = read_manifest(root_b)

    assert list(manifest.keys()) == EXPECTED_KEYS
    assert strip_time(manifest) == strip_time(reference)
    assert manifest["characterization"] == {
        "overall": "pass",
        "criteria_passed": 3,
        "criteria_total": 3,
    }
    assert WRITTEN_AT_RE.match(manifest["written_at"])
    assert not (root_b / "gen").exists()
    assert not (root_b / "verification").exists()