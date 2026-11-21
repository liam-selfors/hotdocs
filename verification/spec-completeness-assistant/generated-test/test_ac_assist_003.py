# hotdocs-criterion: sha256:316edb1c6b957a8bfe69429f71acdecc83778a20b3313a9f7f28dbd5eee30031
import json
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_helper(log_path):
    return (
        "import json\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
        "\n"
    )


def _setup(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")

    linter_src = (
        _log_helper(log_path)
        + "def lint(paths, repo_root, strict=False, judge=None):\n"
        + "    _log({'fn': 'lint', 'paths': None if paths is None else [str(p) for p in paths],\n"
        + "          'strict': strict, 'judge_given': judge is not None})\n"
        + "    return {'findings': [], 'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0}}\n"
    )
    _write(repo_root / "gen" / "spec-linter" / "spec_linter.py", linter_src)

    impact_src = (
        _log_helper(log_path)
        + "def compute_blast_radius(changed_ids, repo_root):\n"
        + "    _log({'fn': 'compute_blast_radius', 'changed_ids': list(changed_ids)})\n"
        + "    return {\n"
        + "        'impacted': [\n"
        + "            {'component_id': " + repr("comp-foo") + ", 'reason': 'direct', 'via': None},\n"
        + "            {'component_id': " + repr("comp-bar") + ", 'reason': 'transitive-interface', 'via': "
        + repr("comp-foo") + "},\n"
        + "        ],\n"
        + "        'precondition_error': None,\n"
        + "    }\n"
    )
    _write(repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py", impact_src)

    reviewer_src = (
        _log_helper(log_path)
        + "class _Report:\n"
        + "    def __init__(self, target):\n"
        + "        self._target = target\n"
        + "\n"
        + "    def to_dict(self):\n"
        + "        return {'findings': [], 'target': self._target}\n"
        + "\n"
        + "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        + "    _log({'fn': 'check', 'targets': list(targets), 'model': model,\n"
        + "          'llm_backend_given': llm_backend is not None,\n"
        + "          'write_proposals': write_proposals})\n"
        + "    if list(targets) == [" + repr("comp-bar") + "]:\n"
        + "        raise RuntimeError(" + repr("boom") + ")\n"
        + "    return _Report(targets[0])\n"
        + "\n"
        + "def _judge(term, local_text, glossary_text):\n"
        + "    return None\n"
        + "\n"
        + "def glossary_judge(model, llm_backend=None):\n"
        + "    _log({'fn': 'glossary_judge', 'model': model})\n"
        + "    return _judge\n"
    )
    _write(repo_root / "gen" / "spec-reviewer" / "spec_reviewer.py", reviewer_src)

    endpoint_src = (
        _log_helper(log_path)
        + "def complete(prompt, model, backend=None, **params):\n"
        + "    _log({'fn': 'complete', 'model': model})\n"
        + "    if 'redundan' in str(prompt).lower() and 'completeness_score' not in str(prompt):\n"
        + "        text = json.dumps({'redundancy_flags': []})\n"
        + "    else:\n"
        + "        text = json.dumps({'completeness_score': 0.5, 'completeness_rationale': 'ok'})\n"
        + "    return {'text': text, 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", endpoint_src)

    return repo_root, log_path


def _read_log(log_path):
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_ac_assist_003_with_model(tmp_path):
    repo_root, log_path = _setup(tmp_path)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    reviews = field(report, "criterion_reviews")
    assert dict(reviews) == {
        "comp-foo": {"findings": [], "target": "comp-foo"},
        "comp-bar": {"error": "boom"},
    }

    calls = _read_log(log_path)
    check_calls = [c for c in calls if c["fn"] == "check"]
    assert [c["targets"] for c in check_calls] == [["comp-foo"], ["comp-bar"]]
    for c in check_calls:
        assert c["model"] is None
        assert c["write_proposals"] is False


def test_ac_assist_003_without_model(tmp_path):
    repo_root, log_path = _setup(tmp_path)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    reviews = field(report, "criterion_reviews")
    assert set(dict(reviews).keys()) == {"comp-foo", "comp-bar"}

    calls = _read_log(log_path)
    assert [c for c in calls if c["fn"] == "complete"] == []
    check_calls = [c for c in calls if c["fn"] == "check"]
    assert [c["targets"] for c in check_calls] == [["comp-foo"], ["comp-bar"]]