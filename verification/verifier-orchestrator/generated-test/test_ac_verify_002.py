import verifier_orchestrator

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root, slug, gen_body, marker_path):
    up = slug.upper()
    comp_id = "comp-" + slug
    cap_id = "P-" + up
    req_id = "R-" + up + "-001"
    ac_id = "AC-" + up + "-001"
    comp_dir = repo_root / "specs" / "components" / slug

    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )

    _write(
        repo_root / "specs" / "product" / (slug + ".md"),
        "---\n"
        "id: " + cap_id + "\n"
        "title: " + slug.capitalize() + " capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + " capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Numbers can be doubled.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-" + up + "-001\n"
        "Covers: " + cap_id + "\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a number\n"
        "When it is doubled\n"
        "Then the result is twice the number\n"
        "```\n",
    )

    _write(
        comp_dir / "component.md",
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [" + cap_id + "]\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        + slug.capitalize() + " doubles a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling integers.\n"
        "- Out of scope: everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
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
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n",
    )

    _write(
        comp_dir / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n"
        "\n"
        "**" + req_id + "** — `double_it(x)` MUST return `2 * x`.\n",
    )

    _write(
        comp_dir / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + req_id + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the integer 2\n"
        "When double_it is called with it\n"
        "Then it returns 4\n"
        "```\n",
    )

    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "double_it(x: int) -> int\n"
        "```\n",
    )

    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")

    # The generated code under test, at gen/<slug>/<module>.py.
    _write(repo_root / "gen" / slug / (slug + ".py"), gen_body)

    # The already-generated test for this criterion, at the glossary's
    # "Criterion test filename" directly under verification/<slug>/generated-test/.
    test_name = "test_" + ac_id.lower().replace("-", "_") + ".py"
    _write(
        repo_root / "verification" / slug / "generated-test" / test_name,
        "import pathlib\n"
        "import " + slug + "\n"
        "\n"
        "MARKER = " + repr(str(marker_path)) + "\n"
        "\n"
        "\n"
        "def test_double_it_returns_twice():\n"
        "    with open(MARKER, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(pathlib.Path(" + slug + ".__file__).resolve()) + '\\n')\n"
        "    assert " + slug + ".double_it(2) == 4\n",
    )
    return comp_id, ac_id


def _criterion(report, ac_id):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == ac_id]
    assert len(matches) == 1, criteria
    return matches[0]


def _marker_lines(marker_path):
    assert marker_path.is_file(), "the cached generated test was never executed"
    return [ln.strip() for ln in marker_path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_cached_generated_test_is_executed_against_gen_and_result_reported(tmp_path):
    # Passing case: gen code is correct, so the cached test passes.
    repo_ok = tmp_path / "repo_ok"
    marker_ok = tmp_path / "markers" / "ok.log"
    marker_ok.parent.mkdir(parents=True, exist_ok=True)
    comp_ok, ac_ok = _build_fixture(
        repo_ok,
        "widget",
        "def double_it(x):\n    return 2 * x\n",
        marker_ok,
    )

    report_ok = verifier_orchestrator.verify(comp_ok, repo_ok)
    entry_ok = _criterion(report_ok, ac_ok)
    assert field(entry_ok, "kind") == "generated-test"
    assert field(entry_ok, "result") == "pass"

    lines_ok = _marker_lines(marker_ok)
    expected_ok = str((repo_ok / "gen" / "widget" / "widget.py").resolve())
    assert expected_ok in lines_ok, lines_ok

    # Failing case: gen code is wrong, so the same cached test fails, and that
    # failure is what the report records.
    repo_bad = tmp_path / "repo_bad"
    marker_bad = tmp_path / "markers" / "bad.log"
    comp_bad, ac_bad = _build_fixture(
        repo_bad,
        "gadget",
        "def double_it(x):\n    return 3 * x\n",
        marker_bad,
    )

    report_bad = verifier_orchestrator.verify(comp_bad, repo_bad)
    entry_bad = _criterion(report_bad, ac_bad)
    assert field(entry_bad, "kind") == "generated-test"
    assert field(entry_bad, "result") == "fail"

    lines_bad = _marker_lines(marker_bad)
    expected_bad = str((repo_bad / "gen" / "gadget" / "gadget.py").resolve())
    assert expected_bad in lines_bad, lines_bad