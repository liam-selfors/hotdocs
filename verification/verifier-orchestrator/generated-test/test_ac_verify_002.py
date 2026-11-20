# hotdocs-criterion: sha256:8e318049a9fa28cb97a30cf68baa60c9bfcaa618d13aef8ba6fd9aa041842903
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
CRITERION_ID = "AC-WIDGET-001"
HASH_KEYS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")


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
        "criterion_text": "Given a number 3\nWhen double is called with it\nThen it returns 6",
        "requirement_text": "**R-WIDGET-001** - `double` MUST return twice its argument.",
        "interface": "# Library\n\ndouble(x: int) -> int",
        "glossary": "# Glossary",
        "dependency_interfaces": {},
        "testing": "",
    }


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in HASH_KEYS},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return "# hotdocs-criterion: sha256:" + digest


def cached_test_source(bundle, expected, marker):
    return (
        header_for(bundle) + "\n"
        + "import widget\n"
        + "\n"
        + "\n"
        + "def test_double_value():\n"
        + "    with open(" + repr(str(marker)) + ", \"a\") as handle:\n"
        + "        handle.write(\"ran\\n\")\n"
        + "    assert widget.double(3) == " + repr(expected) + "\n"
    )


def build_fixture(repo_root, expected, marker):
    bundle = criterion_bundle()

    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubles numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- Doubling.\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a x is 3\n"
        "When widget.double is invoked with [3]\n"
        "Then result equals 6\n"
        "```\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubles a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
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
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** - `double` MUST return twice its argument.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a number 3\n"
        "When double is called with it\n"
        "Then it returns 6\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        repo_root / "gen" / SLUG / "widget.py",
        "def double(x):\n    return x * 2\n",
    )

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(bundle) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )

    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = \"test-probe@1.3.0\"\n"
        "\n"
        "\n"
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 0\n"
        "        self.tests_reached = 0\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\"ok\": self.ok, \"findings\": list(self.findings),\n"
        "                \"tests_run\": self.tests_run, \"tests_reached\": self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return _Report()\n",
    )

    write(
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py",
        cached_test_source(bundle, expected, marker),
    )
    return bundle


def make_author(log_path, bundle, marker):
    def author(b):
        with open(log_path, "a") as handle:
            handle.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": cached_test_source(bundle, 6, marker),
            },
        }

    return author


def find_criterion(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return matches[0]


def run_case(tmp_path, expected):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    marker = tmp_path / "ran.log"
    author_log = tmp_path / "author.log"
    bundle = build_fixture(repo_root, expected, marker)
    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=None, test_author=make_author(author_log, bundle, marker)
    )
    return report, marker, author_log


def test_cached_generated_test_passes_and_is_reported(tmp_path):
    report, marker, author_log = run_case(tmp_path, 6)
    entry = find_criterion(report)
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == "pass", entry
    assert marker.is_file()
    assert marker.read_text().count("ran") >= 1
    assert not author_log.exists() or author_log.read_text() == ""


def test_cached_generated_test_fails_and_is_reported(tmp_path):
    report, marker, author_log = run_case(tmp_path, 7)
    entry = find_criterion(report)
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == "fail", entry
    assert marker.is_file()
    assert marker.read_text().count("ran") >= 1
    assert not author_log.exists() or author_log.read_text() == ""