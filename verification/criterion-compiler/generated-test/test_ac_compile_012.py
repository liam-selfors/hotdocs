import ast

import criterion_compiler


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _surface():
    return criterion_compiler.InterfaceSurface(
        functions={"make_thing": ["a", "b"]},
        types={},
        module_name="widgets",
    )


def _criterion(gherkin):
    return criterion_compiler.ParsedCriterion(
        criterion_id="AC-W-001",
        covers="R-W-001",
        kind="compiled",
        gherkin=gherkin,
        file="specs/components/widgets/acceptance/AC-W-001.md",
    )


def _compile(when_args):
    gherkin = (
        'Given a user_id is "u1"\n'
        "When make_thing is invoked with " + when_args + "\n"
        'Then status equals "ok"\n'
    )
    return criterion_compiler.compile_criterion(_criterion(gherkin), _surface())


def test_bare_fixture_reference_is_substituted_at_compile_time():
    out = _compile('[user_id, {"owner": user_id}]')
    status = _get(out, "status")
    assert status == "compiled", "expected compiled, got %r: %r" % (
        status,
        _get(out, "message"),
    )
    source = _get(out, "source")
    assert isinstance(source, str) and source

    # The emitted file must itself be valid Python.
    ast.parse(source)

    lines = source.splitlines()
    call_lines = [ln for ln in lines if "make_thing(" in ln]
    assert call_lines, "no emitted call line for make_thing in:\n" + source
    for call_line in call_lines:
        assert "user_id" not in call_line, (
            "call line references the fixture name instead of its literal: %r"
            % call_line
        )
        assert call_line.count('"u1"') >= 2, (
            "call line does not hold \"u1\" in both positions: %r" % call_line
        )
        assert '{"owner": "u1"}' in call_line, (
            "nested object literal not substituted: %r" % call_line
        )

    # The Given still binds a local.
    assert any(ln.strip() == 'user_id = "u1"' for ln in lines), (
        "expected a line 'user_id = \"u1\"' in:\n" + source
    )


def test_operator_on_bound_fixture_is_located_not_a_literal_error():
    out = _compile("[user_id + 1]")
    assert _get(out, "status") == "error"
    message = _get(out, "message")
    assert isinstance(message, str)
    assert message.startswith("line 2: "), message
    assert "is not a literal" in message, message
    assert "user_id + 1" in message or "user_id+1" in message, message
    assert "field/index access" not in message, message
    assert not _get(out, "source"), "no source may be emitted on error"


def test_field_access_on_bound_fixture_is_located_error():
    out = _compile("[user_id.id]")
    assert _get(out, "status") == "error"
    message = _get(out, "message")
    assert isinstance(message, str)
    assert message.startswith("line 2: "), message
    assert "user_id.id" in message, message
    assert "is not a literal" in message, message
    assert "field/index access" in message, message
    assert not _get(out, "source"), "no source may be emitted on error"


def test_unbound_bare_identifier_is_located_unresolved_reference_error():
    out = _compile("[does_not_exist]")
    assert _get(out, "status") == "error"
    message = _get(out, "message")
    assert isinstance(message, str)
    assert message.startswith("line 2: "), message
    assert "unresolved reference 'does_not_exist'" in message, message
    assert not _get(out, "source"), "no source may be emitted on error"