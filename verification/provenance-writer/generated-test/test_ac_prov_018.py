import json
import re
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
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

COMPONENT_ID = "comp-foo"
OWNERS = ["pipeline-team", "alice"]
SOURCE_PATH = "pipeline/foo/"
SOURCE_HASH = "sha256:" + ("0123456789abcdef" * 4)
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"

WRITTEN_AT_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def _criterion_dict(n, result):
    return {
        "id": "AC-FOO-00%d" % n,
        "covers": "R-FOO-00%d" % n,
        "kind": "compiled",
        "result": result,
    }


def _dict_report(results, overall):
    criteria = [_criterion_dict(i + 1, r) for i, r in enumerate(results)]
    return {
        "component_id": COMPONENT_ID,
        "criteria": criteria,
        "requirement_results": {
            c["covers"]: ("pass" if c["result"] == "pass" else "fail") for c in criteria
        },
        "interface_drift": False,
        "mutation_score": None,
        "overall": overall,
    }


@dataclass
class _ObjReport:
    component_id: str
    criteria: list
    requirement_results: dict = dc_field(default_factory=dict)
    interface_drift: bool = False
    mutation_score: object = None
    overall: str = "pass"


def _object_report(results, overall):
    criteria = [
        SimpleNamespace(
            id="AC-FOO-00%d" % (i + 1),
            covers="R-FOO-00%d" % (i + 1),
            kind="compiled",
            result=r,
        )
        for i, r in enumerate(results)
    ]
    return _ObjReport(
        component_id=COMPONENT_ID,
        criteria=criteria,
        requirement_results={
            c.covers: ("pass" if c.result == "pass" else "fail") for c in criteria
        },
        interface_drift=False,
        mutation_score=None,
        overall=overall,
    )


def _dataclass_inputs(report):
    return provenance_writer.SealedProvenanceInputs(
        component_id=COMPONENT_ID,
        owners=list(OWNERS),
        source_path=SOURCE_PATH,
        source_hash=SOURCE_HASH,
        verifier_version=VERIFIER_VERSION,
        verification_report=report,
    )


def _dict_inputs(report):
    return {
        "component_id": COMPONENT_ID,
        "owners": list(OWNERS),
        "source_path": SOURCE_PATH,
        "source_hash": SOURCE_HASH,
        "verifier_version": VERIFIER_VERSION,
        "verification_report": report,
    }


def _now_s():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _files_under(path: Path):
    if not path.exists():
        return []
    return [p for p in path.rglob("*") if p.is_file()]


def _run_and_read(repo_root: Path, inputs):
    before = _now_s()
    provenance_writer.write_sealed_provenance(COMPONENT_ID, inputs, repo_root)
    after = _now_s()

    manifest_path = repo_root / "pipeline" / "foo" / ".sealed-provenance.json"
    assert manifest_path.is_file(), "expected %s to exist" % manifest_path
    text = manifest_path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert isinstance(data, dict)

    written_at = data.get("written_at")
    assert isinstance(written_at, str)
    assert WRITTEN_AT_RE.match(written_at), written_at
    ts = datetime.strptime(written_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert before <= ts <= after, (before, ts, after)

    # Nothing written under gen/ or verification/
    assert _files_under(repo_root / "gen") == []
    assert _files_under(repo_root / "verification") == []
    return data


def _assert_common(data):
    assert list(data.keys()) == EXPECTED_KEYS
    assert data["kind"] == "sealed-provenance"
    assert data["version"] == 1
    assert type(data["version"]) is int
    assert data["component_id"] == COMPONENT_ID
    assert data["owners"] == OWNERS
    assert data["source_path"] == SOURCE_PATH
    assert data["source_hash"] == SOURCE_HASH
    assert data["verifier_version"] == VERIFIER_VERSION


def _assert_characterization(data, overall, passed, total):
    char = data["characterization"]
    assert char == {"overall": overall, "criteria_passed": passed, "criteria_total": total}
    assert list(char.keys()) == ["overall", "criteria_passed", "criteria_total"]
    assert type(char["criteria_passed"]) is int
    assert type(char["criteria_total"]) is int


def test_ac_prov_018_all_pass_dataclass_inputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = _dataclass_inputs(_dict_report(["pass", "pass", "pass"], "pass"))

    data = _run_and_read(repo_root, inputs)

    _assert_common(data)
    _assert_characterization(data, "pass", 3, 3)


def test_ac_prov_018_one_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = _dataclass_inputs(_dict_report(["pass", "fail", "pass"], "fail"))

    data = _run_and_read(repo_root, inputs)

    _assert_common(data)
    _assert_characterization(data, "fail", 2, 3)


def test_ac_prov_018_plain_dict_inputs_and_attribute_criteria(tmp_path):
    root_a = tmp_path / "repo_a"
    root_a.mkdir()
    reference = _run_and_read(
        root_a, _dataclass_inputs(_dict_report(["pass", "pass", "pass"], "pass"))
    )

    root_b = tmp_path / "repo_b"
    root_b.mkdir()
    data = _run_and_read(
        root_b, _dict_inputs(_object_report(["pass", "pass", "pass"], "pass"))
    )

    _assert_common(data)
    _assert_characterization(data, "pass", 3, 3)

    ref_wo_ts = {k: v for k, v in reference.items() if k != "written_at"}
    data_wo_ts = {k: v for k, v in data.items() if k != "written_at"}
    assert data_wo_ts == ref_wo_ts
    assert list(data.keys()) == list(reference.keys())