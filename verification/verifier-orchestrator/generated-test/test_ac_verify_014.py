# hotdocs-criterion: sha256:138d81cb52eacc335c9c06e508b6c9dd73be6ca7860f5712bce66a9d218b4a29
import shutil
from pathlib import Path

import verifier_orchestrator


SLUG = "twinslug"
COMPONENT_ID = "comp-twinslug"
MODULE = "twinslug"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CODE_A = (
    "class _Box(dict):\n"
    "    def __getattr__(self, name):\n"
    "        if name in self:\n"
    "            return self[name]\n"
    "        raise AttributeError(name)\n"
    "\n"
    "\n"
    "def twin_value():\n"
    "    return _Box(value=1)\n"
)

CODE_B = (
    "class _Box(dict):\n"
    "    def __getattr__(self, name):\n"
    "        if name in self:\n"
    "            return self[name]\n"
    "        raise AttributeError(name)\n"
    "\n"
    "\n"
    "def other_value():\n"
    "    return _Box(value=2)\n"
)

GENERATED_TEST = (
    "import " + MODULE + "\n"
    "\n"
    "\n"
    "def test_twin_value():\n"
    "    assert " + MODULE + ".twin_value().value == 1\n"
)

PROBE_SOURCE = (
    "class _Report:\n"
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
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
    "          interpreter=None, assets=None):\n"
    "    return _Report()\n"
)

ASSEMBLER_SOURCE = (
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    root = Path(repo_root)\n"
    "    comp = root / 'specs' / 'components' / " + repr(SLUG) + "\n"
    "    covers = 'R-' + criterion_id[len('AC-'):]\n"
    "    crit = (comp / 'acceptance' / (criterion_id + '.md')).read_text(encoding='utf-8')\n"
    "    req = (comp / 'requirements' / (covers + '.md')).read_text(encoding='utf-8')\n"
    "    iface = (comp / 'interface' / 'library.md').read_text(encoding='utf-8')\n"
    "    return dict(\n"
    "        component_id=component_id,\n"
    "        criterion_id=criterion_id,\n"
    "        covers=covers,\n"
    "        criterion_text=crit,\n"
    "        requirement_text=req,\n"
    "        interface=iface,\n"
    "        glossary='',\n"
    "        dependency_interfaces=dict(),\n"
    "        testing='',\n"
    "    )\n"
)


def build_fixture(repo_root, code):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Twin slug\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: [P-TWIN]\n"
        "---\n"
        "\n"
        "# Twin slug\n"
        "\n"
        "## Purpose\n\nReturns a boxed value.\n\n"
        "## Scope\n\n- In scope: twin_value.\n\n"
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
        comp / "requirements" / "R-TWIN-001.md",
        "# R-TWIN-001\n\n**R-TWIN-001** — `twin_value()` MUST return an "
        "object whose `value` is 1.\n",
    )
    write(
        comp / "requirements" / "R-TWIN-002.md",
        "# R-TWIN-002\n\n**R-TWIN-002** — `twin_value().value` MUST equal 1.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ntwin_value() -> dict\n```\n\n"
        "Returns a mapping whose `value` field is also an attribute.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-TWIN-001.md",
        "# AC-TWIN-001\n\n"
        "Covers: R-TWIN-001\n"
        "Kind: compiled\n\n"
        "```gherkin\n"
        "Given a seed is 0\n"
        "When twin_value is invoked with []\n"
        "Then value equals 1\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-TWIN-002.md",
        "# AC-TWIN-002\n\n"
        "Covers: R-TWIN-002\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given the twinslug module\n"
        "When twin_value is called\n"
        "Then its value is 1\n"
        "```\n",
    )
    write(
        repo_root / "specs" / "product" / "twin.md",
        "---\n"
        "id: P-TWIN\n"
        "title: Twin\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n\n"
        "# Twin\n\n## Purpose\n\nTwin capability.\n\n## Scope\n\n- Twin.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), code)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_SOURCE,
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)

    live = (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]
    shutil.copytree(
        live / "pipeline" / "criterion-compiler",
        repo_root / "pipeline" / "criterion-compiler",
        ignore=shutil.ignore_patterns("__pycache__"),
    )


def make_test_author(log_path):
    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(field(bundle, "criterion_id")) + "\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "ignored.py", "content": GENERATED_TEST},
        }

    return author


def results_by_id(report):
    return {c["id"]: c["result"] for c in field(report, "criteria")}


def assert_matches_a(report):
    assert field(report, "interface_drift") is False
    results = results_by_id(report)
    assert results["AC-TWIN-001"] == "pass"
    assert results["AC-TWIN-002"] == "pass"


def assert_matches_b(report):
    assert field(report, "interface_drift") is True
    results = results_by_id(report)
    assert results["AC-TWIN-001"] == "fail"
    assert results["AC-TWIN-002"] == "fail"


def test_same_slug_in_two_repo_roots_never_shares_a_module(tmp_path):
    root_a = tmp_path / "repo_a"
    root_b = tmp_path / "repo_b"
    build_fixture(root_a, CODE_A)
    build_fixture(root_b, CODE_B)
    log = tmp_path / "author.log"
    author = make_test_author(log)

    report_a = verifier_orchestrator.verify(COMPONENT_ID, root_a, test_author=author)
    report_b = verifier_orchestrator.verify(COMPONENT_ID, root_b, test_author=author)
    report_a_again = verifier_orchestrator.verify(COMPONENT_ID, root_a, test_author=author)

    assert log.is_file()
    assert_matches_a(report_a)
    assert_matches_b(report_b)
    assert_matches_a(report_a_again)