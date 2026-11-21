# hotdocs-criterion: sha256:5f96f424b638e727bc757239331ef3f1536323e2a7209db0c204832a9e311665
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, assembler_log):
    comp = repo_root / "specs" / "components" / "foo"
    write(
        repo_root / "specs" / "product" / "foo.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n\n"
        "# Foo capability\n\n"
        "## Purpose\n\nProvides foo.\n\n"
        "## Scope\n\n- foo\n",
    )
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
        "## Purpose\n\nReturns a value.\n\n"
        "## Scope\n\n- In scope: bar_value.\n\n"
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
        comp / "requirements" / "R-FOO-003.md",
        "# R-FOO-003\n\n**R-FOO-003** - `bar_value()` MUST return 1.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-003b.md",
        "# AC-FOO-003b\n\n"
        "Covers: R-FOO-003\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a fresh process\n"
        "When bar_value is called\n"
        "Then it returns 1\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nbar_value() -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    write(
        repo_root / "gen" / "foo" / "foo.py",
        "def bar_value():\n    return 1\n",
    )

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(assembler_log)) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(component_id + ' ' + criterion_id + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-FOO-003',\n"
        "        'criterion_text': 'assembled for ' + criterion_id,\n"
        "        'requirement_text': 'bar_value() MUST return 1.',\n"
        "        'interface': 'bar_value() -> int',\n"
        "        'glossary': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n",
    )

    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
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
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )


TEST_CONTENT = (
    "import foo\n"
    "\n"
    "\n"
    "def test_bar_value():\n"
    "    assert foo.bar_value() == 1\n"
)


def make_test_author(author_log):
    def test_author(bundle):
        cid = field(bundle, "criterion_id")
        text = field(bundle, "criterion_text")
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"criterion_id": cid, "criterion_text": text}) + "\n")
        return {
            "component_id": "comp-foo",
            "criterion_id": cid,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/foo/generated-test/test_ac_foo_003b.py",
                "content": TEST_CONTENT,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author


def test_ac_verify_018_letter_suffix_id_passed_unchanged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    author_log = logs / "author.log"
    build_fixture(repo_root, assembler_log)

    report = verifier_orchestrator.verify(
        "comp-foo", repo_root, judge=None, test_author=make_test_author(author_log)
    )

    criteria = field(report, "criteria")
    ids = [field(c, "id") for c in criteria]
    assert ids == ["AC-FOO-003b"], ids
    entry = criteria[0]
    assert field(entry, "covers") == "R-FOO-003"
    assert field(entry, "kind") == "generated-test"

    assert assembler_log.is_file(), "assemble_criterion was never called"
    assembler_calls = [
        line.split(" ") for line in assembler_log.read_text(encoding="utf-8").splitlines() if line
    ]
    assert assembler_calls, "assemble_criterion was never called"
    for comp_id, crit_id in assembler_calls:
        assert comp_id == "comp-foo"
        assert crit_id == "AC-FOO-003b"

    assert author_log.is_file(), "test_author was never called"
    author_calls = [
        json.loads(line) for line in author_log.read_text(encoding="utf-8").splitlines() if line
    ]
    assert author_calls, "test_author was never called"
    for call in author_calls:
        assert call["criterion_id"] == "AC-FOO-003b"
        assert call["criterion_text"] == "assembled for AC-FOO-003b"