# hotdocs-criterion: sha256:2e44d84be998aadc3cd987873b84f097cd2fb0db5fad63bb676e5245e7395f85
import json
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_line(log_path, tag):
    # Source fragment that appends one JSON line to the log file.
    return (
        "    import json as _json\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as _f:\n"
        "        _f.write(_json.dumps(" + tag + ") + '\\n')\n"
    )


def _build_fakes(repo_root, log_path):
    gen = repo_root / "gen"

    linter_src = (
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        + _log_line(log_path, "{'call': 'lint', 'paths': paths, 'judge_is_none': judge is None}")
        + "    return {\n"
        "        'findings': [],\n"
        "        'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0},\n"
        "        'hard_failures': 0,\n"
        "        'warnings': 0,\n"
        "        'skipped': 0,\n"
        "    }\n"
    )
    _write(gen / "spec-linter" / "spec_linter.py", linter_src)

    impact_src = (
        "def compute_blast_radius(changed_ids, repo_root):\n"
        + _log_line(
            log_path,
            "{'call': 'compute_blast_radius', 'changed_ids': list(changed_ids), "
            "'repo_root': str(repo_root)}",
        )
        + "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': " + repr("comp-alpha") + ", 'reason': 'direct', "
        "'via': None, 'guarantee_ids': None},\n"
        "            {'component_id': " + repr("comp-beta") + ", 'reason': 'transitive-interface', "
        "'via': " + repr("comp-alpha") + ", 'guarantee_ids': None},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    )
    _write(gen / "impact-analyzer" / "impact_analyzer.py", impact_src)

    reviewer_src = (
        "class _ReviewReport:\n"
        "    def __init__(self, targets):\n"
        "        self.targets = list(targets)\n"
        "        self.criteria_checked = []\n"
        "        self.findings = []\n"
        "        self.gaps = []\n"
        "        self.writable = {}\n"
        "        self.lint_findings = []\n"
        "        self.proposals = []\n"
        "        self.degraded = True\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            'targets': list(self.targets),\n"
        "            'criteria_checked': list(self.criteria_checked),\n"
        "            'findings': list(self.findings),\n"
        "            'gaps': list(self.gaps),\n"
        "            'writable': dict(self.writable),\n"
        "            'lint_findings': list(self.lint_findings),\n"
        "            'proposals': list(self.proposals),\n"
        "            'degraded': self.degraded,\n"
        "        }\n"
        "\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        + _log_line(log_path, "{'call': 'check', 'targets': list(targets)}")
        + "    return _ReviewReport(targets)\n"
        "\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        + _log_line(log_path, "{'call': 'glossary_judge'}")
        + "    def judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    return judge\n"
    )
    _write(gen / "spec-reviewer" / "spec_reviewer.py", reviewer_src)

    endpoint_src = (
        "def complete(prompt, model, backend=None, **params):\n"
        + _log_line(log_path, "{'call': 'complete'}")
        + "    return {\n"
        "        'text': " + repr('{"completeness_score": 1.0, "completeness_rationale": "ok"}') + ",\n"
        "        'model': model,\n"
        "        'backend': 'mock',\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    _write(gen / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


def _read_log(log_path):
    if not log_path.is_file():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_ac_assist_002_predicted_blast_radius_lists_exactly_impacted(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_fakes(repo_root, log_path)

    report = spec_completeness_assistant.assist(["R-ALPHA-001"], repo_root)

    calls = _read_log(log_path)
    blast_calls = [c for c in calls if c["call"] == "compute_blast_radius"]
    assert len(blast_calls) == 1, calls
    assert blast_calls[0]["changed_ids"] == ["R-ALPHA-001"]
    assert Path(blast_calls[0]["repo_root"]) == Path(repo_root)

    assert field(report, "halted") is False
    assert list(field(report, "predicted_blast_radius")) == ["comp-alpha", "comp-beta"]

    as_dict = report.to_dict()
    assert list(as_dict["predicted_blast_radius"]) == ["comp-alpha", "comp-beta"]