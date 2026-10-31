"""One test per AC-VERIFY-* criterion in
specs/components/verifier-orchestrator/acceptance/."""

from dataclasses import asdict

from conftest import FOO_CODE_DRIFT, FOO_CODE_TWO_FUNCTIONS, acceptance_md, write_bar, write_foo
from verifier_orchestrator import verify

COMPILED_AC = acceptance_md(
    "AC-FOO-001", "R-FOO-001", "compiled",
    "Given a x is 1\nWhen do_the_thing is invoked with x\nThen value equals 2",
)
FAILING_COMPILED_AC = acceptance_md(
    "AC-FOO-001", "R-FOO-001", "compiled",
    "Given a x is 1\nWhen do_the_thing is invoked with x\nThen value equals 5",
)
JUDGE_AC = acceptance_md(
    "AC-FOO-003", "R-FOO-003", "llm-judge",
    "Given the component\nWhen a judge reads it\nThen it reads well",
)
GENTEST_AC = acceptance_md(
    "AC-FOO-002", "R-FOO-002", "generated-test",
    "Given the component\nWhen do_the_thing runs\nThen it adds one",
)

WORKING_TEST_SOURCE = (
    "import sys\n"
    "sys.path.insert(0, 'gen/foo')\n"
    "from foo import do_the_thing\n\n"
    "def test_adds_one():\n"
    "    assert do_the_thing(1).value == 2\n"
)

WEAK_TEST_SOURCE = (
    "def test_nothing_real():\n"
    "    assert True\n"
)


def test_ac_verify_001_compiled_dispatch_and_result(repo_root):
    write_foo(repo_root, extra_acceptance={"AC-FOO-001.md": COMPILED_AC})
    report = verify("comp-foo", repo_root)
    by_id = {c["id"]: c for c in report.criteria}
    assert by_id["AC-FOO-001"]["result"] == "pass"


def test_ac_verify_002_cached_generated_test_is_executed(repo_root):
    write_foo(repo_root, extra_acceptance={"AC-FOO-002.md": GENTEST_AC})
    cache_path = repo_root / "verification" / "foo" / "generated-test" / "test_ac_foo_002.py"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(WORKING_TEST_SOURCE, encoding="utf-8")

    report = verify("comp-foo", repo_root)
    by_id = {c["id"]: c for c in report.criteria}
    assert by_id["AC-FOO-002"]["result"] == "pass"
    assert "test_authoring" not in by_id["AC-FOO-002"]  # cache hit, no fresh authoring


def test_ac_verify_003_no_judge_configured_is_skipped_with_null_rationale(repo_root):
    write_foo(repo_root, extra_acceptance={"AC-FOO-003.md": JUDGE_AC})
    report = verify("comp-foo", repo_root, judge=None)
    by_id = {c["id"]: c for c in report.criteria}
    assert by_id["AC-FOO-003"]["result"] == "skipped"
    assert by_id["AC-FOO-003"]["rationale"] is None


def test_ac_verify_004_interface_drift_detected(repo_root):
    write_foo(repo_root, code=FOO_CODE_DRIFT, extra_acceptance={"AC-FOO-001.md": COMPILED_AC})
    report = verify("comp-foo", repo_root)
    assert report.interface_drift is True
    assert report.overall == "fail"


def test_ac_verify_005_skipped_llm_judge_alone_does_not_fail_overall(repo_root):
    cache_path_text = acceptance_md(
        "AC-FOO-002", "R-FOO-002", "generated-test", "Given the component\nWhen do_the_thing runs\nThen it adds one",
    )
    write_foo(repo_root, extra_acceptance={
        "AC-FOO-001.md": COMPILED_AC,
        "AC-FOO-002.md": cache_path_text,
        "AC-FOO-003.md": JUDGE_AC,
    })
    cache_path = repo_root / "verification" / "foo" / "generated-test" / "test_ac_foo_002.py"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(WORKING_TEST_SOURCE, encoding="utf-8")

    report = verify("comp-foo", repo_root, judge=None)
    by_id = {c["id"]: c for c in report.criteria}
    assert by_id["AC-FOO-003"]["result"] == "skipped"
    assert report.overall == "pass"


def test_ac_verify_006_mutation_score_below_bar_fails_overall(repo_root):
    write_foo(repo_root, extra_acceptance={"AC-FOO-002.md": GENTEST_AC})
    cache_path = repo_root / "verification" / "foo" / "generated-test" / "test_ac_foo_002.py"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(WEAK_TEST_SOURCE, encoding="utf-8")

    report = verify("comp-foo", repo_root)
    assert report.mutation_score is not None
    assert report.mutation_score < 0.80
    assert report.overall == "fail"


