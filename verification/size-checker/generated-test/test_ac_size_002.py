# hotdocs-criterion: sha256:3816517cc89585f8f474b2afc9426a3a5933767041b640db5a94104be93476bc
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_component(repo_root, slug, constraints_text):
    upper = slug.upper()
    base = repo_root / "specs" / "components" / slug
    write(
        base / "component.md",
        "---\n"
        + "id: " + "comp-" + slug + "\n"
        + "title: " + slug.capitalize() + "\n"
        + "status: draft\n"
        + "owners: [team]\n"
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
    write(
        base / "requirements" / ("R-" + upper + "-001.md"),
        "**R-" + upper + "-001** — The component MUST do one thing.\n",
    )
    write(
        base / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n"
        + "\n"
        + "Covers: R-" + upper + "-001\n"
        + "Kind: generated-test\n"
        + "\n"
        + "Given a thing When it runs Then it works.\n",
    )
    write(
        base / "interface" / "library.md",
        "# Library\n"
        + "\n"
        + "```\n"
        + "run() -> None\n"
        + "```\n",
    )
    write(base / "constraints.md", constraints_text)


def make_gen_code(repo_root, slug, loc):
    lines = []
    for i in range(loc):
        lines.append("x" + str(i) + " = " + repr(i))
    write(repo_root / "gen" / slug / (slug + "_mod.py"), "\n".join(lines) + "\n")


def test_ac_size_002(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Thing** — a thing.\n",
    )

    # alpha: generated_code_loc and generator_words both over warn
    make_component(repo_root, "alpha", "# Constraints\n\n" + ("word " * 9000).strip() + "\n")
    make_gen_code(repo_root, "alpha", 900)

    # beta: only generated_code_loc over warn
    make_component(repo_root, "beta", "# Constraints\n\nNone.\n")
    make_gen_code(repo_root, "beta", 900)

    findings = size_checker.check(repo_root)

    alpha_002 = [
        f for f in findings
        if field(f, "rule_id") == "R-SIZE-002"
        and str(field(f, "message")).startswith("alpha:")
    ]
    assert len(alpha_002) == 1, findings
    finding = alpha_002[0]
    assert field(finding, "severity") == "warn"
    message = field(finding, "message")
    assert message.startswith(
        "alpha: 2 size-cap dimensions over their warn thresholds at once ("
    ), message
    assert "generated_code_loc=900" in message, message
    assert "generator_words=" in message, message
    assert message.index("generated_code_loc=") < message.index("generator_words="), message
    assert "specs/architecture/size-caps.md" in message, message
    assert message.endswith(
        "; see specs/architecture/size-caps.md's decomposition-signal rule"
    ), message

    beta_002 = [
        f for f in findings
        if field(f, "rule_id") == "R-SIZE-002"
        and str(field(f, "message")).startswith("beta:")
    ]
    assert beta_002 == [], findings

    # Never a hard failure
    for f in findings:
        if field(f, "rule_id") == "R-SIZE-002":
            assert field(f, "severity") == "warn"