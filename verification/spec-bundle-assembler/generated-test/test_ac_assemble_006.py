import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import spec_bundle_assembler


FIELDS = [
    "component_id",
    "spec_bundle_hash",
    "spec",
    "interface",
    "constraints",
    "dependency_interfaces",
    "dependency_context",
    "dependency_usage",
    "vars",
    "glossary",
    "hint_code",
]


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

COMPONENT_MD = (
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
    "Foo doubles a number.\n"
)

REQUIREMENT_MD = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

LIBRARY_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)


def _load_spec_linter():
    gen = next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _to_plain(value):
    if isinstance(value, dict):
        return {str(k): _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _bundle_bytes(bundle) -> bytes:
    data = {name: _to_plain(_field(bundle, name)) for name in FIELDS}
    return json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode(
        "utf-8"
    )


def _assert_lint_clean(repo_root: Path) -> None:
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = (
        report.get("hard_failures")
        if isinstance(report, dict)
        else getattr(report, "hard_failures", None)
    )
    assert hard == 0, f"fixture corpus is not lint-clean: {report}"


def _snapshot(repo_root: Path) -> dict:
    return {
        str(p.relative_to(repo_root)): p.read_bytes()
        for p in sorted(repo_root.rglob("*"))
        if p.is_file() and "specs" in p.relative_to(repo_root).parts
    }


def test_assemble_twice_on_unchanged_corpus_is_byte_identical(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    _assert_lint_clean(repo_root)

    before = _snapshot(repo_root)

    first = spec_bundle_assembler.assemble("comp-foo", repo_root)
    second = spec_bundle_assembler.assemble("comp-foo", repo_root)

    # Corpus really was unchanged between (and by) the two runs.
    assert _snapshot(repo_root) == before

    assert _field(first, "component_id") == "comp-foo"
    assert _field(second, "component_id") == "comp-foo"

    first_hash = _field(first, "spec_bundle_hash")
    second_hash = _field(second, "spec_bundle_hash")
    assert first_hash, "spec_bundle_hash must be populated"
    assert first_hash == second_hash

    for name in FIELDS:
        assert _to_plain(_field(first, name)) == _to_plain(_field(second, name)), (
            f"field {name!r} differs between two assemble runs"
        )

    assert _bundle_bytes(first) == _bundle_bytes(second)


def test_assemble_is_unaffected_by_mtime_only_changes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    _assert_lint_clean(repo_root)

    first = spec_bundle_assembler.assemble("comp-foo", repo_root)

    # Touch every file without changing content: bytes are unchanged,
    # so the bundle must be too.
    future = time.time() + 3600
    for p in repo_root.rglob("*"):
        if p.is_file():
            os.utime(p, (future, future))

    second = spec_bundle_assembler.assemble("comp-foo", repo_root)

    assert _field(first, "spec_bundle_hash") == _field(second, "spec_bundle_hash")
    assert _bundle_bytes(first) == _bundle_bytes(second)