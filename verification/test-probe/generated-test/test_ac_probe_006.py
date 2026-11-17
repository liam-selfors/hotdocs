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


PASSING_SOURCE = (
    "import slugify\n"
    "\n"
    "\n"
    "def test_lowercases():\n"
    "    assert slugify.slugify(\"A\") == \"a\"\n"
)


def test_clean_source_reaches_stub_and_cleans_up_temp_dir():
    before = _temp_dirs()
    report = test_probe.probe(PASSING_SOURCE, {}, "slugify")
    after = _temp_dirs()

    assert field(report, "ok") is True
    assert list(field(report, "findings")) == []
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1

    added = after - before
    assert added == set(), "probe left directories behind: %r" % sorted(added)


ORDER_SOURCE = (
    "import hotdocs_probe_no_such_module_zq\n"
    "\n"
    "\n"
    "def test_something():\n"
    "    assert undefined_thing_q == 1\n"
)
# Line 4 must hold the undefined name: adjust so it does.
ORDER_SOURCE = (
    "import hotdocs_probe_no_such_module_zq\n"
    "\n"
    "def test_something():\n"
    "    assert undefined_thing_q == 1\n"
)


def test_findings_ordered_by_check_not_line_and_to_dict_shape():
    lines = ORDER_SOURCE.splitlines()
    assert "undefined_thing_q" in lines[3]
    assert "hotdocs_probe_no_such_module_zq" in lines[0]

    report = test_probe.probe(ORDER_SOURCE, {}, "slugify")
    findings = list(field(report, "findings"))
    kinds = [f["kind"] for f in findings]

    assert "undefined_name" in kinds
    assert "unknown_import" in kinds

    undefined_idx = next(
        i for i, f in enumerate(findings)
        if f["kind"] == "undefined_name" and f["line"] == 4
    )
    unknown_idx = next(
        i for i, f in enumerate(findings)
        if f["kind"] == "unknown_import" and f["line"] == 1
    )
    assert undefined_idx < unknown_idx

    assert field(report, "ok") is False

    as_dict = report.to_dict()
    assert isinstance(as_dict, dict)
    dict_findings = as_dict["findings"]
    assert len(dict_findings) == len(findings)
    for entry in dict_findings:
        assert set(entry.keys()) == {"kind", "severity", "line", "message"}


SAME_LINE_SOURCE = (
    "import slugify\n"
    "\n"
    "\n"
    "def test_something():\n"
    "    assert zeta_q == alpha_q\n"
)


def test_same_line_findings_ordered_by_message():
    lines = SAME_LINE_SOURCE.splitlines()
    assert lines[4].index("zeta_q") < lines[4].index("alpha_q")

    report = test_probe.probe(SAME_LINE_SOURCE, {}, "slugify")
    findings = list(field(report, "findings"))
    undefined = [f for f in findings if f["kind"] == "undefined_name"]

    assert [f["line"] for f in undefined] == [5, 5]
    assert [f["message"] for f in undefined] == [
        "undefined name 'alpha_q'",
        "undefined name 'zeta_q'",
    ]