"""AC-VERIFY-021 / R-VERIFY-018 (D190): the `hotdocs verify-component`
CLI. Kept in its own file so it never collides with edits to the main
suite."""

import json

import pytest

from conftest import acceptance_md, write_foo
from verifier_orchestrator import main

def _ac(cid, req, kind, gherkin):
    return acceptance_md(cid, req, kind, gherkin)


PASSING = _ac("AC-FOO-001", "R-FOO-001", "compiled",
              "Given a x is 1\nWhen do_the_thing is invoked with x\nThen value equals 2")
FAILING = _ac("AC-FOO-001", "R-FOO-001", "compiled",
              "Given a x is 1\nWhen do_the_thing is invoked with x\nThen value equals 5")
GENTEST = _ac("AC-FOO-002", "R-FOO-002", "generated-test",
              "Given the component\nWhen do_the_thing runs\nThen it adds one")
JUDGE = _ac("AC-FOO-003", "R-FOO-003", "llm-judge",
            "Given the component\nWhen a judge reads it\nThen it reads well")
WORKING_TEST = (
    "import sys\n"
    "sys.path.insert(0, 'gen/foo')\n"
    "from foo import do_the_thing\n\n"
    "def test_adds_one():\n"
    "    assert do_the_thing(1).value == 2\n"
    "    assert do_the_thing(-1).value == 0\n"
)


def _component(repo_root, first_ac):
    """The shape the main suite uses for an overall-pass component: a
    compiled criterion, a cached generated test, and a skipped judge."""
    write_foo(repo_root, extra_acceptance={
        "AC-FOO-001.md": first_ac, "AC-FOO-002.md": GENTEST, "AC-FOO-003.md": JUDGE,
    })
    cached = repo_root / "verification" / "foo" / "generated-test" / "test_ac_foo_002.py"
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(WORKING_TEST, encoding="utf-8")


def test_json_and_text_output_for_a_passing_component(repo_root, capsys):
    _component(repo_root, PASSING)

    assert main(["comp-foo", f"--repo-root={repo_root}", "--format=json"]) == 0
    assert json.loads(capsys.readouterr().out)["overall"] == "pass"

    assert main(["comp-foo", "--repo-root", str(repo_root), "--format", "text"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "comp-foo: pass"
    assert any(line.startswith("  AC-FOO-001: ") for line in lines[1:])


def test_failing_component_exits_one(repo_root):
    _component(repo_root, FAILING)
    assert main(["comp-foo", f"--repo-root={repo_root}"]) == 1


@pytest.mark.parametrize("argv_tail", [
    [],
    ["--format=bogus"],
    ["comp-foo", "--unknown-flag"],
    ["comp-foo", "--repo-root"],
    ["comp-nope"],
])
def test_usage_errors_exit_two_and_name_the_verb(repo_root, capsys, argv_tail):
    _component(repo_root, PASSING)
    argv = list(argv_tail)
    if "--repo-root" not in argv and not any(a.startswith("--repo-root=") for a in argv):
        argv += [f"--repo-root={repo_root}"]
    assert main(argv) == 2
    err = capsys.readouterr().err
    if "usage:" in err:
        assert "hotdocs verify-component" in err
        assert "hotdocs verify " not in err
