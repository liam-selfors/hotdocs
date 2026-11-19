# hotdocs-criterion: sha256:a461be5e27324d62ee35ef17872a075b470ab069c50a8b70974dd26059bd74d5
import os
import time
from pathlib import Path

import criterion_compiler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "---\n"
        + "\n"
        + "# Foo\n"
        + "\n"
        + "A small fixture component.\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        + "\n"
        + "**R-FOO-001** — `greet` MUST return a greeting.\n",
    )
    write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        + "\n"
        + "**R-FOO-002** — A fixture value MUST be preserved.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        + "\n"
        + "```\n"
        + "greet(name: str, punctuation: str = \"!\") -> str\n"
        + "```\n"
        + "\n"
        + "`greet` returns a greeting.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        + "\n"
        + "Covers: R-FOO-001\n"
        + "Kind: compiled\n"
        + "\n"
        + "```gherkin\n"
        + "Given a payload is \"world\"\n"
        + "When greet is invoked with {\"name\": payload}\n"
        + "Then length equals 12\n"
        + "```\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        + "\n"
        + "Covers: R-FOO-002\n"
        + "Kind: compiled\n"
        + "\n"
        + "```gherkin\n"
        + "Given a count is 3\n"
        + "Then count equals 3\n"
        + "```\n",
    )


def snapshot(out_dir):
    result = {}
    for p in sorted(out_dir.rglob("*")):
        if p.is_file():
            st = os.stat(p)
            result[str(p.relative_to(out_dir))] = (st.st_mtime_ns, p.read_bytes())
    return result


def test_recompile_unchanged_content_does_not_touch_outputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    out_dir = tmp_path / "out"

    report1 = criterion_compiler.compile("comp-foo", repo_root, "pytest", out_dir)
    outputs1 = field(report1, "outputs")
    compiled1 = [o for o in outputs1 if field(o, "status") == "compiled"]
    assert compiled1, "fixture should compile at least one criterion: " + repr(outputs1)

    before = snapshot(out_dir)
    assert before, "first compile should write output files"

    # Ensure any rewrite would be observable even on coarse-mtime filesystems.
    time.sleep(1.5)

    report2 = criterion_compiler.compile("comp-foo", repo_root, "pytest", out_dir)
    outputs2 = field(report2, "outputs")
    compiled2 = [o for o in outputs2 if field(o, "status") == "compiled"]
    assert len(compiled2) == len(compiled1)

    after = snapshot(out_dir)

    for name, (mtime_ns, content) in before.items():
        assert name in after, "output file disappeared on recompile: " + repr(name)
        new_mtime_ns, new_content = after[name]
        assert new_content == content, "content changed for " + repr(name)
        assert new_mtime_ns == mtime_ns, "mtime changed for " + repr(name)