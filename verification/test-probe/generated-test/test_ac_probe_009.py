# hotdocs-criterion: sha256:0121d8d1390b0c5c61fb152d56460513d8948837d5380d0554be4a0bf91c8468
import os
import shlex
import stat
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


def _plant_wrapper(tmp_path):
    pkg_root = tmp_path / "wraponly_site"
    pkg_dir = pkg_root / "wraponly_pkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("VALUE = 1\n")

    wrapper = tmp_path / "wrapper_python"
    script = (
        "#!/bin/sh\n"
        + "PYTHONPATH=" + shlex.quote(str(pkg_root))
        + '"${PYTHONPATH:+:$PYTHONPATH}"\n'
        + "export PYTHONPATH\n"
        + "exec " + shlex.quote(sys.executable) + ' "$@"\n'
    )
    wrapper.write_text(script)
    wrapper.chmod(
        wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    return str(wrapper), str(pkg_root)


@pytest.mark.skipif(os.name == "nt", reason="the wrapper is a POSIX shell script")
def test_ac_probe_009_wrapper_interpreter(tmp_path):
    wrapper, pkg_root = _plant_wrapper(tmp_path)
    assert pkg_root not in sys.path

    report = test_probe.probe(SOURCE, {}, "slugify", interpreter=wrapper)
    findings = list(field(report, "findings"))
    assert findings == []
    assert field(report, "ok") is True
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1


def test_ac_probe_009_default_interpreter(tmp_path):
    for entry in sys.path:
        assert not os.path.isdir(os.path.join(entry or ".", "wraponly_pkg"))

    report = test_probe.probe(SOURCE, {}, "slugify")
    assert field(report, "ok") is False
    findings = list(field(report, "findings"))
    assert len(findings) == 1
    finding = findings[0]
    assert field(finding, "kind") == "unknown_import"
    assert field(finding, "line") == 1
    assert field(finding, "message") == "cannot import 'wraponly_pkg'"