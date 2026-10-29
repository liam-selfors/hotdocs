"""AC-ASSEMBLE-002 (covers R-ASSEMBLE-002).

Given a component that depends_on another component with its own
component.md, requirements/, and constraints.md, when assemble runs for
the dependent component, then dependency_interfaces contains only the
dependency's interface/ content, and contains neither its
component.md/requirements/ nor its constraints.md.
"""

import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


DEP_ID = "comp-dep-lib"
DEP_SLUG = "dep-lib"
APP_ID = "comp-app-user"
APP_SLUG = "app-user"

DEP_INTERFACE_MARKER = "DEPIFACEMARKER7781"
DEP_PURPOSE_MARKER = "DEPPURPOSEMARKER4412"
DEP_COMPONENT_BODY_MARKER = "DEPCOMPONENTBODYMARKER9023"
DEP_COMPONENT_TITLE_MARKER = "DEPTITLEMARKER3310"
DEP_REQUIREMENT_MARKER = "DEPREQMARKER5567"
DEP_CONSTRAINTS_MARKER = "DEPCONSTRAINTSMARKER2289"
DEP_ACCEPTANCE_MARKER = "DEPACCEPTMARKER6634"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _as_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(f"{k}\n{_as_text(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return "\n".join(_as_text(v) for v in value)
    return str(value)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "---\n"
        "id: glossary\n"
        "title: Glossary\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n"
        "\n"
        "# Glossary\n"
        "\n"
        "- **Widget** — a synthetic fixture term.\n",
    )

    # --- The dependency: comp-dep-lib ---
    dep_dir = repo_root / "specs" / "components" / DEP_SLUG
    _write(
        dep_dir / "component.md",
        "---\n"
        f"id: {DEP_ID}\n"
        f"title: Dep Lib {DEP_COMPONENT_TITLE_MARKER}\n"
        "status: draft\n"
        "owners: [tester]\n"
        "sealed: true\n"
        "source_path: legacy/fake_dep_lib\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Dep Lib\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Provides widgets. {DEP_PURPOSE_MARKER}\n"
        "\n"
        "## Rationale\n"
        "\n"
        f"Internal rationale that a dependent must never see. "
        f"{DEP_COMPONENT_BODY_MARKER}\n",
    )
    _write(
        dep_dir / "requirements" / "R-DEP-001.md",
        "# R-DEP-001\n"
        "\n"
        "**R-DEP-001** — The library MUST return a widget. "
        f"{DEP_REQUIREMENT_MARKER}\n",
    )
    _write(
        dep_dir / "acceptance" / "AC-DEP-001.md",
        "# AC-DEP-001\n"
        "\n"
        "Covers: R-DEP-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a request\n"
        "When the library is called\n"
        f"Then a widget is returned {DEP_ACCEPTANCE_MARKER}\n"
        "```\n",
    )
    _write(
        dep_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "make_widget(name: str) -> dict\n"
        "```\n"
        "\n"
        f"Public contract text. {DEP_INTERFACE_MARKER}\n",
    )
    _write(
        dep_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        f"- Must not use the network. {DEP_CONSTRAINTS_MARKER}\n",
    )

    # --- The dependent: comp-app-user ---
    app_dir = repo_root / "specs" / "components" / APP_SLUG
    _write(
        app_dir / "component.md",
        "---\n"
        f"id: {APP_ID}\n"
        "title: App User\n"
        "status: draft\n"
        "owners: [tester]\n"
        "sealed: true\n"
        "source_path: legacy/fake_app_user\n"
        f"depends_on: [{DEP_ID}]\n"
        "---\n"
        "\n"
        "# App User\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Uses widgets from the dependency.\n",
    )
    _write(
        app_dir / "requirements" / "R-APP-001.md",
        "# R-APP-001\n"
        "\n"
        "**R-APP-001** — The app MUST display a widget.\n",
    )
    _write(
        app_dir / "acceptance" / "AC-APP-001.md",
        "# AC-APP-001\n"
        "\n"
        "Covers: R-APP-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When the app renders\n"
        "Then the widget is displayed\n"
        "```\n",
    )
    _write(
        app_dir / "interface" / "cli.md",
        "# CLI\n"
        "\n"
        "```\n"
        "app-user show\n"
        "```\n",
    )
    _write(
        app_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "- None beyond the defaults.\n",
    )


def _load_lint():
    """Locate spec-linter's real lint() if it is reachable; None otherwise."""
    try:
        import spec_linter  # type: ignore

        return getattr(spec_linter, "lint", None)
    except Exception:
        pass
    here = Path(__file__).resolve()
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


def _is_hard_fail(finding) -> bool:
    for name in ("severity", "level", "kind", "status"):
        value = _get(finding, name)
        if isinstance(value, str) and value.lower().replace("_", "-") in (
            "hard-fail",
            "hard",
            "error",
            "fail",
        ):
            return True
    hard = _get(finding, "hard_fail")
    return hard is True


def _hard_fail_findings(report):
    findings = _get(report, "findings")
    if findings is None:
        findings = report if isinstance(report, (list, tuple)) else []
    return [f for f in findings if _is_hard_fail(f)]


def test_ac_assemble_002_dependency_interfaces_contains_only_interface(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    lint = _load_lint()
    if lint is not None:
        report = lint(None, repo_root)
        hard = _hard_fail_findings(report)
        assert hard == [], f"fixture is not lint-clean: {hard!r}"

    bundle = spec_bundle_assembler.assemble(APP_ID, repo_root=repo_root, mode="cold")

    assert _get(bundle, "component_id") == APP_ID

    dep_interfaces = _get(bundle, "dependency_interfaces")
    assert dep_interfaces is not None, "bundle has no dependency_interfaces"

    keys = list(dep_interfaces.keys()) if isinstance(dep_interfaces, dict) else [
        k for k in vars(dep_interfaces)
    ]
    assert keys == [DEP_ID], f"unexpected dependency_interfaces keys: {keys!r}"

    dep_text = _as_text(_get(dep_interfaces, DEP_ID))

    # Contains the dependency's interface/ content.
    assert DEP_INTERFACE_MARKER in dep_text
    assert "make_widget(name: str) -> dict" in dep_text

    # Contains none of the dependency's component.md (body, Purpose, or frontmatter).
    assert DEP_COMPONENT_BODY_MARKER not in dep_text
    assert DEP_PURPOSE_MARKER not in dep_text
    assert DEP_COMPONENT_TITLE_MARKER not in dep_text

    # Contains none of the dependency's requirements/.
    assert DEP_REQUIREMENT_MARKER not in dep_text
    assert "R-DEP-001" not in dep_text

    # Contains none of the dependency's constraints.md.
    assert DEP_CONSTRAINTS_MARKER not in dep_text

    # And never its acceptance/ either.
    assert DEP_ACCEPTANCE_MARKER not in dep_text

    # The dependency's internals must not leak anywhere else in the
    # dependent's bundle via the fields that carry spec/constraints text.
    for field in ("spec", "constraints", "interface"):
        text = _as_text(_get(bundle, field))
        assert DEP_COMPONENT_BODY_MARKER not in text, field
        assert DEP_REQUIREMENT_MARKER not in text, field
        assert DEP_CONSTRAINTS_MARKER not in text, field