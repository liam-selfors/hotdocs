# hotdocs-criterion: sha256:22db957ef46cdc028242cb438ad3c9c979aa64813f62b283050962054048f3ac
import criterion_compiler

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "---\n"
        + "\n"
        + "# Foo\n"
        + "\n"
        + "A tiny fixture component.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        + "\n"
        + "**R-FOO-001** \u2014 The component MUST double its input.\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        + "\n"
        + "```\n"
        + "double(x: int) -> int\n"
        + "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        + "\n"
        + "Covers: R-FOO-001\n"
        + "Kind: compiled\n"
        + "\n"
        + "```gherkin\n"
        + "Given a n is 2\n"
        + "When double is invoked with {\"x\": n}\n"
        + "Then value equals 4\n"
        + "```\n",
    )


def _compile(repo_root, out_dir):
    try:
        return criterion_compiler.compile("comp-foo", repo_root, "pytest", out_dir)
    except Exception:
        return criterion_compiler.compile("foo", repo_root, "pytest", out_dir)


def test_gate_version_read_from_module_attribute_at_report_time(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    original = criterion_compiler.GATE_VERSION

    first = _compile(repo_root, tmp_path / "out1")
    first_version = field(first, "gate_version")
    assert first_version == original

    monkeypatch.setattr(criterion_compiler, "GATE_VERSION", "criterion-compiler@1.1.0")

    second = _compile(repo_root, tmp_path / "out2")
    second_version = field(second, "gate_version")

    assert second_version == "criterion-compiler@1.1.0"
    assert second_version != first_version