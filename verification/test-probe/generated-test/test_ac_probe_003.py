import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SOURCE_WITH_UNKNOWN = (
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


def _without_second_line(source):
    lines = source.splitlines(keepends=True)
    return "".join(lines[:1] + lines[2:])


def _unknown_import_findings(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "kind") == "unknown_import"]


def test_unknown_import_reported_once_with_line_and_message():
    report = test_probe.probe(SOURCE_WITH_UNKNOWN, {}, "slugify")
    assert field(report, "ok") is False
    unknown = _unknown_import_findings(report)
    assert len(unknown) == 1, unknown
    finding = unknown[0]
    assert field(finding, "line") == 2
    assert field(finding, "message") == "cannot import 'your_module_here'"


def test_no_unknown_import_without_second_line():
    source = _without_second_line(SOURCE_WITH_UNKNOWN)
    assert "your_module_here" not in source
    assert source.startswith("import json\nfrom slugify import slugify\n")
    report = test_probe.probe(source, {}, "slugify")
    assert _unknown_import_findings(report) == []


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
    assert _unknown_import_findings(report) == []