# hotdocs-criterion: sha256:6f927250fe3270a5ce9a1d394c264a03c4445d0ced93f8e79796b0caa200c880
# AC-VERIFY-022 (covers R-VERIFY-014): a component whose
# verification/<slug>/conftest.py forces the committed gen/<slug>/ onto
# sys.path still gets a mutation score of 1.0, because mutation runs use
# --noconftest and run against the sandbox copy.

import hashlib
import json
from pathlib import Path

import verifier_orchestrator


SLUG = "mutfix"
MODULE = "mutfix"
COMPONENT_ID = "comp-" + SLUG
CRITERION_ID = "AC-MUTFIX-001"
REQUIREMENT_ID = "R-MUTFIX-001"
CAPABILITY_ID = "P-MUTFIX"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERION_TEXT = (
    "Given a number is 2\n"
    "When add_one is invoked with 2\n"
    "Then the result is 3\n"
)
REQUIREMENT_TEXT = "**R-MUTFIX-001** - add_one(x) MUST return x + 1."
INTERFACE_TEXT = "# Library\n\n```\nadd_one(x: int) -> int\n```\n"
GLOSSARY_TEXT = "# Glossary\n"
TESTING_TEXT = ""


def bundle_dict():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
        "testing": TESTING_TEXT,
    }


def header_line(bundle):
    keyed = {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")}
    payload = json.dumps(keyed, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generated_test_source(bundle):
    return (
        header_line(bundle) + "\n"
        + "import " + MODULE + "\n"
        + "\n"
        + "\n"
        + "def test_add_one():\n"
        + "    assert " + MODULE + ".add_one(2) == 3\n"
        + "    assert " + MODULE + ".add_one(-5) == -4\n"
    )


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        + "id: " + COMPONENT_ID + "\n"
        + "title: Mutation fixture\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "realizes: [" + CAPABILITY_ID + "]\n"
        + "---\n\n"
        + "# Mutation fixture\n\n"
        + "## Purpose\n\nAdds one to a number.\n\n"
        + "## Scope\n\n- In scope: add_one.\n\n"
        + "## Definitions\n\nNone.\n\n"
        + "## Behavior\n\nSee `requirements/`.\n\n"
        + "## Interfaces\n\nSee `interface/`.\n\n"
        + "## Data\n\nSee `interface/data/`.\n\n"
        + "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        + "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        + "## Open questions\n\n"
        + "## Change log\n\n- Initial.\n",
    )
    write(comp / "requirements" / (REQUIREMENT_ID + ".md"), REQUIREMENT_TEXT + "\n")
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n\n"
        + "Covers: " + REQUIREMENT_ID + "\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\n" + CRITERION_TEXT + "```\n",
    )
    write(
        repo_root / "specs" / "product" / "mutfix-capability.md",
        "---\n"
        + "id: " + CAPABILITY_ID + "\n"
        + "title: Mutation fixture capability\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n\n"
        + "# Mutation fixture capability\n\n"
        + "## Purpose\n\nAdd one.\n\n"
        + "## Scope\n\n- add_one.\n\n"
        + "### CS-MUTFIX-001\n\nCovers: " + CAPABILITY_ID + "\n\n"
        + "```gherkin\nGiven a n is 1\nWhen add_one is invoked with 1\nThen result equals 2\n```\n",
    )
    write(repo_root / "specs" / "glossary.md", GLOSSARY_TEXT)

    # The component's code: one function with exactly one mutation site
    # (binary + -> -); numeric constants are never mutated.
    gen_dir = repo_root / "gen" / SLUG
    write(gen_dir / (MODULE + ".py"), "def add_one(x):\n    return x + 1\n")

    # The conftest that, if it were ever loaded by a mutation run, would put
    # the committed (unmutated) code first on sys.path and import it.
    write(
        repo_root / "verification" / SLUG / "conftest.py",
        "import sys\n"
        + "sys.path.insert(0, " + repr(str(gen_dir.resolve())) + ")\n"
        + "import " + MODULE + "\n",
    )

    bundle = bundle_dict()
    source = generated_test_source(bundle)
    # A current cached generated test, sitting under the conftest.
    write(
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_mutfix_001.py",
        source,
    )

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(bundle) + "\n"
        + "\n"
        + "\n"
        + "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        + "    b = dict(BUNDLE)\n"
        + "    b['component_id'] = component_id\n"
        + "    b['criterion_id'] = criterion_id\n"
        + "    return b\n",
    )

    # test-probe stand-in: always ok, no findings.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        + "\n"
        + "\n"
        + "class _Report:\n"
        + "    def __init__(self):\n"
        + "        self.ok = True\n"
        + "        self.findings = []\n"
        + "        self.tests_run = 1\n"
        + "        self.tests_reached = 1\n"
        + "\n"
        + "    def to_dict(self):\n"
        + "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        + "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        + "\n"
        + "\n"
        + "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        + "          interpreter=None, assets=None):\n"
        + "    return _Report()\n",
    )
    return source


def make_test_author(log_path, source):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/" + SLUG + "/generated-test/test_ac_mutfix_001.py",
                "content": source,
            },
        }

    return test_author


def test_mutation_score_is_one_despite_conftest_forcing_committed_code(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    source = build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID,
        repo_root,
        judge=None,
        test_author=make_test_author(log_path, source),
    )

    try:
        shown = report.to_dict()
    except Exception:
        shown = report
    score = field(report, "mutation_score")
    assert score == 1.0, "expected mutation_score 1.0, report: " + repr(shown)