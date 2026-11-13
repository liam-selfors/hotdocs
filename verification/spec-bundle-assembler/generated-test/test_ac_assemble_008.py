import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
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
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
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
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")


def _normalize_key(key) -> str:
    k = str(key).replace("\\", "/")
    while k.startswith("./"):
        k = k[2:]
    for prefix in ("gen/foo/",):
        if k.startswith(prefix):
            k = k[len(prefix):]
    return k


def _as_text(value):
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8")
    return value


def test_ac_assemble_008_hint_mode_adds_hint_code_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    gen_files = {
        "foo.py": "def foo(x):\n    return 2 * x\n",
        "sub/helper.txt": "helper content for hint mode\n",
    }
    for rel, content in gen_files.items():
        _write(repo_root / "gen" / "foo" / rel, content)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0, [
        (_field(f, "rule_id"), _field(f, "file"), _field(f, "message"))
        for f in (_field(report, "findings") or [])
    ]

    cold = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
    hint = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="hint")

    # Cold mode carries no hint_code.
    assert _field(cold, "hint_code") is None

    # Hint mode carries gen/foo/ content, keyed by relative path.
    hint_code = _field(hint, "hint_code")
    assert hint_code is not None
    hint_map = {_normalize_key(k): _as_text(v) for k, v in dict(hint_code).items()}
    for rel, content in gen_files.items():
        assert rel in hint_map, (rel, sorted(hint_map))
        assert hint_map[rel] == content

    # Every other field except spec_bundle_hash matches cold mode.
    for name in (
        "component_id",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
    ):
        assert _field(hint, name) == _field(cold, name), name

    assert _field(hint, "component_id") == "comp-foo"

    # gen/ content must not leak into the cold bundle's own fields.
    for name in ("spec", "interface", "constraints", "glossary"):
        text = _field(hint, name) or ""
        assert "helper content for hint mode" not in text, name
        assert "return 2 * x" not in text, name

    # spec_bundle_hash differs, since R-ASSEMBLE-007 hashes mode + gen/ in hint mode.
    cold_hash = _field(cold, "spec_bundle_hash")
    hint_hash = _field(hint, "spec_bundle_hash")
    assert isinstance(cold_hash, str) and cold_hash
    assert isinstance(hint_hash, str) and hint_hash
    assert cold_hash != hint_hash