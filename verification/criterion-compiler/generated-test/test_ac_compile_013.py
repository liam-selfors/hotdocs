"""AC-COMPILE-013 (covers R-COMPILE-012).

compile_criterion compiles one already-parsed criterion directly with an
optional interface surface:

- A literal-only criterion compiles with no surface at all, and the emitted
  source is identical to compiling the same content against an empty
  InterfaceSurface.
- A criterion whose When step invokes a named function, compiled with no
  surface, is a located, specific compile error naming the unresolved
  function. It is never silently skipped.
"""

import criterion_compiler


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_criterion(criterion_id, gherkin):
    # Parsed independently of any component's acceptance/ directory: the
    # "file" is a path that lives under no component at all.
    return criterion_compiler.ParsedCriterion(
        criterion_id=criterion_id,
        covers="R-SCEN-001",
        kind="compiled",
        gherkin=gherkin,
        file="capabilities/example-capability/scenarios/SCN-001.md",
    )


LITERAL_ONLY_GHERKIN = (
    'Given a payload is "x"\n'
    "Given a count is 3\n"
    'Then status equals "ok"\n'
)

FUNCTION_GHERKIN = (
    'Given a payload is "x"\n'
    'When frobnicate is invoked with {"text": payload}\n'
    'Then status equals "ok"\n'
)


def test_literal_only_criterion_compiles_with_no_surface():
    criterion = _make_criterion("AC-SCEN-001", LITERAL_ONLY_GHERKIN)

    result = criterion_compiler.compile_criterion(criterion)

    status = _field(result, "status")
    assert status == "compiled", (
        f"expected literal-only criterion to compile with no surface, got {result!r}"
    )
    source = _field(result, "source")
    assert isinstance(source, str) and source.strip(), (
        f"expected non-empty emitted source, got {source!r}"
    )


def test_literal_only_no_surface_matches_empty_surface():
    criterion_a = _make_criterion("AC-SCEN-001", LITERAL_ONLY_GHERKIN)
    criterion_b = _make_criterion("AC-SCEN-001", LITERAL_ONLY_GHERKIN)
    criterion_c = _make_criterion("AC-SCEN-001", LITERAL_ONLY_GHERKIN)

    omitted = criterion_compiler.compile_criterion(criterion_a)
    explicit_none = criterion_compiler.compile_criterion(criterion_b, None)
    empty_surface = criterion_compiler.compile_criterion(
        criterion_c, criterion_compiler.InterfaceSurface()
    )

    assert _field(omitted, "status") == "compiled", omitted
    assert _field(explicit_none, "status") == "compiled", explicit_none
    assert _field(empty_surface, "status") == "compiled", empty_surface

    src_omitted = _field(omitted, "source")
    src_none = _field(explicit_none, "source")
    src_empty = _field(empty_surface, "source")

    assert src_omitted == src_empty, (
        "emitted source with no surface differs from emitted source against an "
        f"empty surface:\n--- no surface ---\n{src_omitted}\n"
        f"--- empty surface ---\n{src_empty}"
    )
    assert src_none == src_empty, (
        "emitted source with surface=None differs from emitted source against an "
        f"empty surface:\n--- surface=None ---\n{src_none}\n"
        f"--- empty surface ---\n{src_empty}"
    )


def test_function_step_with_no_surface_is_located_error_naming_function():
    criterion = _make_criterion("AC-SCEN-002", FUNCTION_GHERKIN)

    try:
        result = criterion_compiler.compile_criterion(criterion)
    except Exception as exc:  # compile_criterion must never raise
        raise AssertionError(
            f"compile_criterion raised instead of returning an error: {exc!r}"
        )

    status = _field(result, "status")
    assert status == "error", (
        "a step referencing a function with no surface must be a compile error, "
        f"never silently compiled or skipped; got {result!r}"
    )
    assert status != "compiled"

    message = _field(result, "message")
    assert isinstance(message, str) and message, (
        f"expected an error message, got {message!r}"
    )
    # Located: the When step is line 2 of the gherkin (first line is line 1).
    assert message.startswith("line 2: "), (
        f"expected error located at 'line 2: ', got {message!r}"
    )
    # Specific: names the unresolved function.
    assert "frobnicate" in message, (
        f"expected error to name the unresolved function 'frobnicate', got {message!r}"
    )


def test_function_step_error_is_due_to_missing_surface_not_grammar():
    # Control: the same content compiles when a surface declaring the function
    # is supplied, so the no-surface error above is about the missing surface,
    # not an unrecognized step.
    criterion = _make_criterion("AC-SCEN-002", FUNCTION_GHERKIN)
    surface = criterion_compiler.InterfaceSurface(
        functions={"frobnicate": ["text"]},
        types={},
        module_name="example_target",
    )

    result = criterion_compiler.compile_criterion(criterion, surface)

    assert _field(result, "status") == "compiled", (
        f"expected compilation to succeed with a surface declaring the function, got {result!r}"
    )
    source = _field(result, "source")
    assert isinstance(source, str) and "frobnicate" in source, (
        f"expected emitted source to call frobnicate, got {source!r}"
    )