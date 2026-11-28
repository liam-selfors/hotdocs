# hotdocs-criterion: sha256:66381a3d72c824f6f3f5d930e160f6326c1c6579639d3407dd2983ac8b88c2cd
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


VALID_OWNERS = ["pipeline-team", "alice"]
WRITTEN_AT = "2026-11-02T00:00:00Z"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(root, sealed=True):
    lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [pipeline-team, alice]",
        "depends_on: []",
    ]
    if sealed:
        lines.append("sealed: true")
        lines.append("source_path: pipeline/foo/")
    lines.append("---")
    lines.append("")
    lines.append("# Foo")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("A fixture component.")
    lines.append("")
    write(root / "specs" / "components" / "foo" / "component.md", "\n".join(lines))

    write(
        root / "pipeline" / "foo" / "foo.py",
        "def answer():\n    return 42\n",
    )

    vo_src = (
        "GATE_VERSION = " + repr("verifier-orchestrator@2.0.0") + "\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [],\n"
        "        'requirement_results': {},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': None,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'drivers': [],\n"
        "        'overall': 'pass',\n"
        "    }\n"
    )
    write(root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", vo_src)

    pk = "sha256:" + "a" * 64
    py_src = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr({
            "ok": True,
            "reason": "",
            "versions": {"python": "3.12.4", "packages": pk},
            "lockfile_sha256": None,
            "interpreter": "/fake/python",
        }) + "\n"
    )
    write(root / "gen" / "kind-python" / "kind_python.py", py_src)


def valid_manifest(source_hash):
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-foo",
        "owners": list(VALID_OWNERS),
        "source_path": "pipeline/foo/",
        "source_hash": source_hash,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "characterization": {"overall": "pass", "criteria_passed": 2, "criteria_total": 2},
        "written_at": WRITTEN_AT,
    }


def manifest_path(root):
    return root / "pipeline" / "foo" / ".sealed-provenance.json"


def snapshot(root):
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if "__pycache__" in rel.parts:
            continue
        if p.is_file():
            out[rel.as_posix()] = ("file", p.read_bytes())
        elif p.is_dir():
            out[rel.as_posix()] = ("dir", None)
    return out


def _set(key, value):
    def mutate(m):
        m[key] = value
        return json.dumps(m)
    return mutate


def _extra_key(m):
    m["extra"] = "x"
    return json.dumps(m)


def _lacks_key(m):
    del m["written_at"]
    return json.dumps(m)


def _owner_alice(m):
    m["owners"] = ["pipeline-team", "Alice"]
    return json.dumps(m)


def _pass_partial(m):
    m["characterization"] = {"overall": "pass", "criteria_passed": 1, "criteria_total": 2}
    return json.dumps(m)


def _different_hash(m):
    m["source_hash"] = "sha256:" + hashlib.sha256(b"different content entirely\n").hexdigest()
    return json.dumps(m)


def _char_fail(m):
    m["characterization"] = {"overall": "fail", "criteria_passed": 1, "criteria_total": 2}
    return json.dumps(m)


CASES = [
    ("missing", True, lambda m: None, "manifest_missing"),
    ("not_json", True, lambda m: "{this is not json", "manifest_invalid"),
    ("extra_key", True, _extra_key, "manifest_invalid"),
    ("lacks_key", True, _lacks_key, "manifest_invalid"),
    ("version_true", True, _set("version", True), "manifest_invalid"),
    ("short_hash", True, _set("source_hash", "sha256:abc"), "manifest_invalid"),
    ("owner_Alice", True, _owner_alice, "manifest_invalid"),
    ("pass_1_of_2", True, _pass_partial, "manifest_invalid"),
    ("component_bar", True, _set("component_id", "comp-bar"), "component_mismatch"),
    ("source_path_other", True, _set("source_path", "pipeline/other/"), "component_mismatch"),
    ("source_changed", True, _different_hash, "source_changed"),
    ("owners_subset", True, _set("owners", ["pipeline-team"]), "owners_changed"),
    ("owners_reordered", True, _set("owners", ["alice", "pipeline-team"]), "owners_changed"),
    ("verifier_changed", True, _set("verifier_version", "verifier-orchestrator@1.0.0"), "verifier_changed"),
    ("char_failed", True, _char_fail, "characterization_failed"),
    ("not_sealed", False, lambda m: json.dumps(m), "not_sealed"),
]


def _prepare(root, sealed, mutate):
    build_repo(root, sealed=sealed)
    if sealed:
        key = provenance_checker.current_sealed_key("comp-foo", root)
        assert key is not None
        source_hash = field(key, "source_hash")
    else:
        source_hash = "sha256:" + "0" * 64
    text = mutate(valid_manifest(source_hash))
    if text is not None:
        write(manifest_path(root), text)
    return source_hash


def test_valid_current_manifest_hits_and_is_read_only(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    source_hash = _prepare(root, True, lambda m: json.dumps(m))

    before = snapshot(root)
    result = provenance_checker.check_sealed_provenance("comp-foo", root)
    after = snapshot(root)

    assert field(result, "hit") is True
    assert field(result, "reason") is None
    assert field(result, "sealed") is True
    assert field(result, "verification_report") == {"overall": "pass"}
    assert field(result, "owners") == VALID_OWNERS
    assert field(result, "written_at") == WRITTEN_AT
    assert field(result, "source_hash") == source_hash
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    assert before == after


@pytest.mark.parametrize(
    "name,sealed,mutate,expected_reason",
    CASES,
    ids=[c[0] for c in CASES],
)
def test_miss_reasons_and_read_only(tmp_path, name, sealed, mutate, expected_reason):
    root = tmp_path / "repo"
    root.mkdir()
    _prepare(root, sealed, mutate)

    before = snapshot(root)
    result = provenance_checker.check_sealed_provenance("comp-foo", root)
    after = snapshot(root)

    assert field(result, "reason") == expected_reason
    assert field(result, "hit") is False
    if expected_reason == "not_sealed":
        assert field(result, "sealed") is False
    else:
        assert field(result, "sealed") is True

    # On any non-null reason, these are null (R-PROVCHECK-008).
    assert field(result, "verification_report") is None
    assert field(result, "owners") is None
    assert field(result, "source_hash") is None
    assert field(result, "written_at") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None

    assert before == after