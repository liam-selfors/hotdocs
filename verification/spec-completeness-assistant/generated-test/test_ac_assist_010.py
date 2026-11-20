# hotdocs-criterion: sha256:06ec7042b6afda9a11d71bebf7bea40b7bd2a6ab4799586ebc6ab1e543594d1a
import json
import sys
from pathlib import Path

import pytest

import spec_completeness_assistant


JUDGE_MARKER = "judge-from-fake-spec-reviewer-ac-assist-010"

DEP_MODULE_NAMES = ["spec_linter", "impact_analyzer", "spec_reviewer", "llm_endpoint"]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(autouse=True)
def _clear_dependency_modules():
    for name in DEP_MODULE_NAMES:
        sys.modules.pop(name, None)
    yield
    for name in DEP_MODULE_NAMES:
        sys.modules.pop(name, None)


LINTER_BODY = '''

def _log(line):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\\n")


def lint(paths, repo_root, strict=False, judge=None):
    marker = getattr(judge, "hotdocs_marker", None) if judge is not None else None
    _log("lint judge=" + repr(marker))
    return {"findings": [], "summary": {"hard_failures": 0, "warnings": 0, "skipped": 0}}
'''

IMPACT_BODY = '''

def _log(line):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\\n")


def compute_blast_radius(changed_ids, repo_root):
    _log("compute_blast_radius " + repr(list(changed_ids)))
    return {
        "impacted": [
            {"component_id": "comp-foo", "reason": "direct", "via": None, "guarantee_ids": None}
        ],
        "precondition_error": None,
    }
'''

REVIEWER_BODY = '''

def _log(line):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\\n")


class ReviewReport:
    def __init__(self, targets):
        self.targets = list(targets)
        self.criteria_checked = []
        self.findings = []
        self.gaps = []
        self.writable = {}
        self.lint_findings = []
        self.proposals = []
        self.degraded = True

    def to_dict(self):
        return {
            "targets": list(self.targets),
            "criteria_checked": list(self.criteria_checked),
            "findings": list(self.findings),
            "gaps": list(self.gaps),
            "writable": dict(self.writable),
            "lint_findings": list(self.lint_findings),
            "proposals": list(self.proposals),
            "degraded": self.degraded,
        }

    def __getitem__(self, key):
        return self.to_dict()[key]


def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):
    _log("check " + repr(list(targets)))
    return ReviewReport(targets)


def glossary_judge(model, llm_backend=None):
    _log("glossary_judge " + repr(model))

    def judge(term, local_text, glossary_text):
        return None

    judge.hotdocs_marker = MARKER
    return judge
'''

ENDPOINT_BODY = '''
import json
import os


def _prior_calls():
    if not os.path.exists(LOG):
        return 0
    with open(LOG, encoding="utf-8") as f:
        return sum(1 for line in f if line.startswith("complete "))


def complete(prompt, model, backend=None, **params):
    index = _prior_calls()
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("complete " + repr(model) + "\\n")
    with open(RESPONSES, encoding="utf-8") as f:
        responses = json.load(f)
    if index < len(responses):
        item = responses[index]
    else:
        item = {"text": json.dumps({"redundancy_flags": []}), "error": None}
    if item.get("error") is not None:
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": item["error"],
        }
    return {
        "text": item["text"],
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }
'''


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + " component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n"
    )


