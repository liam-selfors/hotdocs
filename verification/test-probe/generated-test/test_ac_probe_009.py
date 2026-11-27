# hotdocs-criterion: sha256:cc89e7ad36d7586b0ace560de7abc07fa71fe977e04c0432987253c4d5fc5f44
import os
import sys

import test_probe


SOURCE = (
    "import wraponly_pkg\n"
    "import slugify\n"
    "\n"
    "\n"
    "def test_w():\n"
    "    assert slugify.slugify('x') == 'x'\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_wrapper(tmp_path):
    w = tmp_path
    site = w / "site"
    site.mkdir()
    (site / "wraponly_pkg.py").write_text("")
    wrapper = w / "pywrap"
    content = (
        "#!/bin/sh\n"
        + 'PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}'
        + str(w)
        + '/site" exec \''
        + sys.executable
        + "' \"$@\"\n"
    )
    wrapper.write_text(content)
    os.chmod(str(wrapper), 0o755)
    return str(wrapper)


def test_ac_probe_009_wrapper_interpreter_resolves_import(tmp_path):
    interpreter = make_wrapper(tmp_path)
    report = test_probe.probe(SOURCE, {}, "slugify", interpreter=interpreter)
    findings = field(report, "findings")
    assert findings == [], findings
    assert field(report, "ok") is True
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1


def test_ac_probe_009_default_interpreter_cannot_import(tmp_path):
    make_wrapper(tmp_path)
    report = test_probe.probe(SOURCE, {}, "slugify")
    assert field(report, "ok") is False
    findings = field(report, "findings")
    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, "kind") == "unknown_import"
    assert field(finding, "severity") == "error"
    assert field(finding, "line") == 1
    assert field(finding, "message") == "cannot import 'wraponly_pkg'"