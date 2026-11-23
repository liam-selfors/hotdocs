# hotdocs-criterion: sha256:2c469d4f75b92954edadec225a61d986951c4a39de4e70a88a0d9f4dfa26645f
import hashlib
import json
from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_bundle():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": (
            "Given a widget input is 1\n"
            "When add_one is invoked with [1]\n"
            "Then result equals 2\n"
        ),
        "requirement_text": "R-WIDGET-001: add_one(x) MUST return x plus one.\n",
        "interface": "# Library\n\n```\nadd_one(x: int) -> int\n```\n",
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


def build_fixture(repo_root, implementation_source):
    repo_root = Path(repo_root)
    comp = repo_root / "specs" / "components" / SLUG

    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n\n"
        "# Widget\n\n"
        "## Purpose\n\nAdds one to a number.\n\n"
        "## Scope\n\n- In scope: add_one.\n\n"
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
        "# " + REQUIREMENT_ID + "\n\n**" + REQUIREMENT_ID + "** — `add_one(x)` MUST return `x` plus one.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nadd_one(x: int) -> int\n```\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a widget input is 1\n"
        "When add_one is invoked with [1]\n"
        "Then result equals 2\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "P-WIDGET.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n\n"
        "# Widget capability\n\n## Purpose\n\nWidgets.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    # Code under test.
    write(repo_root / "gen" / SLUG / (SLUG + ".py"), implementation_source)

    # Fake spec-bundle-assembler.
    bundle = make_bundle()
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(bundle) + "\n\n\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )

    # Fake test-probe: always ok, no findings.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = " + repr("test-probe@1.4.0") + "\n\n\n"
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
        "\n\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    return ProbeReport()\n",
    )

    # The already-generated, current test file in the cache.
    test_body = (
        header_for(bundle) + "\n"
        "import widget\n"
        "\n\n"
        "def test_add_one_of_one_is_two():\n"
        "    assert widget.add_one(1) == 2\n"
    )
    write(
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py",
        test_body,
    )
    return repo_root


def make_test_author(log_path):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": {"category": "unexpected", "message": "test_author should not be called"},
            "file": None,
        }

    return test_author


def find_criterion(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return matches[0]


@pytest.mark.parametrize(
    "implementation, expected",
    [
        ("def add_one(x):\n    return x + 1\n", "pass"),
        ("def add_one(x):\n    return x + 2\n", "fail"),
    ],
)
def test_cached_generated_test_runs_against_gen_and_result_is_reported(tmp_path, implementation, expected):
    repo_root = build_fixture(tmp_path / "repo", implementation)
    log_path = tmp_path / "test_author_calls.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=None, test_author=make_test_author(log_path)
    )

    criterion = find_criterion(report)
    assert field(criterion, "kind") == "generated-test"
    assert field(criterion, "covers") == REQUIREMENT_ID
    # The result reflects actually executing the cached test against gen/widget/.
    assert field(criterion, "result") == expected
    if expected == "fail":
        assert field(criterion, "failure_origin") == "implementation"

    # The current cached file was used; test_author was never asked to write one.
    assert not log_path.exists() or log_path.read_text(encoding="utf-8") == ""