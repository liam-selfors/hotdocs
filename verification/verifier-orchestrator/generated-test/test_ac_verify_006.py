# hotdocs-criterion: sha256:bb159dde5774205961839a535852706703f9782f21c873fdbc3d7b41f18a8d82
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-foo"
SLUG = "foo"
CRITERION_ID = "AC-FOO-001"
REQ_ID = "R-FOO-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


BUNDLE = {
    "component_id": COMPONENT_ID,
    "criterion_id": CRITERION_ID,
    "covers": REQ_ID,
    "criterion_text": "Given a combine function\nWhen it is called\nThen it adds",
    "requirement_text": "R-FOO-001 - combine MUST add its two arguments.",
    "interface": "# Library\n\ncombine(a, b) -> int\nis_big(x) -> bool\n",
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


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
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
        "## Purpose\n\nCombines numbers.\n\n"
        "## Scope\n\n- In scope: combining.\n\n"
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
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** - `combine` MUST add its two arguments.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ncombine(a, b) -> int\nis_big(x) -> bool\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a combine function\n"
        "When it is called with two numbers\n"
        "Then it returns their sum\n"
        "```\n",
    )
    write(
        repo_root / "specs" / "product" / "foo.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n\n"
        "# Foo capability\n\n## Purpose\n\nFoo.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    # Code under test with several mutation sites.
    write(
        repo_root / "gen" / SLUG / "foo.py",
        "def combine(a, b):\n"
        "    return a + b\n"
        "\n"
        "\n"
        "def is_big(x):\n"
        "    return x > 10\n"
        "\n"
        "\n"
        "def scale(a, b):\n"
        "    return a * b\n",
    )

    # Fake spec-bundle-assembler.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    out = dict(BUNDLE)\n"
        "    out['component_id'] = component_id\n"
        "    out['criterion_id'] = criterion_id\n"
        "    return out\n",
    )

    # Fake test-probe: always ok, no findings.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None, **kwargs):\n"
        "    return _Report()\n",
    )


WEAK_TEST_BODY = (
    "import foo\n"
    "\n"
    "\n"
    "def test_combine_exists():\n"
    "    assert hasattr(foo, 'combine')\n"
)


def make_test_author(log_path):
    content = header_for(BUNDLE) + "\n" + WEAK_TEST_BODY

    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/foo/generated-test/test_ac_foo_001.py",
                "content": content,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author


def test_mutation_score_below_bar_fails_overall(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=None, test_author=make_test_author(log_path)
    )

    # The test author stand-in actually ran.
    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").count("called") >= 1

    criteria = field(report, "criteria")
    entries = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(entries) == 1
    entry = entries[0]
    assert field(entry, "kind") == "generated-test"
    # The weak test passes on the unmutated code: mutation score never
    # changes a criterion's own result.
    assert field(entry, "result") == "pass"

    # The mutation score is computed and reported, and is below the bar.
    score = field(report, "mutation_score")
    assert score is not None
    assert isinstance(score, (int, float))
    assert score < 0.8
    # No mutant is killed by a test that only checks a name exists.
    assert score == 0.0
    # The shortfall is the cause, not a sandbox/adapter error.
    assert field(report, "mutation_error") is None

    # Overall verdict is fail.
    assert field(report, "overall") == "fail"

    # The JSON form agrees.
    as_dict = report.to_dict()
    assert as_dict["overall"] == "fail"
    assert as_dict["mutation_score"] is not None
    assert as_dict["mutation_score"] < 0.8
    assert as_dict["mutation_error"] is None