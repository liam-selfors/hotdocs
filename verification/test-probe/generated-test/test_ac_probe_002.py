# hotdocs-criterion: sha256:4ba5cfeac5ff85a0225462de5ddbf96623fcaa01baa93a44516bc01a97967373
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


def test_ac_probe_002_undefined_name_only_finding():
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

    # The unused import of os gives no finding of any kind.
    kinds = [field(f, "kind") for f in findings]
    assert kinds == ["undefined_name"]