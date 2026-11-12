"""AC-COMPILE-016 (covers R-COMPILE-007): step literal values are parsed as
literal data and resolved fixture references are substituted at compile time
with the fixture's own literal value, never its name.

Written black-box against criterion_compiler's interface/ contract only:
- compile_criterion(criterion, surface) -> {"status": ..., "source"/"message": ...}
- ParsedCriterion(criterion_id, covers, kind, gherkin, file) built by keyword
- InterfaceSurface(functions, types, module_name)
"""

import ast
import json
import os
import subprocess
import sys

import pytest

import criterion_compiler


MODULE_NAME = "widget"


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _surface():
    # Equivalent of interface/library.md declaring `make(value) -> Result`
    # and interface/data/Thing.md with heading # `Thing` and json example
    # {"name": "x", "size": 1}.
    return criterion_compiler.InterfaceSurface(
        functions={"make": ["value"]},
        types={"Thing": ["name", "size"]},
        module_name=MODULE_NAME,
    )


def _criterion(gherkin, criterion_id="AC-WIDGET-001"):
    return criterion_compiler.ParsedCriterion(
        criterion_id=criterion_id,
        covers="R-WIDGET-001",
        kind="compiled",
        gherkin=gherkin,
        file="specs/components/widget/acceptance/%s.md" % criterion_id,
    )


def _compile(gherkin, criterion_id="AC-WIDGET-001"):
    out = criterion_compiler.compile_criterion(
        _criterion(gherkin, criterion_id), _surface()
    )
    return out


def _write_fake_widget(dir_path, log_path):
    code = (
        "import json\n"
        "_LOG = %r\n"
        "\n"
        "def _log(kind, args, kwargs):\n"
        "    rec = {\n"
        "        'kind': kind,\n"
        "        'args': [repr(a) for a in args],\n"
        "        'arg_types': [type(a).__name__ for a in args],\n"
        "        'kwargs': {k: repr(v) for k, v in kwargs.items()},\n"
        "        'kwarg_types': {k: type(v).__name__ for k, v in kwargs.items()},\n"
        "    }\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(rec) + '\\n')\n"
        "\n"
        "class Result:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "\n"
        "def make(*args, **kwargs):\n"
        "    _log('make', args, kwargs)\n"
        "    if args:\n"
        "        return Result(args[0])\n"
        "    return Result(kwargs.get('value'))\n"
        "\n"
        "class Thing:\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        _log('Thing', args, kwargs)\n"
        "        fields = ['name', 'size']\n"
        "        for i, a in enumerate(args):\n"
        "            setattr(self, fields[i], a)\n"
        "        for k, v in kwargs.items():\n"
        "            setattr(self, k, v)\n"
    ) % str(log_path)
    (dir_path / (MODULE_NAME + ".py")).write_text(code, encoding="utf-8")


