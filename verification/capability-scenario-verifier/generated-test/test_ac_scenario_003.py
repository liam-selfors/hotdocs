import json
import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest

import capability_scenario_verifier


# ---------------------------------------------------------------- helpers


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value and value[name] is not None
    return getattr(value, name, None) is not None


def capability_entry(report, pid):
    if isinstance(report, Mapping) or hasattr(report, "__getitem__"):
        return report[pid]
    return getattr(report, pid)


def _tool_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FAKE_TEST_AUTHOR = '''\
def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):
    cid = bundle["criterion_id"]
    name = "test_" + cid.lower().replace("-", "_") + ".py"
    return {
        "component_id": "capability",
        "criterion_id": cid,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/capabilities/P-X/generated-test/" + name,
            "content": "def test_x():\\n    assert True\\n",
        },
        "model_call_error": None,
    }
'''

FAKE_LLM_ENDPOINT = '''\
def complete(prompt, model, *, backend=None, **params):
    return {
        "text": '{"result": "pass", "rationale": "fake"}',
        "model": model,
        "backend": "fake",
        "model_call_error": None,
    }
'''


def build_repo(repo_root: Path, scenarios):
    """scenarios: list of (scenario_id, kind)."""
    # component realizing P-X
    _write(
        repo_root / "specs/components/foo/component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n\n"
        "# Foo\n\nA fixture component.\n",
    )
    _write(
        repo_root / "specs/components/foo/requirements/R-FOO-001.md",
        "**R-FOO-001** — MUST exist.\n",
    )
    _write(
        repo_root / "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: llm-judge\n\n"
        "```gherkin\nGiven foo\nWhen it is read\nThen it exists\n```\n",
    )
    _write(repo_root / "gen/foo/foo.py", "def hello():\n    return 1\n")

    # capability with its scenarios
    body = (
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n\n"
        "# Capability X\n\nA fixture capability.\n\n"
    )
    for sid, kind in scenarios:
        body += (
            f"### {sid}\n\n"
            "Covers: P-X\n"
            f"Kind: {kind}\n\n"
            "```gherkin\n"
            "Given the system is assembled\n"
            "When a user does the thing\n"
            "Then the thing works\n"
            "```\n\n"
        )
    _write(repo_root / "specs/product/x.md", body)

    # fake dependencies
    _write(repo_root / "gen/test-author/test_author.py", FAKE_TEST_AUTHOR)
    _write(repo_root / "gen/llm-endpoint/llm_endpoint.py", FAKE_LLM_ENDPOINT)

    # real compiler copied from the live repository, when available
    tool_root = _tool_root()
    if tool_root is not None:
        src = tool_root / "pipeline" / "criterion-compiler"
        if src.is_dir():
            shutil.copytree(
                src,
                repo_root / "pipeline" / "criterion-compiler",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    return repo_root


# ------------------------------------------------------------------ tests


def test_mixed_generated_test_and_llm_judge_scenarios(repo, tmp_path):
    build_repo(repo, [("CS-X-001", "generated-test"), ("CS-X-002", "llm-judge")])
    log = tmp_path / "invocations.jsonl"

    def test_author(bundle):
        sid = bundle["scenario_id"] if isinstance(bundle, dict) else getattr(bundle, "scenario_id")
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"fake": "test_author", "scenario_id": sid}) + "\n")
        name = "test_" + sid.lower().replace("-", "_") + ".py"
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-X/generated-test/" + name,
                "content": "def test_x():\n    assert True\n",
            },
        }

    def judge(bundle):
        sid = bundle["scenario_id"] if isinstance(bundle, dict) else getattr(bundle, "scenario_id")
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"fake": "judge", "scenario_id": sid}) + "\n")
        return {"result": "fail", "rationale": "because"}

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo, judge=judge, test_author=test_author
    )

    entry = capability_entry(report, "P-X")
    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 2

    by_kind = {field(s, "kind"): s for s in scenarios}
    assert set(by_kind) == {"generated-test", "llm-judge"}

    gen_entry = by_kind["generated-test"]
    judge_entry = by_kind["llm-judge"]

    assert field(gen_entry, "id") == "CS-X-001"
    assert field(judge_entry, "id") == "CS-X-002"

    assert not has_field(gen_entry, "rationale")
    assert field(judge_entry, "rationale") == "because"
    assert field(judge_entry, "result") == "fail"

    assert field(entry, "overall") == "fail"

    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    fakes = {r["fake"] for r in records}
    assert "judge" in fakes
    assert "test_author" in fakes


def test_capability_with_no_scenarios_fails(repo):
    build_repo(repo, [])

    report = capability_scenario_verifier.run_capability_scenarios(["comp-foo"], repo)

    entry = capability_entry(report, "P-X")
    assert field(entry, "overall") == "fail"
    assert list(field(entry, "scenarios")) == []


def test_llm_judge_only_without_judge_is_skipped(repo):
    build_repo(repo, [("CS-X-001", "llm-judge")])

    report = capability_scenario_verifier.run_capability_scenarios(["comp-foo"], repo)

    entry = capability_entry(report, "P-X")
    scenarios = list(field(entry, "scenarios"))
    assert len(scenarios) == 1
    only = scenarios[0]
    assert field(only, "id") == "CS-X-001"
    assert field(only, "kind") == "llm-judge"
    assert field(only, "result") == "skipped"
    assert field(entry, "overall") == "skipped"