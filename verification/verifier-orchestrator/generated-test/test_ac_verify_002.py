# hotdocs-criterion: sha256:831d4248ceca95f007f18a4b1683823a2955197de036a5ef69639682c3fd8eb9
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


CRITERION_ID = "AC-WIDGET-001"
COMPONENT_ID = "comp-widget"
SLUG = "widget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def criterion_bundle():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": "R-WIDGET-001",
        "criterion_text": "Given a widget module\nWhen double is called with 3\nThen it returns 6",
        "requirement_text": "R-WIDGET-001: double(x) MUST return x times two.",
        "interface": "double(x: int) -> int",
        "glossary": "Glossary text.",
        "dependency_interfaces": {},
        "testing": "",
    }


def criterion_header(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generated_test_source(bundle, ran_log):
    return (
        criterion_header(bundle) + "\n"
        + "import widget\n"
        + "\n"
        + "\n"
        + "def test_double_three():\n"
        + "    with open(" + repr(str(ran_log)) + ", 'a') as handle:\n"
        + "        handle.write('ran\\n')\n"
        + "    assert widget.double(3) == 6\n"
    )


def build_fixture(repo_root, implementation):
    bundle = criterion_bundle()
    ran_log = repo_root / "ran.log"
    comp = repo_root / "specs" / "components" / SLUG

    write(
        comp / "component.md",
        "---\n"
        + "id: comp-widget\n"
        + "title: Widget\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "realizes: [P-WIDGET]\n"
        + "---\n"
        + "\n"
        + "# Widget\n\n"
        + "## Purpose\n\nDoubles numbers.\n\n"
        + "## Scope\n\n- In scope: doubling.\n\n"
        + "## Definitions\n\nNone.\n\n"
        + "## Behavior\n\nSee `requirements/`.\n\n"
        + "## Interfaces\n\nSee `interface/`.\n\n"
        + "## Data\n\nSee `interface/data/`.\n\n"
        + "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        + "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        + "## Open questions\n\n"
        + "## Change log\n\n- Initial.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — `double(x)` MUST return `x` times two.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble(x: int) -> int\n```\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# AC-WIDGET-001\n\n"
        + "Covers: R-WIDGET-001\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\n"
        + "Given a widget module\n"
        + "When double is called with 3\n"
        + "Then it returns 6\n"
        + "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "P-WIDGET.md",
        "---\n"
        + "id: P-WIDGET\n"
        + "title: Widget capability\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "---\n\n"
        + "# Widget capability\n\n## Purpose\n\nDoubling.\n\n## Scope\n\n- Doubling.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    # Code under test.
    write(repo_root / "gen" / SLUG / "widget.py", implementation)

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        + "    return dict(" + repr(bundle) + ")\n",
    )

    # test-probe stand-in: always ok.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        + "\n"
        + "\n"
        + "class ProbeReport:\n"
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
        + "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        + "    return ProbeReport()\n",
    )

    # The already-generated test file, with a current header.
    source = generated_test_source(bundle, ran_log)
    write(
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py",
        source,
    )

    author_log = repo_root / "author.log"

    def test_author(bundle_arg):
        with open(author_log, "a", encoding="utf-8") as handle:
            handle.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": source,
            },
        }

    return ran_log, test_author


def find_criterion(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return matches[0]


def test_generated_test_passes_against_correct_implementation(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    ran_log, author = build_fixture(repo_root, "def double(x):\n    return x * 2\n")

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, judge=None, test_author=author)

    entry = find_criterion(report)
    assert field(entry, "result") == "pass"
    assert ran_log.is_file()
    assert "ran" in ran_log.read_text(encoding="utf-8")


def test_generated_test_fails_against_wrong_implementation(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    ran_log, author = build_fixture(repo_root, "def double(x):\n    return x + 1\n")

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, judge=None, test_author=author)

    entry = find_criterion(report)
    assert field(entry, "result") == "fail"
    assert ran_log.is_file()
    assert "ran" in ran_log.read_text(encoding="utf-8")