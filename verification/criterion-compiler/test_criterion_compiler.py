"""One test per AC-COMPILE-* criterion in
specs/components/criterion-compiler/acceptance/ -- written independently
from this component's hand-maintained implementation (criterion-compiler
is sealed; see component.md's Purpose for why these are Kind:
generated-test rather than Kind: compiled)."""

import subprocess
import sys
from pathlib import Path

from conftest import write_component
import criterion_compiler
from criterion_compiler import compile, main, GATE_VERSION, compile_criterion, ParsedCriterion


def test_ac_compile_001_unrecognized_step_is_a_located_error(repo_root):
    write_component(repo_root, "widget", {
        "AC-WID-001": ("R-WID-001", "compiled", "Given a wizard appears\nWhen nothing happens\nThen it is fine"),
    })
    report = compile("widget", repo_root)
    assert report.summary["errors"] == 1
    assert report.summary["compiled"] == 0
    out = report.outputs[0]
    assert out["status"] == "error"
    assert out["criterion_id"] == "AC-WID-001"
    assert "wizard appears" in out["message"]


def test_ac_compile_002_unresolved_function_reference_is_an_error(repo_root):
    write_component(repo_root, "widget", {
        "AC-WID-002": ("R-WID-002", "compiled",
                        'Given a foo is "bar"\nWhen totally_undeclared_func is invoked with {}\nThen value equals 1'),
    })
    report = compile("widget", repo_root)
    assert report.summary["errors"] == 1
    assert "totally_undeclared_func" in report.outputs[0]["message"]


def test_ac_compile_003_determinism_across_two_processes(repo_root):
    write_component(repo_root, "widget", {
        "AC-WID-003": ("R-WID-003", "compiled",
                        'Given a x is 1\nWhen do_the_thing is invoked with x\nThen value equals 1'),
    })
    report1 = compile("widget", repo_root)
    out_file = repo_root / report1.outputs[0]["file"]
    content1 = out_file.read_bytes()
    out_file.unlink()

    script = (
        "import sys; sys.path.insert(0, %r); import criterion_compiler; "
        "criterion_compiler.compile('widget', %r)"
    ) % (str(Path(__file__).resolve().parents[2] / "pipeline" / "criterion-compiler"), str(repo_root))
    subprocess.run([sys.executable, "-c", script], check=True)
    content2 = out_file.read_bytes()
    assert content1 == content2


def test_ac_compile_004_covers_id_is_traceable_metadata(repo_root):
    write_component(repo_root, "widget", {
        "AC-FOO-003": ("R-FOO-003", "compiled",
                        'Given a x is 1\nWhen do_the_thing is invoked with x\nThen value equals 1'),
    })
    report = compile("widget", repo_root)
    out_file = repo_root / report.outputs[0]["file"]
    assert "R-FOO-003" in out_file.read_text(encoding="utf-8")


def test_ac_compile_005_non_compiled_kind_is_skipped_not_errored(repo_root):
    write_component(repo_root, "widget", {
        "AC-WID-005A": ("R-WID-005A", "compiled",
                         'Given a x is 1\nWhen do_the_thing is invoked with x\nThen value equals 1'),
        "AC-WID-005B": ("R-WID-005B", "llm-judge", "Given anything\nWhen anything\nThen it is judged"),
    })
    report = compile("widget", repo_root)
    assert report.summary["compiled"] == 1
    assert report.summary["errors"] == 0
    assert report.summary["skipped_non_compiled_kind"] == 1
    statuses = {o["criterion_id"]: o["status"] for o in report.outputs}
    assert statuses == {"AC-WID-005A": "compiled"}


def test_ac_compile_006_output_written_under_verification_widget_compiled(repo_root):
    write_component(repo_root, "widget", {
        "AC-WID-006": ("R-WID-006", "compiled",
                        'Given a x is 1\nWhen do_the_thing is invoked with x\nThen value equals 1'),
    })
    report = compile("widget", repo_root)
    out_file = Path(report.outputs[0]["file"])
    assert str(out_file).startswith("verification/widget/compiled/")
    assert (repo_root / out_file).is_file()
    assert not list((repo_root / "specs").rglob("test_*.py"))


def test_ac_compile_007_literal_data_is_inert_never_executed(repo_root):
    dangerous = "$(rm -rf /); import os; os.system('echo pwned')"
    write_component(repo_root, "widget", {
        "AC-WID-007": ("R-WID-007", "compiled",
                        f'Given a danger is "{dangerous}"\nWhen do_the_thing is invoked with danger\nThen value equals 1'),
    })
    report = compile("widget", repo_root)
    assert report.summary["errors"] == 0
    out_file = repo_root / report.outputs[0]["file"]
    source = out_file.read_text(encoding="utf-8")
    assert "os.system" not in source.replace(repr(dangerous), "")  # only inside the quoted literal
    import ast
    ast.parse(source)  # must be valid, inert Python -- the string is data, not spliced code
    ns: dict = {}
    marker = []
    exec(compile_src := source, {"os": type("FakeOS", (), {"system": staticmethod(lambda *a: marker.append(True))})()}, ns)  # noqa: F841
    assert not marker  # os.system is never actually called by defining/holding this module


