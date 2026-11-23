# hotdocs-criterion: sha256:6e91b08182d4664c7d613c3d2db806432ebfde49b5f3fad8d8d0dc61526672c3
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


SLUG = "mutscore-fixture"
MODULE = "mutscore_fixture"
COMPONENT_ID = "comp-" + SLUG
CRITERION_ID = "AC-MUTSCORE-001"
REQUIREMENT_ID = "R-MUTSCORE-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def bundle_values():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": "Given a module with g, h and m\nWhen verify runs\nThen g orders its arguments",
        "requirement_text": "R-MUTSCORE-001 g MUST return whether a is less than b.",
        "interface": "g(a, b) -> bool\nh(a, b) -> int\nm(k, d) -> bool\ndo_the_thing(x) -> object",
        "glossary": "# Glossary",
        "dependency_interfaces": {},
        "testing": "",
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


def module_source():
    return (
        "def g(a, b):\n"
        "    return a < b\n"
        "\n"
        "\n"
        "def h(a, b):\n"
        "    return a // b\n"
        "\n"
        "\n"
        "def m(k, d):\n"
        "    return k in d\n"
        "\n"
        "\n"
        "def do_the_thing(x):\n"
        "    return x\n"
    )


def cached_test_source(bundle):
    return (
        header_for(bundle) + "\n"
        "import " + MODULE + "\n"
        "\n"
        "\n"
        "def test_g_orders_its_arguments():\n"
        "    assert " + MODULE + ".g(1, 2)\n"
    )


def build_fixture(repo_root):
    bundle = bundle_values()

    write(
        repo_root / "specs" / "product" / "mutscore.md",
        "---\n"
        "id: P-MUTSCORE\n"
        "title: Mutation score fixture capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Mutation score fixture capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A capability for the fixture.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Mutation score fixture\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-MUTSCORE]\n"
        "---\n"
        "\n"
        "# Mutation score fixture\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture with three mutation sites.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: g, h, m, do_the_thing.\n"
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
    write(
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "**" + REQUIREMENT_ID + "** - g MUST return whether a is less than b.\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a module with g, h and m\n"
        "When verify runs\n"
        "Then g orders its arguments\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "g(a, b) -> bool\n"
        "h(a, b) -> int\n"
        "m(k, d) -> bool\n"
        "do_the_thing(x) -> object\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(repo_root / "gen" / SLUG / (MODULE + ".py"), module_source())

    test_source = cached_test_source(bundle)
    write(
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_mutscore_001.py",
        test_source,
    )

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(bundle) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    result = dict(BUNDLE)\n"
        "    result['component_id'] = component_id\n"
        "    result['criterion_id'] = criterion_id\n"
        "    result['dependency_interfaces'] = {}\n"
        "    return result\n",
    )

    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 0\n"
        "        self.tests_reached = 0\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    return ProbeReport()\n",
    )

    return test_source


def make_test_author(log_path, content):
    def test_author_stand_in(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/" + SLUG + "/generated-test/test_ac_mutscore_001.py",
                "content": content,
            },
        }

    return test_author_stand_in


def test_mutation_score_is_one_third(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    test_source = build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID,
        repo_root,
        judge=None,
        test_author=make_test_author(log_path, test_source),
    )

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1
    assert field(matching[0], "result") == "pass"

    assert field(report, "mutation_error") is None
    score = field(report, "mutation_score")
    assert score is not None
    assert abs(score - 1 / 3) < 1e-9
    assert field(report, "overall") == "fail"