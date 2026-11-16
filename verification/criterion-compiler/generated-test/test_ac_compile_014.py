import ast
import re

import criterion_compiler


MODULE_NAME = "target_widget_mod"
FUNC_NAME = "make_widget"


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _criterion(gherkin, criterion_id="AC-WIDGET-001", covers="R-WIDGET-001"):
    return criterion_compiler.ParsedCriterion(
        criterion_id=criterion_id,
        covers=covers,
        kind="compiled",
        gherkin=gherkin,
        file="specs/components/widget/acceptance/" + criterion_id + ".md",
    )


def _surface():
    return criterion_compiler.InterfaceSurface(
        functions={FUNC_NAME: ["x"]},
        types={},
        module_name=MODULE_NAME,
    )


def _compile_ok(criterion, surface):
    out = criterion_compiler.compile_criterion(criterion, surface)
    status = _field(out, "status")
    assert status == "compiled", "expected compiled, got %r (message=%r)" % (
        status,
        _field(out, "message"),
    )
    source = _field(out, "source")
    assert isinstance(source, str) and source.strip(), "emitted source is empty"
    return source


def _top_level_imports_of(tree, module_name):
    count = 0
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_name:
                    count += 1
    return count


def _any_import_of(tree, module_name):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_name or alias.name.startswith(module_name + "."):
                    return True
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == module_name or mod.startswith(module_name + "."):
                return True
    return False


def _calls_to(tree, func_name):
    qualified = 0
    bare = 0
    other = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == func_name:
            bare += 1
        elif isinstance(func, ast.Attribute) and func.attr == func_name:
            if isinstance(func.value, ast.Name) and func.value.id == MODULE_NAME:
                qualified += 1
            else:
                other += 1
    return qualified, bare, other


def _assert_qualified_single_import(source, expected_min_calls):
    tree = ast.parse(source)

    assert _top_level_imports_of(tree, MODULE_NAME) == 1, (
        "expected exactly one top-level 'import %s', source:\n%s" % (MODULE_NAME, source)
    )
    import_lines = [
        line for line in source.splitlines() if line.strip() == "import " + MODULE_NAME
    ]
    assert len(import_lines) == 1, source
    assert import_lines[0] == "import " + MODULE_NAME, (
        "import line must be top-level (unindented), source:\n%s" % source
    )

    qualified, bare, other = _calls_to(tree, FUNC_NAME)
    assert bare == 0, "found bare call to %s, source:\n%s" % (FUNC_NAME, source)
    assert other == 0, "found call to %s qualified by something else, source:\n%s" % (
        FUNC_NAME,
        source,
    )
    assert qualified >= expected_min_calls, (
        "expected >= %d calls to %s.%s, found %d, source:\n%s"
        % (expected_min_calls, MODULE_NAME, FUNC_NAME, qualified, MODULE_NAME and source)
    )

    # Textual double-check: no unqualified reference to the function name anywhere.
    for match in re.finditer(r"\b" + re.escape(FUNC_NAME) + r"\b", source):
        start = match.start()
        prefix = source[:start]
        assert prefix.endswith(MODULE_NAME + "."), (
            "unqualified reference to %s at offset %d, source:\n%s" % (FUNC_NAME, start, source)
        )


def test_when_invoke_imports_target_module_once_and_qualifies_call():
    gherkin = "\n".join(
        [
            'Given a payload is "hello"',
            'When %s is invoked with {"x": payload}' % FUNC_NAME,
            'Then status equals "ok"',
        ]
    )
    source = _compile_ok(_criterion(gherkin), _surface())
    _assert_qualified_single_import(source, expected_min_calls=1)


def test_multiple_invocations_share_single_import_and_all_qualified():
    gherkin = "\n".join(
        [
            'Given a payload is "hello"',
            'When %s is invoked with {"x": payload}' % FUNC_NAME,
            'Then status equals "ok"',
            "",
            'Given a other is "world"',
            'When %s is invoked with {"x": other}' % FUNC_NAME,
            'Then status equals "ok"',
        ]
    )
    source = _compile_ok(_criterion(gherkin, "AC-WIDGET-002", "R-WIDGET-002"), _surface())
    _assert_qualified_single_import(source, expected_min_calls=2)


def test_literal_only_steps_emit_no_target_module_import_with_surface():
    gherkin = "\n".join(
        [
            "Given a count is 3",
            "Then count equals 3",
        ]
    )
    source = _compile_ok(_criterion(gherkin, "AC-WIDGET-003", "R-WIDGET-003"), _surface())
    tree = ast.parse(source)
    assert not _any_import_of(tree, MODULE_NAME), (
        "literal-only criterion must not import %s, source:\n%s" % (MODULE_NAME, source)
    )
    assert not re.search(r"^\s*import\s+" + re.escape(MODULE_NAME) + r"\b", source, re.M), source
    assert not re.search(r"^\s*from\s+" + re.escape(MODULE_NAME) + r"\b", source, re.M), source


def test_literal_only_steps_emit_no_target_module_import_without_surface():
    gherkin = "\n".join(
        [
            'Given a label is "abc"',
            'Then label equals "abc"',
        ]
    )
    out = criterion_compiler.compile_criterion(
        _criterion(gherkin, "AC-WIDGET-004", "R-WIDGET-004"), None
    )
    assert _field(out, "status") == "compiled", _field(out, "message")
    source = _field(out, "source")
    assert isinstance(source, str) and source.strip()
    tree = ast.parse(source)
    assert not _any_import_of(tree, MODULE_NAME), source
    assert MODULE_NAME not in source, source