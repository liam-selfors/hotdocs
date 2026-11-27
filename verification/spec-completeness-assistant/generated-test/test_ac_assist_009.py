# hotdocs-criterion: sha256:6d97d22a952e9508fd1232fc071e6a6caec9349b7e6750370e7267ef43ecfaff
import json
from pathlib import Path

import pytest

import spec_completeness_assistant


WARN_RULE_ID = "R-LINT-042"
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
        "A stand-in component.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `x`.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x is 1\n"
        "When foo(x) runs\n"
        "Then it returns 1\n"
        "```\n",
    )


def _write_stand_ins(repo_root, severity, rule_id, completion_text, log_path):
    gen = repo_root / "gen"

    hard = 1 if severity == "fail" else 0
    warns = 1 if severity == "warn" else 0
    linter_src = (
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    return {\n"
        "        'findings': [\n"
        "            {\n"
        "                'rule_id': " + repr(rule_id) + ",\n"
        "                'severity': " + repr(severity) + ",\n"
        "                'file': " + repr("specs/components/foo/component.md") + ",\n"
        "                'line': 1,\n"
        "                'message': " + repr("stand-in finding") + ",\n"
        "            }\n"
        "        ],\n"
        "        'summary': {'hard_failures': " + repr(hard)
        + ", 'warnings': " + repr(warns) + ", 'skipped': 0},\n"
        "    }\n"
    )
    _write(gen / "spec-linter" / "spec_linter.py", linter_src)

    impact_src = (
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': 'comp-foo', 'reason': 'direct', 'via': None,\n"
        "             'guarantee_ids': None}\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    )
    _write(gen / "impact-analyzer" / "impact_analyzer.py", impact_src)

    reviewer_src = (
        "class _Report:\n"
        "    def __init__(self, targets):\n"
        "        self.targets = list(targets)\n"
        "        self.findings = []\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return self.to_dict()[key]\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'findings': []}\n"
        "\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None,\n"
        "          write_proposals=False):\n"
        "    return _Report(targets)\n"
        "\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    return judge\n"
    )
    _write(gen / "spec-reviewer" / "spec_reviewer.py", reviewer_src)

    endpoint_src = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPLY_TEXT = " + repr(completion_text) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, backend=None, **params):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(model) + '\\n')\n"
        "    return {\n"
        "        'text': REPLY_TEXT,\n"
        "        'model': model,\n"
        "        'backend': 'mock',\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    _write(gen / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


COMPLETENESS_TEXT = json.dumps(
    {"completeness_score": 0.7, "completeness_rationale": "AC missing"}
)


def make_repo(tmp_path, severity="warn"):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_corpus(repo_root)
    log_path = tmp_path / "complete_calls.log"
    rule_id = WARN_RULE_ID if severity == "warn" else FAIL_RULE_ID
    _write_stand_ins(repo_root, severity, rule_id, COMPLETENESS_TEXT, log_path)
    return repo_root, log_path


def _read_log(log_path):
    if not log_path.is_file():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def test_json_degraded_equals_form(tmp_path, capsys):
    repo_root, log_path = make_repo(tmp_path)
    rc = spec_completeness_assistant.main(
        ["--changed=R-FOO-001", "--repo-root=" + str(repo_root), "--format=json"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert field(data, "predicted_blast_radius") == ["comp-foo"]
    assert field(data, "degraded") is True
    assert _read_log(log_path) == []


def test_text_degraded_space_form(tmp_path, capsys):
    repo_root, _ = make_repo(tmp_path)
    rc = spec_completeness_assistant.main(
        ["--changed", "R-FOO-001", "--repo-root", str(repo_root), "--format", "text"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert WARN_RULE_ID in out
    assert "comp-foo" in out


def test_json_with_model(tmp_path, capsys):
    repo_root, log_path = make_repo(tmp_path)
    rc = spec_completeness_assistant.main(
        [
            "--changed=R-FOO-001",
            "--repo-root=" + str(repo_root),
            "--model=fake-model",
            "--format=json",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    calls = _read_log(log_path)
    assert calls, "the faked llm-endpoint complete() was never called"
    assert "fake-model" in calls
    data = json.loads(out)
    assert field(data, "degraded") is False
    assert field(data, "completeness_score") == pytest.approx(0.7)


def test_text_with_model(tmp_path, capsys):
    repo_root, log_path = make_repo(tmp_path)
    rc = spec_completeness_assistant.main(
        [
            "--changed=R-FOO-001",
            "--repo-root=" + str(repo_root),
            "--model=fake-model",
            "--format=text",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "fake-model" in _read_log(log_path)
    assert "0.7" in out


def test_fail_finding_inside_changed_component_returns_1(tmp_path, capsys):
    repo_root, _ = make_repo(tmp_path, severity="fail")
    assert (
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md"
    ).is_file()
    rc = spec_completeness_assistant.main(
        ["--changed=R-FOO-001", "--repo-root=" + str(repo_root)]
    )
    capsys.readouterr()
    assert rc == 1


@pytest.mark.parametrize(
    "make_argv",
    [
        lambda root: [],
        lambda root: ["serve", "--changed=R-FOO-001"],
        lambda root: ["--repo-root=" + root, "--format=json"],
        lambda root: ["--changed=R-FOO-001", "--repo-root=" + root, "--format=bogus"],
        lambda root: ["--changed=R-FOO-001", "--repo-root=" + root, "--hotdocs-smoke-unknown"],
        lambda root: ["--changed"],
        lambda root: ["--repo-root=" + root, "--changed"],
    ],
    ids=[
        "empty",
        "stray-word",
        "no-changed",
        "bogus-format",
        "unknown-argument",
        "changed-last-alone",
        "changed-last-after-flags",
    ],
)
def test_usage_errors_return_2(tmp_path, capsys, make_argv):
    repo_root, _ = make_repo(tmp_path)
    rc = spec_completeness_assistant.main(make_argv(str(repo_root)))
    capsys.readouterr()
    assert rc == 2