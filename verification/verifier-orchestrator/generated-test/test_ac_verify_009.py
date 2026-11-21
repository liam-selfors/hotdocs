# hotdocs-criterion: sha256:7e4075daf1346af507ca786f39663a23014dbbe904bca5a32549ec67098ec153
import json
from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-foo-thing"
SLUG = "foo-thing"
MODULE = "foo_thing"
CRITERION_ID = "AC-FOOTHING-001"
REQUIREMENT_ID = "R-FOOTHING-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def expected_bundle():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": "SENTINEL-CRITERION-TEXT-7f3a: Given a value When read Then one",
        "requirement_text": "SENTINEL-REQUIREMENT-TEXT-91bc: the value MUST be one",
        "interface": "SENTINEL-INTERFACE-TEXT-44de: VALUE: int",
        "glossary": "SENTINEL-GLOSSARY-TEXT-0a1b",
        "dependency_interfaces": {},
        "testing": "SENTINEL-TESTING-TEXT-5c6d",
    }


def build_fixture(repo_root, assembler_log):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Foo Thing\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: [P-FOOTHING]\n"
        "---\n"
        "\n"
        "# Foo Thing\n"
        "\n"
        "## Purpose\n\nExposes a value.\n\n"
        "## Scope\n\n- In scope: the value.\n\n"
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
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n\n"
        "**" + REQUIREMENT_ID + "** — The module MUST expose `VALUE` equal to 1.\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given the module foo_thing\n"
        "When its VALUE is read\n"
        "Then it equals 1\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nVALUE: int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "foo-thing-cap.md",
        "---\n"
        "id: P-FOOTHING\n"
        "title: Foo thing capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Foo thing capability\n\n"
        "## Purpose\n\nProvide a value.\n\n"
        "## Scope\n\n- The value.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    # Code under test: no mutation sites (numeric constants are never mutated).
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), "VALUE = 1\n")

    # Fake spec-bundle-assembler.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "import json\n"
        "\n"
        "LOG = " + repr(str(assembler_log)) + "\n"
        "BUNDLE = " + repr(expected_bundle()) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps([component_id, criterion_id]) + '\\n')\n"
        "    return json.loads(json.dumps(BUNDLE))\n",
    )

    # Fake test-probe: always ok.
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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return _ProbeReport()\n",
    )


def authored_test_source(marker, expected_value):
    return (
        "import " + MODULE + "\n"
        "\n"
        "\n"
        "def test_value():\n"
        "    with open(" + repr(str(marker)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('ran\\n')\n"
        "    assert " + MODULE + ".VALUE == " + repr(expected_value) + "\n"
    )


@pytest.mark.parametrize(
    "expected_value, expected_result",
    [(1, "pass"), (2, "fail")],
)
def test_generated_test_criterion_calls_test_author_with_assembled_bundle(
    tmp_path, expected_value, expected_result
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    author_log = logs / "author.log"
    marker = logs / "ran.log"

    build_fixture(repo_root, assembler_log)

    # No cached test exists for the criterion.
    cached = (
        repo_root / "verification" / SLUG / "generated-test"
        / ("test_" + CRITERION_ID.lower().replace("-", "_") + ".py")
    )
    assert not cached.exists()

    received = []
    source = authored_test_source(marker, expected_value)

    def test_author(bundle):
        received.append(bundle)
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "mock-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/" + SLUG + "/generated-test/test_ac_foothing_001.py",
                "content": source,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=test_author)

    # test_author invoked exactly once for the single criterion.
    assert author_log.read_text(encoding="utf-8").splitlines() == ["called"]
    assert len(received) == 1
    bundle = received[0]

    # The bundle came from assemble_criterion for this exact criterion.
    assembler_calls = [
        json.loads(line)
        for line in assembler_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [COMPONENT_ID, CRITERION_ID] in assembler_calls

    # And it is exactly that bundle, not one verify built itself.
    exp = expected_bundle()
    for key, value in exp.items():
        assert field(bundle, key) == value, key

    # The returned test code was executed.
    assert marker.exists()
    assert "ran" in marker.read_text(encoding="utf-8").splitlines()

    # Its run produced that criterion's result.
    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1
    entry = matching[0]
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == expected_result