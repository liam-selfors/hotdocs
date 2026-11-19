# hotdocs-criterion: sha256:18597e4dfc9e42978b9b2ba8877c593e53facf663710dd2997a7952bd93cd5dd
import ast

import criterion_compiler


MODULE_NAME = "widget_maker"
FUNC_NAME = "do_thing"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _surface():
    return criterion_compiler.InterfaceSurface(
        functions={FUNC_NAME: ["x"]},
        types={},
        module_name=MODULE_NAME,
    )


def _criterion(criterion_id, gherkin):
    return criterion_compiler.ParsedCriterion(
        criterion_id=criterion_id,
        covers="R-WIDGET-001",
        kind="compiled",
        gherkin=gherkin,
        file="specs/components/widget-maker/acceptance/" + criterion_id + ".md",
    )


def _imports_of_module(tree, module_name):
    """Return (top_level_count, nested_count) of imports naming module_name."""
    top_level = 0
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_name and alias.asname is None:
                    top_level += 1
    total = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_name or alias.name.startswith(module_name + "."):
                    total += 1
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None and (
                node.module == module_name or node.module.startswith(module_name + ".")
            ):
                total += 1
    return top_level, total


def test_invoked_function_is_imported_once_and_qualified():
    gherkin = (
        'Given a payload is "hi"\n'
        'When ' + FUNC_NAME + ' is invoked with {"x": payload}\n'
        'Then result equals "ok"\n'
    )
    out = criterion_compiler.compile_criterion(_criterion("AC-WIDGET-001", gherkin), _surface())

    assert field(out, "status") == "compiled", out
    source = field(out, "source")
    assert isinstance(source, str)

    tree = ast.parse(source)

    top_level, total = _imports_of_module(tree, MODULE_NAME)
    assert top_level == 1, source
    assert total == 1, source

    qualified_calls = 0
    bare_calls = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == FUNC_NAME:
            bare_calls += 1
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == FUNC_NAME
            and isinstance(func.value, ast.Name)
            and func.value.id == MODULE_NAME
        ):
            qualified_calls += 1

    assert bare_calls == 0, source
    assert qualified_calls >= 1, source

    # No bare global reference to the function name anywhere either.
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == FUNC_NAME:
            raise AssertionError("bare reference to " + FUNC_NAME + " in:\n" + source)


def test_literal_only_steps_emit_no_target_import():
    gherkin = (
        'Given a payload is "hi"\n'
        'Then result equals "hi"\n'
    )
    out = criterion_compiler.compile_criterion(_criterion("AC-WIDGET-002", gherkin), _surface())

    assert field(out, "status") == "compiled", out
    source = field(out, "source")
    assert isinstance(source, str)

    tree = ast.parse(source)
    top_level, total = _imports_of_module(tree, MODULE_NAME)
    assert top_level == 0, source
    assert total == 0, source
    assert ("import " + MODULE_NAME) not in source, source