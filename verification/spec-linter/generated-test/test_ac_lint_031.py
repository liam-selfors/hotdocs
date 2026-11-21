# hotdocs-criterion: sha256:ba842ff7c2e6f149ee6556d988f94559c6c4b4aaa2edda0987e39e30385daddc
import spec_linter

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRODUCT = (
    "---\n"
    "id: P-FOO\n"
    "title: Foo works\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Foo works\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A foo can be made.\n"
    "\n"
    "### CS-FOO-001\n"
    "Covers: P-FOO\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given nothing\n"
    "When a foo is made\n"
    "Then it exists\n"
    "```\n"
)


def component_md(slug):
    title = slug.capitalize()
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Makes a " + slug + ".\n"
        "\n"
        "## Scope\n"
        "\n"
        "**In scope:** making a " + slug + ". **Out of scope:** everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "No deltas from `specs/glossary.md`.\n"
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
        "None.\n"
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
        "None.\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )


def plain_requirement(rid, func):
    return (
        "# " + rid + "\n"
        "\n"
        "**" + rid + "** — `" + func + "()` MUST return the string `\"x\"`.\n"
    )


def cli_requirement(rid, slug):
    return (
        "# " + rid + "\n"
        "\n"
        "**" + rid + "** — The command in `interface/cli.md` MUST accept "
        "`--format=json` and `--format json`, MUST treat `--format` with no "
        "value or an unknown argument as a usage error, and MUST exit `0` on "
        "success and `2` on a usage error.\n"
    )


def acceptance(acid, rid):
    return (
        "# " + acid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When the behavior is exercised\n"
        "Then it holds\n"
        "```\n"
    )


def library_md(slug):
    mod = slug.replace("-", "_")
    return (
        "# Library\n"
        "\n"
        "One module file, `" + mod + ".py`.\n"
        "\n"
        "```\n"
        "make_" + mod + "() -> str\n"
        "```\n"
    )


def cli_md(slug):
    return (
        "# CLI\n"
        "\n"
        "```\n"
        + slug + " [--format=json|text]\n"
        "```\n"
    )


CONSTRAINTS = "# Constraints\n\n- **Pure.** No I/O.\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_component(repo_root, slug, mode):
    up = slug.upper()
    base = repo_root / "specs" / "components" / slug
    write(base / "component.md", component_md(slug))
    write(base / "interface" / "library.md", library_md(slug))
    write(base / "interface" / "cli.md", cli_md(slug))
    write(base / "constraints.md", CONSTRAINTS)
    r1 = "R-" + up + "-001"
    a1 = "AC-" + up + "-001"
    if mode == "covered":
        write(base / "requirements" / (r1 + ".md"), cli_requirement(r1, slug))
        write(base / "acceptance" / (a1 + ".md"), acceptance(a1, r1))
    elif mode == "uncovered":
        write(base / "requirements" / (r1 + ".md"),
              plain_requirement(r1, "make_" + slug))
        write(base / "acceptance" / (a1 + ".md"), acceptance(a1, r1))
        r2 = "R-" + up + "-002"
        write(base / "requirements" / (r2 + ".md"), cli_requirement(r2, slug))
    else:
        write(base / "requirements" / (r1 + ".md"),
              plain_requirement(r1, "make_" + slug))
        write(base / "acceptance" / (a1 + ".md"), acceptance(a1, r1))


def owning_slug(finding, slugs):
    file_value = str(field(finding, "file")).replace("\\", "/")
    message = str(field(finding, "message"))
    for slug in slugs:
        if "/components/" + slug + "/" in "/" + file_value:
            return slug
    for slug in slugs:
        if ("comp-" + slug) in message:
            return slug
    return None


def test_ac_lint_031_cli_without_covered_citing_requirement_warns(tmp_path):
    repo_root = tmp_path
    write(repo_root / "specs" / "product" / "foo.md", PRODUCT)
    build_component(repo_root, "alpha", "covered")
    build_component(repo_root, "beta", "uncovered")
    build_component(repo_root, "gamma", "none")

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    lint031 = [f for f in findings if field(f, "rule_id") == "R-LINT-031"]

    slugs = ["alpha", "beta", "gamma"]
    by_slug = {}
    for f in lint031:
        slug = owning_slug(f, slugs)
        assert slug is not None, "unattributable R-LINT-031 finding: %r" % (f,)
        by_slug.setdefault(slug, []).append(f)

    assert "alpha" not in by_slug, by_slug.get("alpha")
    assert len(by_slug.get("beta", [])) == 1, lint031
    assert len(by_slug.get("gamma", [])) == 1, lint031
    assert len(lint031) == 2, lint031

    for slug in ("beta", "gamma"):
        f = by_slug[slug][0]
        assert field(f, "severity") == "warn"
        assert ("comp-" + slug) in str(field(f, "message"))