# hotdocs-criterion: sha256:a9fb2574f0dc7e03ba98e9e2986d372aec08b1c6d4f2bd026b3e1933fba4a9b8
import citation_checker


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _decision(doc_id, title, builds_on):
    return (
        "---\n"
        f"id: {doc_id}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [alice]\n"
        f"builds_on: [{builds_on}]\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Context\n"
        "\n"
        "A synthetic decision record used only as a test fixture.\n"
        "\n"
        "## Decision\n"
        "\n"
        "Nothing is decided here beyond fixture purposes.\n"
    )


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Fixture term** — a term used only by this test fixture.\n",
    )
    # First record: builds_on names a decision number with no file.
    _write(
        specs / "decisions" / "D100.md",
        _decision("D100", "Dangling builds_on", "D999"),
    )
    # Second record: builds_on names D7, one of D1-D14, never formalized.
    _write(
        specs / "decisions" / "D101.md",
        _decision("D101", "Informal builds_on", "D7"),
    )
    # Third record: builds_on resolves to a real decision file.
    _write(
        specs / "decisions" / "D102.md",
        _decision("D102", "Resolving builds_on", "D100"),
    )
    return repo_root


def test_only_dangling_builds_on_gets_r_cite_005_finding(tmp_path):
    repo_root = _build_repo(tmp_path)

    # Sanity: neither D999 nor D7 exists as a file.
    assert not (repo_root / "specs" / "decisions" / "D999.md").exists()
    assert not (repo_root / "specs" / "decisions" / "D7.md").exists()

    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)

    cite5 = [f for f in findings if _field(f, "rule_id") == "R-CITE-005"]
    files = [_field(f, "file") for f in cite5]

    assert len(cite5) == 1, f"expected exactly one R-CITE-005 finding, got {cite5!r}"
    finding = cite5[0]

    file_value = str(_field(finding, "file")).replace("\\", "/")
    assert file_value == "specs/decisions/D100.md", files

    assert "specs/decisions/D101.md" not in [
        str(x).replace("\\", "/") for x in files
    ]
    assert "specs/decisions/D102.md" not in [
        str(x).replace("\\", "/") for x in files
    ]

    assert _field(finding, "severity") in ("fail", "warn")
    line = _field(finding, "line")
    assert isinstance(line, int) and not isinstance(line, bool)
    assert line >= 1
    message = _field(finding, "message")
    assert isinstance(message, str) and message.strip()


def test_findings_have_exactly_documented_keys_for_r_cite_005(tmp_path):
    repo_root = _build_repo(tmp_path)
    findings = citation_checker.check(repo_root)
    cite5 = [f for f in findings if _field(f, "rule_id") == "R-CITE-005"]
    assert len(cite5) == 1
    finding = cite5[0]
    if isinstance(finding, dict):
        assert set(finding.keys()) == {"rule_id", "severity", "file", "line", "message"}