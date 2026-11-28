# hotdocs-criterion: sha256:13c1a36761b4b77b0b0239119d1937b59d00b09b4a2705e7105bce89989652fc
import copy
import json
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PYTHON_ADAPTER_SRC = (
    "KIND = " + repr("python") + "\n"
    "\n"
    "def guidance():\n"
    "    return {" + repr("generator") + ": " + repr("") + ", "
    + repr("test_author") + ": " + repr("") + "}\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("") + ", "
    + repr("versions") + ": {" + repr("python") + ": " + repr("3.12.4") + ", "
    + repr("packages") + ": " + repr("sha256:" + "a" * 64) + "}, "
    + repr("lockfile_sha256") + ": None, "
    + repr("interpreter") + ": " + repr("/fake/python") + "}\n"
)

VERIFIER_SRC = (
    "GATE_VERSION = " + repr("verifier-orchestrator@2.0.0") + "\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    return {\n"
    "        " + repr("component_id") + ": component_id,\n"
    "        " + repr("criteria") + ": [],\n"
    "        " + repr("requirement_results") + ": {},\n"
    "        " + repr("interface_drift") + ": False,\n"
    "        " + repr("mutation_score") + ": None,\n"
    "        " + repr("mutation_error") + ": None,\n"
    "        " + repr("assets") + ": [],\n"
    "        " + repr("drivers") + ": [],\n"
    "        " + repr("overall") + ": " + repr("pass") + ",\n"
    "    }\n"
)


def make_repo(root, sealed=True):
    root.mkdir(parents=True, exist_ok=True)
    kp = root / "gen" / "kind-python"
    kp.mkdir(parents=True)
    (kp / "kind_python.py").write_text(PYTHON_ADAPTER_SRC)
    vo = root / "gen" / "verifier-orchestrator"
    vo.mkdir(parents=True)
    (vo / "verifier_orchestrator.py").write_text(VERIFIER_SRC)

    comp = root / "specs" / "components" / "foo"
    comp.mkdir(parents=True)
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
    (comp / "component.md").write_text("\n".join(lines))

    src = root / "pipeline" / "foo"
    src.mkdir(parents=True)
    (src / "foo.py").write_text("def foo():\n    return 1\n")
    return root


def valid_manifest(source_hash):
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-foo",
        "owners": ["pipeline-team", "alice"],
        "source_path": "pipeline/foo/",
        "source_hash": source_hash,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "characterization": {"overall": "pass", "criteria_passed": 2, "criteria_total": 2},
        "written_at": "2026-11-02T00:00:00Z",
    }


def manifest_path(root):
    return root / "pipeline" / "foo" / ".sealed-provenance.json"


def write_manifest_text(root, text):
    manifest_path(root).write_text(text)


@pytest.fixture
def sealed_repo(tmp_path):
    root = make_repo(tmp_path / "repo", sealed=True)
    key = provenance_checker.current_sealed_key("comp-foo", root)
    assert key is not None
    source_hash = field(key, "source_hash")
    return root, source_hash


def check(root):
    return provenance_checker.check_sealed_provenance("comp-foo", root)


def assert_miss(result, reason):
    assert field(result, "reason") == reason
    assert field(result, "hit") is False
    assert field(result, "sealed") is True
    for name in ("verification_report", "owners", "source_hash", "written_at"):
        assert field(result, name) is None


def test_valid_current_manifest_hits(sealed_repo):
    root, source_hash = sealed_repo
    write_manifest_text(root, json.dumps(valid_manifest(source_hash)))
    result = check(root)
    assert field(result, "reason") is None
    assert field(result, "hit") is True
    assert field(result, "sealed") is True


@pytest.mark.parametrize(
    "doc",
    [[], [1, 2], 5, "sealed-provenance", None],
    ids=["empty-list", "list", "number", "string", "null"],
)
def test_non_object_document_is_invalid(sealed_repo, doc):
    root, _ = sealed_repo
    write_manifest_text(root, json.dumps(doc))
    assert_miss(check(root), "manifest_invalid")


