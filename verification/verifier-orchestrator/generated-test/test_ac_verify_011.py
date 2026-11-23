# hotdocs-criterion: sha256:56fb9097f281b756105334170aacbac73d1022379b5b8b37885b564515a3a871
import hashlib
import json
import re
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COVERS = {
    "AC-FOO-001": "R-FOO-001",
    "AC-FOO-002": "R-FOO-001",
    "AC-FOO-003": "R-FOO-002",
    "AC-FOO-004": "R-FOO-003",
}

KINDS = {
    "AC-FOO-001": "generated-test",
    "AC-FOO-002": "generated-test",
    "AC-FOO-003": "generated-test",
    "AC-FOO-004": "llm-judge",
}

GHERKIN_MARKER = "Given a widget is 1"


def build_fixture(repo_root):
    repo_root = Path(repo_root)

    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** — a thing.\n")

    write(
        repo_root / "specs" / "product" / "foo.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n\n"
        "# Foo capability\n\n"
        "## Purpose\n\nProvide foo.\n\n"
        "## Scope\n\n- In scope: foo.\n\n"
        "### CS-FOO-001\n\n"
        "Covers: P-FOO\n\n"
        "```gherkin\n"
        "Given a widget is 1\n"
        "When compute_total is invoked with [widget]\n"
        "Then result equals 1\n"
        "```\n",
    )

    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-FOO]\n"
        "---\n\n"
        "# Foo\n\n"
        "## Purpose\n\nComputes totals.\n\n"
        "## Scope\n\n- In scope: totals.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n\n"
        "## Change log\n\n- Initial.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `compute_total` MUST return its input.\n",
    )
    write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — `compute_total` MUST reject negatives.\n",
    )
    write(
        comp / "requirements" / "R-FOO-003.md",
        "# R-FOO-003\n\n**R-FOO-003** — The interface MUST be clear.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ncompute_total(x) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    for cid in sorted(COVERS):
        write(
            comp / "acceptance" / (cid + ".md"),
            "# " + cid + "\n\n"
            "Covers: " + COVERS[cid] + "\n"
            "Kind: " + KINDS[cid] + "\n\n"
            "```gherkin\n"
            + GHERKIN_MARKER + "\n"
            "When compute_total is invoked with [widget]\n"
            "Then result equals 1\n"
            "```\n",
        )

    # The component's code: empty module, so there are no mutation sites.
    write(repo_root / "gen" / "foo" / "foo.py", "")

    # spec-bundle-assembler stand-in.
    assembler_src = (
        "COVERS = " + repr(COVERS) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': COVERS.get(criterion_id, ''),\n"
        "        'criterion_text': 'criterion ' + criterion_id,\n"
        "        'requirement_text': 'requirement text',\n"
        "        'interface': 'compute_total(x) -> int',\n"
        "        'glossary': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_src,
    )

    # test-probe stand-in: always ok.
    probe_src = (
        "class ProbeReport:\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    return ProbeReport()\n"
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_src)


def bundle_get(bundle, name):
    if isinstance(bundle, dict):
        return bundle[name]
    try:
        return bundle[name]
    except Exception:
        return getattr(bundle, name)


def header_for(bundle):
    payload = {
        k: bundle_get(bundle, k)
        for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_test_author(log_path):
    def test_author_stand_in(bundle):
        criterion_id = bundle_get(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(criterion_id) + "\n")
        if criterion_id == "AC-FOO-003":
            body = "\n\ndef test_bad():\n    assert 1 == 2\n"
        else:
            body = "\n\ndef test_ok():\n    assert 1 == 1\n"
        name = "test_" + str(criterion_id).lower().replace("-", "_") + ".py"
        return {
            "component_id": "comp-foo",
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/foo/generated-test/" + name,
                "content": header_for(bundle) + body,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author_stand_in


def test_requirement_results_projection_only_rids_and_verdicts(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        "comp-foo", repo_root, judge=None, test_author=make_test_author(log_path)
    )

    # Sanity check the Given: per-criterion outcomes.
    criteria = field(report, "criteria")
    results = {field(c, "id"): field(c, "result") for c in criteria}
    assert results.get("AC-FOO-001") == "pass", results
    assert results.get("AC-FOO-002") == "pass", results
    assert results.get("AC-FOO-003") == "fail", results
    assert results.get("AC-FOO-004") == "skipped", results

    rr = field(report, "requirement_results")
    assert isinstance(rr, dict)
    assert rr == {"R-FOO-001": "pass", "R-FOO-002": "fail", "R-FOO-003": "fail"}

    for key, value in rr.items():
        assert isinstance(key, str) and re.fullmatch(r"R-[A-Z0-9]+-\d+", key), key
        assert value in ("pass", "fail"), value
        assert not isinstance(value, (dict, list))

    serialized = json.dumps(rr)
    for forbidden in ("Given", "When ", "Then ", GHERKIN_MARKER, "rationale",
                      "expected", "actual", "failure_detail", "criterion "):
        assert forbidden not in serialized, forbidden

    # The JSON form carries the same projection.
    as_dict = report.to_dict()
    assert as_dict["requirement_results"] == {
        "R-FOO-001": "pass",
        "R-FOO-002": "fail",
        "R-FOO-003": "fail",
    }