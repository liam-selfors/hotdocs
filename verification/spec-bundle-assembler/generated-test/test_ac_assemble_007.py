import hashlib

import spec_bundle_assembler


def _get(bundle, name):
    return bundle.get(name) if isinstance(bundle, dict) else getattr(bundle, name, None)


def _write(root, rel_path, content):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_corpus(repo_root):
    _write(
        repo_root,
        "specs/glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )

    _write(
        repo_root,
        "specs/components/foo/component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    _write(
        repo_root,
        "specs/components/foo/requirements/R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        repo_root,
        "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        repo_root,
        "specs/components/foo/interface/library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(
        repo_root,
        "specs/components/foo/constraints.md",
        "# Constraints\n\nNone.\n",
    )
    _write(repo_root, "legacy/foo/foo.py", "def foo(x): return 2 * x\n")

    _write(
        repo_root,
        "specs/components/bar/component.md",
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/bar/\n"
        "depends_on: [comp-foo]\n"
        "---\n"
        "\n"
        "# Bar\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Bar uses Foo.\n",
    )
    _write(
        repo_root,
        "specs/components/bar/requirements/R-BAR-001.md",
        "# R-BAR-001\n\n**R-BAR-001** — `bar(x)` MUST return `foo(x) + 1`.\n",
    )
    _write(
        repo_root,
        "specs/components/bar/acceptance/AC-BAR-001.md",
        "# AC-BAR-001\n"
        "\n"
        "Covers: R-BAR-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When bar(x) is called\n"
        "Then it returns 5\n"
        "```\n",
    )
    _write(
        repo_root,
        "specs/components/bar/interface/library.md",
        "# Library\n\n```\nbar(x: int) -> int\n```\n",
    )
    _write(
        repo_root,
        "specs/components/bar/constraints.md",
        "# Constraints\n\nNone.\n",
    )
    _write(repo_root, "legacy/bar/bar.py", "def bar(x): return foo(x) + 1\n")


_HASHED_PATHS = [
    "legacy/foo/foo.py",
    "specs/components/bar/component.md",
    "specs/components/bar/constraints.md",
    "specs/components/bar/interface/library.md",
    "specs/components/bar/requirements/R-BAR-001.md",
    "specs/components/foo/component.md",
    "specs/components/foo/interface/library.md",
    "specs/glossary.md",
]


def _expected_hash(repo_root, mode):
    stream = mode.encode("utf-8") + b"\x00"
    for rel in sorted(set(_HASHED_PATHS)):
        data = (repo_root / rel).read_bytes()
        stream += rel.encode("utf-8") + b"\x00" + data + b"\x00"
    return "sha256:" + hashlib.sha256(stream).hexdigest()


def test_spec_bundle_hash_matches_defined_stream(tmp_path):
    repo_root = tmp_path
    _build_corpus(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    actual_hash = _get(bundle, "spec_bundle_hash")

    assert actual_hash == _expected_hash(repo_root, "cold")


def test_spec_bundle_hash_unchanged_by_dependency_provenance_manifest(tmp_path):
    repo_root = tmp_path
    _build_corpus(repo_root)

    bundle_before = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    hash_before = _get(bundle_before, "spec_bundle_hash")

    _write(repo_root, "legacy/foo/.provenance.json", '{"anything": "goes"}')

    bundle_after = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    hash_after = _get(bundle_after, "spec_bundle_hash")

    assert hash_after == hash_before


def test_spec_bundle_hash_changes_when_dependency_code_changes(tmp_path):
    repo_root = tmp_path
    _build_corpus(repo_root)

    bundle_before = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    hash_before = _get(bundle_before, "spec_bundle_hash")

    foo_py = repo_root / "legacy/foo/foo.py"
    foo_py.write_text(
        foo_py.read_text(encoding="utf-8") + "\n# extra line\n", encoding="utf-8"
    )

    bundle_after = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    hash_after = _get(bundle_after, "spec_bundle_hash")

    assert hash_after != hash_before