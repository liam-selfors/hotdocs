"""Not an AC-LINT-* criterion — a smoke test added during bootstrap: the
unmutated baseline fixture corpus (and, informally, this repo's own real
corpus, exercised manually, not here) should produce zero fail-severity
findings. A guard against false positives, which the real-corpus run during
bootstrap did in fact catch once (see BOOTSTRAP.md)."""

from conftest import run_lint


def test_baseline_corpus_is_clean(corpus_root):
    report = run_lint(corpus_root)
    assert report.hard_failures == 0, [f for f in report.findings if f.severity == "fail"]
