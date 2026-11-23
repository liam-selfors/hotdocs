# hotdocs-criterion: sha256:f057441e84bf6fcea1eb66d7aa6685f3777ce614c87c891fcb40e1c46b742378
import hashlib
import json
import shutil
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-foo-widget"
SLUG = "foo-widget"
MODULE = "foo_widget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_MD = (
    "---\n"
    "id: comp-foo-widget\n"
    "title: Foo Widget\n"
    "status: draft\n"
    "owners: [test-team]\n"
    "realizes: [P-FOOW]\n"
    "---\n"
    "\n"
    "# Foo Widget\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Builds widgets carrying a value.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: building widgets.\n"
    "- Out of scope: everything else.\n"
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
    "- Initial draft.\n"
)

PRODUCT_MD = (
    "---\n"
    "id: P-FOOW\n"
    "title: Foo Widgets\n"
    "status: draft\n"
    "owners: [test-team]\n"
    "---\n"
    "\n"
    "# Foo Widgets\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Widgets exist.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- Widgets.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "make_widget(x: int) -> object\n"
    "```\n"
    "\n"
    "`make_widget` returns an object whose attribute `value` equals `x`.\n"
)

REQ_1 = "**R-FOOW-001** — `make_widget(x)` MUST return an object whose `value` is `x`.\n"
REQ_2 = "**R-FOOW-002** — `make_widget(3).value` MUST equal `3`.\n"
REQ_3 = "**R-FOOW-003** — The interface text MUST be clear.\n"

AC_1 = (
    "# AC-FOOW-001\n"
    "\n"
    "Covers: R-FOOW-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given a val is 3\n"
    "When make_widget is invoked with [val]\n"
    "Then value equals 3\n"
    "```\n"
)

AC_2 = (
    "# AC-FOOW-002\n"
    "\n"
    "Covers: R-FOOW-002\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given the number 3\n"
    "When make_widget is called with it\n"
    "Then the widget's value is 3\n"
    "```\n"
)

AC_3 = (
    "# AC-FOOW-003\n"
    "\n"
    "Covers: R-FOOW-003\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given the interface text\n"
    "When a reader reads it\n"
    "Then it is clear\n"
    "```\n"
)

MODULE_SRC = (
    "import types as _types\n"
    "\n"
    "\n"
    "def make_widget(x):\n"
    "    return _types.SimpleNamespace(value=x)\n"
)

GLOSSARY_MD = "# Glossary\n\n- **Widget** — a thing with a value.\n"

PROBE_SRC = (
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
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
    "          interpreter=None, assets=None):\n"
    "    return ProbeReport()\n"
)


def make_bundles():
    criteria = {
        "AC-FOOW-001": ("R-FOOW-001", AC_1, REQ_1),
        "AC-FOOW-002": ("R-FOOW-002", AC_2, REQ_2),
        "AC-FOOW-003": ("R-FOOW-003", AC_3, REQ_3),
    }
    bundles = {}
    for cid, (covers, ac_text, req_text) in criteria.items():
        bundles[cid] = {
            "component_id": COMPONENT_ID,
            "criterion_id": cid,
            "covers": covers,
            "criterion_text": ac_text,
            "requirement_text": req_text,
            "interface": LIBRARY_MD,
            "glossary": GLOSSARY_MD,
            "dependency_interfaces": {},
            "testing": "",
        }
    return bundles


def assembler_source(bundles):
    return (
        "BUNDLES = " + repr(bundles) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLES[criterion_id])\n"
    )


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
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOOW-001.md", REQ_1)
    write(comp / "requirements" / "R-FOOW-002.md", REQ_2)
    write(comp / "requirements" / "R-FOOW-003.md", REQ_3)
    write(comp / "acceptance" / "AC-FOOW-001.md", AC_1)
    write(comp / "acceptance" / "AC-FOOW-002.md", AC_2)
    write(comp / "acceptance" / "AC-FOOW-003.md", AC_3)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "specs" / "product" / "foow.md", PRODUCT_MD)
    write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), MODULE_SRC)

    bundles = make_bundles()
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(bundles),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SRC)

    live = (
        Path(verifier_orchestrator.__file__).resolve().parents[1] / "spec-bundle-assembler"
    ).resolve().parents[1]
    src_compiler = live / "pipeline" / "criterion-compiler"
    dst_compiler = repo_root / "pipeline" / "criterion-compiler"
    shutil.copytree(
        src_compiler,
        dst_compiler,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    return bundles


def make_test_author(log_path):
    def test_author_stub(bundle):
        cid = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(cid) + "\n")
        data = {
            k: (bundle[k] if isinstance(bundle, dict) else getattr(bundle, k))
            for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")
        }
        content = (
            header_for(data) + "\n"
            "import foo_widget\n"
            "\n"
            "\n"
            "def test_widget_value_is_three():\n"
            "    assert foo_widget.make_widget(3).value == 3\n"
        )
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/foo-widget/generated-test/test_ac_foow_002.py",
                "content": content,
            },
        }

    return test_author_stub


def test_skipped_llm_judge_alone_does_not_fail_overall(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "test_author.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID,
        repo_root,
        judge=None,
        test_author=make_test_author(log_path),
    )

    criteria = field(report, "criteria")
    by_id = {c["id"]: c for c in criteria}

    # The Given: compiled and generated-test criteria pass, the llm-judge one is skipped.
    assert by_id["AC-FOOW-001"]["result"] == "pass", by_id["AC-FOOW-001"]
    assert by_id["AC-FOOW-002"]["result"] == "pass", by_id["AC-FOOW-002"]
    assert by_id["AC-FOOW-003"]["result"] == "skipped", by_id["AC-FOOW-003"]
    assert log_path.is_file()
    assert field(report, "mutation_score") == 1.0
    assert field(report, "interface_drift") is False

    # The Then: a skipped finding alone never causes fail.
    assert field(report, "overall") == "pass"