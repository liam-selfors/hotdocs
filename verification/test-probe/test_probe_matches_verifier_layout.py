"""Hand suite: a test that passes in the verifier's layout reaches the
stub in the probe's (`D303`), so the probe never rejects a sound test
for layout reasons alone.

The verifier runs a generated test with `PYTHONPATH` the component's
`gen/<slug>/` and `--noconftest` (verifier-orchestrator's R-VERIFY-001,
R-VERIFY-014); the probe runs it with `PYTHONPATH` its stub directory.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "test-probe"))
import test_probe  # noqa: E402

SAMPLE = '''import pytest
from widget_maker import make, Widget


def test_make_returns_a_widget(tmp_path):
    (tmp_path / "in.txt").write_text("a")
    w = make(str(tmp_path / "in.txt"))
    assert isinstance(w, Widget)


def test_bad_input_raises():
    with pytest.raises(ValueError):
        make("")
'''

MODULE = '''class Widget:
    pass


def make(path):
    if not path:
        raise ValueError("empty")
    return Widget()
'''


def test_sample_passes_in_the_verifier_layout(tmp_path):
    code = tmp_path / "gen" / "widget-maker"
    code.mkdir(parents=True)
    (code / "widget_maker.py").write_text(MODULE)
    tests = tmp_path / "verification" / "widget-maker" / "generated-test"
    tests.mkdir(parents=True)
    (tests / "test_ac_widget_001.py").write_text(SAMPLE)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--noconftest", str(tests)],
        cwd=tmp_path, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(code)}, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_same_sample_reaches_the_stub_in_the_probe():
    report = test_probe.probe(SAMPLE, {}, "widget_maker")
    findings = report.findings if hasattr(report, "findings") else report["findings"]
    assert report.ok if hasattr(report, "ok") else report["ok"], findings
    reached = report.tests_reached if hasattr(report, "tests_reached") else report["tests_reached"]
    assert reached == 2
