# hotdocs-criterion: sha256:22b012a0355e76d715f5d1b7ce39278368b9ac5e3f8476e2691b43364c576c9f
import criterion_compiler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _surface():
    return criterion_compiler.InterfaceSurface(
        functions={"make_thing": ["a", "b"]},
        types={},
        module_name="widget_mod",
    )


def _criterion(gherkin):
    return criterion_compiler.ParsedCriterion(
        criterion_id="AC-WIDGET-001",
        covers="R-WIDGET-001",
        kind="compiled",
        gherkin=gherkin,
        file="specs/components/widget/acceptance/AC-WIDGET-001.md",
    )


def _compile(gherkin):
    return criterion_compiler.compile_criterion(_criterion(gherkin), _surface())


def test_bare_fixture_reference_is_substituted_at_compile_time():
    gherkin = (
        'Given a user_id is "u1"\n'
        'When make_thing is invoked with [user_id, {"owner": user_id}]\n'
        'Then status equals "ok"\n'
    )
    out = _compile(gherkin)
    assert field(out, "status") == "compiled", out
    source = field(out, "source")
    lines = source.splitlines()

    call_lines = [ln for ln in lines if "make_thing(" in ln]
    assert call_lines, source
    call_line = call_lines[0]
    assert call_line.count('"u1"') >= 2, call_line
    assert '{"owner": "u1"}' in call_line, call_line
    assert "user_id" not in call_line, call_line

    assert any(ln.strip() == 'user_id = "u1"' for ln in lines), source


def test_operator_on_fixture_is_rejected_as_not_a_literal():
    gherkin = (
        'Given a user_id is "u1"\n'
        "When make_thing is invoked with [user_id + 1]\n"
        'Then status equals "ok"\n'
    )
    out = _compile(gherkin)
    assert field(out, "status") == "error", out
    message = field(out, "message")
    assert message.startswith("line 2: "), message
    assert "is not a literal" in message, message
    assert "user_id + 1" in message, message


def test_field_access_on_fixture_is_rejected():
    gherkin = (
        'Given a user_id is "u1"\n'
        "When make_thing is invoked with [user_id.id]\n"
        'Then status equals "ok"\n'
    )
    out = _compile(gherkin)
    assert field(out, "status") == "error", out
    message = field(out, "message")
    assert message.startswith("line 2: "), message
    assert "is not a literal" in message, message
    assert "field/index access" in message, message
    assert "user_id.id" in message, message


def test_unbound_identifier_is_unresolved_reference_error():
    gherkin = (
        'Given a user_id is "u1"\n'
        "When make_thing is invoked with [does_not_exist]\n"
        'Then status equals "ok"\n'
    )
    out = _compile(gherkin)
    assert field(out, "status") == "error", out
    message = field(out, "message")
    assert message.startswith("line 2: "), message
    assert "unresolved reference 'does_not_exist'" in message, message