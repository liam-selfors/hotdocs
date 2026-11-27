# hotdocs-criterion: sha256:3ab53e15851eb5f1084d1f51ac01b12e7dd56519a86e37cc381dae0710f2337e
import json
from pathlib import Path

import pytest

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


JUDGE_TAG = "assist-010-judge-marker"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + " Component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + " Component\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n"
    )


def _requirement_md(req_id):
    return (
        "# " + req_id + "\n"
        "\n"
        "**" + req_id + "** — The widget MUST return the stored value "
        "for a known key and MUST raise KeyError for an unknown key.\n"
    )


def _acceptance_md(ac_id, req_id):
    return (
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + req_id + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a stored key\n"
        "When the widget is asked for it\n"
        "Then it returns the stored value\n"
        "```\n"
    )


def _build_corpus(repo_root):
    comps = repo_root / "specs" / "components"
    for slug, upper in (("foo", "FOO"), ("bar", "BAR")):
        base = comps / slug
        req_id = "R-" + upper + "-001"
        ac_id = "AC-" + upper + "-001"
        _write(base / "component.md", _component_md(slug))
        _write(base / "requirements" / (req_id + ".md"), _requirement_md(req_id))
        _write(base / "acceptance" / (ac_id + ".md"), _acceptance_md(ac_id, req_id))


def _write_fakes(repo_root, responses):
    logs = repo_root.parent / (repo_root.name + "-logs")
    logs.mkdir(parents=True, exist_ok=True)
    complete_log = logs / "complete.log"
    lint_log = logs / "lint.log"
    gen = repo_root / "gen"

    linter_src = (
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    tag = getattr(judge, '_assist_tag', None)\n"
        "    with open(" + repr(str(lint_log)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('lint judge=' + str(tag) + '\\n')\n"
        "    return {'findings': [], 'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0}}\n"
    )
    _write(gen / "spec-linter" / "spec_linter.py", linter_src)

    impact_src = (
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': 'comp-foo', 'reason': 'direct', 'via': None, 'guarantee_ids': None}\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    )
    _write(gen / "impact-analyzer" / "impact_analyzer.py", impact_src)

    reviewer_src = (
        "class _Report:\n"
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
        "        return self.to_dict()[key]\n"
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
        "    return _Report(targets)\n"
        "\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    def _judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    _judge._assist_tag = " + repr(JUDGE_TAG) + "\n"
        "    return _judge\n"
    )
    _write(gen / "spec-reviewer" / "spec_reviewer.py", reviewer_src)

    endpoint_src = (
        "import json\n"
        "import os\n"
        "\n"
        "_RESPONSES = json.loads(" + repr(json.dumps(responses)) + ")\n"
        "_LOG = " + repr(str(complete_log)) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, backend=None, **params):\n"
        "    index = 0\n"
        "    if os.path.exists(_LOG):\n"
        "        with open(_LOG, 'r', encoding='utf-8') as fh:\n"
        "            index = len([line for line in fh.read().splitlines() if line.strip()])\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('complete ' + str(index) + '\\n')\n"
        "    if index < len(_RESPONSES):\n"
        "        entry = _RESPONSES[index]\n"
        "    else:\n"
        "        entry = {'text': None, 'model_call_error': {'category': 'network', 'message': 'no more responses'}}\n"
        "    return {\n"
        "        'text': entry.get('text'),\n"
        "        'model': model,\n"
        "        'backend': 'mock',\n"
        "        'model_call_error': entry.get('model_call_error'),\n"
        "    }\n"
    )
    _write(gen / "llm-endpoint" / "llm_endpoint.py", endpoint_src)

    return complete_log, lint_log


def _ok(text):
    return {"text": text, "model_call_error": None}


def _err():
    return {"text": None, "model_call_error": {"category": "network", "message": "backend unreachable"}}


GOOD_REDUNDANCY = json.dumps({
    "redundancy_flags": [
        {
            "new_requirement": "R-FOO-001",
            "overlaps_with": "R-BAR-001",
            "rationale": "Both state the same widget lookup behavior.",
        }
    ]
})


def _run(tmp_path, responses):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    complete_log, lint_log = _write_fakes(repo_root, responses)
    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")
    return report, complete_log, lint_log


def _lines(path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_two_calls_fenced_completeness_and_filtered_redundancy(tmp_path):
    completeness = (
        "```json\n"
        + json.dumps({"completeness_score": 0.7, "completeness_rationale": "AC missing"})
        + "\n```"
    )
    redundancy = json.dumps({
        "redundancy_flags": [
            {
                "new_requirement": "R-FOO-001",
                "overlaps_with": "R-BAR-001",
                "rationale": "Both require the same widget lookup behavior.",
            },
            {
                "new_requirement": "R-FOO-001",
                "overlaps_with": "R-BAR-001",
                "rationale": "",
            },
        ]
    })
    report, complete_log, lint_log = _run(tmp_path, [_ok(completeness), _ok(redundancy)])

    assert len(_lines(complete_log)) == 2

    lint_lines = _lines(lint_log)
    assert lint_lines, "lint stand-in was never called"
    assert all(line == "lint judge=" + JUDGE_TAG for line in lint_lines)

    assert field(report, "completeness_score") == pytest.approx(0.7)
    assert field(report, "completeness_rationale") == "AC missing"

    flags = field(report, "redundancy_flags")
    assert len(flags) == 1
    entry = flags[0]
    assert field(entry, "new_requirement") == "R-FOO-001"
    assert field(entry, "overlaps_with") == "R-BAR-001"
    assert field(entry, "rationale") == "Both require the same widget lookup behavior."

    assert field(report, "degraded") is False


def test_model_call_error_and_unparseable_redundancy(tmp_path):
    report, _, _ = _run(tmp_path, [_err(), _ok("this is not json at all")])

    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None
    assert list(field(report, "redundancy_flags")) == []


def test_empty_rationale_does_not_parse(tmp_path):
    completeness = json.dumps({"completeness_score": 0.6, "completeness_rationale": ""})
    report, _, _ = _run(tmp_path, [_ok(completeness), _ok(GOOD_REDUNDANCY)])

    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None


@pytest.mark.parametrize(
    "completeness_text",
    [
        json.dumps({"completeness_rationale": "x"}),
        json.dumps({"completeness_score": True, "completeness_rationale": "x"}),
        "",
    ],
    ids=["missing-score", "boolean-score", "empty-string"],
)
def test_invalid_completeness_responses_do_not_parse(tmp_path, completeness_text):
    report, _, _ = _run(tmp_path, [_ok(completeness_text), _ok(GOOD_REDUNDANCY)])

    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None


def test_score_above_range_is_clamped(tmp_path):
    completeness = json.dumps({"completeness_score": 1.7, "completeness_rationale": "x"})
    report, _, _ = _run(tmp_path, [_ok(completeness), _ok(GOOD_REDUNDANCY)])

    assert field(report, "completeness_score") == pytest.approx(1.0)