def test_ac_compile_008_no_network_access(repo_root, monkeypatch):
    import socket

    def _forbidden(*args, **kwargs):
        raise AssertionError("criterion-compiler must never open a socket")

    monkeypatch.setattr(socket, "socket", _forbidden)
    write_component(repo_root, "widget", {
        "AC-WID-008": ("R-WID-008", "compiled",
                        'Given a x is 1\nWhen do_the_thing is invoked with x\nThen value equals 1'),
        "AC-WID-008B": ("R-WID-008B", "compiled", "Given a wizard appears\nWhen nothing\nThen nothing"),
    })
    report = compile("widget", repo_root)  # must not raise, valid or invalid content alike
    assert report.summary["compiled"] == 1
    assert report.summary["errors"] == 1


def test_ac_compile_009_idempotent_recompile_does_not_touch_output(repo_root):
    write_component(repo_root, "widget", {
        "AC-WID-009": ("R-WID-009", "compiled",
                        'Given a x is 1\nWhen do_the_thing is invoked with x\nThen value equals 1'),
    })
    report = compile("widget", repo_root)
    out_file = repo_root / report.outputs[0]["file"]
    mtime1 = out_file.stat().st_mtime_ns
    content1 = out_file.read_bytes()

    compile("widget", repo_root)
    assert out_file.stat().st_mtime_ns == mtime1
    assert out_file.read_bytes() == content1


def test_ac_compile_010_gate_version_reflects_the_live_module_constant(repo_root, monkeypatch):
    write_component(repo_root, "widget", {
        "AC-WID-010": ("R-WID-010", "compiled",
                        'Given a x is 1\nWhen do_the_thing is invoked with x\nThen value equals 1'),
    })
    report1 = compile("widget", repo_root)
    assert report1.gate_version == GATE_VERSION

    monkeypatch.setattr(criterion_compiler, "GATE_VERSION", "criterion-compiler@2.0.0")
    report2 = compile("widget", repo_root)
    assert report2.gate_version == "criterion-compiler@2.0.0"
    assert report1.gate_version != report2.gate_version


def test_ac_compile_011_unsupported_target_fails_exit_2_no_output(repo_root, capsys):
    write_component(repo_root, "widget", {
        "AC-WID-011": ("R-WID-011", "compiled",
                        'Given a x is 1\nWhen do_the_thing is invoked with x\nThen value equals 1'),
    })
    code = main(["widget", "--target=jest", f"--repo-root={repo_root}"])
    assert code == 2
    captured = capsys.readouterr()
    assert "jest" in captured.err
    assert not (repo_root / "verification" / "widget" / "compiled").exists()

    report_a = compile("widget", repo_root, target="pytest")
    content_a = (repo_root / report_a.outputs[0]["file"]).read_bytes()
    (repo_root / report_a.outputs[0]["file"]).unlink()
    report_b = compile("widget", repo_root, target="pytest")
    content_b = (repo_root / report_b.outputs[0]["file"]).read_bytes()
    assert content_a == content_b


def test_ac_compile_012_literal_substitution_and_expression_rejection(repo_root):
    write_component(repo_root, "widget", {
        "AC-WID-012A": ("R-WID-012A", "compiled",
                         'Given a user_id is "u1"\n'
                         'When process is invoked with [user_id, {"owner": user_id}]\n'
                         'Then value equals 1'),
        "AC-WID-012B": ("R-WID-012B", "compiled",
                         'Given a user_id is "u1"\n'
                         'When process is invoked with user_id + 1\n'
                         'Then value equals 1'),
        "AC-WID-012C": ("R-WID-012C", "compiled",
                         'Given a user_id is "u1"\n'
                         'When process is invoked with user_id.id\n'
                         'Then value equals 1'),
        "AC-WID-012D": ("R-WID-012D", "compiled",
                         'Given a user_id is "u1"\n'
                         'When process is invoked with does_not_exist\n'
                         'Then value equals 1'),
    })
    report = compile("widget", repo_root)
    by_id = {o["criterion_id"]: o for o in report.outputs}

    assert by_id["AC-WID-012A"]["status"] == "compiled"
    source_a = (repo_root / by_id["AC-WID-012A"]["file"]).read_text(encoding="utf-8")
    exercise_line = next(line for line in source_a.splitlines() if "process(" in line)
    assert "user_id" not in exercise_line  # no runtime lookup left in the call itself
    assert exercise_line.count('"u1"') == 2  # both positions resolved to the literal at compile time

    assert by_id["AC-WID-012B"]["status"] == "error"
    assert "not a literal" in by_id["AC-WID-012B"]["message"]

    assert by_id["AC-WID-012C"]["status"] == "error"
    assert "field/index access" in by_id["AC-WID-012C"]["message"]

    assert by_id["AC-WID-012D"]["status"] == "error"
    assert "unresolved reference" in by_id["AC-WID-012D"]["message"]


def test_ac_compile_013_compile_criterion_works_with_no_surface_at_all(repo_root):
    literal_only = ParsedCriterion(
        criterion_id="CS-FOO-001", covers="P-FOO", kind="compiled",
        gherkin='Given a x is 1\nThen x equals 1', file="CS-FOO-001.md",
    )
    result = compile_criterion(literal_only, surface=None)
    assert result["status"] == "compiled"
    assert "x = 1" in result["source"]

    references_a_function = ParsedCriterion(
        criterion_id="CS-FOO-002", covers="P-FOO", kind="compiled",
        gherkin='Given a x is 1\nWhen do_the_thing is invoked with x\nThen result.value equals 1',
        file="CS-FOO-002.md",
    )
    result2 = compile_criterion(references_a_function, surface=None)
    assert result2["status"] == "error"
    assert "do_the_thing" in result2["message"]
