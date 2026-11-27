# hotdocs-criterion: sha256:b6bb19c251bceee85952833253fbace6f832056e6cee8b24205eea7bf5109d7c
import re
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    words = ["word" + str(i) for i in range(160)]
    purpose_text = " ".join(words)
    assert len(purpose_text.split()) == 160
    # No decision citation anywhere in the Purpose text.
    assert re.search(r"\bD\d+\b", purpose_text) is None

    component_md = (
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "---\n"
        + "\n"
        + "# Foo\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + purpose_text
        + "\n"
        + "\n"
        + "## Rationale\n"
        + "\n"
        + "Short.\n"
    )
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(comp_dir / "component.md", component_md)
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        + "```gherkin\nGiven foo\nWhen it runs\nThen it does one thing\n```\n",
    )
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Thing** — a thing.\n",
    )

    lines = component_md.splitlines()
    heading_line = lines.index("## Purpose") + 1
    return heading_line


def test_ac_size_004_purpose_over_hard_fail_threshold(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    heading_line = _build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size_004 = [f for f in findings if field(f, "rule_id") == "R-SIZE-004"]
    assert size_004, "expected an R-SIZE-004 finding, got: " + repr(findings)

    fails = [f for f in size_004 if field(f, "severity") == "fail"]
    assert len(fails) == 1, repr(size_004)
    finding = fails[0]

    assert field(finding, "file") == "specs/components/foo/component.md"
    line = field(finding, "line")
    assert isinstance(line, int)
    assert line == heading_line
    assert field(finding, "message") == (
        "foo: Purpose section has 160 words, above the fail threshold of 150 "
        "(specs/architecture/size-caps.md)"
    )