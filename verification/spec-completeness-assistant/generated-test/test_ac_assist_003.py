# hotdocs-criterion: sha256:3dc8777c6c7ba09dac745d4d68051d94a777718b57487ee9dbdc9aaea64ac72f
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
        "def _log(entry):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
        "\n"
    )


def _setup(repo_root, log_path):
    repo_root.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")
    gen = repo_root / "gen"

    linter_src = (
        _log_helper(log_path)
        + "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    _log({'call': 'lint', 'paths': None if paths is None else [str(p) for p in paths],"
        " 'judge_given': judge is not None})\n"
        "    return {'findings': [], 'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0}}\n"
    )
    _write(gen / "spec-linter" / "spec_linter.py", linter_src)

    impact_src = (
        _log_helper(log_path)
        + "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log({'call': 'compute_blast_radius', 'changed_ids': list(changed_ids)})\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': 'comp-foo', 'reason': 'direct', 'via': None},\n"
        "            {'component_id': 'comp-bar', 'reason': 'transitive-interface', 'via': 'comp-foo'},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    )
    _write(gen / "impact-analyzer" / "impact_analyzer.py", impact_src)

    reviewer_src = (
        _log_helper(log_path)
        + "class _Report:\n"
        "    def __init__(self, target):\n"
        "        self._target = target\n"
        "    def to_dict(self):\n"
        "        return {'findings': [], 'target': self._target}\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        "    _log({'call': 'check', 'targets': list(targets), 'model': model,"
        " 'write_proposals': write_proposals, 'llm_backend_given': llm_backend is not None})\n"
        "    if list(targets) == ['comp-bar']:\n"
        "        raise RuntimeError('boom')\n"
        "    return _Report(targets[0])\n"
        "\n"
        "def _judge(term, local_text, glossary_text):\n"
        "    return None\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    _log({'call': 'glossary_judge', 'model': model})\n"
        "    return _judge\n"
    )
    _write(gen / "spec-reviewer" / "spec_reviewer.py", reviewer_src)

    endpoint_src = (
        _log_helper(log_path)
        + "def complete(prompt, model, backend=None, **params):\n"
        "    _log({'call': 'complete', 'model': model})\n"
        "    if 'redundancy' in prompt.lower() and 'completeness_score' not in prompt:\n"
        "        text = json.dumps({'redundancy_flags': []})\n"
        "    else:\n"
        "        text = json.dumps({'completeness_score': 0.5, 'completeness_rationale': 'ok'})\n"
        "    return {'text': text, 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
    )
    _write(gen / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


def _read_log(log_path):
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


def test_criterion_reviews_with_model(tmp_path):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "calls.log"
    _setup(repo_root, log_path)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    reviews = field(report, "criterion_reviews")
    assert reviews == {
        "comp-foo": {"findings": [], "target": "comp-foo"},
        "comp-bar": {"error": "boom"},
    }

    entries = _read_log(log_path)
    checks = [e for e in entries if e["call"] == "check"]
    assert [c["targets"] for c in checks] == [["comp-foo"], ["comp-bar"]]
    for c in checks:
        assert c["model"] is None
        assert c["write_proposals"] is False
        assert c["llm_backend_given"] is False


def test_criterion_reviews_without_model(tmp_path):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "calls.log"
    _setup(repo_root, log_path)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    reviews = field(report, "criterion_reviews")
    assert set(reviews.keys()) == {"comp-foo", "comp-bar"}
    assert reviews["comp-bar"] == {"error": "boom"}

    entries = _read_log(log_path)
    assert not [e for e in entries if e["call"] == "complete"]
    checks = [e for e in entries if e["call"] == "check"]
    assert [c["targets"] for c in checks] == [["comp-foo"], ["comp-bar"]]
    for c in checks:
        assert c["model"] is None
        assert c["write_proposals"] is False