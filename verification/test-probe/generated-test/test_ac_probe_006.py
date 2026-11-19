# hotdocs-criterion: sha256:05dc45b644e384ed9d6ae5ed1d843ef32726da26bfd76f84003db1a4ed5af55d
import os
import tempfile

import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _temp_dir_names():
    base = tempfile.gettempdir()
    names = set()
    for entry in os.listdir(base):
        if os.path.isdir(os.path.join(base, entry)):
            names.add(entry)
    return names


def test_clean_source_reaches_stub_and_leaves_no_temp_dir():
    source = (
        "from slugify import slugify\n"
        "\n"
        "\n"
        "def test_lowercases():\n"
        "    assert slugify(" + repr("A") + ") == " + repr("a") + "\n"
    )
    before = _temp_dir_names()
    report = test_probe.probe(source, {}, "slugify")
    after = _temp_dir_names()

    assert field(report, "ok") is True
    assert list(field(report, "findings")) == []
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1
    added = after - before
    assert added == set(), "probe left directories behind: " + repr(sorted(added))


def test_findings_ordered_by_check_and_to_dict_shape():
    source = (
        "import zz_hotdocs_no_such_module_qq\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    assert undefined_thing_q == zz_hotdocs_no_such_module_qq\n"
    )
    # line 4 must carry the undefined name: adjust so it is exactly line 4
    source = (
        "import zz_hotdocs_no_such_module_qq\n"
        "\n"
        "def test_x():\n"
        "    assert undefined_thing_q == zz_hotdocs_no_such_module_qq\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = list(field(report, "findings"))
    kinds = [field(f, "kind") for f in findings]

    assert "undefined_name" in kinds
    assert "unknown_import" in kinds
    undef_idx = kinds.index("undefined_name")
    unknown_idx = kinds.index("unknown_import")
    assert undef_idx < unknown_idx
    assert field(findings[undef_idx], "line") == 4
    assert field(findings[unknown_idx], "line") == 1
    assert field(report, "ok") is False

    as_dict = report.to_dict()
    assert isinstance(as_dict, dict)
    assert isinstance(as_dict["findings"], list)
    assert len(as_dict["findings"]) == len(findings)
    for entry in as_dict["findings"]:
        assert isinstance(entry, dict)
        assert set(entry.keys()) == {"kind", "severity", "line", "message"}


def test_same_line_undefined_names_ordered_by_message():
    source = (
        "import slugify\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    assert slugify.slugify(zeta_q) == alpha_q\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = list(field(report, "findings"))
    undefined = [f for f in findings if field(f, "kind") == "undefined_name"]

    assert len(undefined) == 2
    assert [field(f, "line") for f in undefined] == [5, 5]
    assert [field(f, "message") for f in undefined] == [
        "undefined name 'alpha_q'",
        "undefined name 'zeta_q'",
    ]
    assert field(report, "ok") is False