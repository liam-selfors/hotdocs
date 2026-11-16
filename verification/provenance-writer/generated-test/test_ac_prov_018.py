import provenance_writer

import json
import re
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from pathlib import Path

import pytest


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
SOURCE_HASH = "sha256:" + "0123456789abcdef" * 4
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"

WRITTEN_AT_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


@dataclass
class FakeVerificationReport:
    """Mirrors verifier-orchestrator's VerificationReport: a dataclass whose
    fields are attributes, with to_dict() giving the JSON form."""

    component_id: str
    criteria: list
    requirement_results: dict = dc_field(default_factory=dict)
    interface_drift: bool = False
    mutation_score: object = None
    overall: str = "pass"

    def to_dict(self):
        def crit(c):
            if isinstance(c, dict):
                return dict(c)
            return {"id": c.id, "covers": c.covers, "kind": c.kind, "result": c.result}

        return {
            "component_id": self.component_id,
            "criteria": [crit(c) for c in self.criteria],
            "requirement_results": dict(self.requirement_results),
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "overall": self.overall,
        }


@dataclass
class CriterionObject:
    id: str
    covers: str
    kind: str
    result: str


def _criteria_dicts(results):
    out = []
    for i, r in enumerate(results, start=1):
        out.append(
            {
                "id": "AC-FOO-%03d" % i,
                "covers": "R-FOO-%03d" % i,
                "kind": "compiled",
                "result": r,
            }
        )
    return out


def _report(results, overall, as_objects=False):
    crits = _criteria_dicts(results)
    if as_objects:
        crits = [CriterionObject(**c) for c in crits]
    req_results = {
        "R-FOO-%03d" % i: r for i, r in enumerate(results, start=1)
    }
    return FakeVerificationReport(
        component_id=COMPONENT_ID,
        criteria=crits,
        requirement_results=req_results,
        interface_drift=False,
        mutation_score=None,
        overall=overall,
    )


def _inputs_dataclass(report):
    return provenance_writer.SealedProvenanceInputs(
        component_id=COMPONENT_ID,
        owners=list(OWNERS),
        source_path=SOURCE_PATH,
        source_hash=SOURCE_HASH,
        verifier_version=VERIFIER_VERSION,
        verification_report=report,
    )


def _inputs_dict(report):
    return {
        "component_id": COMPONENT_ID,
        "owners": list(OWNERS),
        "source_path": SOURCE_PATH,
        "source_hash": SOURCE_HASH,
        "verifier_version": VERIFIER_VERSION,
        "verification_report": report,
    }


def _manifest_path(repo_root):
    return Path(repo_root) / "pipeline" / "foo" / ".sealed-provenance.json"


def _all_files(root):
    return sorted(
        p.relative_to(root).as_posix() for p in Path(root).rglob("*") if p.is_file()
    )


def _run(repo_root, inputs):
    repo_root = Path(repo_root)
    repo_root.mkdir(parents=True, exist_ok=True)
    before = datetime.now(timezone.utc).replace(microsecond=0)
    provenance_writer.write_sealed_provenance(COMPONENT_ID, inputs, repo_root)
    after = datetime.now(timezone.utc).replace(microsecond=0)
    path = _manifest_path(repo_root)
    assert path.is_file(), "expected manifest at %s" % path
    text = path.read_text(encoding="utf-8")
    manifest = json.loads(text)
    return manifest, before, after


def _assert_common(manifest, before, after):
    assert isinstance(manifest, dict)
    assert list(manifest.keys()) == EXPECTED_KEYS
    assert manifest["kind"] == "sealed-provenance"
    assert manifest["version"] == 1
    assert type(manifest["version"]) is int
    assert manifest["component_id"] == COMPONENT_ID
    assert manifest["owners"] == OWNERS
    assert manifest["source_path"] == SOURCE_PATH
    assert manifest["source_hash"] == SOURCE_HASH
    assert manifest["verifier_version"] == VERIFIER_VERSION
    written_at = manifest["written_at"]
    assert isinstance(written_at, str)
    assert WRITTEN_AT_RE.match(written_at), written_at
    ts = datetime.strptime(written_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert before <= ts <= after


def _assert_characterization(manifest, overall, passed, total):
    char = manifest["characterization"]
    assert char == {
        "overall": overall,
        "criteria_passed": passed,
        "criteria_total": total,
    }
    assert type(char["criteria_passed"]) is int
    assert type(char["criteria_total"]) is int


def test_all_pass_writes_manifest_only_at_source_path(tmp_path):
    repo_root = tmp_path / "repo"
    report = _report(["pass", "pass", "pass"], "pass")
    manifest, before, after = _run(repo_root, _inputs_dataclass(report))

    _assert_common(manifest, before, after)
    _assert_characterization(manifest, "pass", 3, 3)

    assert not (repo_root / "gen").exists()
    assert not (repo_root / "verification").exists()
    assert _all_files(repo_root) == ["pipeline/foo/.sealed-provenance.json"]


def test_one_failing_criterion_yields_fail_characterization(tmp_path):
    repo_root = tmp_path / "repo"
    report = _report(["pass", "fail", "pass"], "fail")
    manifest, before, after = _run(repo_root, _inputs_dataclass(report))

    _assert_common(manifest, before, after)
    _assert_characterization(manifest, "fail", 2, 3)

    assert not (repo_root / "gen").exists()
    assert not (repo_root / "verification").exists()


def test_plain_dict_inputs_and_attribute_criteria_write_same_manifest(tmp_path):
    ref_root = tmp_path / "ref"
    ref_manifest, before_ref, after_ref = _run(
        ref_root, _inputs_dataclass(_report(["pass", "pass", "pass"], "pass"))
    )
    _assert_common(ref_manifest, before_ref, after_ref)

    alt_root = tmp_path / "alt"
    alt_report = _report(["pass", "pass", "pass"], "pass", as_objects=True)
    alt_manifest, before_alt, after_alt = _run(alt_root, _inputs_dict(alt_report))

    _assert_common(alt_manifest, before_alt, after_alt)
    _assert_characterization(alt_manifest, "pass", 3, 3)

    assert list(alt_manifest.keys()) == list(ref_manifest.keys())
    for key in EXPECTED_KEYS:
        if key == "written_at":
            continue
        assert alt_manifest[key] == ref_manifest[key], key

    assert not (alt_root / "gen").exists()
    assert not (alt_root / "verification").exists()