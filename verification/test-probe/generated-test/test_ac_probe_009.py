# hotdocs-criterion: sha256:69f19314d1744a6a92281464267b2a569a8a15f34f86c49d336bd58d12d9f5b3
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


def _plant_wrapper(w):
    site = w / "site"
    site.mkdir(parents=True, exist_ok=True)
    (site / "wraponly_pkg.py").write_text("")
    wrapper = w / "pywrap"
    content = (
        "#!/bin/sh\n"
        + 'PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}'
        + str(site)
        + '" exec '
        + "'"
        + sys.executable
        + "'"
        + ' "$@"\n'
    )
    wrapper.write_text(content)
    os.chmod(str(wrapper), 0o755)
    return str(wrapper)


def test_wrapper_interpreter_resolves_its_own_imports(tmp_path):
    interpreter = _plant_wrapper(tmp_path)

    report = test_probe.probe(SOURCE, {}, "slugify", interpreter=interpreter)

    assert field(report, "ok") is True, field(report, "findings")
    assert list(field(report, "findings")) == []
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1


def test_default_interpreter_cannot_import_wraponly_pkg(tmp_path):
    _plant_wrapper(tmp_path)

    report = test_probe.probe(SOURCE, {}, "slugify")

    assert field(report, "ok") is False
    findings = list(field(report, "findings"))
    assert len(findings) == 1, findings
    finding = findings[0]
    assert finding["kind"] == "unknown_import"
    assert finding["severity"] == "error"
    assert finding["line"] == 1
    assert finding["message"] == "cannot import 'wraponly_pkg'"