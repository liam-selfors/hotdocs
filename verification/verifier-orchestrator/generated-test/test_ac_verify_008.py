# hotdocs-criterion: sha256:7ef14df027c18addfff9056cb3f5c34cdf38423b12ba44e8a0678eeef8e70cb1
# Test for AC-VERIFY-008 (covers R-VERIFY-008): with unchanged gen/<component>/
# and acceptance/ content and a judge that always returns the same result,
# running verify twice yields identical VerificationReports.

import hashlib
import json
from pathlib import Path

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
MODULE = "widget"

INTERFACE_TEXT = "# Library\n\n```\ndouble(x: int) -> int\n```\n"
GLOSSARY_TEXT = "# Glossary\n\n- **Widget** - a thing that doubles numbers.\n"

BUNDLES = {
    "AC-WIDGET-001": {
        "component_id": COMPONENT_ID,
        "criterion_id": "AC-WIDGET-001",
        "covers": "R-WIDGET-001",
        "criterion_text": "Given a widget spec\nWhen it is read\nThen it is clear",
        "requirement_text": "The widget spec MUST be clear.",
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
        "testing": "",
    },
    "AC-WIDGET-002": {
        "component_id": COMPONENT_ID,
        "criterion_id": "AC-WIDGET-002",
        "covers": "R-WIDGET-002",
        "criterion_text": "Given a number 3\nWhen double is invoked\nThen the result is 6",
        "requirement_text": "double(x) MUST return x times two.",
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
        "testing": "",
    },
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generated_test_content():
    return (
        header_for(BUNDLES["AC-WIDGET-002"]) + "\n"
        "import widget\n"
        "\n"
        "\n"
        "def test_double():\n"
        "    assert widget.double(3) == 6\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n\n"
        "## Purpose\n\nDoubles numbers.\n\n"
        "## Scope\n\n- In scope: doubling.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial.\n",
    )
    write(comp / "requirements" / "R-WIDGET-001.md",
          "# R-WIDGET-001\n\n**R-WIDGET-001** - The widget spec MUST be clear.\n")
    write(comp / "requirements" / "R-WIDGET-002.md",
          "# R-WIDGET-002\n\n**R-WIDGET-002** - double(x) MUST return x times two.\n")
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n\n"
        "Covers: R-WIDGET-001\n"
        "Kind: llm-judge\n\n"
        "```gherkin\n"
        "Given a widget spec\n"
        "When it is read\n"
        "Then it is clear\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-002.md",
        "# AC-WIDGET-002\n\n"
        "Covers: R-WIDGET-002\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a number 3\n"
        "When double is invoked\n"
        "Then the result is 6\n"
        "```\n",
    )
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Widget capability\n\n"
        "## Purpose\n\nDoubling.\n\n"
        "## Scope\n\n- Doubling numbers.\n\n"
        "### CS-WIDGET-001\n\n"
        "Covers: P-WIDGET\n\n"
        "```gherkin\n"
        "Given a number is 3\n"
        "When double is invoked with 3\n"
        "Then result equals 6\n"
        "```\n",
    )
    write(repo_root / "specs" / "glossary.md", GLOSSARY_TEXT)

    # The component's own code.
    write(repo_root / "gen" / SLUG / (MODULE + ".py"),
          "def double(x):\n    return x * 2\n")

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "import copy\n"
        "\n"
        "_BUNDLES = " + repr(BUNDLES) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return copy.deepcopy(_BUNDLES[criterion_id])\n",
    )

    # test-probe stand-in: always ok, no findings.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
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
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    return ProbeReport()\n",
    )

    # A current cached generated test for AC-WIDGET-002.
    write(
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_002.py",
        generated_test_content(),
    )


def make_judge(log_path):
    def judge(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("judge\n")
        return {"result": "pass", "rationale": "The spec is clear."}
    return judge


def make_test_author(log_path):
    content = generated_test_content()

    def test_author_fn(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("test_author\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_002.py",
                "content": content,
            },
        }
    return test_author_fn


def snapshot(root):
    out = {}
    for sub in ("gen/" + SLUG, "specs/components/" + SLUG + "/acceptance"):
        base = root / sub
        for p in sorted(base.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def as_dict(report):
    if hasattr(report, "to_dict"):
        return report.to_dict()
    return report


def test_verify_twice_gives_identical_reports(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    log_path = tmp_path / "calls.log"
    judge = make_judge(log_path)
    author = make_test_author(log_path)

    before = snapshot(repo_root)

    report1 = verifier_orchestrator.verify(COMPONENT_ID, repo_root, judge=judge, test_author=author)

    middle = snapshot(repo_root)
    assert middle == before, "gen/<component>/ or acceptance/ content changed during verify"

    report2 = verifier_orchestrator.verify(COMPONENT_ID, repo_root, judge=judge, test_author=author)

    after = snapshot(repo_root)
    assert after == before, "gen/<component>/ or acceptance/ content changed during verify"

    d1 = as_dict(report1)
    d2 = as_dict(report2)

    # Sanity: both reports concern the fixture's criteria.
    ids1 = sorted(field(c, "id") for c in field(report1, "criteria"))
    assert ids1 == ["AC-WIDGET-001", "AC-WIDGET-002"]

    assert json.dumps(d1, sort_keys=True, default=repr) == json.dumps(d2, sort_keys=True, default=repr)
    assert d1 == d2
    assert field(report1, "overall") == field(report2, "overall")
    assert field(report1, "criteria") == field(report2, "criteria")
    assert field(report1, "requirement_results") == field(report2, "requirement_results")
    assert field(report1, "mutation_score") == field(report2, "mutation_score")
    assert field(report1, "mutation_error") == field(report2, "mutation_error")
    assert field(report1, "interface_drift") == field(report2, "interface_drift")
    assert field(report1, "assets") == field(report2, "assets")