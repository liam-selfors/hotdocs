# hotdocs-criterion: sha256:a1e4f7c9ee4f9544f3c44dbd720e07bc51728be3d8ec74c7a927f70c6b29eea9
import os
import sys

import test_probe


SOURCE = "import wraponly_pkg\nimport slugify\n\n\ndef test_w():\n    assert slugify.slugify('x') == 'x'\n"


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
        + str(w / "site")
        + "\" exec '"
        + sys.executable
        + "' \"$@\"\n"
    )
    wrapper.write_text(content)
    os.chmod(str(wrapper), 0o755)
    return str(wrapper)


def test_wrapper_interpreter_resolves_import_and_runs_under_it(tmp_path):
    interpreter = make_wrapper(tmp_path)
    report = test_probe.probe(SOURCE, {}, "slugify", interpreter=interpreter)
    findings = field(report, "findings")
    assert findings == [], findings
    assert field(report, "ok") is True
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1


def test_default_interpreter_cannot_import_wraponly_pkg(tmp_path):
    make_wrapper(tmp_path)
    report = test_probe.probe(SOURCE, {}, "slugify")
    assert field(report, "ok") is False
    findings = field(report, "findings")
    assert len(findings) == 1, findings
    finding = findings[0]
    assert finding["kind"] == "unknown_import"
    assert finding["severity"] == "error"
    assert finding["line"] == 1
    assert finding["message"] == "cannot import 'wraponly_pkg'"