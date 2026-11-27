# hotdocs-criterion: sha256:c12c5e2277286ece22e88f962007bc4419938b91e4ade6f75e90f3deaf2b6632
import json
from pathlib import Path

import spec_completeness_assistant


FOO_SENTENCE = "R-FOO-001 MUST retry the upload three times before reporting failure"
BAR_SENTENCE = (
    "R-BAR-007 MUST retry the upload three times before reporting failure to the caller"
)
BAZ_SENTENCE = "R-BAZ-001 MUST render the page in dark mode"

COMPLETENESS_REPLY = json.dumps(
    {"completeness_score": 0.8, "completeness_rationale": "covers the retry rule"}
)
REDUNDANCY_REPLY = json.dumps(
    {
        "redundancy_flags": [
            {
                "new_requirement": "R-FOO-001",
                "overlaps_with": "R-BAR-007",
                "rationale": "same retry rule",
            },
            {
                "new_requirement": "R-FOO-001",
                "overlaps_with": "R-BAZ-001",
                "rationale": "x",
            },
        ]
    }
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root, slug):
    _write(
        repo_root / "specs" / "components" / slug / "component.md",
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug.capitalize() + " component\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n\n"
        + "# " + slug + "\n\nA fixture component.\n",
    )


def _requirement(repo_root, slug, req_id, ac_id, sentence):
    _write(
        repo_root / "specs" / "components" / slug / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n" + sentence + "\n",
    )
    _write(
        repo_root / "specs" / "components" / slug / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\n"
        + "Covers: " + req_id + "\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\n"
        + "Given a fixture\n"
        + "When it runs\n"
        + "Then it behaves\n"
        + "```\n",
    )


def _write_stand_ins(repo_root, log_path):
    gen = repo_root / "gen"

    linter_src = "\n".join(
        [
            "def lint(paths, repo_root, strict=False, judge=None):",
            "    return {",
            "        'findings': [],",
            "        'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0},",
            "    }",
            "",
        ]
    )
    _write(gen / "spec-linter" / "spec_linter.py", linter_src)

    impact_src = "\n".join(
        [
            "def compute_blast_radius(changed_ids, repo_root):",
            "    return {",
            "        'impacted': [",
            "            {'component_id': 'comp-foo', 'reason': 'direct', 'via': None,",
            "             'guarantee_ids': None},",
            "        ],",
            "        'precondition_error': None,",
            "    }",
            "",
        ]
    )
    _write(gen / "impact-analyzer" / "impact_analyzer.py", impact_src)

    reviewer_src = "\n".join(
        [
            "class ReviewReport:",
            "    def __init__(self, targets):",
            "        self.targets = list(targets)",
            "        self.criteria_checked = []",
            "        self.findings = []",
            "        self.gaps = []",
            "        self.writable = {}",
            "        self.lint_findings = []",
            "        self.proposals = []",
            "        self.degraded = True",
            "",
            "    def to_dict(self):",
            "        return {",
            "            'targets': list(self.targets),",
            "            'criteria_checked': list(self.criteria_checked),",
            "            'findings': list(self.findings),",
            "            'gaps': list(self.gaps),",
            "            'writable': dict(self.writable),",
            "            'lint_findings': list(self.lint_findings),",
            "            'proposals': list(self.proposals),",
            "            'degraded': self.degraded,",
            "        }",
            "",
            "    def __getitem__(self, key):",
            "        return self.to_dict()[key]",
            "",
            "",
            "def check(targets, repo_root, model=None, *, llm_backend=None,",
            "          write_proposals=False):",
            "    return ReviewReport(targets)",
            "",
            "",
            "def glossary_judge(model, llm_backend=None):",
            "    def judge(term, local_text, glossary_text):",
            "        return None",
            "    return judge",
            "",
        ]
    )
    _write(gen / "spec-reviewer" / "spec_reviewer.py", reviewer_src)

    endpoint_src = "\n".join(
        [
            "import json",
            "",
            "LOG = " + repr(str(log_path)),
            "REPLIES = [" + repr(COMPLETENESS_REPLY) + ", " + repr(REDUNDANCY_REPLY) + "]",
            "",
            "",
            "def complete(prompt, model, backend=None, **params):",
            "    with open(LOG, 'a', encoding='utf-8') as f:",
            "        f.write(json.dumps(prompt) + '\\n')",
            "    with open(LOG, encoding='utf-8') as f:",
            "        n = sum(1 for line in f if line.strip())",
            "    idx = n - 1",
            "    text = REPLIES[idx] if idx < len(REPLIES) else REPLIES[-1]",
            "    return {'text': text, 'model': model, 'backend': 'mock',",
            "            'model_call_error': None}",
            "",
        ]
    )
    _write(gen / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


def _build_repo(tmp_path, include_bar):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "logs" / "llm_calls.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _component(repo_root, "foo")
    _requirement(repo_root, "foo", "R-FOO-001", "AC-FOO-001", FOO_SENTENCE)
    _component(repo_root, "bar")
    if include_bar:
        _requirement(repo_root, "bar", "R-BAR-007", "AC-BAR-007", BAR_SENTENCE)
    _component(repo_root, "baz")
    _requirement(repo_root, "baz", "R-BAZ-001", "AC-BAZ-001", BAZ_SENTENCE)

    _write_stand_ins(repo_root, log_path)
    return repo_root, log_path


def _read_prompts(log_path):
    if not log_path.exists():
        return []
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def _normalize_flags(flags):
    return [
        {
            "new_requirement": field(e, "new_requirement"),
            "overlaps_with": field(e, "overlaps_with"),
            "rationale": field(e, "rationale"),
        }
        for e in flags
    ]


def test_redundancy_candidate_prompted_and_non_candidate_dropped(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, include_bar=True)

    report = spec_completeness_assistant.assist(
        ["R-FOO-001"], repo_root, model="fake-model"
    )

    prompts = _read_prompts(log_path)
    assert len(prompts) == 2
    second = prompts[1]
    assert BAR_SENTENCE in second
    assert BAZ_SENTENCE not in second
    assert "render the page in dark mode" not in second

    flags = field(report, "redundancy_flags")
    assert _normalize_flags(flags) == [
        {
            "new_requirement": "R-FOO-001",
            "overlaps_with": "R-BAR-007",
            "rationale": "same retry rule",
        }
    ]


def test_no_candidate_means_no_redundancy_call(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, include_bar=False)

    report = spec_completeness_assistant.assist(
        ["R-FOO-001"], repo_root, model="fake-model"
    )

    prompts = _read_prompts(log_path)
    assert len(prompts) == 1

    flags = field(report, "redundancy_flags")
    assert list(flags) == []