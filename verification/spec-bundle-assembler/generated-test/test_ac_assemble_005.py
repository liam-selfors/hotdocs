"""AC-ASSEMBLE-005: a corpus with a hard-fail spec-linter finding anywhere in
it makes assemble fail with a precondition-failure result for any component,
never a partial bundle (R-ASSEMBLE-005)."""

from pathlib import Path

import pytest

import spec_bundle_assembler


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _clean_component(root: Path, slug: str, prefix: str) -> None:
    base = root / "specs" / "components" / slug
    _write(
        base / "component.md",
        f"---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.replace('-', ' ').title()}\n"
        f"status: draft\n"
        f"owners: [test-owner]\n"
        f"depends_on: []\n"
        f"sealed: true\n"
        f"source_path: legacy/{slug}/fake.py\n"
        f"---\n\n"
        f"# {slug}\n\n"
        f"## Purpose\n\n"
        f"A synthetic fixture component used only by a test.\n",
    )
    _write(
        base / "requirements" / f"R-{prefix}-001.md",
        f"# R-{prefix}-001\n\n"
        f"**R-{prefix}-001** — The component MUST do the one fixture thing.\n",
    )
    _write(
        base / "acceptance" / f"AC-{prefix}-001.md",
        f"# AC-{prefix}-001\n\n"
        f"Covers: R-{prefix}-001\n"
        f"Kind: generated-test\n\n"
        f"```gherkin\n"
        f"Given a fixture\n"
        f"When the fixture thing runs\n"
        f"Then it is done\n"
        f"```\n",
    )
    _write(
        base / "interface" / "library.md",
        "# Library\n\n```\ndo_thing() -> None\n```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")


def _broken_component(root: Path, slug: str, prefix: str) -> None:
    """A component carrying several unambiguous hard-fail lint violations."""
    base = root / "specs" / "components" / slug
    # Invalid `status` value and missing `owners`/`title` frontmatter.
    _write(
        base / "component.md",
        f"---\n"
        f"id: comp-{slug}\n"
        f"status: not-a-real-status\n"
        f"sealed: true\n"
        f"source_path: legacy/{slug}/fake.py\n"
        f"---\n\n"
        f"# {slug}\n\n"
        f"## Purpose\n\n"
        f"A deliberately lint-broken fixture component.\n",
    )
    # A requirement with no acceptance criterion covering it.
    _write(
        base / "requirements" / f"R-{prefix}-001.md",
        f"# R-{prefix}-001\n\n"
        f"**R-{prefix}-001** — This requirement is covered by nothing.\n",
    )
    _write(
        base / "interface" / "library.md",
        "# Library\n\n```\nbroken() -> None\n```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(
        root / "specs" / "glossary.md",
        "---\n"
        "id: glossary\n"
        "title: Glossary\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "---\n\n"
        "# Glossary\n\n"
        "- **Fixture** — a synthetic test corpus.\n",
    )
    _clean_component(root, "target", "TARGET")
    _broken_component(root, "broken", "BROKEN")
    return root


_FAILURE_HINTS = ("precondition", "lint", "hard", "finding")


def _looks_like_precondition_failure_exception(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    if any(hint in text for hint in _FAILURE_HINTS):
        return True
    for attr in ("findings", "report", "lint_report", "precondition"):
        if getattr(exc, attr, None):
            return True
    return False


def _assert_not_a_bundle(result) -> None:
    assert result is not None, "assemble returned None instead of a precondition-failure result"
    assert not _get(result, "spec_bundle_hash"), (
        f"assemble produced a (partial) bundle with a hash despite a lint-dirty corpus: {result!r}"
    )
    assert not _get(result, "spec"), (
        f"assemble produced (partial) bundle content despite a lint-dirty corpus: {result!r}"
    )
    failure_marked = (
        _get(result, "ok") is False
        or _get(result, "success") is False
        or _get(result, "exit_code") == 1
        or bool(_get(result, "error"))
        or bool(_get(result, "errors"))
        or bool(_get(result, "findings"))
        or bool(_get(result, "precondition_failure"))
        or any(
            hint in str(_get(result, field, "")).lower()
            for field in ("status", "result", "kind", "reason", "message")
            for hint in _FAILURE_HINTS
        )
    )
    assert failure_marked, (
        f"assemble returned something that is neither a bundle nor a recognisable "
        f"precondition-failure result: {result!r}"
    )


@pytest.mark.parametrize("component_id", ["comp-target", "comp-broken"])
@pytest.mark.parametrize("mode", ["cold", "hint"])
def test_ac_assemble_005_lint_dirty_corpus_refuses_bundle(repo_root, component_id, mode):
    try:
        result = spec_bundle_assembler.assemble(component_id, repo_root, mode=mode)
    except Exception as exc:  # precondition failure surfaced as an exception
        assert _looks_like_precondition_failure_exception(exc), (
            f"assemble raised, but not recognisably as a lint precondition failure: "
            f"{type(exc).__name__}: {exc}"
        )
        return
    _assert_not_a_bundle(result)


def test_ac_assemble_005_clean_component_still_refused_when_violation_elsewhere(repo_root):
    """The finding lives only in comp-broken; assembling comp-target must still fail."""
    try:
        result = spec_bundle_assembler.assemble("comp-target", repo_root)
    except Exception as exc:
        assert _looks_like_precondition_failure_exception(exc), (
            f"assemble raised, but not recognisably as a lint precondition failure: "
            f"{type(exc).__name__}: {exc}"
        )
        return
    _assert_not_a_bundle(result)