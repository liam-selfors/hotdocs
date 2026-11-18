# hotdocs-criterion: sha256:eef1b1ce919b7fe3e121bfd3c1f565b4668977003782d61a61a23b6c7b739e03
import json
from pathlib import Path

import pytest

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


RECORD_SRC = (
    "class _Record(dict):\n"
    "    def __getattr__(self, name):\n"
    "        try:\n"
    "            return self[name]\n"
    "        except KeyError:\n"
    "            raise AttributeError(name)\n"
    "\n"
    "    def to_json(self):\n"
    "        return dict(self)\n"
    "\n"
)


SPEC_LINTER_SRC = (
    RECORD_SRC
    + "class LintReport(_Record):\n"
    "    @property\n"
    "    def hard_failures(self):\n"
    "        return 0\n"
    "\n"
    "    @property\n"
    "    def warnings(self):\n"
    "        return 0\n"
    "\n"
    "    @property\n"
    "    def skipped(self):\n"
    "        return 0\n"
    "\n"
    "\n"
    "def lint(paths, repo_root, strict=False, judge=None):\n"
    "    return LintReport(findings=[], summary=_Record(hard_failures=0, warnings=0, skipped=0))\n"
)


IMPACT_ANALYZER_SRC = (
    RECORD_SRC
    + "def compute_blast_radius(changed_ids, repo_root):\n"
    "    return _Record(\n"
    "        impacted=[_Record(component_id='comp-foo', reason='direct', via=None)],\n"
    "        precondition_error=None,\n"
    "    )\n"
)


ASSEMBLER_SRC = (
    RECORD_SRC
    + "def assemble(component_id, repo_root, mode='cold'):\n"
    "    return _Record(\n"
    "        component_id=component_id,\n"
    "        spec_bundle_hash='sha256:' + '0' * 64,\n"
    "        spec='Foo doubles a number.\\n\\n**R-FOO-001** \\u2014 foo(x) MUST return 2 * x.',\n"
    "        interface='# Library\\n\\nfoo(x: int) -> int',\n"
    "        constraints='None.',\n"
    "        dependency_interfaces={},\n"
    "        dependency_context={},\n"
    "        dependency_usage={},\n"
    "        vars={},\n"
    "        glossary='- **Foo** \\u2014 a test term.',\n"
    "        hint_code=({'foo.py': 'def foo(x):\\n    return 2 * x\\n'} if mode == 'hint' else None),\n"
    "    )\n"
)


GENERATOR_SRC = (
    RECORD_SRC
    + "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
    "    try:\n"
    "        cid = bundle['component_id']\n"
    "    except Exception:\n"
    "        cid = getattr(bundle, 'component_id', 'comp-foo')\n"
    "    try:\n"
    "        h = bundle['spec_bundle_hash']\n"
    "    except Exception:\n"
    "        h = getattr(bundle, 'spec_bundle_hash', 'sha256:' + '0' * 64)\n"
    "    return _Record(\n"
    "        component_id=cid,\n"
    "        spec_bundle_hash=h,\n"
    "        model=model,\n"
    "        prompt_version='v10',\n"
    "        cache_hit=False,\n"
    "        files={'foo.py': 'def foo(x):\\n    return 2 * x\\n'},\n"
    "        model_call_error=None,\n"
    "        refused=None,\n"
    "        retry_feedback=retry_feedback,\n"
    "    )\n"
)


def llm_endpoint_src(responses_path, log_path):
    return (
        "import json\n"
        "\n"
        "RESPONSES = " + repr(str(responses_path)) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write('call ' + json.dumps(model) + '\\n')\n"
        "    with open(LOG, encoding='utf-8') as f:\n"
        "        n = len([l for l in f.read().splitlines() if l.strip()])\n"
        "    with open(RESPONSES, encoding='utf-8') as f:\n"
        "        responses = json.load(f)\n"
        "    item = responses[n - 1] if n - 1 < len(responses) else {'text': ''}\n"
        "    if item.get('error'):\n"
        "        return {\n"
        "            'text': None,\n"
        "            'model': model,\n"
        "            'backend': 'fake',\n"
        "            'model_call_error': {'category': 'network', 'message': 'fake failure'},\n"
        "        }\n"
        "    return {'text': item['text'], 'model': model, 'backend': 'fake', 'model_call_error': None}\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** \u2014 a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")


