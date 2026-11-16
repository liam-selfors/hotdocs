import os
import tempfile

import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _temp_dirs():
    root = tempfile.gettempdir()
    names = set()
    for name in os.listdir(root):
        try:
            if os.path.isdir(os.path.join(root, name)):
                names.add(name)
        except OSError:
            pass
    return names


def test_clean_probe_reaches_stub_and_leaves_no_temp_dir():
    source = "\n".join(
        [
            "from slugify import slugify",
            "",
            "",
            "def test_lowercases():",
            '    assert slugify("A") == "a"',
            "",
        ]
    )
    before = _temp_dirs()
    report = test_probe.probe(source, {}, "slugify")
    after = _temp_dirs()

    findings = list(field(report, "findings"))
    assert findings == [], findings
    assert field(report, "ok") is True
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1

    added = after - before
    assert added == set(), "probe left temporary directories behind: %r" % (added,)


def test_findings_ordered_by_check_and_to_dict_shape():
    # line 1: unknown import; line 4: undefined name
    source = "\n".join(
        [
            "import hotdocs_no_such_module_qzx",
            "",
            "",
            "def test_something():",
            "    assert undefined_thing_qzx == 1",
            "",
        ]
    )
    # Confirm the line numbering of the fixture itself.
    lines = source.split("\n")
    assert lines[0].startswith("import hotdocs_no_such_module_qzx")
    assert "undefined_thing_qzx" in lines[4 - 1 + 1] or "undefined_thing_qzx" in lines[3]

    # Rebuild so the undefined name is exactly on line 4.
    source = "\n".join(
        [
            "import hotdocs_no_such_module_qzx",
            "",
            "def test_something():",
            "    assert undefined_thing_qzx == 1",
            "",
        ]
    )
    assert source.split("\n")[3].strip() == "assert undefined_thing_qzx == 1"

    report = test_probe.probe(source, {}, "slugify")
    findings = list(field(report, "findings"))
    kinds = [field(f, "kind") for f in findings]

    assert "undefined_name" in kinds, findings
    assert "unknown_import" in kinds, findings

    undefined_idx = kinds.index("undefined_name")
    unknown_idx = kinds.index("unknown_import")
    assert undefined_idx < unknown_idx, kinds

    assert field(findings[undefined_idx], "line") == 4
    assert field(findings[unknown_idx], "line") == 1
    assert field(report, "ok") is False

    as_dict = report.to_dict()
    assert isinstance(as_dict, dict)
    dict_findings = as_dict["findings"]
    assert isinstance(dict_findings, list)
    assert len(dict_findings) == len(findings)
    for entry in dict_findings:
        assert isinstance(entry, dict)
        assert set(entry.keys()) == {"kind", "severity", "line", "message"}, entry
    assert [e["kind"] for e in dict_findings] == kinds


def test_same_line_undefined_names_ordered_by_message():
    source = "\n".join(
        [
            "def test_something():",
            "    x = 1",
            "    y = 2",
            "    z = x + y",
            "    assert zeta_q == alpha_q + z",
            "",
        ]
    )
    assert "zeta_q" in source.split("\n")[4] and "alpha_q" in source.split("\n")[4]

    report = test_probe.probe(source, {}, "slugify")
    findings = list(field(report, "findings"))
    undefined = [f for f in findings if field(f, "kind") == "undefined_name"]

    assert [field(f, "message") for f in undefined] == [
        "undefined name 'alpha_q'",
        "undefined name 'zeta_q'",
    ], findings
    assert all(field(f, "line") == 5 for f in undefined)
    assert field(report, "ok") is False