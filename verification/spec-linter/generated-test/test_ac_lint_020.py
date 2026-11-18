# hotdocs-criterion: sha256:a2c026f248489e34630d928e971ca850ece728c653de287bd659a9bc0549649e
import shutil
import tempfile
import unittest
from pathlib import Path

import spec_linter


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, depends_on=None, depends_on_guarantees=None):
    lines = [
        "---",
        f"id: {comp_id}",
        f"title: {title}",
        "status: draft",
        "owners: [alice]",
    ]
    if depends_on:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    if depends_on_guarantees:
        lines.append(
            "depends_on_guarantees: [" + ", ".join(depends_on_guarantees) + "]"
        )
    lines.append("sealed: true")
    lines.append(f"source_path: legacy/{comp_id}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append(f"{title} does one small thing for test purposes.")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("- In scope: the one small thing.")
    lines.append("- Out of scope: everything else.")
    lines.append("")
    lines.append("## Definitions")
    lines.append("")
    lines.append("None.")
    lines.append("")
    lines.append("## Behavior")
    lines.append("")
    lines.append("See `requirements/`.")
    lines.append("")
    lines.append("## Interfaces")
    lines.append("")
    lines.append("See `interface/`.")
    lines.append("")
    lines.append("## Data")
    lines.append("")
    lines.append("See `interface/data/`.")
    lines.append("")
    lines.append("## Acceptance criteria")
    lines.append("")
    lines.append("See `acceptance/`.")
    lines.append("")
    lines.append("## Non-functional constraints")
    lines.append("")
    lines.append("See `constraints.md`.")
    lines.append("")
    lines.append("## Open questions")
    lines.append("")
    lines.append("## Change log")
    lines.append("")
    lines.append("- Initial draft.")
    lines.append("")
    return "\n".join(lines)


def _write_component(repo_root, slug, upper, depends_on=None,
                     depends_on_guarantees=None, guarantees=()):
    base = repo_root / "specs" / "components" / slug
    comp_id = f"comp-{slug}"
    _write(
        base / "component.md",
        _component_md(comp_id, slug.capitalize(), depends_on,
                      depends_on_guarantees),
    )
    req_id = f"R-{upper}-001"
    ac_id = f"AC-{upper}-001"
    _write(
        base / "requirements" / f"{req_id}.md",
        f"# {req_id}\n\n**{req_id}** — The component MUST do its one small "
        f"thing.\n",
    )
    _write(
        base / "acceptance" / f"{ac_id}.md",
        f"# {ac_id}\n\nCovers: {req_id}\nKind: compiled\n\n```gherkin\n"
        f"Given an input\nWhen the component runs\nThen it does its one "
        f"small thing\n```\n",
    )
    _write(
        base / "constraints.md",
        "# Constraints\n\n- None beyond the defaults. Measured by "
        "inspection.\n",
    )
    for gid in guarantees:
        _write(
            base / "interface" / "guarantees" / f"{gid}.md",
            f"# {gid}\n\n**{gid}** — The component MUST behave "
            f"idempotently.\n",
        )


def _build_corpus(repo_root: Path, foo_depends_on):
    _write_component(repo_root, "bar", "BAR", guarantees=("G-BAR-001",))
    _write_component(repo_root, "baz", "BAZ")
    _write_component(
        repo_root,
        "foo",
        "FOO",
        depends_on=foo_depends_on,
        depends_on_guarantees=["G-BAR-001"],
    )


def _findings(report):
    findings = _get(report, "findings", None)
    if findings is None:
        return []
    return list(findings)


def _lint_018_fails(report):
    out = []
    for f in _findings(report):
        if _get(f, "rule_id") == "R-LINT-018" and _get(f, "severity") == "fail":
            out.append(f)
    return out


class TestAcLint020(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="ac_lint_020_")
        self.addCleanup(shutil.rmtree, self._tmp, True)

    def _new_root(self, name):
        root = Path(self._tmp) / name
        root.mkdir(parents=True, exist_ok=True)
        return root

    def test_guarantee_owner_not_in_depends_on_fails_r_lint_018(self):
        repo_root = self._new_root("missing_dep")
        _build_corpus(repo_root, foo_depends_on=["comp-baz"])

        report = spec_linter.lint(None, repo_root)
        hits = _lint_018_fails(report)
        self.assertTrue(
            hits,
            "expected an R-LINT-018 fail finding when comp-foo's "
            "depends_on_guarantees names G-BAR-001 but depends_on omits "
            "comp-bar; got findings: %r" % (_findings(report),),
        )

        hard_failures = _get(report, "hard_failures", None)
        if hard_failures is not None:
            self.assertGreaterEqual(hard_failures, 1)

    def test_guarantee_owner_in_depends_on_passes_r_lint_018(self):
        repo_root = self._new_root("with_dep")
        _build_corpus(repo_root, foo_depends_on=["comp-baz", "comp-bar"])

        report = spec_linter.lint(None, repo_root)
        hits = _lint_018_fails(report)
        self.assertEqual(
            hits,
            [],
            "expected no R-LINT-018 fail finding when comp-foo depends on "
            "comp-bar, the owner of G-BAR-001 by its file path; got: %r"
            % (hits,),
        )

    def test_cli_exits_one_on_unlisted_guarantee_owner(self):
        repo_root = self._new_root("cli_missing_dep")
        _build_corpus(repo_root, foo_depends_on=["comp-baz"])

        code = spec_linter.main(
            [f"--repo-root={repo_root}", "--format=json"]
        )
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()