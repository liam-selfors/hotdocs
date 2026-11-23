# hotdocs-criterion: sha256:632cccf2c2e733fb0f8bc74635af78b32763d7b97dacc158cce271f7052be164
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SOURCE = (
    "import os\n"
    "from slugify import slugify\n"
    "\n"
    "def test_a():\n"
    "    assert slugify(tmp_dir) == 'x'\n"
)


def test_undefined_name_is_the_only_finding():
    report = test_probe.probe(SOURCE, {}, "slugify")

    assert field(report, "ok") is False

    findings = field(report, "findings")
    assert isinstance(findings, list)
    assert len(findings) == 1, findings

    finding = findings[0]
    assert field(finding, "kind") == "undefined_name"
    assert field(finding, "severity") == "error"
    assert field(finding, "line") == 5
    assert field(finding, "message") == "undefined name 'tmp_dir'"


def test_unused_import_gives_no_finding_and_no_stub_run():
    report = test_probe.probe(SOURCE, {}, "slugify")

    findings = field(report, "findings")
    kinds = [field(f, "kind") for f in findings]
    assert kinds == ["undefined_name"]
    assert all("os" not in field(f, "message") for f in findings)

    assert field(report, "tests_run") == 0
    assert field(report, "tests_reached") == 0