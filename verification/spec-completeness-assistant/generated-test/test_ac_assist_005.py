# hotdocs-criterion: sha256:729dff1705f61706ca148af7a47470971ca4a8b8a99caaca02cec6350ed3c703
import json
from pathlib import Path

import spec_completeness_assistant


FOO_TEXT = "R-FOO-001 MUST retry the upload three times before reporting failure\n"
BAR_TEXT = (
    "R-BAR-007 MUST retry the upload three times before reporting failure to the "
    "caller\n"
)
BAZ_TEXT = "R-BAZ-001 MUST render the page in dark mode\n"

COMPLETENESS_REPLY = json.dumps(
    {"completeness_score": 0.8, "completeness_rationale": "looks complete"}
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
    path.write_text(text)


def _component(repo_root, slug):
    text = (
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
        "A fixture component.\n"
    )
    _write(repo_root / "specs" / "components" / slug / "component.md", text)


def _requirement(repo_root, slug, req_id, ac_id, text):
    base = repo_root / "specs" / "components" / slug
    _write(base / "requirements" / (req_id + ".md"), text)
    ac = (
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + req_id + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a fixture\n"
        "When it runs\n"
        "Then it works\n"
        "```\n"
    )
    _write(base / "acceptance" / (ac_id + ".md"), ac)


def _write_fakes(repo_root, log_path):
    gen = repo_root / "gen"

    linter = (
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    return {'findings': [], 'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0}}\n"
    )
    _write(gen / "spec-linter" / "spec_linter.py", linter)

    impact = (
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    return {'impacted': [{'component_id': 'comp-foo', 'reason': 'direct', 'via': None}],\n"
        "            'precondition_error': None}\n"
    )
    _write(gen / "impact-analyzer" / "impact_analyzer.py", impact)

    reviewer = (
        "class _Report:\n"
        "    def __init__(self, targets):\n"
        "        self._d = {'targets': list(targets), 'criteria_checked': [], 'findings': [],\n"
        "                   'gaps': [], 'writable': {}, 'lint_findings': [], 'proposals': [],\n"
        "                   'degraded': True}\n"
        "        for k, v in self._d.items():\n"
        "            setattr(self, k, v)\n"
        "    def __getitem__(self, key):\n"
        "        return self._d[key]\n"
        "    def to_dict(self):\n"
        "        return dict(self._d)\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        "    return _Report(targets)\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    return judge\n"
    )
    _write(gen / "spec-reviewer" / "spec_reviewer.py", reviewer)

    endpoint = (
        "import json\n"
        "import os\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REPLIES = [" + repr(COMPLETENESS_REPLY) + ", " + repr(REDUNDANCY_REPLY) + "]\n"
        "\n"
        "def complete(prompt, model, backend=None, **params):\n"
        "    n = 0\n"
        "    if os.path.exists(LOG):\n"
        "        with open(LOG) as f:\n"
        "            n = len([line for line in f.read().splitlines() if line.strip()])\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps({'prompt': prompt}) + '\\n')\n"
        "    text = REPLIES[n] if n < len(REPLIES) else REPLIES[-1]\n"
        "    return {'text': text, 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
    )
    _write(gen / "llm-endpoint" / "llm_endpoint.py", endpoint)


def _build(tmp_path, with_bar):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "logs" / "complete.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    for slug in ("foo", "bar", "baz"):
        _component(repo_root, slug)
    _requirement(repo_root, "foo", "R-FOO-001", "AC-FOO-001", FOO_TEXT)
    if with_bar:
        _requirement(repo_root, "bar", "R-BAR-007", "AC-BAR-007", BAR_TEXT)
    _requirement(repo_root, "baz", "R-BAZ-001", "AC-BAZ-001", BAZ_TEXT)
    _write_fakes(repo_root, log_path)
    return repo_root, log_path


def _prompts(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)["prompt"]
        for line in log_path.read_text().splitlines()
        if line.strip()
    ]


def _normalize(entries):
    return [
        {
            "new_requirement": field(e, "new_requirement"),
            "overlaps_with": field(e, "overlaps_with"),
            "rationale": field(e, "rationale"),
        }
        for e in entries
    ]


def test_redundancy_candidate_found_and_non_candidate_dropped(tmp_path):
    repo_root, log_path = _build(tmp_path, with_bar=True)

    report = spec_completeness_assistant.assist(
        ["R-FOO-001"], repo_root, model="fake-model"
    )

    prompts = _prompts(log_path)
    assert len(prompts) == 2
    second = prompts[1]
    assert BAR_TEXT.strip() in second
    assert BAZ_TEXT.strip() not in second
    assert "render the page in dark mode" not in second

    flags = field(report, "redundancy_flags")
    assert isinstance(flags, list)
    assert _normalize(flags) == [
        {
            "new_requirement": "R-FOO-001",
            "overlaps_with": "R-BAR-007",
            "rationale": "same retry rule",
        }
    ]


def test_no_candidate_means_no_redundancy_call(tmp_path):
    repo_root, log_path = _build(tmp_path, with_bar=False)

    report = spec_completeness_assistant.assist(
        ["R-FOO-001"], repo_root, model="fake-model"
    )

    prompts = _prompts(log_path)
    assert len(prompts) == 1
    assert list(field(report, "redundancy_flags")) == []