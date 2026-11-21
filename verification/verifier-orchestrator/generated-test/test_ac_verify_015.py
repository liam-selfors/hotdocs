# hotdocs-criterion: sha256:658047b890f107acf818962774e98f900311dd6b6cbc8198d06f3b24f64408e2
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


SLUG = "widget-math"
COMPONENT_ID = "comp-widget-math"
MODULE = "widget_math"

LIBRARY_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "alpha(x: int) -> int\n"
    "beta(x: int, y: int) -> int\n"
    "```\n"
    "\n"
    "`alpha(x)` returns `x + 1` when `x > 0`, else `x - 1`.\n"
    "`beta(x, y)` returns `x * y - y`.\n"
)

MODULE_SOURCE = (
    "def alpha(x):\n"
    "    if x > 0:\n"
    "        return x + 1\n"
    "    return x - 1\n"
    "\n"
    "\n"
    "def beta(x, y):\n"
    "    return x * y - y\n"
)

GLOSSARY_TEXT = "# Glossary\n\n- **Widget** - a thing.\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_bundles():
    bundles = {}
    specs = [
        ("AC-WMATH-001", "R-WMATH-001", "alpha"),
        ("AC-WMATH-002", "R-WMATH-002", "beta"),
    ]
    for crit_id, req_id, fn in specs:
        bundles[crit_id] = {
            "component_id": COMPONENT_ID,
            "criterion_id": crit_id,
            "covers": req_id,
            "criterion_text": (
                "Given a number\nWhen " + fn + " is called\nThen it returns the documented value"
            ),
            "requirement_text": "**" + req_id + "** - `" + fn + "` MUST behave as documented.",
            "interface": LIBRARY_TEXT,
            "glossary": GLOSSARY_TEXT,
            "dependency_interfaces": {},
            "testing": "",
        }
    return bundles


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def alpha_test_source(bundle):
    return (
        header_for(bundle) + "\n"
        "import widget_math\n"
        "\n"
        "\n"
        "def test_alpha_positive():\n"
        "    assert widget_math.alpha(5) == 6\n"
        "\n"
        "\n"
        "def test_alpha_negative():\n"
        "    assert widget_math.alpha(-5) == -6\n"
        "\n"
        "\n"
        "def test_alpha_zero():\n"
        "    assert widget_math.alpha(0) == -1\n"
    )


def beta_test_source(bundle):
    return (
        header_for(bundle) + "\n"
        "import widget_math\n"
        "\n"
        "\n"
        "def test_beta():\n"
        "    assert widget_math.beta(4, 2) == 6\n"
        "\n"
        "\n"
        "def test_beta_other():\n"
        "    assert widget_math.beta(3, 5) == 10\n"
    )


def build_fixture(repo_root, bundles):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget Math\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-WMATH]\n"
        "---\n"
        "\n"
        "# Widget Math\n"
        "\n"
        "## Purpose\n\nTwo small arithmetic functions.\n\n"
        "## Scope\n\n- In scope: alpha and beta.\n\n"
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
        comp / "requirements" / "R-WMATH-001.md",
        "# R-WMATH-001\n\n**R-WMATH-001** - `alpha(x)` MUST return `x + 1` when `x > 0`, else `x - 1`.\n",
    )
    write(
        comp / "requirements" / "R-WMATH-002.md",
        "# R-WMATH-002\n\n**R-WMATH-002** - `beta(x, y)` MUST return `x * y - y`.\n",
    )
    write(
        comp / "acceptance" / "AC-WMATH-001.md",
        "# AC-WMATH-001\n\nCovers: R-WMATH-001\nKind: generated-test\n\n"
        "```gherkin\n"
        "Given a number x\n"
        "When alpha is called with x\n"
        "Then it returns x + 1 for positive x and x - 1 otherwise\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-WMATH-002.md",
        "# AC-WMATH-002\n\nCovers: R-WMATH-002\nKind: generated-test\n\n"
        "```gherkin\n"
        "Given numbers x and y\n"
        "When beta is called with x and y\n"
        "Then it returns x * y - y\n"
        "```\n",
    )
    write(comp / "interface" / "library.md", LIBRARY_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "wmath.md",
        "---\n"
        "id: P-WMATH\n"
        "title: Widget math capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Widget math\n\n## Purpose\n\nArithmetic.\n\n## Scope\n\n- alpha, beta.\n",
    )
    write(repo_root / "specs" / "glossary.md", GLOSSARY_TEXT)

    write(repo_root / "gen" / SLUG / (MODULE + ".py"), MODULE_SOURCE)

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLES = " + repr(bundles) + "\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    raise RuntimeError('assemble is not used by verify')\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLES[criterion_id])\n",
    )

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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )


def make_author(log_path, bundles):
    def author(bundle):
        crit_id = field(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(crit_id + "\n")
        source_bundle = bundles[crit_id]
        if crit_id == "AC-WMATH-001":
            content = alpha_test_source(source_bundle)
        else:
            content = beta_test_source(source_bundle)
        name = "test_" + crit_id.lower().replace("-", "_") + ".py"
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": crit_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {"path": "verification/" + SLUG + "/generated-test/" + name, "content": content},
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return author


def test_mutation_score_is_union_of_both_tests_kills(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bundles = make_bundles()
    build_fixture(repo_root, bundles)
    log_path = tmp_path / "author.log"
    author = make_author(log_path, bundles)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, judge=None, test_author=author)

    calls = log_path.read_text(encoding="utf-8").split()
    assert sorted(set(calls)) == ["AC-WMATH-001", "AC-WMATH-002"]

    criteria = field(report, "criteria")
    results = {field(c, "id"): field(c, "result") for c in criteria}
    assert results.get("AC-WMATH-001") == "pass", criteria
    assert results.get("AC-WMATH-002") == "pass", criteria

    assert field(report, "mutation_error") is None
    score = field(report, "mutation_score")
    assert score is not None
    # alpha has 3 mutation sites, beta has 2: each test alone would score
    # 0.6 or 0.4 against the whole module; the union kills all 5.
    assert abs(score - 0.6) > 1e-9
    assert abs(score - 0.4) > 1e-9
    assert abs(score - 0.5) > 1e-9
    assert score == 1.0
    assert field(report, "overall") == "pass"