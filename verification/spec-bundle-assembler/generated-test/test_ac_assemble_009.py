import dataclasses
from pathlib import Path

import spec_bundle_assembler


COMPONENT_ID = "comp-widget"
SLUG = "widget"

GLOSSARY_MARKER = "GLOSSARY_MARKER_7f3a91"
INTERFACE_MARKER = "INTERFACE_MARKER_c41d02"
CRITERION_ONE_MARKER = "CRITERION_ONE_MARKER_88b2e4"
CRITERION_TWO_MARKER = "CRITERION_TWO_MARKER_19aa6c"
REQUIREMENT_ONE_MARKER = "REQUIREMENT_ONE_MARKER_5e0c7b"
REQUIREMENT_TWO_MARKER = "REQUIREMENT_TWO_MARKER_d2f813"
CONSTRAINTS_MARKER = "CONSTRAINTS_MARKER_0b9e55"
GEN_MARKER = "GEN_MARKER_a6c3f0"
GEN_DATA_MARKER = "GEN_DATA_MARKER_31e7d9"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


def _all_text(value, _seen=None):
    """Recursively stringify every piece of content reachable from value."""
    if _seen is None:
        _seen = set()
    if id(value) in _seen:
        return ""
    _seen.add(id(value))
    if value is None:
        return ""
    if isinstance(value, (str, bytes)):
        return value.decode("utf-8", "replace") if isinstance(value, bytes) else value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            parts.append(_all_text(k, _seen))
            parts.append(_all_text(v, _seen))
        return "\n".join(parts)
    if isinstance(value, (list, tuple, set, frozenset)):
        return "\n".join(_all_text(v, _seen) for v in value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return "\n".join(
            _all_text(getattr(value, f.name), _seen) for f in dataclasses.fields(value)
        )
    if hasattr(value, "__dict__"):
        return _all_text(dict(vars(value)), _seen)
    if hasattr(value, "_asdict"):
        return _all_text(value._asdict(), _seen)
    return str(value)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    specs = repo_root / "specs"
    comp_dir = specs / "components" / SLUG

    _write(
        specs / "glossary.md",
        "---\n"
        "id: glossary\n"
        "title: Glossary\n"
        "status: draft\n"
        "owners: [someone]\n"
        "---\n\n"
        "# Glossary\n\n"
        f"- **Widget** — a synthetic test thing. {GLOSSARY_MARKER}\n",
    )

    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: {COMPONENT_ID}\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [someone]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/fake_widget_src\n"
        "---\n\n"
        "# Widget\n\n"
        "## Purpose\n\n"
        "A synthetic component used only as a test fixture.\n",
    )

    _write(
        comp_dir / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n"
        f"**R-WIDGET-001** — MUST frobnicate the widget. {REQUIREMENT_ONE_MARKER}\n",
    )
    _write(
        comp_dir / "requirements" / "R-WIDGET-002.md",
        "# R-WIDGET-002\n\n"
        f"**R-WIDGET-002** — MUST defrobnicate the widget. {REQUIREMENT_TWO_MARKER}\n",
    )

    _write(
        comp_dir / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is frobnicated\n"
        f"Then it is frobnicated {CRITERION_ONE_MARKER}\n"
        "```\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-WIDGET-002.md",
        "# AC-WIDGET-002\n\n"
        "Covers: R-WIDGET-002\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a frobnicated widget\n"
        "When it is defrobnicated\n"
        f"Then it is defrobnicated {CRITERION_TWO_MARKER}\n"
        "```\n",
    )

    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n"
        "```\n"
        "frobnicate(widget: str) -> str\n"
        "```\n\n"
        f"{INTERFACE_MARKER}\n",
    )

    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n"
        f"- Must run fast. {CONSTRAINTS_MARKER}\n",
    )

    _write(
        repo_root / "gen" / SLUG / "widget.py",
        f'# {GEN_MARKER}\n'
        'def frobnicate(widget):\n'
        f'    return "{GEN_MARKER}"\n',
    )
    _write(
        repo_root / "gen" / SLUG / "data.txt",
        f"{GEN_DATA_MARKER}\n",
    )


def test_ac_assemble_009_criterion_bundle_is_narrow(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion(
        COMPONENT_ID, "AC-WIDGET-001", repo_root
    )
    assert bundle is not None

    # Identity fields.
    assert _get(bundle, "component_id") == COMPONENT_ID
    assert _get(bundle, "criterion_id") == "AC-WIDGET-001"
    assert _get(bundle, "covers") == "R-WIDGET-001"

    # The criterion's own text.
    criterion_text = _get(bundle, "criterion_text")
    assert isinstance(criterion_text, str)
    assert CRITERION_ONE_MARKER in criterion_text
    assert CRITERION_TWO_MARKER not in criterion_text

    # Its covered requirement's text.
    requirement_text = _get(bundle, "requirement_text")
    assert isinstance(requirement_text, str)
    assert REQUIREMENT_ONE_MARKER in requirement_text
    assert REQUIREMENT_TWO_MARKER not in requirement_text

    # The interface.
    interface = _get(bundle, "interface")
    assert INTERFACE_MARKER in _all_text(interface)

    # The glossary.
    glossary = _get(bundle, "glossary")
    assert GLOSSARY_MARKER in _all_text(glossary)

    # No field derived from gen/<component>/, any other requirements/ file,
    # or constraints.md — anywhere in the bundle.
    everything = _all_text(bundle)
    assert GEN_MARKER not in everything
    assert GEN_DATA_MARKER not in everything
    assert REQUIREMENT_TWO_MARKER not in everything
    assert CONSTRAINTS_MARKER not in everything
    assert CRITERION_TWO_MARKER not in everything

    # SpecBundle-only fields carrying forbidden content must not be present
    # (or, if present at all, must be empty).
    for forbidden in ("constraints", "hint_code", "spec"):
        if _has_field(bundle, forbidden):
            assert not _get(bundle, forbidden), (
                f"CriterionBundle unexpectedly carries non-empty {forbidden!r}"
            )


def test_ac_assemble_009_other_criterion_is_symmetric(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion(
        COMPONENT_ID, "AC-WIDGET-002", repo_root
    )

    assert _get(bundle, "criterion_id") == "AC-WIDGET-002"
    assert _get(bundle, "covers") == "R-WIDGET-002"
    assert CRITERION_TWO_MARKER in _get(bundle, "criterion_text")
    assert REQUIREMENT_TWO_MARKER in _get(bundle, "requirement_text")
    assert INTERFACE_MARKER in _all_text(_get(bundle, "interface"))
    assert GLOSSARY_MARKER in _all_text(_get(bundle, "glossary"))

    everything = _all_text(bundle)
    assert GEN_MARKER not in everything
    assert GEN_DATA_MARKER not in everything
    assert REQUIREMENT_ONE_MARKER not in everything
    assert CRITERION_ONE_MARKER not in everything
    assert CONSTRAINTS_MARKER not in everything