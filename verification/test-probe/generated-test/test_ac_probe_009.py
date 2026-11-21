# hotdocs-criterion: sha256:0aba7a3478bbe64349b30ea6968472e750b1f8fa09457dc6e0a778dc1e57df9c
import os
import sys

import pytest

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


def make_wrapper(w):
    site = w / "site"
    site.mkdir(parents=True, exist_ok=True)
    (site / "wraponly_pkg.py").write_text("")
    pywrap = w / "pywrap"
    content = (
        "#!/bin/sh\n"
        + 'PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}'
        + str(w)
        + '/site" exec \''
        + sys.executable
        + '\' "$@"\n'
    )
    pywrap.write_text(content)
    os.chmod(str(pywrap), 0o755)
    return str(pywrap)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell wrapper")
def test_ac_probe_009_wrapper_interpreter_resolves_import(tmp_path):
    interpreter = make_wrapper(tmp_path)

    report = test_probe.probe(SOURCE, {}, "slugify", interpreter=interpreter)

    assert field(report, "ok") is True
    assert list(field(report, "findings")) == []
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1


def test_ac_probe_009_default_interpreter_cannot_import():
    report = test_probe.probe(SOURCE, {}, "slugify")

    assert field(report, "ok") is False
    findings = list(field(report, "findings"))
    assert len(findings) == 1
    finding = findings[0]
    assert field(finding, "kind") == "unknown_import"
    assert field(finding, "line") == 1
    assert field(finding, "message") == "cannot import 'wraponly_pkg'"