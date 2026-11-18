# hotdocs-criterion: sha256:08c76b981f5921b00f87ad4ebba57486663607b25ca2c38742598ceef32e8ca0
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERION_TEXT = (
    "# AC-FOO-003b\n"
    "\n"
    "Covers: R-FOO-003\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When double(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

REQUIREMENT_TEXT = (
    "# R-FOO-003\n"
    "\n"
    "**R-FOO-003** \u2014 `double(x)` MUST return `2 * x`.\n"
)


def build_fixture(repo_root, assembler_log):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "foo.md",
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
        "Doubling numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-FOO-001\n"
        "\n"
        "Covers: P-FOO\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When double(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    write(comp / "requirements" / "R-FOO-003.md", REQUIREMENT_TEXT)
    write(comp / "acceptance" / "AC-FOO-003b.md", CRITERION_TEXT)
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "gen" / "foo" / "foo.py", "")

    assembler_src = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(assembler_log)) + "\n"
        "CRITERION_TEXT = " + repr(CRITERION_TEXT) + "\n"
        "REQUIREMENT_TEXT = " + repr(REQUIREMENT_TEXT) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'component_id': component_id, 'criterion_id': criterion_id}) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-FOO-003',\n"
        "        'criterion_text': CRITERION_TEXT,\n"
        "        'requirement_text': REQUIREMENT_TEXT,\n"
        "        'interface': '# Library\\n\\n```\\ndouble(x: int) -> int\\n```',\n"
        "        'glossary': '# Glossary\\n\\n- **Foo** \\u2014 a test term.',\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "        'spec': '',\n"
        "        'interface': '',\n"
        "        'constraints': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'dependency_context': {},\n"
        "        'dependency_usage': {},\n"
        "        'vars': {},\n"
        "        'glossary': '',\n"
        "        'hint_code': None,\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_src,
    )


def make_test_author(author_log):
    def test_author_stub(bundle):
        criterion_id = field(bundle, "criterion_id")
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"criterion_id": criterion_id}) + "\n")
        return {
            "component_id": "comp-foo",
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/foo/generated-test/test_ac_foo_003b.py",
                "content": "def test_ok():\n    assert True\n",
            },
            "model_call_error": None,
        }

    return test_author_stub


def read_log(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_verify_018_criterion_id_with_letter_suffix_passed_unchanged(tmp_path):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    author_log = logs / "author.log"
    build_fixture(repo_root, assembler_log)

    report = verifier_orchestrator.verify(
        "comp-foo", repo_root, test_author=make_test_author(author_log)
    )

    criteria = field(report, "criteria")
    ids = [field(c, "id") for c in criteria]
    assert ids == ["AC-FOO-003b"], ids

    entry = criteria[0]
    assert field(entry, "kind") == "generated-test"

    assembled = read_log(assembler_log)
    assembled_ids = [e["criterion_id"] for e in assembled]
    assert "AC-FOO-003b" in assembled_ids, assembled_ids
    assert all(cid == "AC-FOO-003b" for cid in assembled_ids), assembled_ids

    authored = read_log(author_log)
    assert len(authored) >= 1, authored
    assert all(e["criterion_id"] == "AC-FOO-003b" for e in authored), authored