def setup_repo(tmp_path, responses):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    responses_path = tmp_path / "fake_responses.json"
    log_path = tmp_path / "llm_calls.log"
    responses_path.write_text(json.dumps(responses), encoding="utf-8")
    gen = repo_root / "gen"
    write(gen / "spec-linter" / "spec_linter.py", SPEC_LINTER_SRC)
    write(gen / "impact-analyzer" / "impact_analyzer.py", IMPACT_ANALYZER_SRC)
    write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", ASSEMBLER_SRC)
    write(gen / "generator" / "generator.py", GENERATOR_SRC)
    write(gen / "llm-endpoint" / "llm_endpoint.py", llm_endpoint_src(responses_path, log_path))
    return repo_root, log_path


def call_count(log_path):
    if not log_path.exists():
        return 0
    return len([l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()])


GOOD_ENTRY = {
    "new_requirement": "R-FOO-001",
    "overlaps_with": "R-BAR-002",
    "rationale": "Both require doubling, worded differently.",
}
BAD_ENTRY = {
    "new_requirement": "R-FOO-001",
    "overlaps_with": "R-BAZ-003",
    "rationale": "",
}
REDUNDANCY_TEXT = json.dumps({"redundancy_flags": [GOOD_ENTRY, BAD_ENTRY]})


def normalize_flags(flags):
    out = []
    for entry in flags:
        out.append(
            {
                "new_requirement": field(entry, "new_requirement"),
                "overlaps_with": field(entry, "overlaps_with"),
                "rationale": field(entry, "rationale"),
            }
        )
    return out


def run_assist(repo_root):
    return spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")


@pytest.mark.parametrize("fence_open", ["```json", "```"])
def test_fenced_completeness_and_redundancy_parse(tmp_path, fence_open):
    completeness = json.dumps({"completeness_score": 0.7, "completeness_rationale": "AC missing"})
    fenced = fence_open + "\n" + completeness + "\n```"
    repo_root, log_path = setup_repo(tmp_path, [{"text": fenced}, {"text": REDUNDANCY_TEXT}])

    report = run_assist(repo_root)

    assert call_count(log_path) == 2
    assert field(report, "completeness_score") == pytest.approx(0.7)
    assert field(report, "completeness_rationale") == "AC missing"
    assert normalize_flags(field(report, "redundancy_flags")) == [GOOD_ENTRY]
    assert field(report, "degraded") is False


def test_model_call_error_and_unparseable_text_leave_fields_null(tmp_path):
    repo_root, log_path = setup_repo(
        tmp_path, [{"error": True}, {"text": "this is not json at all"}]
    )

    report = run_assist(repo_root)

    assert call_count(log_path) == 2
    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None
    assert list(field(report, "redundancy_flags")) == []


def test_empty_rationale_does_not_parse(tmp_path):
    completeness = json.dumps({"completeness_score": 0.6, "completeness_rationale": ""})
    repo_root, _ = setup_repo(tmp_path, [{"text": completeness}, {"text": REDUNDANCY_TEXT}])

    report = run_assist(repo_root)

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
    repo_root, _ = setup_repo(
        tmp_path, [{"text": completeness_text}, {"text": REDUNDANCY_TEXT}]
    )

    report = run_assist(repo_root)

    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None


def test_score_above_range_is_clamped(tmp_path):
    completeness = json.dumps({"completeness_score": 1.7, "completeness_rationale": "x"})
    repo_root, _ = setup_repo(tmp_path, [{"text": completeness}, {"text": REDUNDANCY_TEXT}])

    report = run_assist(repo_root)

    assert field(report, "completeness_score") == pytest.approx(1.0)