"""AC-PROVCHECK-013 (covers R-PROVCHECK-008).

Each scenario changes exactly one thing in an otherwise valid and current
sealed provenance manifest, written as JSON, and calls
check_sealed_provenance.
"""

import json
from pathlib import Path

import pytest

import provenance_checker


COMPONENT_ID = "comp-foo"
UNSEALED_ID = "comp-bar"
HEX64 = "0123456789abcdef" * 4

NULL_ON_MISS = (
    "verification_report",
    "owners",
    "source_hash",
    "written_at",
    "license_scan",
    "secret_scan",
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    "sealed: false\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Bar\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Bar triples a number.\n"
)

VERIFIER_STUB = '''\
GATE_VERSION = "verifier-orchestrator@2.0.0"


class VerificationReport:
    def __init__(self, component_id):
        self.component_id = component_id
        self.criteria = []
        self.requirement_results = {}
        self.interface_drift = False
        self.mutation_score = None
        self.overall = "pass"

    def to_dict(self):
        return {
            "component_id": self.component_id,
            "criteria": list(self.criteria),
            "requirement_results": dict(self.requirement_results),
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "overall": self.overall,
        }


def verify(component_id, repo_root, judge=None, test_author=None):
    return VerificationReport(component_id)
'''


def _write_component(repo_root: Path, slug: str, upper: str, fn: str,
                     component_md: str) -> None:
    base = repo_root / "specs" / "components" / slug
    _write(base / "component.md", component_md)
    rid = "R-%s-001" % upper
    acid = "AC-%s-001" % upper
    _write(
        base / "requirements" / (rid + ".md"),
        "# %s\n\n**%s** — `%s(x)` MUST return `2 * x`.\n" % (rid, rid, fn),
    )
    _write(
        base / "acceptance" / (acid + ".md"),
        "# %s\n\nCovers: %s\nKind: generated-test\n\n```gherkin\n"
        "Given x = 2\nWhen %s(x) is called\nThen it returns 4\n```\n"
        % (acid, rid, fn),
    )
    _write(
        base / "interface" / "library.md",
        "# Library\n\n```\n%s(x: int) -> int\n```\n" % fn,
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")


def build_repo(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md",
           "# Glossary\n\n- **Foo** — a test term.\n")
    _write_component(repo_root, "foo", "FOO", "foo", FOO_COMPONENT_MD)
    _write_component(repo_root, "bar", "BAR", "bar", BAR_COMPONENT_MD)
    _write(repo_root / "legacy" / "foo" / "foo.py",
           "def foo(x):\n    return 2 * x\n")
    _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
           VERIFIER_STUB)


def valid_manifest(repo_root: Path) -> dict:
    key = provenance_checker.current_sealed_key(COMPONENT_ID, repo_root)
    assert key is not None, "fixture component comp-foo should be sealed"
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": COMPONENT_ID,
        "owners": list(field(key, "owners")),
        "source_path": field(key, "source_path"),
        "source_hash": field(key, "source_hash"),
        "verifier_version": field(key, "verifier_version"),
        "characterization": {
            "overall": "pass",
            "criteria_passed": 1,
            "criteria_total": 1,
        },
        "written_at": "2026-11-02T00:00:00Z",
    }


def manifest_path(repo_root: Path, manifest: dict) -> Path:
    return repo_root / manifest["source_path"] / ".sealed-provenance.json"


def write_doc(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


def assert_miss(result, reason, sealed=True):
    assert field(result, "reason") == reason, (
        "expected reason %r, got %r" % (reason, field(result, "reason")))
    assert field(result, "sealed") is sealed
    assert field(result, "hit") is False
    for name in NULL_ON_MISS:
        assert field(result, name) is None, "%s should be null on a miss" % name


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    build_repo(root)
    return root


def test_baseline_valid_current_manifest_is_hit(repo):
    manifest = valid_manifest(repo)
    write_doc(manifest_path(repo, manifest), manifest)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, repo)
    assert field(result, "reason") is None
    assert field(result, "hit") is True
    assert field(result, "sealed") is True