def test_ac_verify_007_exactly_one_report_with_all_fields(repo_root):
    write_foo(repo_root, extra_acceptance={"AC-FOO-001.md": COMPILED_AC})
    report = verify("comp-foo", repo_root)
    assert report.component_id == "comp-foo"
    assert isinstance(report.criteria, list)
    assert isinstance(report.requirement_results, dict)
    assert report.interface_drift in (True, False)
    assert report.overall in ("pass", "fail")


def test_ac_verify_008_idempotent_given_consistent_judge(repo_root):
    write_foo(repo_root, extra_acceptance={
        "AC-FOO-001.md": COMPILED_AC,
        "AC-FOO-003.md": JUDGE_AC,
    })

    def judge(payload):
        return {"pass": True, "rationale": "looks fine"}

    report1 = verify("comp-foo", repo_root, judge=judge)
    report2 = verify("comp-foo", repo_root, judge=judge)
    assert asdict(report1) == asdict(report2)


def test_ac_verify_009_test_author_dispatched_with_exact_criterion_bundle(repo_root):
    write_foo(repo_root, extra_acceptance={"AC-FOO-002.md": GENTEST_AC})
    calls = []

    def test_author(bundle):
        calls.append(bundle)
        return {"model_call_error": None, "file": {"content": WORKING_TEST_SOURCE}}

    report = verify("comp-foo", repo_root, test_author=test_author)
    assert len(calls) == 1
    bundle = calls[0]
    get = (lambda k: bundle.get(k)) if isinstance(bundle, dict) else (lambda k: getattr(bundle, k))
    assert get("component_id") == "comp-foo"
    assert get("criterion_id") == "AC-FOO-002"
    assert get("covers") == "R-FOO-002"
    by_id = {c["id"]: c for c in report.criteria}
    assert by_id["AC-FOO-002"]["result"] == "pass"


def test_ac_verify_009_bundle_includes_real_dependency_interfaces(repo_root):
    # D119: this component MUST pass exactly the CriterionBundle
    # spec-bundle-assembler.assemble_criterion() returns, never a
    # smaller, independently-built one -- dependency_interfaces must
    # carry comp-bar's own real, documented interface text.
    write_bar(repo_root)
    write_foo(repo_root, extra_acceptance={"AC-FOO-002.md": GENTEST_AC}, depends_on=["comp-bar"])
    calls = []

    def test_author(bundle):
        calls.append(bundle)
        return {"model_call_error": None, "file": {"content": WORKING_TEST_SOURCE}}

    verify("comp-foo", repo_root, test_author=test_author)
    assert len(calls) == 1
    bundle = calls[0]
    get = (lambda k: bundle.get(k)) if isinstance(bundle, dict) else (lambda k: getattr(bundle, k))
    dependency_interfaces = get("dependency_interfaces")
    assert dependency_interfaces is not None
    assert "do_bar_thing" in dependency_interfaces["comp-bar"]


def test_ac_verify_010_no_cache_no_test_author_fails_not_skipped(repo_root):
    write_foo(repo_root, extra_acceptance={"AC-FOO-002.md": GENTEST_AC})
    report = verify("comp-foo", repo_root, test_author=None)
    by_id = {c["id"]: c for c in report.criteria}
    assert by_id["AC-FOO-002"]["result"] == "fail"
    assert report.overall == "fail"


def test_ac_verify_011_requirement_results_projection_is_content_free(repo_root):
    second_r001_ac = acceptance_md(
        "AC-FOO-001B", "R-FOO-001", "compiled",
        "Given a x is 1\nWhen do_the_thing is invoked with x\nThen value equals 2",
    )
    write_foo(repo_root, extra_acceptance={
        "AC-FOO-001.md": COMPILED_AC,
        "AC-FOO-001B.md": second_r001_ac,
        "AC-FOO-002.md": GENTEST_AC,  # no cache, no test_author -> fail -> R-FOO-002 fail
        "AC-FOO-003.md": JUDGE_AC,  # no judge -> skipped -> R-FOO-003 fail
    })
    report = verify("comp-foo", repo_root, judge=None, test_author=None)
    assert report.requirement_results == {"R-FOO-001": "pass", "R-FOO-002": "fail", "R-FOO-003": "fail"}
    import json
    serialized = json.dumps(report.requirement_results)
    assert "Gherkin" not in serialized
    assert "rationale" not in serialized.lower()


def test_ac_verify_012_judge_called_exactly_once(repo_root):
    write_foo(repo_root, extra_acceptance={"AC-FOO-003.md": JUDGE_AC})
    calls = []

    def judge(payload):
        calls.append(payload)
        return {"pass": True, "rationale": "fine"}

    verify("comp-foo", repo_root, judge=judge)
    assert len(calls) == 1


