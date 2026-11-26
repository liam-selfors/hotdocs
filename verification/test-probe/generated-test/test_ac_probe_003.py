# hotdocs-criterion: sha256:c1b3e242cd91b1cd91a0d099ddf04ba179d67efd4a4272f3370f7c5403466c68
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SOURCE = (
    "import json\n"
    "import your_module_here\n"
    "from slugify import slugify\n"
    "try:\n"
    "    import nosuchpkg_optional\n"
    "except ImportError:\n"
    "    nosuchpkg_optional = None\n"
    "\n"
    "def test_a():\n"
    "    assert slugify('A') == 'a'\n"
)


def _unknown_imports(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "kind") == "unknown_import"]


def test_unresolvable_import_is_reported_once():
    report = test_probe.probe(SOURCE, {}, "slugify")
    assert field(report, "ok") is False
    unknown = _unknown_imports(report)
    assert len(unknown) == 1
    finding = unknown[0]
    assert field(finding, "line") == 2
    assert field(finding, "message") == "cannot import 'your_module_here'"
    assert field(finding, "severity") == "error"


def test_without_second_line_no_unknown_import():
    lines = SOURCE.split("\n")
    del lines[1]
    source = "\n".join(lines)
    assert "your_module_here" not in source
    report = test_probe.probe(source, {}, "slugify")
    assert _unknown_imports(report) == []


def test_relative_stdlib_and_guarded_imports_not_reported():
    source = (
        "from . import helpers\n"
        "from os import path\n"
        "import xml.etree.ElementTree\n"
        "try:\n"
        "    import yaml_nonexistent_q\n"
        "except (OSError, ImportError):\n"
        "    yaml_nonexistent_q = None\n"
        "\n"
        "def test_sep():\n"
        "    assert path.sep\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    assert _unknown_imports(report) == []