# hotdocs-criterion: sha256:3a3d7edd033e236c8ceb0363a0fc42b1a10ff633dc0a59d814eea2593e8a7870
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


def test_unresolvable_import_reported_once_with_line_and_message():
    report = test_probe.probe(SOURCE, {}, "slugify")
    assert field(report, "ok") is False
    unknown = _unknown_imports(report)
    assert len(unknown) == 1, unknown
    finding = unknown[0]
    assert field(finding, "line") == 2
    assert field(finding, "message") == "cannot import 'your_module_here'"
    assert field(finding, "severity") == "error"


def test_without_unresolvable_import_no_unknown_import_finding():
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
        "def test_sep():\n"
        "    assert path.sep\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    assert _unknown_imports(report) == []