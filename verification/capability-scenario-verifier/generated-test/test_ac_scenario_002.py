import capability_scenario_verifier


def field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_report_only_includes_realized_capability_in_blast_radius(tmp_path):
    repo_root = tmp_path

    write_file(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: 0000000\n"
        "realizes: [P-ZERO-EDIT]\n"
        "sealed: false\n"
        "---\n",
    )
    write_file(
        repo_root / "specs" / "components" / "bar" / "component.md",
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: 0000000\n"
        "realizes: []\n"
        "sealed: false\n"
        "---\n",
    )

    write_file(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")
    write_file(repo_root / "gen" / "bar" / "bar.py", "VALUE = 1\n")

    write_file(
        repo_root / "specs" / "product" / "P-ZERO-EDIT.md",
        "---\n"
        "id: P-ZERO-EDIT\n"
        "title: Zero Edit\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: 0000000\n"
        "---\n"
        "\n"
        "### CS-ZERO-EDIT-001\n"
        "\n"
        "Covers: P-ZERO-EDIT\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it happens\n"
        "Then it passes\n"
        "```\n",
    )
    write_file(
        repo_root / "specs" / "product" / "P-UNRELATED.md",
        "---\n"
        "id: P-UNRELATED\n"
        "title: Unrelated\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: 0000000\n"
        "---\n"
        "\n"
        "### CS-UNRELATED-001\n"
        "\n"
        "Covers: P-UNRELATED\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When nothing happens\n"
        "Then nothing changes\n"
        "```\n",
    )

    responses = {
        "CS-ZERO-EDIT-001": {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-ZERO-EDIT/generated-test/test_cs_zero_edit_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }
    }
    calls = []

    def fake_test_author(bundle):
        calls.append(bundle)
        scenario_id = field(bundle, "scenario_id")
        return responses[scenario_id]

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo", "comp-bar"], repo_root, test_author=fake_test_author
    )

    assert isinstance(report, dict)
    assert set(report.keys()) == {"P-ZERO-EDIT"}
    assert len(calls) == 1
    assert field(calls[0], "scenario_id") == "CS-ZERO-EDIT-001"


def test_sealed_component_scenario_imports_from_source_path(tmp_path):
    repo_root = tmp_path

    write_file(
        repo_root / "specs" / "components" / "baz" / "component.md",
        "---\n"
        "id: comp-baz\n"
        "title: Baz\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: 0000000\n"
        "realizes: [P-SEALED]\n"
        "sealed: true\n"
        "source_path: pipeline/baz/\n"
        "---\n",
    )

    write_file(repo_root / "pipeline" / "baz" / "baz_impl.py", 'VALUE = "ok"\n')

    assert not (repo_root / "gen" / "baz").exists()

    write_file(
        repo_root / "specs" / "product" / "P-SEALED.md",
        "---\n"
        "id: P-SEALED\n"
        "title: Sealed Capability\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: 0000000\n"
        "---\n"
        "\n"
        "### CS-SEALED-001\n"
        "\n"
        "Covers: P-SEALED\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given comp-baz exists under pipeline/baz/\n"
        "When its scenario test runs\n"
        "Then it imports baz_impl from pipeline/baz/\n"
        "```\n",
    )

    responses = {
        "CS-SEALED-001": {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-SEALED/generated-test/test_cs_sealed_001.py",
                "content": (
                    "import baz_impl\n"
                    "\n"
                    "def test_cs_sealed_001():\n"
                    '    assert baz_impl.VALUE == "ok"\n'
                ),
            },
        }
    }

    def fake_test_author(bundle):
        scenario_id = field(bundle, "scenario_id")
        return responses[scenario_id]

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-baz"], repo_root, test_author=fake_test_author
    )

    assert isinstance(report, dict)
    assert "P-SEALED" in report
    entry = report["P-SEALED"]
    assert field(entry, "overall") == "pass"

    scenarios = field(entry, "scenarios")
    matching = [s for s in scenarios if field(s, "id") == "CS-SEALED-001"]
    assert len(matching) == 1
    assert field(matching[0], "result") == "pass"