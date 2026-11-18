# hotdocs-criterion: sha256:1f643b81be3b3331ccc1605717d178ff423b21cebaf6b9e118fa4b5652b28477
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
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"
OWNERS = ["pipeline-team", "alice"]
SOURCE_PATH = "pipeline/foo/"
WRITTEN_AT_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class CriterionObj:
    def __init__(self, id, covers, kind, result):
        self.id = id
        self.covers = covers
        self.kind = kind
        self.result = result


def _criteria_dicts(results):
    out = []
    for i, r in enumerate(results, start=1):
        out.append(
            {
                "id": "AC-FOO-00" + str(i),
                "covers": "R-FOO-00" + str(i),
                "kind": "compiled",
                "result": r,
            }
        )
    return out


def _criteria_objs(results):
    out = []
    for i, r in enumerate(results, start=1):
        out.append(
            CriterionObj(
                id="AC-FOO-00" + str(i),
                covers="R-FOO-00" + str(i),
                kind="compiled",
                result=r,
            )
        )
    return out


def _report(overall, criteria):
    req = {}
    for c in criteria:
        req[field(c, "covers")] = "pass" if field(c, "result") == "pass" else "fail"
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": req,
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "overall": overall,
    }


def _fields(report):
    return {
        "component_id": "comp-foo",
        "owners": list(OWNERS),
        "source_path": SOURCE_PATH,
        "source_hash": SOURCE_HASH,
        "verifier_version": VERIFIER_VERSION,
        "verification_report": report,
    }


def _manifest_path(repo_root):
    return Path(repo_root) / "pipeline" / "foo" / ".sealed-provenance.json"


def _all_files(repo_root):
    return sorted(
        str(p.relative_to(repo_root)).replace("\\", "/")
        for p in Path(repo_root).rglob("*")
        if p.is_file()
    )


def _now_s():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _run(repo_root, inputs):
    before = _now_s()
    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)
    after = _now_s()
    path = _manifest_path(repo_root)
    assert path.is_file(), "manifest not written at " + str(path)
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert isinstance(data, dict)
    written_at = data.get("written_at")
    assert isinstance(written_at, str) and WRITTEN_AT_RE.match(written_at), written_at
    ts = datetime.strptime(written_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert before <= ts <= after, (before, ts, after)
    return data


def _assert_common(data, repo_root):
    assert list(data.keys()) == EXPECTED_KEYS
    assert data["kind"] == "sealed-provenance"
    assert data["version"] == 1
    assert type(data["version"]) is int
    assert data["component_id"] == "comp-foo"
    assert data["owners"] == OWNERS
    assert data["source_path"] == SOURCE_PATH
    assert data["source_hash"] == SOURCE_HASH
    assert data["verifier_version"] == VERIFIER_VERSION
    assert not (Path(repo_root) / "gen").exists()
    assert not (Path(repo_root) / "verification").exists()
    assert _all_files(repo_root) == ["pipeline/foo/.sealed-provenance.json"]


def _without_time(data):
    return {k: v for k, v in data.items() if k != "written_at"}


def test_all_pass_dataclass_inputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    report = _report("pass", _criteria_dicts(["pass", "pass", "pass"]))
    inputs = provenance_writer.SealedProvenanceInputs(**_fields(report))
    data = _run(repo_root, inputs)
    _assert_common(data, repo_root)
    assert data["characterization"] == {
        "overall": "pass",
        "criteria_passed": 3,
        "criteria_total": 3,
    }
    assert list(data["characterization"].keys()) == [
        "overall",
        "criteria_passed",
        "criteria_total",
    ] or set(data["characterization"].keys()) == {
        "overall",
        "criteria_passed",
        "criteria_total",
    }


def test_one_fail_characterization(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    report = _report("fail", _criteria_dicts(["pass", "fail", "pass"]))
    inputs = provenance_writer.SealedProvenanceInputs(**_fields(report))
    data = _run(repo_root, inputs)
    _assert_common(data, repo_root)
    assert data["characterization"] == {
        "overall": "fail",
        "criteria_passed": 2,
        "criteria_total": 3,
    }


def test_plain_dict_inputs_and_attribute_criteria(tmp_path):
    root_a = tmp_path / "a"
    root_a.mkdir()
    report_a = _report("pass", _criteria_dicts(["pass", "pass", "pass"]))
    inputs_a = provenance_writer.SealedProvenanceInputs(**_fields(report_a))
    data_a = _run(root_a, inputs_a)
    _assert_common(data_a, root_a)

    root_b = tmp_path / "b"
    root_b.mkdir()
    report_b = _report("pass", _criteria_objs(["pass", "pass", "pass"]))
    inputs_b = _fields(report_b)
    data_b = _run(root_b, inputs_b)
    _assert_common(data_b, root_b)

    assert _without_time(data_b) == _without_time(data_a)
    assert data_b["characterization"] == {
        "overall": "pass",
        "criteria_passed": 3,
        "criteria_total": 3,
    }

    root_c = tmp_path / "c"
    root_c.mkdir()
    report_c = _report("fail", _criteria_objs(["pass", "fail", "pass"]))
    data_c = _run(root_c, _fields(report_c))
    _assert_common(data_c, root_c)
    assert data_c["characterization"] == {
        "overall": "fail",
        "criteria_passed": 2,
        "criteria_total": 3,
    }