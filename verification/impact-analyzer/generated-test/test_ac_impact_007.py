"""AC-IMPACT-007 (covers R-IMPACT-007).

Given a corpus containing a dangling depends_on reference unrelated to the
  changed ids
When hotdocs impact --changed comp-foo runs
Then the report's precondition_error is non-null, impacted is empty, and the
  CLI exits with code 1
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import impact_analyzer


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Synthetic, otherwise lint-clean corpus
# ---------------------------------------------------------------------------


def _component(root: Path, slug: str, prefix: str, depends_on=None) -> None:
    comp_dir = root / "specs" / "components" / slug
    fm = [
        "---",
        f"id: comp-{slug}",
        f"title: Fixture component {slug}",
        "status: draft",
        "owners: [test-owner]",
        "sealed: true",
        f"source_path: legacy/{slug}",
    ]
    if depends_on:
        fm.append("depends_on: [" + ", ".join(depends_on) + "]")
    fm.append("---")
    body = "\n".join(
        [
            "",
            f"# comp-{slug}",
            "",
            "## Purpose",
            "",
            f"A small synthetic fixture component named {slug}, used only to "
            "exercise impact analysis over a tiny corpus.",
            "",
            "## Scope",
            "",
            "- In scope: one trivial behavior.",
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
            "- Initial draft.",
            "",
        ]
    )
    _write(comp_dir / "component.md", "\n".join(fm) + "\n" + body)

    rid = f"R-{prefix}-001"
    acid = f"AC-{prefix}-001"
    _write(
        comp_dir / "requirements" / f"{rid}.md",
        f"# {rid}\n\n**{rid}** \u2014 The component MUST return the value it is "
        "given, unchanged.\n",
    )
    _write(
        comp_dir / "acceptance" / f"{acid}.md",
        f"# {acid}\n\nCovers: {rid}\nKind: compiled\n\n```gherkin\n"
        "Given an input value\n"
        "When the component is called with it\n"
        "Then the same value is returned\n"
        "```\n",
    )
    func = slug.replace("-", "_")
    _write(
        comp_dir / "interface" / "library.md",
        f"# Library\n\n```\n{func}(value: str) -> str\n```\n\n"
        "Returns its argument unchanged.\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n- A call MUST complete within 10 ms; measured by "
        "timing one call in a unit test.\n",
    )
    _write(root / "legacy" / slug / "README.txt", "fixture source placeholder\n")


def _build_corpus(root: Path, dangling: bool) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** \u2014 a synthetic test corpus.\n",
    )
    # comp-foo: the changed id. Neither depends on nor is depended on by baz.
    _component(root, "foo", "FOO")
    # comp-baz: carries the dangling reference (only in the broken variant),
    # entirely unrelated to comp-foo.
    _component(root, "baz", "BAZ", depends_on=["comp-ghost"] if dangling else None)
    return root


# ---------------------------------------------------------------------------
# spec-linter access (real one, never faked)
# ---------------------------------------------------------------------------


def _find_spec_linter_file():
    starts = []
    f = getattr(impact_analyzer, "__file__", None)
    if f:
        starts.append(Path(f).resolve())
    starts.append(Path(__file__).resolve())
    starts.append(Path.cwd().resolve())
    for s in starts:
        for p in [s] + list(s.parents):
            base = p / "gen" / "spec-linter"
            flat = base / "spec_linter.py"
            pkg = base / "spec_linter" / "__init__.py"
            if flat.is_file():
                return flat, False
            if pkg.is_file():
                return pkg, True
    return None


def _load_lint():
    existing = sys.modules.get("spec_linter")
    if existing is not None and callable(getattr(existing, "lint", None)):
        return existing.lint
    found = _find_spec_linter_file()
    if found is None:
        return None
    module_path, is_pkg = found
    module_name = "spec_linter"
    try:
        if is_pkg:
            spec = importlib.util.spec_from_file_location(
                module_name,
                module_path,
                submodule_search_locations=[str(module_path.parent)],
            )
        else:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # register BEFORE exec_module
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop("spec_linter", None)
        return None
    lint = getattr(module, "lint", None)
    return lint if callable(lint) else None


def _hard_failures(report):
    findings = _get(report, "findings", []) or []
    fails = [f for f in findings if _get(f, "severity") == "fail"]
    count = len(fails)
    hf = _get(report, "hard_failures", None)
    if isinstance(hf, int):
        count = max(count, hf)
    summary = _get(report, "summary", None)
    if summary is not None:
        shf = _get(summary, "hard_failures", None)
        if isinstance(shf, int):
            count = max(count, shf)
    return count, fails


# ---------------------------------------------------------------------------
# CLI invocation
# ---------------------------------------------------------------------------


def _parse_report(text: str):
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return None
    return None


def _run_cli(root: Path, capsys):
    argv = [f"--repo-root={root}", "--format=json", "--changed", "comp-foo"]
    main = getattr(impact_analyzer, "main", None)
    if callable(main):
        capsys.readouterr()
        try:
            rc = main(argv)
        except SystemExit as e:
            code = e.code
            rc = code if isinstance(code, int) else (0 if code is None else 1)
        if rc is None:
            rc = 0
        captured = capsys.readouterr()
        return rc, captured.out, captured.err
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    proc = subprocess.run(
        [sys.executable, "-m", "impact_analyzer"] + argv,
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _cli_report(out: str, err: str):
    report = _parse_report(out)
    if report is None:
        report = _parse_report(err)
    return report


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def corpora(tmp_path):
    clean = _build_corpus(tmp_path / "clean", dangling=False)
    broken = _build_corpus(tmp_path / "broken", dangling=True)
    lint = _load_lint()
    if lint is not None:
        clean_report = lint(None, clean)
        clean_count, clean_fails = _hard_failures(clean_report)
        assert clean_count == 0, (
            "baseline fixture must lint clean; fail findings: "
            + repr([(_get(f, "rule_id"), _get(f, "file"), _get(f, "message")) for f in clean_fails])
        )
        broken_report = lint(None, broken)
        broken_count, _ = _hard_failures(broken_report)
        assert broken_count >= 1, (
            "fixture with dangling depends_on must produce a fail-severity lint finding"
        )
    return clean, broken


def test_clean_baseline_computes_blast_radius(corpora, capsys):
    clean, _ = corpora
    report = impact_analyzer.compute_blast_radius(["comp-foo"], clean)
    assert _get(report, "precondition_error") is None
    impacted = _get(report, "impacted") or []
    ids = [_get(e, "component_id") for e in impacted]
    assert "comp-foo" in ids
    assert len(ids) == len(set(ids))
    foo = [e for e in impacted if _get(e, "component_id") == "comp-foo"][0]
    assert _get(foo, "reason") == "direct"
    assert _get(foo, "via") is None

    rc, out, err = _run_cli(clean, capsys)
    assert rc == 0, f"expected exit 0 on clean corpus, got {rc}; stderr={err!r}"
    cli_report = _cli_report(out, err)
    assert cli_report is not None, f"no JSON report emitted: stdout={out!r} stderr={err!r}"
    assert cli_report.get("precondition_error") is None


def test_library_fails_closed_on_unrelated_dangling_reference(corpora):
    _, broken = corpora
    try:
        report = impact_analyzer.compute_blast_radius(["comp-foo"], broken)
    except (TypeError, AttributeError, NameError):
        raise
    except Exception:
        # Raising an explicit precondition failure is permitted by the
        # library contract ("Raises/returns ... precondition-failure result").
        return
    assert _get(report, "precondition_error") is not None
    impacted = _get(report, "impacted")
    assert impacted is not None
    assert list(impacted) == []


def test_cli_fails_closed_with_exit_1_on_unrelated_dangling_reference(corpora, capsys):
    _, broken = corpora
    rc, out, err = _run_cli(broken, capsys)
    assert rc == 1, f"expected exit 1 (precondition failure), got {rc}; stderr={err!r}"
    report = _cli_report(out, err)
    assert report is not None, f"no JSON report emitted: stdout={out!r} stderr={err!r}"
    assert report.get("precondition_error") is not None
    assert report.get("impacted") == []