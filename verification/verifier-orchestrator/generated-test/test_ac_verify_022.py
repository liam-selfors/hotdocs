# hotdocs-criterion: sha256:da9fa8d72c768a0546678e8568c9911e4b9393d1f31e774233bdf2a0017eceaa
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
CRITERION_ID = "AC-WIDGET-001"
MODULE = "widget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def bundle_values():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": "R-WIDGET-001",
        "criterion_text": "Given a number When double_it is called Then it returns twice the number",
        "requirement_text": "R-WIDGET-001: double_it(x) MUST return x added to itself.",
        "interface": "# Library\n\n```\ndouble_it(x: int) -> int\n```\n",
        "glossary": "# Glossary\n",
        "dependency_interfaces": {},
        "testing": "",
    }


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generated_test_source(bundle):
    return (
        header_for(bundle) + "\n"
        + "import widget\n"
        + "\n"
        + "\n"
        + "def test_double_it_returns_twice():\n"
        + "    assert widget.double_it(3) == 6\n"
    )


def build_fixture(repo_root):
    bundle = bundle_values()

    write(
        repo_root / "specs" / "product" / "P-WIDGET.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n\n"
        "# Widget capability\n\n"
        "## Purpose\n\nDoubles numbers.\n\n"
        "## Scope\n\n- doubling\n\n"
        "### CS-WIDGET-001\n\n"
        "Covers: P-WIDGET\n\n"
        "```gherkin\n"
        "Given a number is 3\n"
        "When double_it is invoked with 3\n"
        "Then result equals 6\n"
        "```\n",
    )

    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n\n"
        "# Widget\n\n"
        "## Purpose\n\nDoubles a number.\n\n"
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
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — `double_it(x)` MUST return x added to itself.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble_it(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a number 3\n"
        "When double_it is called with it\n"
        "Then it returns 6\n"
        "```\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    # The component's code: one function with one mutation site (x + x).
    code_dir = repo_root / "gen" / SLUG
    write(
        code_dir / (MODULE + ".py"),
        "def double_it(x):\n"
        "    return x + x\n",
    )

    # A conftest that would pin the unmutated module if it were ever loaded.
    write(
        repo_root / "verification" / SLUG / "conftest.py",
        "import sys\n"
        "sys.path.insert(0, " + repr(str(code_dir.resolve())) + ")\n"
        "import " + MODULE + "\n",
    )

    # A current cached generated test.
    write(
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py",
        generated_test_source(bundle),
    )

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(bundle) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )

    # test-probe stand-in: always ok.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return dict(ok=self.ok, findings=list(self.findings),\n"
        "                    tests_run=self.tests_run, tests_reached=self.tests_reached)\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )

    return bundle


def test_conftest_does_not_shield_mutants(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bundle = build_fixture(repo_root)
    content = generated_test_source(bundle)
    log = tmp_path / "author_calls.log"

    def author(b):
        with open(log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": content,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    detail = report.to_dict() if hasattr(report, "to_dict") else report
    criteria = field(report, "criteria")
    entry = next(c for c in criteria if field(c, "id") == CRITERION_ID)
    assert field(entry, "result") == "pass", detail
    assert field(report, "mutation_score") == 1.0, detail