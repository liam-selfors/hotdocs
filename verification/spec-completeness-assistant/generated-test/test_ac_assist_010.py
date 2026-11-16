import json
from pathlib import Path

import pytest

import spec_completeness_assistant


CHANGED_IDS = ["R-FOO-001"]

COMPLETE_ENTRY = {
    "new_requirement": "R-FOO-001",
    "overlaps_with": "R-BAR-002",
    "rationale": "Both require doubling the input, worded differently.",
}
EMPTY_RATIONALE_ENTRY = {
    "new_requirement": "R-FOO-001",
    "overlaps_with": "R-BAR-003",
    "rationale": "",
}
REDUNDANCY_TEXT = json.dumps(
    {"redundancy_flags": [COMPLETE_ENTRY, EMPTY_RATIONALE_ENTRY]}
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    _write(
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
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
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
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")


_COMMON = '''
class _Rec(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


class _Obj:
    _fields = ()

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return list(self._fields)

    def __iter__(self):
        return iter(self._fields)

    def __len__(self):
        return len(self._fields)

    def __contains__(self, key):
        return key in self._fields
'''


def _write_fakes(repo_root: Path, responses: list) -> Path:
    gen = repo_root / "gen"
    log_path = repo_root / "llm_calls.log"
    resp_path = repo_root / "llm_responses.json"
    resp_path.write_text(json.dumps(responses), encoding="utf-8")

    _write(
        gen / "spec-linter" / "spec_linter.py",
        _COMMON
        + '''

class LintReport(_Rec):
    def __missing__(self, key):
        summary = dict.get(self, "summary", {})
        if key in summary:
            return summary[key]
        raise KeyError(key)

    @property
    def hard_failures(self):
        return self["summary"]["hard_failures"]

    @property
    def warnings(self):
        return self["summary"]["warnings"]

    @property
    def skipped(self):
        return self["summary"]["skipped"]

    def to_json(self):
        return {"findings": [], "summary": dict(self["summary"])}


def lint(paths, repo_root, strict=False, judge=None):
    return LintReport(
        findings=[],
        summary={"hard_failures": 0, "warnings": 0, "skipped": 0},
    )
''',
    )

    _write(
        gen / "impact-analyzer" / "impact_analyzer.py",
        _COMMON
        + '''

def compute_blast_radius(changed_ids, repo_root):
    return _Rec(
        impacted=[_Rec(component_id="comp-foo", reason="direct", via=None)],
        precondition_error=None,
    )
''',
    )

    _write(
        gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        _COMMON
        + '''

class SpecBundle(_Obj):
    _fields = (
        "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
        "dependency_interfaces", "dependency_context", "dependency_usage",
        "vars", "glossary", "hint_code",
    )


def assemble(component_id, repo_root, mode="cold"):
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="# Foo\\n\\nFoo doubles a number.\\n\\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\\n\\nfoo(x: int) -> int",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="- **Foo** — a test term.",
        hint_code=({} if mode == "hint" else None),
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    raise NotImplementedError("not used by this test")
''',
    )

    _write(
        gen / "generator" / "generator.py",
        _COMMON
        + '''

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


class GenerationResult(_Obj):
    _fields = (
        "component_id", "spec_bundle_hash", "model", "prompt_version",
        "cache_hit", "files", "model_call_error", "refused", "retry_feedback",
    )


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    cid = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id", "comp-foo")
    h = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else getattr(bundle, "spec_bundle_hash", "sha256:0")
    return GenerationResult(
        component_id=cid,
        spec_bundle_hash=h,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "def foo(x):\\n    return 2 * x\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
''',
    )

    _write(
        gen / "llm-endpoint" / "llm_endpoint.py",
        "import json\n"
        f"LOG_PATH = {str(log_path)!r}\n"
        f"RESP_PATH = {str(resp_path)!r}\n"
        + '''

DEFAULT_TIMEOUT_SECONDS = 600


class ModelResolutionError(Exception):
    pass


def complete(prompt, model, *, backend=None, **params):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"model": model, "prompt_len": len(str(prompt))}) + "\\n")
    with open(LOG_PATH, "r", encoding="utf-8") as fh:
        index = sum(1 for line in fh if line.strip()) - 1
    with open(RESP_PATH, "r", encoding="utf-8") as fh:
        responses = json.load(fh)
    if index >= len(responses):
        return {
            "text": None,
            "model": model,
            "backend": "fake",
            "model_call_error": {"category": "network", "message": "unexpected extra call"},
        }
    r = responses[index]
    if r.get("error"):
        return {
            "text": None,
            "model": model,
            "backend": "fake",
            "model_call_error": {"category": "network", "message": "fake failure"},
        }
    return {"text": r["text"], "model": model, "backend": "fake", "model_call_error": None}
''',
    )
    return log_path


def _setup(tmp_path: Path, responses: list):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_corpus(repo_root)
    log_path = _write_fakes(repo_root, responses)
    return repo_root, log_path


def _call_count(log_path: Path) -> int:
    if not log_path.exists():
        return 0
    return sum(1 for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip())


def _run(repo_root: Path):
    return spec_completeness_assistant.assist(list(CHANGED_IDS), repo_root, model="fake-model")


@pytest.mark.parametrize("tag", ["json", ""])
def test_fenced_completeness_and_partial_redundancy(tmp_path, monkeypatch, tag):
    completeness = json.dumps(
        {"completeness_score": 0.7, "completeness_rationale": "AC missing"}
    )
    fenced = "```" + tag + "\n" + completeness + "\n```"
    repo_root, log_path = _setup(
        tmp_path, [{"text": fenced}, {"text": REDUNDANCY_TEXT}]
    )
    monkeypatch.chdir(tmp_path)

    report = _run(repo_root)

    assert _call_count(log_path) == 2
    score = field(report, "completeness_score")
    assert score is not None and not isinstance(score, bool)
    assert score == pytest.approx(0.7)
    assert field(report, "completeness_rationale") == "AC missing"
    flags = list(field(report, "redundancy_flags"))
    assert len(flags) == 1
    entry = flags[0]
    for key, expected in COMPLETE_ENTRY.items():
        assert field(entry, key) == expected
    assert field(report, "degraded") is False


def test_model_call_error_and_unparseable_redundancy(tmp_path, monkeypatch):
    repo_root, log_path = _setup(
        tmp_path,
        [{"error": True}, {"text": "this is not JSON at all, sorry"}],
    )
    monkeypatch.chdir(tmp_path)

    report = _run(repo_root)

    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None
    assert list(field(report, "redundancy_flags")) == []


def test_empty_rationale_is_not_parsed(tmp_path, monkeypatch):
    completeness = json.dumps({"completeness_score": 0.6, "completeness_rationale": ""})
    repo_root, log_path = _setup(
        tmp_path, [{"text": completeness}, {"text": REDUNDANCY_TEXT}]
    )
    monkeypatch.chdir(tmp_path)

    report = _run(repo_root)

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
def test_malformed_completeness_is_not_parsed(tmp_path, monkeypatch, completeness_text):
    repo_root, log_path = _setup(
        tmp_path, [{"text": completeness_text}, {"text": REDUNDANCY_TEXT}]
    )
    monkeypatch.chdir(tmp_path)

    report = _run(repo_root)

    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None


def test_score_above_range_is_clamped(tmp_path, monkeypatch):
    completeness = json.dumps({"completeness_score": 1.7, "completeness_rationale": "x"})
    repo_root, log_path = _setup(
        tmp_path, [{"text": completeness}, {"text": REDUNDANCY_TEXT}]
    )
    monkeypatch.chdir(tmp_path)

    report = _run(repo_root)

    score = field(report, "completeness_score")
    assert score is not None and not isinstance(score, bool)
    assert score == pytest.approx(1.0)