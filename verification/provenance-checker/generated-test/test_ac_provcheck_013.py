# hotdocs-criterion: sha256:50bd13e816693f6bb9ee5f43f81251640a433dd44f00c2f046b8125d1f6600e8
import json
from pathlib import Path

import pytest

import provenance_checker


COMPONENT_ID = "comp-foo"
UNSEALED_ID = "comp-bar"
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FOO_COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

BAR_COMPONENT_MD = (
    "---\n"
    "id: comp-bar\n"
    "title: Bar\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Bar\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Bar triples a number.\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(root, slug, component_md, req_id, ac_id, fn):
    base = root / "specs" / "components" / slug
    _write(base / "component.md", component_md)
    _write(
        base / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** \u2014 `" + fn + "(x)` MUST return `2 * x`.\n",
    )
    _write(
        base / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + req_id + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When " + fn + "(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        base / "interface" / "library.md",
        "# Library\n\n```\n" + fn + "(x: int) -> int\n```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")


def build_fixture(root):
    _write(root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** \u2014 a test term.\n")
    _write_component(root, "foo", FOO_COMPONENT_MD, "R-FOO-001", "AC-FOO-001", "foo")
    _write_component(root, "bar", BAR_COMPONENT_MD, "R-BAR-001", "AC-BAR-001", "bar")
    _write(root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")
    _write(
        root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "GATE_VERSION = " + repr(VERIFIER_VERSION) + "\n",
    )


def manifest_path(root):
    return root / "legacy" / "foo" / ".sealed-provenance.json"


def valid_manifest(root):
    key = provenance_checker.current_sealed_key(COMPONENT_ID, root)
    assert key is not None
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": COMPONENT_ID,
        "owners": list(field(key, "owners")),
        "source_path": field(key, "source_path"),
        "source_hash": field(key, "source_hash"),
        "verifier_version": field(key, "verifier_version"),
        "characterization": {"overall": "pass", "criteria_passed": 2, "criteria_total": 2},
        "written_at": "2026-11-02T00:00:00Z",
    }


def write_manifest_text(root, text):
    _write(manifest_path(root), text)


def check(root):
    return provenance_checker.check_sealed_provenance(COMPONENT_ID, root)


def assert_miss(result, reason):
    assert field(result, "reason") == reason
    assert field(result, "hit") is False
    assert field(result, "sealed") is True
    for name in ("verification_report", "owners", "source_hash", "written_at"):
        assert field(result, name) is None


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    build_fixture(root)
    return root


def test_valid_current_manifest_is_a_hit(repo):
    m = valid_manifest(repo)
    write_manifest_text(repo, json.dumps(m))
    result = check(repo)
    assert field(result, "reason") is None
    assert field(result, "hit") is True
    assert field(result, "sealed") is True


@pytest.mark.parametrize("doc", [["a", "b"], 5, "sealed-provenance", None],
                         ids=["list", "number", "string", "null"])
def test_non_object_document_is_invalid(repo, doc):
    write_manifest_text(repo, json.dumps(doc))
    assert_miss(check(repo), "manifest_invalid")


TOP_LEVEL_CHANGES = [
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


@pytest.mark.parametrize("key,value", TOP_LEVEL_CHANGES,
                         ids=[k + "-" + repr(v) for k, v in TOP_LEVEL_CHANGES])
def test_invalid_top_level_field(repo, key, value):
    m = valid_manifest(repo)
    m[key] = value
    write_manifest_text(repo, json.dumps(m))
    assert_miss(check(repo), "manifest_invalid")


CHARACTERIZATION_CHANGES = [
    ("list", ["pass", 2, 2]),
    ("missing_total", {"overall": "pass", "criteria_passed": 2}),
    ("extra_key", {"overall": "pass", "criteria_passed": 2, "criteria_total": 2, "extra": 1}),
    ("overall_ok", {"overall": "ok", "criteria_passed": 2, "criteria_total": 2}),
    ("overall_5", {"overall": 5, "criteria_passed": 2, "criteria_total": 2}),
    ("passed_str", {"overall": "pass", "criteria_passed": "2", "criteria_total": 2}),
    ("passed_true", {"overall": "pass", "criteria_passed": True, "criteria_total": 2}),
    ("total_neg", {"overall": "fail", "criteria_passed": 0, "criteria_total": -1}),
    ("passed_gt_total", {"overall": "fail", "criteria_passed": 3, "criteria_total": 2}),
    ("pass_zero", {"overall": "pass", "criteria_passed": 0, "criteria_total": 0}),
]


@pytest.mark.parametrize("value", [c[1] for c in CHARACTERIZATION_CHANGES],
                         ids=[c[0] for c in CHARACTERIZATION_CHANGES])
def test_invalid_characterization(repo, value):
    m = valid_manifest(repo)
    m["characterization"] = value
    write_manifest_text(repo, json.dumps(m))
    assert_miss(check(repo), "manifest_invalid")


@pytest.mark.parametrize("value", [
    {"overall": "fail", "criteria_passed": 0, "criteria_total": 2},
    {"overall": "fail", "criteria_passed": 0, "criteria_total": 0},
], ids=["fail_0_of_2", "fail_0_of_0"])
def test_failed_characterization_is_valid_manifest(repo, value):
    m = valid_manifest(repo)
    m["characterization"] = value
    write_manifest_text(repo, json.dumps(m))
    assert_miss(check(repo), "characterization_failed")


def test_not_sealed_component(repo):
    assert provenance_checker.current_sealed_key(UNSEALED_ID, repo) is None
    result = provenance_checker.check_sealed_provenance(UNSEALED_ID, repo)
    assert field(result, "reason") == "not_sealed"
    assert field(result, "sealed") is False
    assert field(result, "hit") is False
    for name in ("verification_report", "owners", "source_hash", "written_at"):
        assert field(result, name) is None


def test_missing_manifest_is_sealed_miss(repo):
    assert not manifest_path(repo).exists()
    assert_miss(check(repo), "manifest_missing")