def _requirement_md(req_id):
    return (
        "# " + req_id + "\n"
        "\n"
        "**" + req_id + "** — The widget MUST return the stored value for a\n"
        "  known key and MUST raise `KeyError` for an unknown key.\n"
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


def _build_repo(tmp_path, responses):
    repo_root = tmp_path / "repo"
    log = tmp_path / "calls.log"
    resp_path = tmp_path / "responses.json"
    resp_path.write_text(json.dumps(responses), encoding="utf-8")

    comps = repo_root / "specs" / "components"
    for slug, upper in (("foo", "FOO"), ("bar", "BAR")):
        base = comps / slug
        req_id = "R-" + upper + "-001"
        ac_id = "AC-" + upper + "-001"
        _write(base / "component.md", _component_md(slug))
        _write(base / "requirements" / (req_id + ".md"), _requirement_md(req_id))
        _write(base / "acceptance" / (ac_id + ".md"), _acceptance_md(ac_id, req_id))
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — the fixture's thing.\n",
    )

    header = "LOG = " + repr(str(log)) + "\n"
    _write(repo_root / "gen" / "spec-linter" / "spec_linter.py", header + LINTER_BODY)
    _write(repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py", header + IMPACT_BODY)
    _write(
        repo_root / "gen" / "spec-reviewer" / "spec_reviewer.py",
        header + "MARKER = " + repr(JUDGE_MARKER) + "\n" + REVIEWER_BODY,
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        header + "RESPONSES = " + repr(str(resp_path)) + "\n" + ENDPOINT_BODY,
    )
    return repo_root, log


def _log_lines(log):
    if not log.exists():
        return []
    return [line for line in log.read_text(encoding="utf-8").splitlines() if line]


def _text(obj):
    return {"text": obj, "error": None}


def _json_text(obj):
    return _text(json.dumps(obj))


EMPTY_REDUNDANCY = _json_text({"redundancy_flags": []})


def test_happy_path_parses_fenced_completeness_and_filters_redundancy(tmp_path):
    completeness = {"completeness_score": 0.7, "completeness_rationale": "AC missing"}
    fenced = "```json\n" + json.dumps(completeness) + "\n```"
    complete_entry = {
        "new_requirement": "R-FOO-001",
        "overlaps_with": "R-BAR-001",
        "rationale": "Both state the same widget behavior word for word.",
    }
    empty_entry = {
        "new_requirement": "R-FOO-001",
        "overlaps_with": "R-BAR-001",
        "rationale": "",
    }
    responses = [
        _text(fenced),
        _json_text({"redundancy_flags": [complete_entry, empty_entry]}),
    ]
    repo_root, log = _build_repo(tmp_path, responses)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    lines = _log_lines(log)
    complete_calls = [line for line in lines if line.startswith("complete ")]
    assert len(complete_calls) == 2, lines

    lint_calls = [line for line in lines if line.startswith("lint ")]
    assert lint_calls, lines
    assert all(line == "lint judge=" + repr(JUDGE_MARKER) for line in lint_calls), lines

    assert field(report, "completeness_score") == 0.7
    assert field(report, "completeness_rationale") == "AC missing"

    flags = field(report, "redundancy_flags")
    assert len(flags) == 1, flags
    flag = flags[0]
    assert field(flag, "new_requirement") == complete_entry["new_requirement"]
    assert field(flag, "overlaps_with") == complete_entry["overlaps_with"]
    assert field(flag, "rationale") == complete_entry["rationale"]

    assert field(report, "degraded") is False


def test_model_call_error_and_unparseable_leave_fields_null(tmp_path):
    responses = [
        {"text": None, "error": {"category": "rate_limit", "message": "429 from backend"}},
        _text("this is not json at all {"),
    ]
    repo_root, log = _build_repo(tmp_path, responses)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None
    assert list(field(report, "redundancy_flags")) == []
    assert field(report, "degraded") is False


def test_empty_rationale_does_not_parse(tmp_path):
    responses = [
        _json_text({"completeness_score": 0.6, "completeness_rationale": ""}),
        EMPTY_REDUNDANCY,
    ]
    repo_root, log = _build_repo(tmp_path, responses)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

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
def test_malformed_completeness_does_not_parse(tmp_path, completeness_text):
    responses = [_text(completeness_text), EMPTY_REDUNDANCY]
    repo_root, log = _build_repo(tmp_path, responses)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None


def test_out_of_range_score_is_clamped(tmp_path):
    responses = [
        _json_text({"completeness_score": 1.7, "completeness_rationale": "x"}),
        EMPTY_REDUNDANCY,
    ]
    repo_root, log = _build_repo(tmp_path, responses)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    assert field(report, "completeness_score") == 1.0