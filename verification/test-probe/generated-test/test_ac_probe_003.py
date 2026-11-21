# hotdocs-criterion: sha256:3edf1f2d463d4de2a319de4f31d24a240b67dd028d72eecbbd13af3bb52d7654
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


def test_unknown_import_reported_once_with_line_and_message():
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
    source = "\n".join(lines[:1] + lines[2:])
    assert "your_module_here" not in source
    report = test_probe.probe(source, {}, "slugify")
    assert _unknown_imports(report) == []


def test_relative_stdlib_dotted_and_guarded_imports_not_reported():
    source = (
        "from . import helpers\n"
        "from os import path\n"
        "import xml.etree.ElementTree\n"
        "try:\n"
        "    import yaml_nonexistent_q\n"
        "except (OSError, ImportError):\n"
        "    yaml_nonexistent_q = None\n"
        "\n"
        "\n"
        "def test_sep():\n"
        "    assert path.sep\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    assert _unknown_imports(report) == []