# hotdocs-criterion: sha256:97ab8b3cd7975a5081230c1f9aa3667c8b0cb94cefed809dce3e1102c6c80c9e
import sys
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_component(repo_root, slug, upper, constraints_words, code_lines):
    base = repo_root / "specs" / "components" / slug
    write(
        base / "component.md",
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug.capitalize() + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# " + slug.capitalize() + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A small fixture component used for size checks.\n",
    )
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    write(
        base / "requirements" / (rid + ".md"),
        "# " + rid + "\n\n**" + rid + "** — The component MUST do its one thing.\n",
    )
    write(
        base / "acceptance" / (acid + ".md"),
        "# " + acid + "\n\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )
    write(
        base / "interface" / "library.md",
        "# Library\n\nA short prose description of the library.\n",
    )
    write(
        base / "constraints.md",
        "# Constraints\n\n" + " ".join(["word"] * constraints_words) + "\n",
    )
    lines = []
    for i in range(code_lines):
        lines.append("x" + str(i) + " = " + str(i))
    write(repo_root / "gen" / slug / "big.py", "\n".join(lines) + "\n")


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Thing** — a thing.\n",
    )
    # alpha: generated_code_loc and generator_words both over warn
    make_component(repo_root, "alpha", "ALPHA", 8600, 900)
    # beta: only generated_code_loc over warn
    make_component(repo_root, "beta", "BETA", 20, 900)


def test_ac_size_002(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    findings = size_checker.check(repo_root)
    assert isinstance(findings, list)

    size002 = [f for f in findings if field(f, "rule_id") == "R-SIZE-002"]

    alpha = [
        f for f in size002
        if str(field(f, "message")).startswith("alpha: ")
        or "/alpha/" in str(field(f, "file"))
    ]
    assert len(alpha) == 1, size002
    finding = alpha[0]
    message = str(field(finding, "message"))
    assert field(finding, "severity") == "warn"
    assert message.startswith("alpha: ")
    assert "size-cap dimensions over their warn thresholds at once (" in message
    assert "generated_code_loc=900" in message
    assert "generator_words=" in message
    assert message.index("generated_code_loc=") < message.index("generator_words=")
    assert "specs/architecture/size-caps.md" in message
    assert message.endswith("see specs/architecture/size-caps.md's decomposition-signal rule")
    assert isinstance(field(finding, "line"), int)

    beta = [
        f for f in size002
        if str(field(f, "message")).startswith("beta: ")
        or "/beta/" in str(field(f, "file"))
    ]
    assert beta == [], beta

    # No R-SIZE-002 finding is ever a hard failure.
    for f in size002:
        assert field(f, "severity") == "warn"