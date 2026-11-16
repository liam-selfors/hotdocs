import spec_bundle_assembler

import importlib.util
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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


def _assert_lint_clean(repo_root):
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    if hard != 0:
        findings = report["findings"] if isinstance(report, dict) else report.findings
        raise AssertionError(f"fixture is not lint-clean: {findings!r}")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"


def _write_glossary(repo_root):
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)


def _write_component(repo_root, slug, depends_on, library_md, data_files=None):
    """Write one complete, lint-shaped sealed component."""
    upper = slug.upper()
    title = slug.capitalize()
    comp_dir = repo_root / "specs" / "components" / slug
    deps = "[" + ", ".join(depends_on) + "]"
    component_md = (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        f"depends_on: {deps}\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{title} doubles a number.\n"
    )
    _write(comp_dir / "component.md", component_md)

    req_id = f"R-{upper}-001"
    ac_id = f"AC-{upper}-001"
    _write(
        comp_dir / "requirements" / f"{req_id}.md",
        f"# {req_id}\n\n**{req_id}** — `{slug}(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp_dir / "acceptance" / f"{ac_id}.md",
        f"# {ac_id}\n"
        "\n"
        f"Covers: {req_id}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        f"When {slug}(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(comp_dir / "interface" / "library.md", library_md)
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    for name, text in (data_files or {}).items():
        _write(comp_dir / "interface" / "data" / f"{name}.md", text)
    return ac_id


def _plain_library(slug):
    return "# Library\n\n```\n" + f"{slug}(x: int) -> int\n" + "```\n"


# comp-bar's own interface names "Widget" (scenario 1/3) but never owns it.
BAR_LIBRARY_WIDGET = (
    "# Library\n"
    "\n"
    "```\n"
    "make_widget(label: str) -> Widget\n"
    "```\n"
    "\n"
    "Returns a new Widget for the given label.\n"
)

# comp-bar's own interface names "Gadget", which nobody in the corpus owns.
BAR_LIBRARY_GADGET = (
    "# Library\n"
    "\n"
    "```\n"
    "make_gadget(label: str) -> Gadget\n"
    "```\n"
    "\n"
    "Returns a new Gadget for the given label.\n"
)

BAZ_WIDGET_SENTINEL = "baz-widget-doc-sentinel-7f3a"
QUX_WIDGET_SENTINEL = "qux-widget-doc-sentinel-91c2"

BAZ_WIDGET_MD = (
    "# `Widget`\n"
    "\n"
    "A record with a `label` field and a `size` field.\n"
    "\n"
    f"Marker: {BAZ_WIDGET_SENTINEL}\n"
)

QUX_WIDGET_MD = (
    "# `Widget`\n"
    "\n"
    "A different record with a `label` field only.\n"
    "\n"
    f"Marker: {QUX_WIDGET_SENTINEL}\n"
)


def _dep_entry(repo_root, dep_ac):
    bundle = spec_bundle_assembler.assemble_criterion("comp-dep", dep_ac, repo_root)
    dep_ifaces = field(bundle, "dependency_interfaces")
    assert "comp-bar" in dep_ifaces, f"comp-bar missing from {list(dep_ifaces)!r}"
    entry = dep_ifaces["comp-bar"]
    assert isinstance(entry, str)
    return entry


# ---------------------------------------------------------------------------
# Scenario 1: a uniquely-owned referenced type is appended, labeled with owner
# ---------------------------------------------------------------------------

def test_referenced_type_owned_elsewhere_is_appended_with_owner_label(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_glossary(repo_root)
    _write_component(repo_root, "bar", [], BAR_LIBRARY_WIDGET)
    _write_component(
        repo_root, "baz", [], _plain_library("baz"), data_files={"Widget": BAZ_WIDGET_MD}
    )
    dep_ac = _write_component(repo_root, "dep", ["comp-bar"], _plain_library("dep"))

    _assert_lint_clean(repo_root)

    entry = _dep_entry(repo_root, dep_ac)
    own = BAR_LIBRARY_WIDGET.strip()

    # comp-bar's own interface content is present.
    assert own in entry

    # Widget's own documented content (from comp-baz) is appended.
    assert BAZ_WIDGET_SENTINEL in entry
    assert "A record with a `label` field and a `size` field." in entry
    assert entry.index(own) < entry.index(BAZ_WIDGET_SENTINEL)

    # ...under a label naming both the type and its real owner, comp-baz.
    appended = entry[entry.index(own) + len(own):]
    label_lines = [
        line for line in appended.splitlines() if "Widget" in line and "comp-baz" in line
    ]
    assert label_lines, (
        "no label naming both 'Widget' and its owner 'comp-baz' in the appended "
        f"section:\n{appended}"
    )
    label_pos = appended.index(label_lines[0])
    assert label_pos < appended.index(BAZ_WIDGET_SENTINEL), (
        "the owner label must precede Widget's appended content"
    )


# ---------------------------------------------------------------------------
# Scenario 2: an unresolved name is skipped silently — nothing fabricated
# ---------------------------------------------------------------------------

def test_unresolved_type_name_adds_no_section(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_glossary(repo_root)
    _write_component(repo_root, "bar", [], BAR_LIBRARY_GADGET)
    dep_ac = _write_component(repo_root, "dep", ["comp-bar"], _plain_library("dep"))

    _assert_lint_clean(repo_root)

    entry = _dep_entry(repo_root, dep_ac)
    own = BAR_LIBRARY_GADGET.strip()

    # comp-bar's own content, unchanged, and nothing else.
    assert own in entry
    assert entry.replace(own, "", 1).strip() == "", (
        f"unexpected extra content in comp-bar's entry:\n{entry}"
    )
    # No fabricated section for the unresolved name.
    assert entry.count("Gadget") == own.count("Gadget")


# ---------------------------------------------------------------------------
# Scenario 3: an ambiguously-owned name is skipped silently — never a guess
# ---------------------------------------------------------------------------

def test_ambiguously_owned_type_name_adds_no_section(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_glossary(repo_root)
    _write_component(repo_root, "bar", [], BAR_LIBRARY_WIDGET)
    _write_component(
        repo_root, "baz", [], _plain_library("baz"), data_files={"Widget": BAZ_WIDGET_MD}
    )
    _write_component(
        repo_root, "qux", [], _plain_library("qux"), data_files={"Widget": QUX_WIDGET_MD}
    )
    dep_ac = _write_component(repo_root, "dep", ["comp-bar"], _plain_library("dep"))

    _assert_lint_clean(repo_root)

    entry = _dep_entry(repo_root, dep_ac)
    own = BAR_LIBRARY_WIDGET.strip()

    # comp-bar's own content, unchanged, and nothing else.
    assert own in entry
    assert entry.replace(own, "", 1).strip() == "", (
        f"unexpected extra content in comp-bar's entry:\n{entry}"
    )
    # Neither claimant's Widget documentation was guessed in.
    assert BAZ_WIDGET_SENTINEL not in entry
    assert QUX_WIDGET_SENTINEL not in entry
    assert "comp-baz" not in entry
    assert "comp-qux" not in entry
    assert entry.count("Widget") == own.count("Widget")