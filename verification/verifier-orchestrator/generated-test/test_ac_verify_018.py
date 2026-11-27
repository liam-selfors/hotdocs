# hotdocs-criterion: sha256:130842e9706a2ba30f5ef06b906315867f55806887c4fd847f45091eff852807
"""AC-VERIFY-018: a criterion id with a lowercase letter suffix is kept exactly.

Covers R-VERIFY-016: the id is taken exactly from the file's `# AC-...`
heading, including a suffix such as `AC-FOO-003b`, and passed unchanged
everywhere, including to `assemble_criterion`.
"""

from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GENERATED_TEST_SOURCE = (
    "def test_widget_counts_one():\n"
    "    assert 1 == 1\n"
)


def build_fixture(repo_root, assembler_log):
    comp = repo_root / "specs" / "components" / "foo"

    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a countable thing.\n",
    )

    write(
        repo_root / "specs" / "product" / "foo.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo Capability\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "---\n"
        "\n"
        "# Foo Capability\n"
        "\n"
        "Counting widgets.\n",
    )

    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Counts widgets.\n",
    )

    write(
        comp / "requirements" / "R-FOO-003.md",
        "# R-FOO-003\n"
        "\n"
        "**R-FOO-003** — A widget MUST count as one.\n",
    )

    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "The module `foo` exposes nothing yet.\n",
    )

    write(
        comp / "acceptance" / "AC-FOO-003b.md",
        "# AC-FOO-003b\n"
        "\n"
        "Covers: R-FOO-003\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is counted\n"
        "Then it counts as one\n"
        "```\n",
    )

    # The component's own code: empty, the generated test imports nothing.
    write(repo_root / "gen" / "foo" / "foo.py", "")

    # spec-bundle-assembler stand-in: records each assemble_criterion call.
    assembler_source = (
        "LOG_PATH = " + repr(str(assembler_log)) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(component_id + '|' + criterion_id + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr("R-FOO-003") + ",\n"
        "        'criterion_text': " + repr("Given a widget\nWhen it is counted\nThen it counts as one") + ",\n"
        "        'requirement_text': " + repr("**R-FOO-003** — A widget MUST count as one.") + ",\n"
        "        'interface': " + repr("# Library\n\nThe module `foo` exposes nothing yet.") + ",\n"
        "        'glossary': " + repr("# Glossary") + ",\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )

    # test-probe stand-in: always sound, no findings.
    probe_source = (
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings)}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    return ProbeReport()\n"
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source)


def make_author_stub(author_log):
    def author_stub(bundle):
        criterion_id = field(bundle, "criterion_id")
        component_id = field(bundle, "component_id")
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write(str(component_id) + "|" + str(criterion_id) + "\n")
        return {
            "component_id": component_id,
            "criterion_id": criterion_id,
            "model": "stub-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/foo/generated-test/test_ac_foo_003b.py",
                "content": GENERATED_TEST_SOURCE,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return author_stub


def read_log(path):
    path = Path(path)
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_suffixed_criterion_id_is_kept_exactly(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    author_log = logs / "author.log"

    build_fixture(repo_root, assembler_log)

    report = verifier_orchestrator.verify(
        "comp-foo",
        repo_root,
        judge=None,
        test_author=make_author_stub(author_log),
    )

    criteria = field(report, "criteria")
    ids = [field(c, "id") for c in criteria]
    assert ids == ["AC-FOO-003b"], ids

    entry = criteria[0]
    assert field(entry, "id") == "AC-FOO-003b"
    assert field(entry, "kind") == "generated-test"

    # The JSON form carries the same exact id.
    as_dict = report.to_dict()
    assert [c["id"] for c in as_dict["criteria"]] == ["AC-FOO-003b"]

    # test_author was called with a bundle assembled for "AC-FOO-003b".
    author_calls = read_log(author_log)
    assert author_calls, "test_author was never called"
    for line in author_calls:
        assert line == "comp-foo|AC-FOO-003b", author_calls

    # assemble_criterion received the id unchanged on every call.
    assembler_calls = read_log(assembler_log)
    assert assembler_calls, "assemble_criterion was never called"
    for line in assembler_calls:
        component_id, criterion_id = line.split("|", 1)
        assert criterion_id == "AC-FOO-003b", assembler_calls