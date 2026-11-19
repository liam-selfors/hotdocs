# hotdocs-criterion: sha256:2b63054bc3aef671134a495788d7f2056e67c491521c2f901a2c73ca7286d9a9
import criterion_compiler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _criterion(criterion_id, gherkin):
    return criterion_compiler.ParsedCriterion(
        criterion_id=criterion_id,
        covers="R-CAP-001",
        kind="compiled",
        gherkin=gherkin,
        file="specs/capabilities/some-capability/scenarios/" + criterion_id + ".md",
    )


def test_literal_only_criterion_compiles_without_surface_same_as_empty_surface():
    gherkin = (
        'Given a payload is "x"\n'
        'Given a count is 3\n'
        'Then payload equals "x"\n'
    )
    criterion = _criterion("S-LIT-001", gherkin)

    no_surface = criterion_compiler.compile_criterion(criterion)
    assert field(no_surface, "status") == "compiled", no_surface

    criterion_again = _criterion("S-LIT-001", gherkin)
    empty_surface = criterion_compiler.compile_criterion(
        criterion_again, criterion_compiler.InterfaceSurface()
    )
    assert field(empty_surface, "status") == "compiled", empty_surface

    assert field(no_surface, "source") == field(empty_surface, "source")


def test_function_step_without_surface_is_located_specific_error():
    gherkin = (
        'Given a payload is "x"\n'
        'When do_frobnicate is invoked with {"text": payload}\n'
        'Then value equals "x"\n'
    )
    criterion = _criterion("S-FN-001", gherkin)

    result = criterion_compiler.compile_criterion(criterion)
    assert field(result, "status") == "error", result
    message = field(result, "message")
    assert isinstance(message, str)
    assert message.startswith("line 2: "), message
    assert "do_frobnicate" in message, message