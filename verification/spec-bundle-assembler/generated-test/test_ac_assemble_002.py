# hotdocs-criterion: sha256:0551bdbea48470e69c9d579a55a52915ba76a819449493d737eacc9ad931a4f5
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen"
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FENCE = "```"

BAR_PURPOSE_MARKER = "zqbarpurposemarker"
BAR_REQUIREMENT_MARKER = "zqbarrequirementmarker"
BAR_CONSTRAINTS_MARKER = "zqbarconstraintsmarker"
BAR_INTERFACE_MARKER = "zqbarinterfacemarker"


def build_component(
    repo_root,
    slug,
    comp_id,
    title,
    req_id,
    ac_id,
    depends_on,
    purpose,
    requirement_text,
    interface_sig,
    constraints_text,
):
    comp_dir = repo_root / "specs" / "components" / slug
    write(
        comp_dir / "component.md",
        "---\n"
        + "id: " + comp_id + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "depends_on: " + depends_on + "\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + purpose + "\n",
    )
    write(
        comp_dir / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n"
        + "\n"
        + "**" + req_id + "** — " + requirement_text + "\n",
    )
    write(
        comp_dir / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n"
        + "\n"
        + "Covers: " + req_id + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + FENCE + "gherkin\n"
        + "Given x = 2\n"
        + "When the function is called with x\n"
        + "Then it returns the documented result\n"
        + FENCE + "\n",
    )
    write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        + "\n"
        + FENCE + "\n"
        + interface_sig + "\n"
        + FENCE + "\n",
    )
    write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        + "\n"
        + constraints_text + "\n",
    )
    # Sealed component's real code lives under its source_path, never gen/.
    write(
        repo_root / "legacy" / slug / (slug + ".py"),
        "def " + slug + "(x):\n"
        + "    return x\n",
    )


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        + "\n"
        + "- **Foo** — a test term.\n",
    )
    build_component(
        repo_root,
        slug="bar",
        comp_id="comp-bar",
        title="Bar",
        req_id="R-BAR-001",
        ac_id="AC-BAR-001",
        depends_on="[]",
        purpose="Bar triples a number " + BAR_PURPOSE_MARKER + ".",
        requirement_text="`bar(x)` MUST return `3 * x` " + BAR_REQUIREMENT_MARKER + ".",
        interface_sig="bar(x: int) -> int  # " + BAR_INTERFACE_MARKER,
        constraints_text="None " + BAR_CONSTRAINTS_MARKER + ".",
    )
    build_component(
        repo_root,
        slug="foo",
        comp_id="comp-foo",
        title="Foo",
        req_id="R-FOO-001",
        ac_id="AC-FOO-001",
        depends_on="[comp-bar]",
        purpose="Foo doubles a number.",
        requirement_text="`foo(x)` MUST return `2 * x`.",
        interface_sig="foo(x: int) -> int",
        constraints_text="None.",
    )


def test_dependency_interfaces_contains_only_interface_content(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    dep_ifaces = field(bundle, "dependency_interfaces")
    assert set(dep_ifaces.keys()) == {"comp-bar"}

    bar_iface = dep_ifaces["comp-bar"]
    assert isinstance(bar_iface, str)

    # The dependency's interface/ content is present.
    assert BAR_INTERFACE_MARKER in bar_iface
    assert "bar(x: int) -> int" in bar_iface

    # Never its component.md content.
    assert BAR_PURPOSE_MARKER not in bar_iface
    assert "Bar triples a number" not in bar_iface
    assert "comp-bar" not in bar_iface
    assert "source_path" not in bar_iface
    assert "## Purpose" not in bar_iface

    # Never its requirements/ content.
    assert BAR_REQUIREMENT_MARKER not in bar_iface
    assert "R-BAR-001" not in bar_iface
    assert "MUST return" not in bar_iface

    # Never its constraints.md content.
    assert BAR_CONSTRAINTS_MARKER not in bar_iface
    assert "# Constraints" not in bar_iface

    # No other dict-valued bundle field smuggles the dependency's
    # requirements or constraints into the dependency_interfaces view.
    for value in dep_ifaces.values():
        assert BAR_REQUIREMENT_MARKER not in value
        assert BAR_CONSTRAINTS_MARKER not in value
        assert BAR_PURPOSE_MARKER not in value