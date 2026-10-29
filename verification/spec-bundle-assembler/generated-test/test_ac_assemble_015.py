"""AC-ASSEMBLE-015 (covers R-ASSEMBLE-013).

A dependency's `dependency_interfaces` entry resolves, one level deep,
any data type its own interface/ content names but does not own:
uniquely-owned types are appended under a heading naming the type and
its real owner, while unresolved and ambiguous names are skipped
silently, leaving the dependency's own content unchanged.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


FOO_CRITERION_ID = "AC-FOO-001"

BAR_OWN_MARKER = "BAR_OWN_INTERFACE_MARKER_7f3a"
WIDGET_OWN_MARKER = "WIDGET_OWN_CONTENT_MARKER_91c2"
DOOHICKEY_BAZ_MARKER = "DOOHICKEY_BAZ_CONTENT_MARKER_4d10"
DOOHICKEY_QUX_MARKER = "DOOHICKEY_QUX_CONTENT_MARKER_b8e5"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


# ---------------------------------------------------------------------------
# spec-linter precondition (R-ASSEMBLE-005)
# ---------------------------------------------------------------------------


def _load_lint():
    try:
        import spec_linter  # noqa: F401

        return getattr(sys.modules["spec_linter"], "lint", None)
    except ImportError:
        pass
    here = Path(spec_bundle_assembler.__file__).resolve()
    for parent in here.parents:
        for candidate in (
            parent / "gen" / "spec-linter" / "spec_linter.py",
            parent / "gen" / "spec-linter" / "spec_linter" / "__init__.py",
        ):
            if candidate.is_file():
                spec = importlib.util.spec_from_file_location("spec_linter", candidate)
                module = importlib.util.module_from_spec(spec)
                sys.modules["spec_linter"] = module
                spec.loader.exec_module(module)
                return getattr(module, "lint", None)
    return None


_HARD_SEVERITIES = {"hard-fail", "hard_fail", "hardfail", "hard", "error", "fail"}


def _hard_fail_findings(report):
    if isinstance(report, (list, tuple)):
        findings = list(report)
    else:
        findings = _get(report, "findings")
        if findings is None:
            findings = _get(report, "hard_fails") or _get(report, "hard_failures") or []
            return list(findings)
        findings = list(findings)
    hard = []
    for finding in findings:
        severity = _get(finding, "severity")
        if severity is None:
            severity = _get(finding, "level")
        if severity is None:
            severity = _get(finding, "kind")
        if severity is not None and str(severity).strip().lower() in _HARD_SEVERITIES:
            hard.append(finding)
    return hard


def _assert_lint_clean(repo_root):
    lint = _load_lint()
    if lint is None:
        return
    report = lint(None, repo_root)
    hard = _hard_fail_findings(report)
    assert hard == [], f"fixture corpus is not lint-clean: {hard!r}"


# ---------------------------------------------------------------------------
# Synthetic fixture corpus
# ---------------------------------------------------------------------------


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(
    repo_root: Path,
    slug: str,
    prefix: str,
    depends_on=(),
    interface_text=None,
    data_types=None,
):
    comp_id = f"comp-{slug}"
    base = repo_root / "specs" / "components" / slug
    depends = ", ".join(depends_on)
    _write(
        base / "component.md",
        "---\n"
        f"id: {comp_id}\n"
        f"title: {slug.capitalize()} fixture component\n"
        "status: draft\n"
        "owners: [fixture-owner]\n"
        f"depends_on: [{depends}]\n"
        "sealed: true\n"
        f"source_path: legacy/fake-{slug}\n"
        "---\n"
        "\n"
        f"# {slug.capitalize()}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Synthetic fixture component {slug} used only by an automated test.\n",
    )
    req_id = f"R-{prefix}-001"
    _write(
        base / "requirements" / f"{req_id}.md",
        f"# {req_id}\n\n**{req_id}** — The {slug} fixture MUST exist.\n",
    )
    _write(
        base / "acceptance" / f"AC-{prefix}-001.md",
        f"# AC-{prefix}-001\n"
        "\n"
        f"Covers: {req_id}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        f"Given the {slug} fixture\n"
        "When it is inspected\n"
        "Then it exists\n"
        "```\n",
    )
    if interface_text is None:
        interface_text = f"# Library\n\n```\nping_{slug}() -> None\n```\n"
    _write(base / "interface" / "library.md", interface_text)
    for type_name, body in (data_types or {}).items():
        _write(base / "interface" / "data" / f"{type_name}.md", body)
    _write(base / "constraints.md", f"# Constraints\n\nNone for {slug}.\n")
    return interface_text


def _write_glossary(repo_root: Path):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a synthetic test-only corpus entry.\n",
    )


def _dependency_interfaces(repo_root: Path):
    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-foo", FOO_CRITERION_ID, repo_root
    )
    deps = _get(bundle, "dependency_interfaces")
    if deps is None:
        # CriterionBundle is documented narrower than SpecBundle; the
        # dependency_interfaces field itself is defined on SpecBundle.
        full = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
        deps = _get(full, "dependency_interfaces")
    assert deps is not None, "no dependency_interfaces field found"
    assert "comp-bar" in deps, f"comp-bar missing from {list(deps)!r}"
    entry = deps["comp-bar"]
    assert isinstance(entry, str)
    return entry


# ---------------------------------------------------------------------------
# Scenario 1: uniquely-owned type is appended, labeled with its real owner
# ---------------------------------------------------------------------------


def test_uniquely_owned_type_is_appended_labeled_with_real_owner(tmp_path):
    repo_root = tmp_path
    _write_glossary(repo_root)
    _write_component(repo_root, "foo", "FOO", depends_on=["comp-bar"])
    _write_component(
        repo_root,
        "bar",
        "BAR",
        interface_text=(
            "# Library\n"
            "\n"
            f"{BAR_OWN_MARKER}\n"
            "\n"
            "```\n"
            "make_part(name: str) -> Widget\n"
            "```\n"
            "\n"
            "Returns a Widget describing the part.\n"
        ),
    )
    _write_component(
        repo_root,
        "baz",
        "BAZ",
        data_types={
            "Widget": (
                "# `Widget`\n"
                "\n"
                f"{WIDGET_OWN_MARKER}\n"
                "\n"
                "```json\n"
                '{"name": "w1", "size": 3}\n'
                "```\n"
            )
        },
    )
    _assert_lint_clean(repo_root)

    entry = _dependency_interfaces(repo_root)

    assert BAR_OWN_MARKER in entry, "comp-bar's own interface content missing"
    assert WIDGET_OWN_MARKER in entry, "Widget's own documented content not appended"
    assert "comp-baz" in entry, "appended Widget content not labeled with real owner comp-baz"

    widget_pos = entry.index(WIDGET_OWN_MARKER)
    label_region = entry[:widget_pos]
    assert "comp-baz" in label_region, (
        "the comp-baz ownership label must precede Widget's appended content"
    )
    # The label heading names the type itself, after comp-bar's own content.
    after_bar = entry[entry.index(BAR_OWN_MARKER):widget_pos]
    assert "Widget" in after_bar and "comp-baz" in after_bar


# ---------------------------------------------------------------------------
# Scenario 2: unresolved type name is skipped silently
# ---------------------------------------------------------------------------


def test_unresolved_type_name_is_skipped_silently(tmp_path):
    repo_root = tmp_path
    _write_glossary(repo_root)
    _write_component(repo_root, "foo", "FOO", depends_on=["comp-bar"])
    bar_text = _write_component(
        repo_root,
        "bar",
        "BAR",
        interface_text=(
            "# Library\n"
            "\n"
            f"{BAR_OWN_MARKER}\n"
            "\n"
            "```\n"
            "make_thing(name: str) -> Gadget\n"
            "```\n"
            "\n"
            "Returns a Gadget describing the thing.\n"
        ),
    )
    _write_component(repo_root, "baz", "BAZ")
    _assert_lint_clean(repo_root)

    entry = _dependency_interfaces(repo_root)

    assert BAR_OWN_MARKER in entry, "comp-bar's own interface content missing"
    assert "make_thing(name: str) -> Gadget" in entry
    assert entry.count("Gadget") == bar_text.count("Gadget"), (
        "a section was fabricated for the unresolved name Gadget"
    )
    assert "comp-baz" not in entry
    assert "comp-foo" not in entry


# ---------------------------------------------------------------------------
# Scenario 3: ambiguous (multiply-owned) type name is skipped silently
# ---------------------------------------------------------------------------


def test_ambiguous_type_name_is_skipped_silently(tmp_path):
    repo_root = tmp_path
    _write_glossary(repo_root)
    _write_component(repo_root, "foo", "FOO", depends_on=["comp-bar"])
    bar_text = _write_component(
        repo_root,
        "bar",
        "BAR",
        interface_text=(
            "# Library\n"
            "\n"
            f"{BAR_OWN_MARKER}\n"
            "\n"
            "```\n"
            "make_tool(name: str) -> Doohickey\n"
            "```\n"
            "\n"
            "Returns a Doohickey describing the tool.\n"
        ),
    )
    _write_component(
        repo_root,
        "baz",
        "BAZ",
        data_types={
            "Doohickey": f"# `Doohickey`\n\n{DOOHICKEY_BAZ_MARKER}\n",
        },
    )
    _write_component(
        repo_root,
        "qux",
        "QUX",
        data_types={
            "Doohickey": f"# `Doohickey`\n\n{DOOHICKEY_QUX_MARKER}\n",
        },
    )
    _assert_lint_clean(repo_root)

    entry = _dependency_interfaces(repo_root)

    assert BAR_OWN_MARKER in entry, "comp-bar's own interface content missing"
    assert "make_tool(name: str) -> Doohickey" in entry
    assert DOOHICKEY_BAZ_MARKER not in entry, "guessed comp-baz for an ambiguous name"
    assert DOOHICKEY_QUX_MARKER not in entry, "guessed comp-qux for an ambiguous name"
    assert "comp-baz" not in entry
    assert "comp-qux" not in entry
    assert entry.count("Doohickey") == bar_text.count("Doohickey"), (
        "a section was added for the ambiguous name Doohickey"
    )