TOP_LEVEL_CASES = [
    ("kind", "sealed"),
    ("kind", 5),
    ("version", 2),
    ("version", "1"),
    ("version", 1.0),
    ("component_id", 5),
    ("component_id", "Comp-foo"),
    ("component_id", "foo"),
    ("owners", "pipeline-team"),
    ("owners", []),
    ("owners", [5]),
    ("owners", ["pipeline-team", ""]),
    ("owners", ["Pipeline"]),
    ("source_path", 5),
    ("source_path", "../x/"),
    ("source_path", "gen/foo/"),
    ("source_path", "/abs/"),
    ("source_path", "a b/"),
    ("source_hash", 5),
    ("source_hash", "sha256:" + "a" * 63),
    ("source_hash", "sha256:" + "A" * 64),
    ("source_hash", "sha1:" + "a" * 64),
    ("verifier_version", 5),
    ("verifier_version", "verifier-orchestrator@2"),
    ("verifier_version", "other@2.0.0"),
    ("written_at", 5),
    ("written_at", "2026-11-02"),
    ("written_at", "2026-11-02 00:00:00Z"),
    ("written_at", "2026-11-02T00:00:00"),
]


@pytest.mark.parametrize(
    "key,value",
    TOP_LEVEL_CASES,
    ids=[k + "=" + repr(v) for k, v in TOP_LEVEL_CASES],
)
def test_top_level_field_invalid(sealed_repo, key, value):
    root, source_hash = sealed_repo
    m = valid_manifest(source_hash)
    m[key] = copy.deepcopy(value)
    write_manifest_text(root, json.dumps(m))
    assert_miss(check(root), "manifest_invalid")


def _char_cases():
    base = {"overall": "pass", "criteria_passed": 2, "criteria_total": 2}
    cases = []
    cases.append(("list", [base["overall"], 2, 2]))
    c = dict(base)
    del c["criteria_total"]
    cases.append(("missing-total", c))
    c = dict(base)
    c["extra"] = 1
    cases.append(("extra-key", c))
    c = dict(base)
    c["overall"] = "ok"
    cases.append(("overall-ok", c))
    c = dict(base)
    c["overall"] = 5
    cases.append(("overall-5", c))
    c = dict(base)
    c["criteria_passed"] = "2"
    cases.append(("passed-string", c))
    c = dict(base)
    c["criteria_passed"] = True
    cases.append(("passed-true", c))
    c = dict(base)
    c["criteria_total"] = -1
    cases.append(("total-negative", c))
    c = dict(base)
    c["criteria_passed"] = 3
    c["criteria_total"] = 2
    cases.append(("passed-over-total", c))
    cases.append(("pass-zero", {"overall": "pass", "criteria_passed": 0, "criteria_total": 0}))
    return cases


CHAR_CASES = _char_cases()


@pytest.mark.parametrize(
    "characterization",
    [c for _, c in CHAR_CASES],
    ids=[n for n, _ in CHAR_CASES],
)
def test_characterization_invalid(sealed_repo, characterization):
    root, source_hash = sealed_repo
    m = valid_manifest(source_hash)
    m["characterization"] = copy.deepcopy(characterization)
    write_manifest_text(root, json.dumps(m))
    assert_miss(check(root), "manifest_invalid")


@pytest.mark.parametrize(
    "characterization",
    [
        {"overall": "fail", "criteria_passed": 0, "criteria_total": 2},
        {"overall": "fail", "criteria_passed": 0, "criteria_total": 0},
    ],
    ids=["fail-0-of-2", "fail-0-of-0"],
)
def test_failed_characterization_is_valid_but_failed(sealed_repo, characterization):
    root, source_hash = sealed_repo
    m = valid_manifest(source_hash)
    m["characterization"] = copy.deepcopy(characterization)
    write_manifest_text(root, json.dumps(m))
    assert_miss(check(root), "characterization_failed")


def test_missing_manifest_is_sealed(sealed_repo):
    root, _ = sealed_repo
    assert not manifest_path(root).exists()
    assert_miss(check(root), "manifest_missing")


def test_not_sealed_component(tmp_path):
    root = make_repo(tmp_path / "repo", sealed=False)
    assert provenance_checker.current_sealed_key("comp-foo", root) is None
    result = check(root)
    assert field(result, "reason") == "not_sealed"
    assert field(result, "sealed") is False
    assert field(result, "hit") is False
    for name in ("verification_report", "owners", "source_hash", "written_at"):
        assert field(result, name) is None