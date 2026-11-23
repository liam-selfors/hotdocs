# hotdocs-criterion: sha256:b1cf34d43281d64590afbc08c2ed6f26112ed47200b5dadc428196fd192d3000
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def bundle_field(value, name):
    if isinstance(value, dict):
        return value[name]
    try:
        return value[name]
    except Exception:
        return getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, assembler_log):
    write(
        repo_root / "specs" / "product" / "P-FOO.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Foo capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo things.\n",
    )
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a thing.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-FOO]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides bar_value.\n"
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
        comp / "requirements" / "R-FOO-003.md",
        "# R-FOO-003\n\n**R-FOO-003** — `bar_value()` MUST return 3.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nbar_value() -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-FOO-003b.md",
        "# AC-FOO-003b\n"
        "\n"
        "Covers: R-FOO-003\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the foo module\n"
        "When bar_value is called\n"
        "Then it returns 3\n"
        "```\n",
    )
    write(
        repo_root / "gen" / "foo" / "foo.py",
        "def bar_value():\n    return 3\n",
    )

    assembler_src = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(assembler_log)) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps([component_id, criterion_id]) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-FOO-003',\n"
        "        'criterion_text': 'Given the foo module When bar_value is called Then it returns 3',\n"
        "        'requirement_text': 'bar_value() MUST return 3.',\n"
        "        'interface': 'bar_value() -> int',\n"
        "        'glossary': 'Foo',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_src,
    )

    probe_src = (
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
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None, **kwargs):\n"
        "    return ProbeReport()\n"
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_src)


GENERATED_TEST = (
    "import foo\n"
    "\n"
    "\n"
    "def test_bar_value():\n"
    "    assert foo.bar_value() == 3\n"
)


def test_criterion_id_with_letter_suffix_passed_unchanged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    author_log = logs / "author.log"
    build_fixture(repo_root, assembler_log)

    def author(bundle):
        cid = bundle_field(bundle, "criterion_id")
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(cid) + "\n")
        return {
            "component_id": "comp-foo",
            "criterion_id": cid,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/foo/generated-test/test_ac_foo_003b.py",
                "content": GENERATED_TEST,
            },
            "repair_attempts": 0,
            "probe_findings": [],
        }

    report = verifier_orchestrator.verify("comp-foo", repo_root, test_author=author)

    criteria = field(report, "criteria")
    ids = [field(c, "id") for c in criteria]
    assert ids == ["AC-FOO-003b"]

    assert assembler_log.is_file()
    assembled = [
        json.loads(line)
        for line in assembler_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert assembled, "assemble_criterion was never called"
    assert all(entry[1] == "AC-FOO-003b" for entry in assembled)
    assert ["comp-foo", "AC-FOO-003b"] in assembled

    assert author_log.is_file()
    authored = [
        json.loads(line)
        for line in author_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert authored, "test_author was never called"
    assert all(cid == "AC-FOO-003b" for cid in authored)