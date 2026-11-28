# hotdocs-criterion: sha256:955abd488b3bd34e7794c7938e2439c41e6b677788bdf0c8d773ac56331e18d2
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


CRITERION_TEXT = (
    "Given g(a, b) returns a < b\n"
    "When g is called with (1, 2) and (2, 1)\n"
    "Then the results are True and False"
)
REQUIREMENT_TEXT = "R-QUX-001: g(a, b) MUST return a < b."
INTERFACE_TEXT = "# Library\n\ng(a, b) -> bool\nh(a, b) -> int"
GLOSSARY_TEXT = "# Glossary"
TESTING_TEXT = ""


def bundle_dict():
    return {
        "component_id": "comp-qux",
        "criterion_id": "AC-QUX-001",
        "covers": "R-QUX-001",
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
        "testing": TESTING_TEXT,
    }


def header_line():
    bundle = bundle_dict()
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cached_test_body():
    return (
        "import qux\n"
        "\n"
        "\n"
        "def test_g_orders():\n"
        "    assert qux.g(1, 2) is True\n"
        "    assert qux.g(2, 1) is False\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: [P-QUX]\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Compares and divides numbers.\n",
    )
    write(
        comp / "requirements" / "R-QUX-001.md",
        "# R-QUX-001\n\n**R-QUX-001** — g(a, b) MUST return a < b.\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n"
        "\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given g(a, b) returns a < b\n"
        "When g is called with (1, 2) and (2, 1)\n"
        "Then the results are True and False\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ng(a, b) -> bool\nh(a, b) -> int\n```\n",
    )
    write(
        repo_root / "specs" / "product" / "P-QUX.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Qux capability\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    write(
        repo_root / "gen" / "qux" / "qux.py",
        "def g(a, b):\n"
        "    return a < b\n"
        "\n"
        "\n"
        "def h(a, b):\n"
        "    return a // b\n",
    )

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return " + repr(bundle_dict()) + "\n",
    )

    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings)}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    return _Report()\n",
    )

    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        header_line() + "\n" + cached_test_body(),
    )


def make_test_author(log_path):
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
                "path": "verification/qux/generated-test/test_ac_qux_001.py",
                "content": cached_test_body(),
            },
        }

    return test_author


def test_mutation_score_half_fails_overall(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        "comp-qux", repo_root, test_author=make_test_author(log_path)
    )

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-QUX-001"]
    assert len(matching) == 1, criteria
    criterion = matching[0]

    assert field(criterion, "result") == "pass", criterion
    assert field(report, "mutation_error") is None
    assert field(report, "mutation_score") == 0.5
    assert field(report, "overall") == "fail"