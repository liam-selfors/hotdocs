"""AC-ASSEMBLE-008: hint mode adds the component's current gen/<component>/
content as a separate ``hint_code`` field, keyed by relative path, and every
other field matches what cold mode would have produced (R-ASSEMBLE-008)."""

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

import spec_bundle_assembler


COMPONENT_ID = "comp-widget"
SLUG = "widget"

GEN_FILES = {
    "widget.py": "# HINT-MARKER-ALPHA\ndef widget():\n    return 42\n",
    "sub/helper.py": "# HINT-MARKER-BETA\ndef helper():\n    return 'help'\n",
}

SPEC_BUNDLE_FIELDS = (
    "component_id",
    "spec_bundle_hash",
    "spec",
    "interface",
    "constraints",
    "dependency_interfaces",
    "dependency_context",
    "dependency_usage",
    "vars",
    "glossary",
)


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def _load_lint():
    try:
        import spec_linter  # type: ignore

        return spec_linter.lint
    except ImportError:
        pass
    here = Path(__file__).resolve()
    for parent in here.parents:
        for candidate in (
            parent / "gen" / "spec-linter" / "spec_linter.py",
            parent / "gen" / "spec-linter" / "spec_linter" / "__init__.py",
        ):
            if candidate.is_file():
                module_name = "spec_linter"
                spec = importlib.util.spec_from_file_location(module_name, candidate)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                return module.lint
    raise RuntimeError("could not locate spec-linter's lint() to check the fixture")


def _hard_fail_findings(report):
    findings = _get(report, "findings", None)
    if findings is None:
        if isinstance(report, (list, tuple)):
            findings = report
        else:
            findings = []
    hard = []
    for finding in findings:
        severity = (
            _get(finding, "severity", None)
            or _get(finding, "level", None)
            or _get(finding, "kind", None)
            or ""
        )
        normalized = str(severity).lower().replace("_", "-").replace(" ", "-")
        if normalized in ("hard-fail", "hard", "error", "fail"):
            hard.append(finding)
    return hard


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"

    _write(
        root / "specs" / "glossary.md",
        """
        ---
        id: glossary
        title: Glossary
        status: draft
        owners: [tester]
        ---

        # Glossary

        - **Widget** — a synthetic fixture thing used only by this test.
        """,
    )

    comp_dir = root / "specs" / "components" / SLUG
    _write(
        comp_dir / "component.md",
        f"""
        ---
        id: {COMPONENT_ID}
        title: Widget
        status: draft
        owners: [tester]
        depends_on: []
        sealed: true
        source_path: legacy/widget-fake
        ---

        # Widget

        ## Purpose

        A synthetic fixture component that produces widgets.
        """,
    )
    _write(
        comp_dir / "requirements" / "R-WIDGET-001.md",
        """
        # R-WIDGET-001

        **R-WIDGET-001** — The widget MUST return 42.
        """,
    )
    _write(
        comp_dir / "acceptance" / "AC-WIDGET-001.md",
        """
        # AC-WIDGET-001

        Covers: R-WIDGET-001
        Kind: generated-test

        ```gherkin
        Given a widget
        When it is called
        Then it returns 42
        ```
        """,
    )
    _write(
        comp_dir / "interface" / "library.md",
        """
        # Library

        ```
        widget() -> int
        ```
        """,
    )
    _write(
        comp_dir / "constraints.md",
        """
        # Constraints

        - Pure Python, no dependencies.
        """,
    )

    for rel, content in GEN_FILES.items():
        target = root / "gen" / SLUG / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    return root


def _normalize_hint_keys(hint_code):
    if isinstance(hint_code, dict):
        items = hint_code.items()
    else:
        items = vars(hint_code).items()
    return {str(k).replace("\\", "/").lstrip("./") if str(k).startswith("./") else str(k).replace("\\", "/"): v
            for k, v in items}


def test_ac_assemble_008_hint_mode_adds_hint_code_only(repo_root: Path):
    lint = _load_lint()
    report = lint(None, repo_root)
    hard = _hard_fail_findings(report)
    assert hard == [], f"fixture corpus is not lint-clean: {hard!r}"

    cold = spec_bundle_assembler.assemble(COMPONENT_ID, repo_root, mode="cold")
    hint = spec_bundle_assembler.assemble(COMPONENT_ID, repo_root, mode="hint")

    # Cold mode carries no hint code.
    assert _get(cold, "hint_code", None) is None

    # Hint mode carries the gen/<component>/ content, keyed by relative path.
    hint_code = _get(hint, "hint_code", None)
    assert hint_code is not None, "hint mode must populate hint_code"
    normalized = _normalize_hint_keys(hint_code)
    for rel, content in GEN_FILES.items():
        assert rel in normalized, (
            f"expected relative path {rel!r} in hint_code keys {sorted(normalized)!r}"
        )
        assert normalized[rel] == content

    # Every other field matches what cold mode produced.
    for field in SPEC_BUNDLE_FIELDS:
        assert _get(hint, field, None) == _get(cold, field, None), (
            f"field {field!r} differs between hint and cold mode"
        )
    assert _get(hint, "component_id", None) == COMPONENT_ID

    # The hint content is never merged into the cold bundle's own fields.
    for field in SPEC_BUNDLE_FIELDS:
        rendered = repr(_get(hint, field, None))
        assert "HINT-MARKER-ALPHA" not in rendered, f"hint code leaked into {field!r}"
        assert "HINT-MARKER-BETA" not in rendered, f"hint code leaked into {field!r}"