# hotdocs-criterion: sha256:51547c676f524efa5ac3043a0c8b41799bc657d4d2281f91ac16145e9c049d41
# Test for AC-VERIFY-011 (covers R-VERIFY-011): requirement_results is the
# per-R-id pass/fail projection, holding only R-id keys and pass/fail values.
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERIA = {
    "AC-FOO-001": ("R-FOO-001", "generated-test"),
    "AC-FOO-002": ("R-FOO-001", "generated-test"),
    "AC-FOO-003": ("R-FOO-002", "generated-test"),
    "AC-FOO-004": ("R-FOO-003", "llm-judge"),
}

PASSING_TEST = "def test_passes():\n    assert 1 + 1 == 2\n"
FAILING_TEST = "def test_fails():\n    assert 1 + 1 == 3\n"


def criterion_gherkin(criterion_id):
    return (
        "Given a widget_input is 3\n"
        "When widget_compute is invoked with [widget_input]\n"
        "Then value equals 3\n"
    )


def acceptance_text(criterion_id, covers, kind):
    return (
        "# " + criterion_id + "\n\n"
        "Covers: " + covers + "\n"
        "Kind: " + kind + "\n\n"
        "```gherkin\n" + criterion_gherkin(criterion_id) + "```\n"
    )


def assembler_source():
    criteria = {cid: covers for cid, (covers, _kind) in CRITERIA.items()}
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    covers = " + repr(criteria) + "[criterion_id]\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': covers,\n"
        "        'criterion_text': 'criterion text for ' + criterion_id,\n"
        "        'requirement_text': 'requirement text for ' + covers,\n"
        "        'interface': 'widget_compute(x) -> int',\n"
        "        'glossary': 'glossary text',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
    )


def probe_source():
    return (
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return _Report()\n"
    )


def bundle_get(bundle, key):
    if isinstance(bundle, dict):
        return bundle[key]
    try:
        return bundle[key]
    except Exception:
        return getattr(bundle, key)


def header_for(bundle):
    payload = {
        k: bundle_get(bundle, k)
        for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-FOO]\n"
        "---\n\n"
        "# Foo\n\n"
        "## Purpose\n\nComputes widgets.\n\n"
        "## Scope\n\n- In scope: widgets.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial.\n",
    )
    for rid in ("R-FOO-001", "R-FOO-002", "R-FOO-003"):
        write(
            comp / "requirements" / (rid + ".md"),
            "# " + rid + "\n\n**" + rid + "** — widget_compute MUST return its input.\n",
        )
    for cid, (covers, kind) in CRITERIA.items():
        write(comp / "acceptance" / (cid + ".md"), acceptance_text(cid, covers, kind))
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nwidget_compute(x) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "P-FOO.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n\n"
        "# Foo capability\n\n## Purpose\n\nWidgets.\n\n## Scope\n\n- Widgets.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** — a thing.\n")
    write(repo_root / "gen" / "foo" / "foo.py", "")
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())


def make_test_author(log_path):
    def test_author(bundle):
        criterion_id = bundle_get(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(criterion_id) + "\n")
        body = FAILING_TEST if criterion_id == "AC-FOO-003" else PASSING_TEST
        content = header_for(bundle) + "\n" + body
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/foo/generated-test/test_"
                + str(criterion_id).lower().replace("-", "_")
                + ".py",
                "content": content,
            },
        }

    return test_author


def test_requirement_results_is_pass_fail_projection(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        "comp-foo", repo_root, judge=None, test_author=make_test_author(log_path)
    )

    # Sanity: the criteria came out as the Given describes.
    results = {field(c, "id"): field(c, "result") for c in field(report, "criteria")}
    assert results.get("AC-FOO-001") == "pass"
    assert results.get("AC-FOO-002") == "pass"
    assert results.get("AC-FOO-003") == "fail"
    assert results.get("AC-FOO-004") == "skipped"

    expected = {"R-FOO-001": "pass", "R-FOO-002": "fail", "R-FOO-003": "fail"}

    requirement_results = field(report, "requirement_results")
    assert isinstance(requirement_results, dict)
    assert requirement_results == expected

    as_dict = report.to_dict()
    assert as_dict["requirement_results"] == expected

    for rr in (requirement_results, as_dict["requirement_results"]):
        for key, value in rr.items():
            assert isinstance(key, str) and key.startswith("R-")
            assert value in ("pass", "fail")
            assert not isinstance(value, (dict, list))
        serialized = json.dumps(rr)
        for forbidden in (
            "Given", "When", "Then", "gherkin", "rationale",
            "expected", "actual", "failure_detail", "message",
            "AC-FOO",
        ):
            assert forbidden not in serialized