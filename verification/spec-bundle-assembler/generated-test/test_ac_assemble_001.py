"""AC-ASSEMBLE-001 — cold-mode SpecBundle includes spec/interface/constraints
content and nothing derived from acceptance/ (covers R-ASSEMBLE-001)."""

import dataclasses
from pathlib import Path

import spec_bundle_assembler


COMPONENT_MD_SENTINEL = "COMPONENT_MD_SENTINEL_b41e9c"
REQUIREMENT_SENTINEL = "REQUIREMENT_SENTINEL_5d02aa"
INTERFACE_SENTINEL = "INTERFACE_SENTINEL_e7713f"
CONSTRAINTS_SENTINEL = "CONSTRAINTS_SENTINEL_9a6c40"
ACCEPTANCE_SENTINEL = "ACCEPTANCE_SENTINEL_7f3a12"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


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
        "owners: [test-owner]\n"
        "---\n"
        "\n"
        "# Glossary\n"
        "\n"
        "- **Widget** — a synthetic fixture term.\n",
    )

    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "depends_on: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/fake-foo\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Foo produces widgets. {COMPONENT_MD_SENTINEL}\n"
        "\n"
        "## Scope\n"
        "\n"
        "Only widgets.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None beyond the glossary.\n"
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
        "See the component's criteria directory.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — Foo MUST produce exactly one widget per call. "
        f"{REQUIREMENT_SENTINEL}\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "make_widget() -> str\n"
        "```\n"
        "\n"
        f"{INTERFACE_SENTINEL}\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        f"- Must run in under one second. {CONSTRAINTS_SENTINEL}\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When make_widget is called\n"
        f"Then exactly one widget is returned {ACCEPTANCE_SENTINEL}\n"
        "```\n",
    )


def _iter_fields(value, _depth=0):
    """Yield (key, leaf) pairs for every nested field/value in the bundle."""
    if _depth > 20:
        return
    if isinstance(value, dict):
        for k, v in value.items():
            yield (k, None)
            yield from _iter_fields(v, _depth + 1)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _iter_fields(item, _depth + 1)
    elif isinstance(value, (str, bytes)):
        yield (None, value if isinstance(value, str) else value.decode("utf-8", "replace"))
    elif value is None or isinstance(value, (int, float, bool)):
        return
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        yield from _iter_fields(dataclasses.asdict(value), _depth + 1)
    elif hasattr(value, "__dict__"):
        yield from _iter_fields(dict(vars(value)), _depth + 1)
    else:
        yield (None, str(value))


def test_cold_bundle_includes_spec_interface_constraints_and_excludes_acceptance(tmp_path):
    repo_root = tmp_path / "repo"
    _build_fixture(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    assert _get(bundle, "component_id") == "comp-foo"

    spec = _get(bundle, "spec")
    interface = _get(bundle, "interface")
    constraints = _get(bundle, "constraints")

    assert isinstance(spec, str) and spec
    assert COMPONENT_MD_SENTINEL in spec, "component.md body missing from spec"
    assert REQUIREMENT_SENTINEL in spec, "requirements/ content missing from spec"

    assert isinstance(interface, str) and interface
    assert INTERFACE_SENTINEL in interface, "interface/ content missing from interface"

    assert isinstance(constraints, str) and constraints
    assert CONSTRAINTS_SENTINEL in constraints, "constraints.md body missing from constraints"

    assert _get(bundle, "hint_code") is None

    for key, leaf in _iter_fields(bundle):
        if key is not None:
            lowered = str(key).lower()
            assert "acceptance" not in lowered, f"bundle has acceptance-derived field {key!r}"
            assert "criterion" not in lowered, f"bundle has criterion-derived field {key!r}"
            assert "criteria" not in lowered, f"bundle has criteria-derived field {key!r}"
        if leaf is not None:
            assert ACCEPTANCE_SENTINEL not in leaf, "acceptance/ content leaked into the bundle"
            assert "AC-FOO-001" not in leaf, "acceptance criterion id leaked into the bundle"