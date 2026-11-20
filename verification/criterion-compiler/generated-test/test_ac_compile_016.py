# hotdocs-criterion: sha256:6d515c287dc08e02312add5962c7f1d8b2eade9d607245121b92183eca2944da
import ast

import pytest

import criterion_compiler


MODULE_NAME = "widget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_surface():
    return criterion_compiler.InterfaceSurface(
        functions={"make": ["value"]},
        types={"Thing": ["name", "size"]},
        module_name=MODULE_NAME,
    )


def make_criterion(gherkin):
    return criterion_compiler.ParsedCriterion(
        criterion_id="AC-WIDGET-001",
        covers="R-WIDGET-001",
        kind="compiled",
        gherkin=gherkin,
        file="specs/components/widget/acceptance/AC-WIDGET-001.md",
    )


def compile_text(gherkin):
    return criterion_compiler.compile_criterion(make_criterion(gherkin), make_surface())


def is_qualified(func, attr):
    return (
        isinstance(func, ast.Attribute)
        and func.attr == attr
        and isinstance(func.value, ast.Name)
        and func.value.id == MODULE_NAME
    )


def find_calls(source, attr):
    tree = ast.parse(source)
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and is_qualified(node.func, attr)
    ]


LITERAL_CASES = [
    ("n", "3", 3),
    ("f", "2.5", 2.5),
    ("e", "1e3", 1000.0),
    ("t", "true", True),
    ("b", "false", False),
    ("z", "null", None),
    ("s", r'"say \"hi\""', 'say "hi"'),
    ("l", '[1, [2, 3], {"k": null}]', [1, [2, 3], {"k": None}]),
]


@pytest.mark.parametrize("name,literal,expected", LITERAL_CASES)
def test_fixture_literal_substituted_into_call(name, literal, expected):
    gherkin = (
        "Given a " + name + " is " + literal + "\n"
        + "When make is invoked with [" + name + "]\n"
        + "Then value equals " + literal + "\n"
    )
    outcome = compile_text(gherkin)
    status = field(outcome, "status")
    assert status == "compiled", repr(outcome)
    source = field(outcome, "source")
    assert isinstance(source, str)

    calls = find_calls(source, "make")
    assert calls, "no call to " + MODULE_NAME + ".make in emitted source:\n" + source
    for call in calls:
        assert not call.keywords, source
        assert len(call.args) == 1, source
        # The argument must be a literal (not a reference to the fixture name)
        value = ast.literal_eval(call.args[0])
        assert value == expected, source
        assert type(value) is type(expected), source
        if isinstance(expected, list):
            assert type(value[1]) is list
            assert type(value[2]) is dict
            assert value[2]["k"] is None


def test_type_construction_with_fields_compiles():
    gherkin = (
        'Given a Thing with name: "a", size: 2\n'
        + "When make is invoked with [1]\n"
        + "Then value equals 1\n"
    )
    outcome = compile_text(gherkin)
    assert field(outcome, "status") == "compiled", repr(outcome)
    source = field(outcome, "source")

    calls = find_calls(source, "Thing")
    assert calls, "no construction of " + MODULE_NAME + ".Thing in:\n" + source
    call = calls[0]
    built = {}
    for kw in call.keywords:
        assert kw.arg is not None, source
        built[kw.arg] = ast.literal_eval(kw.value)
    field_order = ["name", "size"]
    for idx, arg in enumerate(call.args):
        built[field_order[idx]] = ast.literal_eval(arg)
    assert built == {"name": "a", "size": 2}, source


def test_type_construction_with_unknown_field_fails():
    gherkin = (
        'Given a Thing with colour: "red"\n'
        + "When make is invoked with [1]\n"
        + "Then value equals 1\n"
    )
    outcome = compile_text(gherkin)
    assert field(outcome, "status") == "error", repr(outcome)
    message = field(outcome, "message")
    assert isinstance(message, str)
    assert "colour" in message