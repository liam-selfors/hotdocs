# hotdocs-criterion: sha256:dcdbee30b69bf77142bac9ade7edc52c69690c4e529af004dd53d7f079181351
import json
import sys
from pathlib import Path

import pytest

import spec_completeness_assistant


WARN_RULE_ID = "R-LINT-007"
FAIL_RULE_ID = "R-LINT-003"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_corpus(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does foo things.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo()` MUST return `1`.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When foo() runs\n"
        "Then it returns 1\n"
        "```\n",
    )


def _write_fakes(repo_root, finding, log_path):
    gen = repo_root / "gen"

    lint_src = (
        "FINDINGS = " + repr([finding]) + "\n"
        "\n"
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    findings = [dict(f) for f in FINDINGS]\n"
        "    hard = sum(1 for f in findings if f['severity'] == 'fail')\n"
        "    warns = sum(1 for f in findings if f['severity'] == 'warn')\n"
        "    skipped = sum(1 for f in findings if f['severity'] == 'skipped')\n"
        "    return {'findings': findings, 'summary': {'hard_failures': hard, "
        "'warnings': warns, 'skipped': skipped}}\n"
    )
    _write(gen / "spec-linter" / "spec_linter.py", lint_src)

    impact_src = (
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    return {'impacted': [{'component_id': 'comp-foo', 'reason': 'direct', "
        "'via': None}], 'precondition_error': None}\n"
    )
    _write(gen / "impact-analyzer" / "impact_analyzer.py", impact_src)

    reviewer_src = (
        "class ReviewReport:\n"
        "    def to_dict(self):\n"
        "        return {'findings': []}\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, "
        "write_proposals=False):\n"
        "    return ReviewReport()\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    return judge\n"
    )
    _write(gen / "spec-reviewer" / "spec_reviewer.py", reviewer_src)

    response_text = json.dumps(
        {"completeness_score": 0.7, "completeness_rationale": "AC missing"}
    )
    endpoint_src = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "RESPONSE_TEXT = " + repr(response_text) + "\n"
        "\n"
        "def complete(prompt, model, backend=None, **params):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(model) + '\\n')\n"
        "    return {'text': RESPONSE_TEXT, 'model': model, 'backend': 'mock', "
        "'model_call_error': None}\n"
    )
    _write(gen / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


def _make_repo(tmp_path, severity, file):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_corpus(repo_root)
    log_path = tmp_path / "complete_calls.log"
    rule_id = WARN_RULE_ID if severity == "warn" else FAIL_RULE_ID
    finding = {
        "rule_id": rule_id,
        "severity": severity,
        "file": file,
        "line": 3,
        "message": "synthetic " + severity + " finding",
    }
    _write_fakes(repo_root, finding, log_path)
    return repo_root, log_path


@pytest.fixture
def warn_repo(tmp_path, monkeypatch):
    repo_root, log_path = _make_repo(
        tmp_path, "warn", "specs/components/foo/requirements/R-FOO-001.md"
    )
    monkeypatch.chdir(repo_root)
    return repo_root, log_path


def test_json_degraded(warn_repo, capsys):
    repo_root, _ = warn_repo
    code = spec_completeness_assistant.main(
        ["--changed=R-FOO-001", "--repo-root=" + str(repo_root), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert field(data, "predicted_blast_radius") == ["comp-foo"]
    assert field(data, "degraded") is True


def test_text_degraded_space_separated(warn_repo, capsys):
    repo_root, _ = warn_repo
    code = spec_completeness_assistant.main(
        ["--changed", "R-FOO-001", "--repo-root", str(repo_root), "--format", "text"]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert WARN_RULE_ID in out
    assert "comp-foo" in out


def test_json_with_model(warn_repo, capsys):
    repo_root, log_path = warn_repo
    code = spec_completeness_assistant.main(
        [
            "--changed=R-FOO-001",
            "--repo-root=" + str(repo_root),
            "--model=fake-model",
            "--format=json",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert log_path.is_file()
    models = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    assert models
    assert "fake-model" in models
    assert all(m == "fake-model" for m in models)
    data = json.loads(out)
    assert field(data, "degraded") is False
    assert field(data, "completeness_score") == 0.7


def test_text_with_model(warn_repo, capsys):
    repo_root, log_path = warn_repo
    code = spec_completeness_assistant.main(
        [
            "--changed=R-FOO-001",
            "--repo-root=" + str(repo_root),
            "--model=fake-model",
            "--format=text",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "0.7" in out
    models = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    assert "fake-model" in models


def test_fail_finding_inside_changed_component_halts(tmp_path, monkeypatch, capsys):
    repo_root, _ = _make_repo(tmp_path, "fail", "specs/components/foo/component.md")
    monkeypatch.chdir(repo_root)
    code = spec_completeness_assistant.main(
        ["--changed=R-FOO-001", "--repo-root=" + str(repo_root)]
    )
    capsys.readouterr()
    assert code == 1


@pytest.mark.parametrize(
    "argv_builder",
    [
        lambda root: [],
        lambda root: ["serve", "--changed=R-FOO-001"],
        lambda root: ["--repo-root=" + root, "--format=json"],
        lambda root: ["--changed=R-FOO-001", "--repo-root=" + root, "--format=bogus"],
        lambda root: ["--changed=R-FOO-001", "--repo-root=" + root, "--hotdocs-smoke-unknown"],
        lambda root: ["--repo-root=" + root, "--changed"],
    ],
    ids=[
        "empty",
        "stray-word",
        "no-changed",
        "bogus-format",
        "unknown-argument",
        "changed-last-no-value",
    ],
)
def test_usage_errors(warn_repo, capsys, argv_builder):
    repo_root, _ = warn_repo
    argv = argv_builder(str(repo_root))
    code = spec_completeness_assistant.main(argv)
    capsys.readouterr()
    assert code == 2