def test_ac_verify_013_failure_detail_has_expected_and_actual(repo_root):
    write_foo(repo_root, extra_acceptance={"AC-FOO-001.md": FAILING_COMPILED_AC})
    report = verify("comp-foo", repo_root)
    by_id = {c["id"]: c for c in report.criteria}
    entry = by_id["AC-FOO-001"]
    assert entry["result"] == "fail"
    assert entry["failure_detail"]["expected"] == 5
    assert entry["failure_detail"]["actual"] == 2


def test_ac_verify_015_mutation_score_is_a_union_not_a_per_criterion_average(repo_root):
    # D124: AC-FOO-002's own test only calls do_the_thing; a new
    # AC-FOO-004's own test only calls double_it. Each function has
    # its own mutable node the OTHER criterion's test cannot kill.
    # Scored in isolation and averaged, this would be low; unioned
    # across both criteria's tests, it must be high.
    write_foo(
        repo_root,
        code=FOO_CODE_TWO_FUNCTIONS,
        extra_acceptance={"AC-FOO-002.md": GENTEST_AC},
    )
    (repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-004.md").write_text(
        "# R-FOO-004\n\n**R-FOO-004** -- Foo MUST double its input.\n", encoding="utf-8"
    )
    double_ac = acceptance_md(
        "AC-FOO-004", "R-FOO-004", "generated-test",
        "Given the component\nWhen double_it runs\nThen it doubles the input",
    )
    (repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-004.md").write_text(
        double_ac, encoding="utf-8"
    )

    do_the_thing_test = (
        "import sys\n"
        "sys.path.insert(0, 'gen/foo')\n"
        "from foo import do_the_thing\n\n"
        "def test_adds_one():\n"
        "    assert do_the_thing(1).value == 2\n"
        "    assert do_the_thing(-1).value == 0\n"
    )
    double_it_test = (
        "import sys\n"
        "sys.path.insert(0, 'gen/foo')\n"
        "from foo import double_it\n\n"
        "def test_doubles():\n"
        "    assert double_it(3) == 6\n"
        "    assert double_it(-3) == 0\n"
    )
    gentest_dir = repo_root / "verification" / "foo" / "generated-test"
    gentest_dir.mkdir(parents=True, exist_ok=True)
    (gentest_dir / "test_ac_foo_002.py").write_text(do_the_thing_test, encoding="utf-8")
    (gentest_dir / "test_ac_foo_004.py").write_text(double_it_test, encoding="utf-8")

    report = verify("comp-foo", repo_root)
    by_id = {c["id"]: c for c in report.criteria}
    assert by_id["AC-FOO-002"]["result"] == "pass"
    assert by_id["AC-FOO-004"]["result"] == "pass"
    assert report.mutation_score > 0.75


FOO_CODE_LOOP = """from dataclasses import dataclass


@dataclass
class Thing:
    value: int


def do_the_thing(x):
    i = 0
    while i < x:
        i = i + 1
    return Thing(value=i + 1)
"""


def test_ac_verify_016_hanging_mutant_times_out_and_counts_killed(repo_root):
    # D158: mutating the loop's `i + 1` into `i - 1` never terminates.
    # Without a per-run timeout, verify() hangs forever on that mutant.
    import time

    write_foo(repo_root, code=FOO_CODE_LOOP, extra_acceptance={
        "AC-FOO-001.md": COMPILED_AC,
        "AC-FOO-002.md": GENTEST_AC,
        "AC-FOO-003.md": JUDGE_AC,
    })
    loop_test = (
        "import sys\n"
        "sys.path.insert(0, 'gen/foo')\n"
        "from foo import do_the_thing\n\n"
        "def test_counts_up():\n"
        "    assert do_the_thing(1).value == 2\n"
        "    assert do_the_thing(3).value == 4\n"
    )
    gentest_dir = repo_root / "verification" / "foo" / "generated-test"
    gentest_dir.mkdir(parents=True, exist_ok=True)
    (gentest_dir / "test_ac_foo_002.py").write_text(loop_test, encoding="utf-8")

    started = time.monotonic()
    report = verify("comp-foo", repo_root)
    elapsed = time.monotonic() - started

    by_id = {c["id"]: c for c in report.criteria}
    assert by_id["AC-FOO-002"]["result"] == "pass"
    # R-VERIFY-006's four operators give exactly three mutants here
    # (one comparison, two additions); all must count as killed,
    # including the loop's `i - 1` hang (D158), and no numeric-constant
    # mutant may appear (D159).
    assert report.mutation_score == 1.0
    assert report.overall == "pass"
    assert elapsed < 60
