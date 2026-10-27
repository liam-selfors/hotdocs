"""One test per AC-SCENARIO-* criterion in
specs/components/capability-scenario-verifier/acceptance/."""

from conftest import scenario_block, write_capability, write_component
from capability_scenario_verifier import run_capability_scenarios


def mock_test_author(content: str, passes: bool = True):
    body = "def test_x():\n    assert True\n" if passes else "def test_x():\n    assert False\n"

    def _call(bundle):
        return {"model_call_error": None, "file": {"path": "x.py", "content": body}}
    return _call


def test_ac_scenario_001_dispatched_and_keyed_by_p_id_distinct_from_components(repo_root):
    write_component(repo_root, "foo", realizes=["P-TEST"])
    write_component(repo_root, "bar", realizes=["P-TEST"])
    write_capability(
        repo_root, "P-TEST",
        scenario_block("CS-TEST-001", "P-TEST", "generated-test", "Given a thing\nWhen it happens\nThen it works"),
    )

    report = run_capability_scenarios(
        ["comp-foo", "comp-bar"], repo_root, test_author=mock_test_author("x", passes=True),
    )

    assert "P-TEST" in report
    assert "comp-foo" not in report
    assert "comp-bar" not in report
    assert report["P-TEST"]["overall"] == "pass"
    assert report["P-TEST"]["scenarios"][0]["id"] == "CS-TEST-001"


def test_ac_scenario_002_intersection_uses_edges_not_a_bespoke_lookup(repo_root):
    write_component(repo_root, "foo", realizes=["P-ZERO-EDIT"])
    write_component(repo_root, "bar", realizes=[])
    write_capability(
        repo_root, "P-ZERO-EDIT",
        scenario_block("CS-ZERO-EDIT-001", "P-ZERO-EDIT", "generated-test", "Given a thing\nWhen it happens\nThen it works"),
    )
    write_capability(
        repo_root, "P-UNRELATED",
        scenario_block("CS-UNRELATED-001", "P-UNRELATED", "generated-test", "Given a thing\nWhen it happens\nThen it works"),
    )

    report = run_capability_scenarios(
        ["comp-foo", "comp-bar"], repo_root, test_author=mock_test_author("x", passes=True),
    )

    assert set(report.keys()) == {"P-ZERO-EDIT"}


def test_ac_scenario_003_two_scenarios_each_named_with_own_result(repo_root):
    write_component(repo_root, "foo", realizes=["P-MULTI"])
    blocks = scenario_block(
        "CS-MULTI-001", "P-MULTI", "compiled", "Given a x is 1\nThen x equals 1",
    ) + scenario_block(
        "CS-MULTI-002", "P-MULTI", "llm-judge", "Given a thing\nWhen judged\nThen it is judged",
    )
    write_capability(repo_root, "P-MULTI", blocks)

    def judge(scenario):
        return {"result": "fail", "rationale": "did not meet the bar"}

    report = run_capability_scenarios(["comp-foo"], repo_root, judge=judge)

    assert report["P-MULTI"]["overall"] == "fail"
    scenarios_by_id = {s["id"]: s for s in report["P-MULTI"]["scenarios"]}
    assert scenarios_by_id["CS-MULTI-001"]["result"] == "pass"
    assert "rationale" not in scenarios_by_id["CS-MULTI-001"]
    assert scenarios_by_id["CS-MULTI-002"]["result"] == "fail"
    assert scenarios_by_id["CS-MULTI-002"]["rationale"] == "did not meet the bar"


def test_ac_scenario_004_generated_test_dispatch_never_cache_short_circuited(repo_root):
    """D84 -- no verification/<component>/-anchored cache file exists for
    a capability scenario; test_author must be called on every dispatch."""
    write_component(repo_root, "foo", realizes=["P-TEST"])
    write_capability(
        repo_root, "P-TEST",
        scenario_block("CS-TEST-001", "P-TEST", "generated-test", "Given a thing\nWhen it happens\nThen it works"),
    )

    calls = []

    def counting_test_author(bundle):
        calls.append(bundle)
        return {"model_call_error": None, "file": {"path": "x.py", "content": "def test_x():\n    assert True\n"}}

    run_capability_scenarios(["comp-foo"], repo_root, test_author=counting_test_author)
    run_capability_scenarios(["comp-foo"], repo_root, test_author=counting_test_author)
    assert len(calls) == 2
