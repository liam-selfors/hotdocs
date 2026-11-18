# hotdocs-criterion: sha256:23b6160925ef9f5414dd4773d14e84b6b16d9c3230484adbd0a9f402eb84f92e
import json
import shutil
from pathlib import Path

import pytest

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _SentinelBackend:
    def __repr__(self):
        return "<SENTINEL-BACKEND-AC-SCENARIO-011>"

    def __call__(self, prompt, model, **params):
        raise AssertionError("sentinel backend must never be invoked by the fake")


PASS_TEXT = "```json\n" + '{"result": "pass", "rationale": "ok"}' + "\n```"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _live_repo_root():
    gen = next(
        (p for p in Path(capability_scenario_verifier.__file__).resolve().parents if p.name == "gen"),
        None,
    )
    return gen.parent if gen is not None else None


def _build_repo(repo_root, log_path, mode):
    # Realizing component, unsealed, code under gen/foo/
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "# MARKER_SOURCE\n"
        "def foo():\n"
        "    return 'MARKER_SOURCE'\n",
    )

    # Capability with one llm-judge scenario
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n"
        "\n"
        "# Capability X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a MARKER_GHERKIN situation\n"
        "When foo is used\n"
        "Then it behaves well\n"
        "```\n",
    )

    # Fake llm-endpoint
    fake_endpoint = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "MODE = " + repr(mode) + "\n"
        "PASS_TEXT = " + repr(PASS_TEXT) + "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'prompt': prompt, 'model': model, 'backend': repr(backend)}) + '\\n')\n"
        "    if MODE == 'error':\n"
        "        return {'text': None, 'model': model, 'backend': 'fake',\n"
        "                'model_call_error': {'category': 'network', 'message': 'fake network failure'}}\n"
        "    if MODE == 'pass':\n"
        "        text = PASS_TEXT\n"
        "    elif MODE == 'not_json':\n"
        "        text = 'not json'\n"
        "    elif MODE == 'maybe':\n"
        "        text = json.dumps({'result': 'maybe'})\n"
        "    else:\n"
        "        raise AssertionError('unknown mode')\n"
        "    return {'text': text, 'model': model, 'backend': 'fake', 'model_call_error': None}\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", fake_endpoint)

    # Fake test-author (unused for an llm-judge scenario, supplied per fixture rules)
    fake_author = (
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        'component_id': 'comp-foo',\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': 'verification/capabilities/P-X/generated-test/test_cs_x_001.py',\n"
        "                 'content': 'def test_x():\\n    assert True\\n'},\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", fake_author)

    # Real compiler copied from the live repository, when present
    live = _live_repo_root()
    if live is not None:
        src = live / "pipeline" / "criterion-compiler"
        if src.is_dir():
            shutil.copytree(
                src,
                repo_root / "pipeline" / "criterion-compiler",
                ignore=shutil.ignore_patterns("__pycache__"),
            )


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _scenario(result):
    report = field(result, "capability_scenario_report")
    assert report is not None
    cap = report["P-X"] if isinstance(report, dict) else getattr(report, "P-X")
    scenarios = field(cap, "scenarios")
    matching = [s for s in scenarios if field(s, "id") == "CS-X-001"]
    assert len(matching) == 1, scenarios
    return matching[0]


def test_judge_pass_with_fenced_reply(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "complete_calls.log"
    _build_repo(repo_root, log_path, "pass")

    sentinel = _SentinelBackend()
    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", llm_backend=sentinel
    )

    calls = _read_log(log_path)
    assert len(calls) == 1, calls
    call = calls[0]
    assert call["model"] == "m"
    assert call["backend"] == repr(sentinel)
    assert "MARKER_SOURCE" in call["prompt"]
    assert "MARKER_GHERKIN" in call["prompt"]

    scenario = _scenario(result)
    assert field(scenario, "result") == "pass"
    assert field(scenario, "rationale") == "ok"


@pytest.mark.parametrize("mode", ["error", "not_json", "maybe"])
def test_judge_unavailable_is_fail(tmp_path, mode):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "complete_calls.log"
    _build_repo(repo_root, log_path, mode)

    sentinel = _SentinelBackend()
    result = capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", llm_backend=sentinel
    )

    assert len(_read_log(log_path)) >= 1

    scenario = _scenario(result)
    assert field(scenario, "result") == "fail"
    rationale = field(scenario, "rationale")
    assert isinstance(rationale, str)
    assert rationale.startswith("judge unavailable"), rationale