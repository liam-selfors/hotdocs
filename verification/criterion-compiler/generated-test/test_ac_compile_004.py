# hotdocs-criterion: sha256:0610f09828995caf11b5e42132b49f0b43b743d78675d946f6b46faeab2a8578
"""AC-COMPILE-004: compiled output carries the criterion's Covers: id as metadata.

Covers: R-COMPILE-004
"""

import criterion_compiler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _compile_foo_003():
    gherkin = (
        "Given a payload is 1\n"
        "Then value equals 1\n"
    )
    criterion = criterion_compiler.ParsedCriterion(
        criterion_id="AC-FOO-003",
        covers="R-FOO-003",
        kind="compiled",
        gherkin=gherkin,
        file="specs/components/foo/acceptance/AC-FOO-003.md",
    )
    return criterion_compiler.compile_criterion(criterion)


def test_emitted_test_contains_covers_id_as_comment_metadata():
    outcome = _compile_foo_003()

    status = field(outcome, "status")
    assert status == "compiled", (
        "expected successful compilation, got: " + repr(outcome)
    )

    source = field(outcome, "source")
    assert isinstance(source, str)

    # The emitted code must be valid Python.
    compile(source, "test_ac_foo_003.py", "exec")

    # R-COMPILE-004: the covered id appears as the comment line `# Covers: <id>`.
    stripped_lines = [line.strip() for line in source.splitlines()]
    assert "# Covers: R-FOO-003" in stripped_lines, (
        "emitted source lacks a '# Covers: R-FOO-003' comment line:\n" + source
    )


def test_covers_metadata_is_not_only_part_of_test_name():
    outcome = _compile_foo_003()
    assert field(outcome, "status") == "compiled"
    source = field(outcome, "source")

    # The id must appear as traceable metadata in a comment, not merely
    # embedded in an opaque identifier such as a test function name.
    comment_lines = [
        line.strip() for line in source.splitlines() if line.strip().startswith("#")
    ]
    assert any("R-FOO-003" in line for line in comment_lines), (
        "R-FOO-003 does not appear in any comment line:\n" + source
    )