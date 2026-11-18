# hotdocs-criterion: sha256:89b65bad9f3e45cf253595727e43f86d4c8dfa5f495c7ebdffcb553a3d076b6b
import json
from pathlib import Path

import verifier_orchestrator


COMPONENT_MD = (
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
    "Foo doubles a number.\n"
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
    "- Initial.\n"
)

PRODUCT_MD = (
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
    "- Doubling.\n"
)

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `double_it(x)` MUST return a `Doubled` whose "
    "`value` is `2 * x`.\n"
)

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given a n is 2\n"
    "When double_it is invoked with {\"x\": n}\n"
    "Then value equals 4\n"
    "```\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "double_it(x: int) -> Doubled\n"
    "```\n"
)

DOUBLED_MD = (
    "# `Doubled`\n"
    "\n"
    "```json\n"
    "{\"value\": 4}\n"
    "```\n"
)

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

GLOSSARY_MD = "# Glossary\n\n- **Foo** \u2014 a test term.\n"


def module_source(wrong):
    expr = "2 * x + 1" if wrong else "2 * x"
    return (
        "class Doubled(dict):\n"
        "    def __getattr__(self, name):\n"
        "        try:\n"
        "            return self[name]\n"
        "        except KeyError:\n"
        "            raise AttributeError(name)\n"
        "\n"
        "\n"
        "def double_it(x):\n"
        "    return Doubled(value=" + expr + ")\n"
    )


def assembler_source():
    criterion_text = ACCEPTANCE_MD
    requirement_text = REQUIREMENT_MD
    interface_text = LIBRARY_MD + "\n" + DOUBLED_MD
    return (
        "CRITERION_TEXT = " + repr(criterion_text) + "\n"
        "REQUIREMENT_TEXT = " + repr(requirement_text) + "\n"
        "INTERFACE_TEXT = " + repr(interface_text) + "\n"
        "GLOSSARY_TEXT = " + repr(GLOSSARY_MD) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-FOO-001',\n"
        "        'criterion_text': CRITERION_TEXT,\n"
        "        'requirement_text': REQUIREMENT_TEXT,\n"
        "        'interface': INTERFACE_TEXT,\n"
        "        'glossary': GLOSSARY_TEXT,\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "        'spec': REQUIREMENT_TEXT,\n"
        "        'interface': INTERFACE_TEXT,\n"
        "        'constraints': 'None.',\n"
        "        'dependency_interfaces': {},\n"
        "        'dependency_context': {},\n"
        "        'dependency_usage': {},\n"
        "        'vars': {},\n"
        "        'glossary': GLOSSARY_TEXT,\n"
        "        'hint_code': None,\n"
        "    }\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(root, wrong=False):
    root = Path(root)
    write(root / "specs" / "glossary.md", GLOSSARY_MD)
    write(root / "specs" / "product" / "foo.md", PRODUCT_MD)
    comp = root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "interface" / "data" / "Doubled.md", DOUBLED_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)
    write(root / "gen" / "foo" / "foo.py", module_source(wrong))
    write(
        root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    return root


def run_main(argv):
    try:
        return verifier_orchestrator.main(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 2


def test_passing_component_json_and_text(tmp_path, capsys):
    root = build_fixture(tmp_path / "repo")
    capsys.readouterr()

    rc_json = run_main(["comp-foo", "--repo-root=" + str(root), "--format=json"])
    out_json = capsys.readouterr().out
    assert rc_json == 0
    report = json.loads(out_json)
    assert report["overall"] == "pass"

    rc_text = run_main(["comp-foo", "--repo-root", str(root), "--format", "text"])
    out_text = capsys.readouterr().out
    assert rc_text == 0
    lines = [line for line in out_text.splitlines() if line.strip()]
    assert lines[0].strip() == "comp-foo: pass"
    assert len(lines) >= 2
    criterion_lines = lines[1:]
    for line in criterion_lines:
        assert line[0] in (" ", "\t"), line
    assert "AC-FOO-001: pass" in [line.strip() for line in criterion_lines]


def test_failing_component_returns_1(tmp_path, capsys):
    root = build_fixture(tmp_path / "repo", wrong=True)
    capsys.readouterr()
    rc = run_main(["comp-foo", "--repo-root=" + str(root)])
    capsys.readouterr()
    assert rc == 1


def test_usage_errors_return_2(tmp_path, capsys):
    root = build_fixture(tmp_path / "repo")
    cases = [
        [],
        ["comp-foo", "--repo-root=" + str(root), "--format=bogus"],
        ["comp-foo", "--repo-root=" + str(root), "--bogus-flag"],
        ["comp-foo", "--repo-root"],
        ["comp-nope", "--repo-root=" + str(root)],
    ]
    capsys.readouterr()
    for argv in cases:
        rc = run_main(argv)
        captured = capsys.readouterr()
        assert rc == 2, argv
        assert "hotdocs verify-component" in captured.err, argv