def _run_emitted(tmp_path, source, file_stem):
    run_dir = tmp_path / ("run_" + file_stem)
    run_dir.mkdir()
    log_path = tmp_path / ("log_" + file_stem + ".jsonl")
    _write_fake_widget(run_dir, log_path)
    test_file = run_dir / ("test_" + file_stem + ".py")
    test_file.write_text(source, encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(run_dir) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(run_dir),
            str(test_file),
        ],
        cwd=str(run_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    records = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return proc, records


# (fixture name, literal as written in Gherkin, expected emitted Python
#  literal text, expected repr of the runtime value, expected type name)
LITERAL_CASES = [
    ("n", "3", "3", "3", "int"),
    ("f", "2.5", "2.5", "2.5", "float"),
    ("e", "1e3", "1000.0", "1000.0", "float"),
    ("t", "true", "True", "True", "bool"),
    ("b", "false", "False", "False", "bool"),
    ("z", "null", "None", "None", "NoneType"),
    (
        "s",
        r'"say \"hi\""',
        json.dumps('say "hi"'),
        repr('say "hi"'),
        "str",
    ),
    (
        "l",
        '[1, [2, 3], {"k": null}]',
        '[1, [2, 3], {"k": None}]',
        repr([1, [2, 3], {"k": None}]),
        "list",
    ),
]


@pytest.mark.parametrize(
    "name,gherkin_literal,emitted_literal,runtime_repr,runtime_type",
    LITERAL_CASES,
    ids=[c[0] for c in LITERAL_CASES],
)
def test_fixture_literal_is_substituted_into_call(
    tmp_path, name, gherkin_literal, emitted_literal, runtime_repr, runtime_type
):
    gherkin = (
        "Given a %s is %s\n"
        "When make is invoked with [%s]\n"
        "Then value equals %s\n"
    ) % (name, gherkin_literal, name, gherkin_literal)

    out = _compile(gherkin, "AC-WIDGET-%s" % name.upper())
    status = _get(out, "status")
    assert status == "compiled", (
        "expected %r to compile, got %r (message=%r)"
        % (gherkin, status, _get(out, "message"))
    )
    source = _get(out, "source")
    assert isinstance(source, str) and source.strip()

    # Emitted source is valid Python.
    ast.parse(source)

    # The emitted call passes the literal itself, qualified by module name.
    expected_call = "%s.make(%s)" % (MODULE_NAME, emitted_literal)
    assert expected_call in source, (
        "expected emitted call %r in source:\n%s" % (expected_call, source)
    )
    # Never the fixture's name in the call.
    assert "make(%s)" % name not in source, source

    # Exactly one top-level import of the target module.
    import_lines = [
        ln for ln in source.splitlines() if ln.strip() == "import %s" % MODULE_NAME
    ]
    assert len(import_lines) == 1, source

    # Executing the emitted test passes exactly that value to make().
    proc, records = _run_emitted(tmp_path, source, "case_" + name)
    assert proc.returncode == 0, (
        "emitted test failed:\nSTDOUT:\n%s\nSTDERR:\n%s\nSOURCE:\n%s"
        % (proc.stdout, proc.stderr, source)
    )
    make_calls = [r for r in records if r["kind"] == "make"]
    assert len(make_calls) == 1, records
    call = make_calls[0]
    if call["args"]:
        assert call["args"] == [runtime_repr], call
        assert call["arg_types"] == [runtime_type], call
        assert call["kwargs"] == {}, call
    else:  # pragma: no cover - array args must be positional per contract
        pytest.fail("array args must compile to positional arguments: %r" % call)


def test_type_construction_with_declared_fields_compiles(tmp_path):
    gherkin = (
        'Given a Thing with name: "a", size: 2\n'
        "When make is invoked with [1]\n"
        "Then value equals 1\n"
    )
    out = _compile(gherkin, "AC-WIDGET-THING")
    status = _get(out, "status")
    assert status == "compiled", (
        "expected Thing step to compile, got %r (message=%r)"
        % (status, _get(out, "message"))
    )
    source = _get(out, "source")
    assert isinstance(source, str) and source.strip()
    ast.parse(source)

    marker = "%s.Thing(" % MODULE_NAME
    assert marker in source, source
    after = source[source.index(marker):]
    assert "name" in after or '"a"' in after, source
    assert '"a"' in after, source
    assert "size" in after or "2" in after, source

    proc, records = _run_emitted(tmp_path, source, "thing")
    assert proc.returncode == 0, (
        "emitted test failed:\nSTDOUT:\n%s\nSTDERR:\n%s\nSOURCE:\n%s"
        % (proc.stdout, proc.stderr, source)
    )
    thing_calls = [r for r in records if r["kind"] == "Thing"]
    assert len(thing_calls) == 1, records
    rec = thing_calls[0]
    built = {}
    for field, arg in zip(["name", "size"], rec["args"]):
        built[field] = arg
    built.update(rec["kwargs"])
    assert built == {"name": repr("a"), "size": repr(2)}, rec


def test_type_construction_with_undeclared_field_fails_naming_it():
    gherkin = (
        'Given a Thing with colour: "red"\n'
        "When make is invoked with [1]\n"
        "Then value equals 1\n"
    )
    out = _compile(gherkin, "AC-WIDGET-COLOUR")
    status = _get(out, "status")
    message = _get(out, "message")
    assert status == "error", (
        "expected undeclared field to fail to compile, got %r (source=%r)"
        % (status, _get(out, "source"))
    )
    assert isinstance(message, str) and message
    assert "colour" in message, message
    assert message.startswith("line 1: "), message