import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import spec_linter


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _sev(value):
    sev = _get(value, "severity")
    inner = getattr(sev, "value", None)
    if isinstance(inner, str):
        return inner
    return sev if isinstance(sev, str) else str(sev)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug: str) -> str:
    return textwrap.dedent(
        f"""\
        ---
        id: comp-{slug}
        title: {slug.capitalize()} Tool
        status: draft
        owners: [alice]
        depends_on: []
        sealed: true
        source_path: legacy/{slug}
        ---

        # {slug.capitalize()} Tool

        ## Purpose

        A small command-line tool used as a synthetic fixture.

        ## Scope

        - In scope: running the tool.
        - Out of scope: everything else.

        ## Definitions

        None.

        ## Behavior

        See `requirements/`.

        ## Interfaces

        See `interface/`.

        ## Data

        See `interface/data/`.

        ## Acceptance criteria

        See `acceptance/`.

        ## Non-functional constraints

        See `constraints.md`.

        ## Open questions

        ## Change log

        - Initial draft.
        """
    )


def _cli_md(slug: str) -> str:
    return textwrap.dedent(
        f"""\
        # CLI

        ```
        {slug} run [--mode=fast|slow]
        ```

        - `--mode` — `fast` (default) or `slow`.

        **Exit codes:** `0` success, `2` usage error.
        """
    )


def _constraints_md() -> str:
    return textwrap.dedent(
        """\
        # Constraints

        - Runs in under one second on the fixture input, measured by a timer.
        """
    )


def _requirement(rid: str, text: str) -> str:
    return f"# {rid}\n\n**{rid}** — {text}\n"


def _acceptance(acid: str, covers: str) -> str:
    return textwrap.dedent(
        f"""\
        # {acid}

        Covers: {covers}
        Kind: generated-test

        ```gherkin
        Given the tool is installed
        When it runs
        Then it exits with code 0
        ```
        """
    )


CITING_TEXT = (
    "The command line documented in `interface/cli.md` MUST accept "
    "`--mode=value` and `--mode value`, MUST treat `--mode` given with no "
    "value as a usage error, MUST reject an unknown argument with exit "
    "code `2`, and MUST exit `0` on success."
)

NON_CITING_TEXT = "The tool MUST print a greeting when it runs."


def _build_fixture(root: Path) -> None:
    specs = root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )

    # Component 1: alpha — citing requirement, covered by a criterion.
    a = specs / "components" / "alpha"
    _write(a / "component.md", _component_md("alpha"))
    _write(a / "interface" / "cli.md", _cli_md("alpha"))
    _write(a / "constraints.md", _constraints_md())
    _write(a / "requirements" / "R-ALPHA-001.md", _requirement("R-ALPHA-001", CITING_TEXT))
    _write(a / "acceptance" / "AC-ALPHA-001.md", _acceptance("AC-ALPHA-001", "R-ALPHA-001"))

    # Component 2: beta — citing requirement with NO covering criterion.
    b = specs / "components" / "beta"
    _write(b / "component.md", _component_md("beta"))
    _write(b / "interface" / "cli.md", _cli_md("beta"))
    _write(b / "constraints.md", _constraints_md())
    _write(b / "requirements" / "R-BETA-001.md", _requirement("R-BETA-001", CITING_TEXT))
    _write(b / "requirements" / "R-BETA-002.md", _requirement("R-BETA-002", NON_CITING_TEXT))
    _write(b / "acceptance" / "AC-BETA-001.md", _acceptance("AC-BETA-001", "R-BETA-002"))

    # Component 3: gamma — no requirement citing interface/cli.md at all.
    g = specs / "components" / "gamma"
    _write(g / "component.md", _component_md("gamma"))
    _write(g / "interface" / "cli.md", _cli_md("gamma"))
    _write(g / "constraints.md", _constraints_md())
    _write(g / "requirements" / "R-GAMMA-001.md", _requirement("R-GAMMA-001", NON_CITING_TEXT))
    _write(g / "acceptance" / "AC-GAMMA-001.md", _acceptance("AC-GAMMA-001", "R-GAMMA-001"))


def _owner_of(finding):
    file = str(_get(finding, "file") or "").replace("\\", "/")
    message = str(_get(finding, "message") or "")
    owners = set()
    for slug in ("alpha", "beta", "gamma"):
        if f"specs/components/{slug}/" in file or f"comp-{slug}" in message:
            owners.add(slug)
    return owners


class TestAcLint031(unittest.TestCase):
    def test_only_uncovered_or_uncited_cli_components_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp).resolve()
            _build_fixture(repo_root)

            report = spec_linter.lint(None, repo_root)
            findings = list(_get(report, "findings") or [])

            r031 = [f for f in findings if _get(f, "rule_id") == "R-LINT-031"]

            by_comp = {"alpha": [], "beta": [], "gamma": []}
            for f in r031:
                owners = _owner_of(f)
                self.assertEqual(
                    len(owners),
                    1,
                    f"R-LINT-031 finding not attributable to exactly one component: {f!r}",
                )
                by_comp[owners.pop()].append(f)

            self.assertEqual(
                by_comp["alpha"],
                [],
                f"component with a covered citing requirement must not get R-LINT-031: {by_comp['alpha']!r}",
            )
            self.assertTrue(
                by_comp["beta"],
                f"component whose citing requirement is uncovered must get R-LINT-031; got {r031!r}",
            )
            self.assertTrue(
                by_comp["gamma"],
                f"component with no citing requirement must get R-LINT-031; got {r031!r}",
            )

            for slug in ("beta", "gamma"):
                for f in by_comp[slug]:
                    self.assertEqual(
                        _sev(f), "warn", f"R-LINT-031 finding for {slug} must be warn: {f!r}"
                    )
                    self.assertIn(
                        f"comp-{slug}",
                        str(_get(f, "message") or ""),
                        f"R-LINT-031 finding must name comp-{slug}: {f!r}",
                    )


if __name__ == "__main__":
    sys.exit(unittest.main())