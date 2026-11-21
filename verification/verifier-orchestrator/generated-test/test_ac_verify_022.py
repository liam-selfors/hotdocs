# hotdocs-criterion: sha256:d12967aabdc7203ed04ae5f43fb1b147a5466e8153d59b7ea9db0231af542daa
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


SLUG = "widget-math"
COMPONENT_ID = "comp-widget-math"
MODULE = "widget_math"
CRITERION_ID = "AC-WIDGET-001"
COVERS = "R-WIDGET-001"

CRITERION_TEXT = (
    "Given a number a is 2\n"
    "When add_two is invoked with [2, 3]\n"
    "Then result equals 5\n"
)
REQUIREMENT_TEXT = "**R-WIDGET-001** - add_two(a, b) MUST return a plus b."
INTERFACE_TEXT = "# Library\n\n```\nadd_two(a: int, b: int) -> int\n```\n"
GLOSSARY_TEXT = "# Glossary\n"
TESTING_TEXT = ""


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def bundle_dict():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": COVERS,
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
        "testing": TESTING_TEXT,
    }


def header_for(bundle):
    keys = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    payload = json.dumps(
        {k: bundle[k] for k in keys},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generated_test_source(bundle):
    return (
        header_for(bundle) + "\n"
        + "import " + MODULE + "\n"
        + "\n"
        + "\n"
        + "def test_add_two_sums():\n"
        + "    assert " + MODULE + ".add_two(2, 3) == 5\n"
    )


def build_fixture(repo_root):
    # Product capability so the unsealed component's realizes resolves.
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Adds numbers.\n",
    )
    write(repo_root / "specs" / "glossary.md", GLOSSARY_TEXT)

    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget math\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget math\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Adds two numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: addition.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial.\n",
    )
    write(comp / "requirements" / (COVERS + ".md"), REQUIREMENT_TEXT + "\n")
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + COVERS + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        + CRITERION_TEXT
        + "```\n",
    )

    # The component's code: one function with exactly one mutation site.
    gen_dir = repo_root / "gen" / SLUG
    write(
        gen_dir / (MODULE + ".py"),
        "def add_two(a, b):\n"
        "    return a + b\n",
    )

    # conftest that pins the unmutated repo copy first on sys.path.
    write(
        repo_root / "verification" / SLUG / "conftest.py",
        "import sys\n"
        "sys.path.insert(0, " + repr(str(gen_dir.resolve())) + ")\n"
        "import " + MODULE + "\n",
    )

    # spec-bundle-assembler stand-in.
    bundle = bundle_dict()
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(COVERS) + ",\n"
        "        'criterion_text': " + repr(CRITERION_TEXT) + ",\n"
        "        'requirement_text': " + repr(REQUIREMENT_TEXT) + ",\n"
        "        'interface': " + repr(INTERFACE_TEXT) + ",\n"
        "        'glossary': " + repr(GLOSSARY_TEXT) + ",\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': " + repr(TESTING_TEXT) + ",\n"
        "    }\n",
    )

    # test-probe stand-in: always ok.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "class _ProbeReport:\n"
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
        "    return _ProbeReport()\n",
    )

    # The one generated test, cached with a current header.
    source = generated_test_source(bundle)
    write(
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py",
        source,
    )
    return source


def test_ac_verify_022(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    source = build_fixture(repo_root)

    log = tmp_path / "author.log"

    def author(bundle):
        with open(log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/" + SLUG + "/generated-test/test_ac_widget_001.py",
                "content": source,
            },
        }

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    details = report.to_dict() if hasattr(report, "to_dict") else report
    assert field(report, "mutation_score") == 1.0, repr(details)