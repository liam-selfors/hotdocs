# hotdocs-criterion: sha256:0683c39870a6a573058d2d905c93a8f776dca7793dd75f71bf55f7a3dbf0a6dd
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


JS = "function f(a, b) { return a === b; }" + " " * 200

CRITERION_ID = "AC-QUX-001"

EXPECTED_ERROR = (
    "javascript in a string at qux.py:3; declare it as an asset "
    "(specs/architecture/asset-kinds.md)"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def criterion_bundle():
    return {
        "component_id": "comp-qux",
        "criterion_id": CRITERION_ID,
        "covers": "R-QUX-001",
        "criterion_text": "Given the qux module\nWhen qux is invoked\nThen it returns 4",
        "requirement_text": "R-QUX-001: qux() MUST return 4.",
        "interface": "# Library\n\nqux() -> int",
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
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return "# hotdocs-criterion: sha256:" + digest


def generated_test_body():
    return (
        "import qux\n"
        "\n"
        "\n"
        "def test_qux_returns_four():\n"
        "    assert qux.qux() == 4\n"
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
    "        return {\n"
    "            'ok': self.ok,\n"
    "            'findings': list(self.findings),\n"
    "            'tests_run': self.tests_run,\n"
    "            'tests_reached': self.tests_reached,\n"
    "        }\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
    "          interpreter=None, assets=None):\n"
    "    return _Report()\n"
)


def build_fixture(repo_root, qux_source):
    bundle = criterion_bundle()

    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Qux capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provide qux.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-QUX]\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Returns four.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: qux.\n"
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
        comp / "requirements" / "R-QUX-001.md",
        "**R-QUX-001** — `qux()` MUST return 4.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nqux() -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the qux module\n"
        "When qux is invoked\n"
        "Then it returns 4\n"
        "```\n",
    )

    write(repo_root / "gen" / "qux" / "qux.py", qux_source)

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(bundle) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)

    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        header_for(bundle) + "\n" + generated_test_body(),
    )
    return bundle


def make_author(log_path, bundle):
    content = header_for(bundle) + "\n" + generated_test_body()

    def author(given_bundle):
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/qux/generated-test/test_ac_qux_001.py",
                "content": content,
            },
        }

    return author


def find_criterion(report):
    for c in field(report, "criteria"):
        if field(c, "id") == CRITERION_ID:
            return c
    raise AssertionError("criterion " + CRITERION_ID + " missing from report")


def test_javascript_in_string_constant_fails_mutation(tmp_path):
    repo_root = tmp_path / "repo"
    source = (
        '"""Doc."""\n\nSCRIPT = ' + repr(JS) + "\n\n\ndef qux():\n    return 4\n"
    )
    bundle = build_fixture(repo_root, source)
    log = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        "comp-qux", repo_root, test_author=make_author(log, bundle)
    )

    crit = find_criterion(report)
    assert field(crit, "result") == "pass"
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"
    assert field(report, "mutation_error") == EXPECTED_ERROR


def test_javascript_as_docstring_is_not_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    source = repr(JS) + "\n\n\ndef qux():\n    return 4\n"
    bundle = build_fixture(repo_root, source)
    log = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        "comp-qux", repo_root, test_author=make_author(log, bundle)
    )

    crit = find_criterion(report)
    assert field(crit, "result") == "pass"
    assert field(report, "mutation_error") is None
    assert field(report, "mutation_score") == 1.0