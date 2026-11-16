# Covers: R-COMPILE-004
"""AC-COMPILE-004: compiled test output carries the criterion's Covers: id
as traceable metadata, the comment line `# Covers: <id>`.

Written against the interface/ contract only:
  compile_criterion(criterion: ParsedCriterion,
                    surface: InterfaceSurface | None = None) -> dict
returning {"status": "compiled", "source": <text>} or
{"status": "error", "message": <text>}.
"""

import ast

import pytest

import criterion_compiler


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_criterion(criterion_id, covers, gherkin):
    return criterion_compiler.ParsedCriterion(
        criterion_id=criterion_id,
        covers=covers,
        kind="compiled",
        gherkin=gherkin,
        file="specs/components/foo/acceptance/%s.md" % criterion_id,
    )


def _compiled_source(result):
    status = _field(result, "status")
    assert status == "compiled", (
        "expected successful compilation, got %r (message: %r)"
        % (status, _field(result, "message"))
    )
    source = _field(result, "source")
    assert isinstance(source, str) and source.strip(), (
        "compiled result must carry non-empty emitted source text"
    )
    return source


def _covers_comment_lines(source):
    return [line.strip() for line in source.splitlines()]


def _assert_covers_comment(source, covers_id):
    lines = _covers_comment_lines(source)
    expected = "# Covers: %s" % covers_id
    assert expected in lines, (
        "emitted source must contain the comment line %r; got:\n%s"
        % (expected, source)
    )
    # The emitted output must still be valid Python.
    ast.parse(source)


NO_SURFACE_GHERKIN = (
    'Given a payload is "hello"\n'
    'Then value equals "hello"\n'
)


def test_covers_id_emitted_as_comment_line_without_surface():
    criterion = _make_criterion("AC-FOO-003", "R-FOO-003", NO_SURFACE_GHERKIN)
    result = criterion_compiler.compile_criterion(criterion)
    source = _compiled_source(result)
    _assert_covers_comment(source, "R-FOO-003")


def test_covers_id_emitted_as_comment_line_with_surface():
    surface = criterion_compiler.InterfaceSurface(
        functions={"do_thing": ["text"]},
        module_name="foo",
    )
    gherkin = (
        'Given a payload is "hello"\n'
        'When do_thing is invoked with {"text": payload}\n'
        "Then value equals 1\n"
    )
    criterion = _make_criterion("AC-FOO-003", "R-FOO-003", gherkin)
    result = criterion_compiler.compile_criterion(criterion, surface)
    source = _compiled_source(result)
    _assert_covers_comment(source, "R-FOO-003")


@pytest.mark.parametrize("covers_id", ["R-BAR-042", "P-FOO-001"])
def test_covers_metadata_comes_from_covers_field_not_criterion_id(covers_id):
    # The covered id deliberately differs from anything derivable from the
    # criterion id or its test name, so it can only appear in the output if
    # the compiler emits the Covers: id itself as metadata.
    criterion = _make_criterion("AC-FOO-003", covers_id, NO_SURFACE_GHERKIN)
    result = criterion_compiler.compile_criterion(criterion)
    source = _compiled_source(result)
    _assert_covers_comment(source, covers_id)
    assert "# Covers: R-FOO-003" not in _covers_comment_lines(source), (
        "the Covers: comment must carry the criterion's own covers id, "
        "not one derived from its criterion id"
    )