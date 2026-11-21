# hotdocs-criterion: sha256:d9eeee7c4e72d1ee6c9946b6ca19959dcd81d943bdedfdb967bcd4fe06188ace
import json
from pathlib import Path

import verifier_orchestrator


CRITERION_ID = "AC-FOO-003b"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, assembler_log):
    comp = repo_root / "specs" / "components" / "foo"

    write(
        repo_root / "specs" / "product" / "P-FOO.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Foo capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo things.\n",
    )

    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-FOO]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Returns a value.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: bar_value.\n"
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
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** - `bar_value(x)` MUST return `x`.\n",
    )

    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "bar_value(x) -> int\n"
        "```\n",
    )

    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a value 3\n"
        "When bar_value is called with it\n"
        "Then the result is 3\n"
        "```\n",
    )

    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    write(
        repo_root / "gen" / "foo" / "foo.py",
        "def bar_value(x):\n"
        "    return x\n",
    )

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(assembler_log)) + "\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    raise RuntimeError('assemble not expected')\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(component_id + '\\t' + criterion_id + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-FOO-001',\n"
        "        'criterion_text': 'criterion text',\n"
        "        'requirement_text': 'requirement text',\n"
        "        'interface': 'bar_value(x) -> int',\n"
        "        'glossary': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n",
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


def make_test_author(author_log):
    content = (
        "import foo\n"
        "\n"
        "\n"
        "def test_bar_value():\n"
        "    assert foo.bar_value(3) == 3\n"
    )

    def test_author_fake(bundle):
        criterion_id = field(bundle, "criterion_id")
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"criterion_id": criterion_id}) + "\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/foo/generated-test/test_ac_foo_003b.py",
                "content": content,
            },
        }

    return test_author_fake


def test_criterion_id_with_letter_suffix_passed_unchanged(tmp_path):
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
    assert ids == [CRITERION_ID]

    assert assembler_log.is_file(), "assemble_criterion was never called"
    assembled_ids = [
        line.split("\t")[1]
        for line in assembler_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert assembled_ids, "assemble_criterion was never called"
    assert all(cid == CRITERION_ID for cid in assembled_ids), assembled_ids

    assert author_log.is_file(), "test_author was never called"
    authored = [
        json.loads(line)["criterion_id"]
        for line in author_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert authored, "test_author was never called"
    assert all(cid == CRITERION_ID for cid in authored), authored