NON_OBJECT_DOCS = [
    pytest.param("list", id="list"),
    pytest.param(5, id="number-5"),
    pytest.param("a string", id="string"),
    pytest.param(None, id="null"),
]


@pytest.mark.parametrize("doc", NON_OBJECT_DOCS)
def test_non_object_document_is_manifest_invalid(repo, doc):
    manifest = valid_manifest(repo)
    if doc == "list":
        doc = [manifest]
    write_doc(manifest_path(repo, manifest), doc)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, repo)
    assert_miss(result, "manifest_invalid", sealed=True)


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
    ("source_hash", "sha256:" + HEX64[:63]),
    ("source_hash", "sha256:" + "ABCDEF0123456789" * 4),
    ("source_hash", "sha1:" + HEX64),
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
    [pytest.param(k, v, id="%s=%r" % (k, v)) for k, v in TOP_LEVEL_CHANGES],
)
def test_invalid_top_level_field_is_manifest_invalid(repo, key, value):
    manifest = valid_manifest(repo)
    # The manifest file always lives at the component's real source_path.
    path = manifest_path(repo, manifest)
    manifest[key] = value
    write_doc(path, manifest)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, repo)
    assert_miss(result, "manifest_invalid", sealed=True)


def _char_list(base):
    return [base["overall"], base["criteria_passed"], base["criteria_total"]]


def _char_missing_total(base):
    c = dict(base)
    del c["criteria_total"]
    return c


def _char_extra_key(base):
    c = dict(base)
    c["extra"] = 1
    return c


def _char_set(**changes):
    def make(base):
        c = dict(base)
        c.update(changes)
        return c
    return make


CHARACTERIZATION_CHANGES = [
    pytest.param(_char_list, id="list"),
    pytest.param(_char_missing_total, id="missing-criteria_total"),
    pytest.param(_char_extra_key, id="extra-key"),
    pytest.param(_char_set(overall="ok"), id="overall-ok"),
    pytest.param(_char_set(overall=5), id="overall-5"),
    pytest.param(_char_set(criteria_passed="2"), id="criteria_passed-str"),
    pytest.param(_char_set(criteria_passed=True), id="criteria_passed-true"),
    pytest.param(_char_set(criteria_total=-1), id="criteria_total-neg"),
    pytest.param(_char_set(criteria_passed=3, criteria_total=2),
                 id="passed-gt-total"),
    pytest.param(_char_set(overall="pass", criteria_passed=0, criteria_total=0),
                 id="pass-with-zero-total"),
]


@pytest.mark.parametrize("make", CHARACTERIZATION_CHANGES)
def test_invalid_characterization_is_manifest_invalid(repo, make):
    manifest = valid_manifest(repo)
    manifest["characterization"] = make(manifest["characterization"])
    write_doc(manifest_path(repo, manifest), manifest)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, repo)
    assert_miss(result, "manifest_invalid", sealed=True)


@pytest.mark.parametrize(
    "characterization",
    [
        pytest.param({"overall": "fail", "criteria_passed": 0,
                      "criteria_total": 2}, id="fail-0-of-2"),
        pytest.param({"overall": "fail", "criteria_passed": 0,
                      "criteria_total": 0}, id="fail-0-of-0"),
    ],
)
def test_failing_characterization_is_valid_but_failed(repo, characterization):
    manifest = valid_manifest(repo)
    manifest["characterization"] = characterization
    write_doc(manifest_path(repo, manifest), manifest)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, repo)
    assert_miss(result, "characterization_failed", sealed=True)


def test_unsealed_component_is_not_sealed(repo):
    assert provenance_checker.current_sealed_key(UNSEALED_ID, repo) is None
    result = provenance_checker.check_sealed_provenance(UNSEALED_ID, repo)
    assert_miss(result, "not_sealed", sealed=False)