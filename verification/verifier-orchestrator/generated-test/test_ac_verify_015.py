# hotdocs-criterion: sha256:2590c13211f01655490ce8e068d4a07a9c9c054ac7d5b940a6d7a56a05398633
"""AC-VERIFY-015: the mutation score is one union score across all
generated-test files, never either test's isolated score."""

from pathlib import Path

import pytest

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

PRODUCT = (
    "---\n"
    "id: P-MIX\n"
    "title: Mix\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Mix\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Mixes numbers.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: mixing numbers.\n"
    "\n"
    "### CS-MIX-001\n"
    "\n"
    "Covers: P-MIX\n"
    "\n"
    "```gherkin\n"
    "Given two numbers\n"
    "When they are mixed\n"
    "Then a mixed number results\n"
    "```\n"
)

COMPONENT = (
    "---\n"
    "id: comp-mixer\n"
    "title: Mixer\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "realizes: [P-MIX]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Mixer\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Mixer combines numbers and checks bounds.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: blend and both.\n"
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

REQ_1 = "# R-MIXER-001\n\n**R-MIXER-001** \u2014 `blend(a, b, c, d)` MUST return `(a + b) * c - d`.\n"
REQ_2 = "# R-MIXER-002\n\n**R-MIXER-002** \u2014 `both(p, q)` MUST return whether `p > 3` and `q < 7`.\n"

AC_1 = (
    "# AC-MIXER-001\n"
    "\n"
    "Covers: R-MIXER-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given the integers 5, 3, 4 and 2\n"
    "When blend is called with them\n"
    "Then it returns 30\n"
    "```\n"
)

AC_2 = (
    "# AC-MIXER-002\n"
    "\n"
    "Covers: R-MIXER-002\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given the pairs (5, 5), (5, 9) and (1, 5)\n"
    "When both is called with each pair\n"
    "Then it returns True, False and False\n"
    "```\n"
)

LIBRARY = (
    "# Library\n"
    "\n"
    "```\n"
    "blend(a: int, b: int, c: int, d: int) -> int\n"
    "both(p: int, q: int) -> bool\n"
    "```\n"
)

CONSTRAINTS = "# Constraints\n\nNone.\n"

MODULE = (
    "def blend(a, b, c, d):\n"
    "    return (a + b) * c - d\n"
    "\n"
    "\n"
    "def both(p, q):\n"
    "    return p > 3 and q < 7\n"
)

TEST_BLEND = (
    "import mixer\n"
    "\n"
    "\n"
    "def test_blend():\n"
    "    assert mixer.blend(5, 3, 4, 2) == 30\n"
)

TEST_BOTH = (
    "import mixer\n"
    "\n"
    "\n"
    "def test_both():\n"
    "    assert mixer.both(5, 5) is True\n"
    "    assert mixer.both(5, 9) is False\n"
    "    assert mixer.both(1, 5) is False\n"
)

ASSEMBLER_BODY = (
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    root = Path(repo_root)\n"
    "    slug = component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
    "    comp = root / 'specs' / 'components' / slug\n"
    "    criterion_text = (comp / 'acceptance' / (criterion_id + '.md')).read_text(encoding='utf-8')\n"
    "    covers = ''\n"
    "    for line in criterion_text.splitlines():\n"
    "        if line.startswith('Covers:'):\n"
    "            covers = line.split(':', 1)[1].strip()\n"
    "            break\n"
    "    req = comp / 'requirements' / (covers + '.md')\n"
    "    requirement_text = req.read_text(encoding='utf-8') if req.is_file() else ''\n"
    "    interface = (comp / 'interface' / 'library.md').read_text(encoding='utf-8')\n"
    "    glossary = (root / 'specs' / 'glossary.md').read_text(encoding='utf-8')\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write('assemble ' + criterion_id + '\\n')\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': covers,\n"
    "        'criterion_text': criterion_text,\n"
    "        'requirement_text': requirement_text,\n"
    "        'interface': interface,\n"
    "        'glossary': glossary,\n"
    "        'dependency_interfaces': {},\n"
    "    }\n"
)


def build_fixture(repo_root, assembler_log):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    write(repo_root / "specs" / "product" / "mix.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "mixer"
    write(comp / "component.md", COMPONENT)
    write(comp / "requirements" / "R-MIXER-001.md", REQ_1)
    write(comp / "requirements" / "R-MIXER-002.md", REQ_2)
    write(comp / "acceptance" / "AC-MIXER-001.md", AC_1)
    write(comp / "acceptance" / "AC-MIXER-002.md", AC_2)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "constraints.md", CONSTRAINTS)
    write(repo_root / "gen" / "mixer" / "mixer.py", MODULE)
    assembler_source = "LOG_PATH = " + repr(str(assembler_log)) + "\n" + ASSEMBLER_BODY
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )


def make_author(log_path):
    contents = {"AC-MIXER-001": TEST_BLEND, "AC-MIXER-002": TEST_BOTH}

    def author(bundle):
        criterion_id = field(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("author " + criterion_id + "\n")
        filename = "test_" + criterion_id.lower().replace("-", "_") + ".py"
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/mixer/generated-test/" + filename,
                "content": contents[criterion_id],
            },
        }

    return author


def test_mutation_score_is_union_of_both_generated_tests(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    author_log = logs / "author.log"
    build_fixture(repo_root, assembler_log)

    report = verifier_orchestrator.verify(
        "comp-mixer", repo_root, test_author=make_author(author_log)
    )

    # Both stand-in test files were authored and both pass on the real code.
    authored = author_log.read_text(encoding="utf-8").splitlines()
    assert sorted(authored) == ["author AC-MIXER-001", "author AC-MIXER-002"]

    criteria = {field(c, "id"): c for c in field(report, "criteria")}
    assert field(criteria["AC-MIXER-001"], "result") == "pass"
    assert field(criteria["AC-MIXER-002"], "result") == "pass"

    assert field(report, "mutation_error") is None
    score = field(report, "mutation_score")
    assert score is not None

    # Six mutants in total: three in blend, three in both. Each test kills
    # all of its own function's mutants and none of the other's, so either
    # test's isolated score against the whole module is 0.5; the union of
    # both tests kills every mutant.
    assert score > 0.5
    assert score >= 0.8
    assert score == pytest.approx(1.0)