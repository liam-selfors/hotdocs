# hotdocs-criterion: sha256:ce12ea3b078d59e4fcd62a2421eccd29fa44766e88745820f03c1c45a678239b
import importlib.util
import os
import sys
from pathlib import Path

import impact_analyzer


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id: str, title: str, source_path: str, depends_on=None) -> str:
    lines = [
        "---",
        f"id: {comp_id}",
        f"title: {title}",
        "status: draft",
        "owners: [alice]",
    ]
    if depends_on:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    lines += [
        "sealed: true",
        f"source_path: {source_path}",
        "---",
        "",
        f"# {title}",
        "",
        "## Purpose",
        "",
        f"{title} is a small synthetic component used only as a test fixture.",
        "",
        "## Scope",
        "",
        "- In scope: fixture behavior.",
        "- Out of scope: everything else.",
        "",
        "## Definitions",
        "",
        "None.",
        "",
        "## Behavior",
        "",
        "See `requirements/`.",
        "",
        "## Interfaces",
        "",
        "See `interface/`.",
        "",
        "## Data",
        "",
        "See `interface/data/`.",
        "",
        "## Acceptance criteria",
        "",
        "See `acceptance/`.",
        "",
        "## Non-functional constraints",
        "",
        "See `constraints.md`.",
        "",
        "## Open questions",
        "",
        "## Change log",
        "",
        "- Initial fixture.",
        "",
    ]
    return "\n".join(lines)


def _requirement(req_id: str) -> str:
    return (
        f"# {req_id}\n"
        "\n"
        "The component MUST match its existing behavior.\n"
    )


def _acceptance(ac_id: str, req_id: str) -> str:
    return (
        f"# {ac_id}\n"
        "\n"
        f"Covers: {req_id}\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given the component exists\n"
        "When it is invoked\n"
        "Then it matches its existing behavior\n"
        "```\n"
    )


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a placeholder term for this test corpus.\n",
    )

    # comp-bar: no dependencies.
    bar = repo_root / "specs" / "components" / "bar"
    _write(bar / "component.md", _component_md("comp-bar", "Bar", "legacy/bar"))
    _write(bar / "requirements" / "R-BAR-001.md", _requirement("R-BAR-001"))
    _write(bar / "acceptance" / "AC-BAR-001.md", _acceptance("AC-BAR-001", "R-BAR-001"))
    _write(
        bar / "interface" / "library.md",
        "# Library\n\n```\nbar_fn(x: str) -> str\n```\n\nA pure function that MUST return its input unchanged.\n",
    )
    _write(
        bar / "constraints.md",
        "# Constraints\n\n- None beyond matching existing behavior.\n",
    )

    # comp-foo: depends_on comp-bar, declared only in its own component.md frontmatter.
    foo = repo_root / "specs" / "components" / "foo"
    _write(
        foo / "component.md",
        _component_md("comp-foo", "Foo", "legacy/foo", depends_on=["comp-bar"]),
    )
    _write(foo / "requirements" / "R-FOO-001.md", _requirement("R-FOO-001"))
    _write(foo / "acceptance" / "AC-FOO-001.md", _acceptance("AC-FOO-001", "R-FOO-001"))
    _write(
        foo / "constraints.md",
        "# Constraints\n\n- None beyond matching existing behavior.\n",
    )

    # Hand-maintained sealed source locations (never under gen/).
    _write(repo_root / "legacy" / "bar" / "bar.py", "def bar_fn(x):\n    return x\n")
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo_fn(x):\n    return x\n")


def _find_spec_linter_path():
    candidates = []
    mod_file = getattr(impact_analyzer, "__file__", None)
    if mod_file:
        candidates.extend(Path(mod_file).resolve().parents)
    candidates.extend([Path.cwd().resolve()] + list(Path.cwd().resolve().parents))
    seen = set()
    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        flat = base / "gen" / "spec-linter" / "spec_linter.py"
        if flat.is_file():
            return flat
        pkg = base / "gen" / "spec-linter" / "spec_linter" / "__init__.py"
        if pkg.is_file():
            return pkg
    return None


def _load_lint():
    path = _find_spec_linter_path()
    if path is not None:
        module_name = "spec_linter"
        if path.name == "__init__.py":
            spec = importlib.util.spec_from_file_location(
                module_name, path, submodule_search_locations=[str(path.parent)]
            )
        else:
            spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # register BEFORE exec_module
        spec.loader.exec_module(module)
        return module.lint
    import spec_linter  # fallback if it happens to be importable

    return spec_linter.lint


def _no_precomputed_graph(repo_root: Path) -> bool:
    for dirpath, _dirnames, filenames in os.walk(repo_root):
        for name in filenames:
            if name == "corpus-graph.json" or name.startswith("corpus-graph"):
                return False
    return True


def test_ac_impact_009_transitive_interface_from_component_md_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    # Precondition: no precomputed graph artifact anywhere in the repo.
    assert not (repo_root / "verification").exists()
    assert _no_precomputed_graph(repo_root)

    # Precondition: the fixture corpus lints clean.
    lint = _load_lint()
    report = lint(None, repo_root)
    hard_failures = _get(report, "hard_failures")
    findings = _get(report, "findings") or []
    fail_findings = [f for f in findings if _get(f, "severity") == "fail"]
    assert hard_failures == 0 and not fail_findings, (
        "fixture corpus is not lint-clean: "
        + "; ".join(
            f"{_get(f, 'rule_id')} {_get(f, 'file')}:{_get(f, 'line')} {_get(f, 'message')}"
            for f in fail_findings
        )
    )

    # Still no precomputed graph artifact after linting.
    assert _no_precomputed_graph(repo_root)

    result = impact_analyzer.compute_blast_radius(["comp-bar"], repo_root)

    assert _get(result, "precondition_error") is None, (
        f"unexpected precondition_error: {_get(result, 'precondition_error')!r}"
    )

    impacted = _get(result, "impacted") or []
    by_id = {}
    for entry in impacted:
        cid = _get(entry, "component_id")
        assert cid not in by_id, f"component {cid!r} appears more than once"
        by_id[cid] = entry

    assert "comp-foo" in by_id, f"comp-foo missing from impacted: {list(by_id)}"
    foo_entry = by_id["comp-foo"]
    assert _get(foo_entry, "reason") == "transitive-interface"
    assert _get(foo_entry, "via") == "comp-bar"

    # The changed component itself is always direct.
    assert "comp-bar" in by_id
    assert _get(by_id["comp-bar"], "reason") == "direct"
    assert _get(by_id["comp-bar"], "via") is None

    # Computing the answer did not require (or leave behind) a precomputed graph.
    assert _no_precomputed_graph(repo_root)