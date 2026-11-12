"""AC-COMPILE-003 / R-COMPILE-003.

Given a fixed component's acceptance/ and interface/ content,
when compile-criteria runs against it twice, in two separate processes,
then both runs produce byte-identical output files.
"""

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import criterion_compiler


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / SLUG

    _write(
        comp_dir / "component.md",
        textwrap.dedent(
            """\
            ---
            id: comp-widget-maker
            title: Widget Maker
            status: draft
            owners: [alice]
            depends_on: []
            sealed: true
            source_path: legacy/widget
            ---

            # Widget Maker

            ## Purpose

            Makes widgets, for a criterion-compiler determinism fixture.
            """
        ),
    )

    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\nNone.\n",
    )

    requirements = {
        "R-WIDGET-001": "make_widget MUST return a widget carrying the given name.",
        "R-WIDGET-002": "make_widget MUST accept positional arguments.",
        "R-WIDGET-003": "make_widget MUST return the widget's tags.",
        "R-WIDGET-004": "describe MUST accept a Widget.",
    }
    for rid, text in requirements.items():
        _write(
            comp_dir / "requirements" / f"{rid}.md",
            f"# {rid}\n\n**{rid}** — {text}\n",
        )

    fence = "```"
    acceptance = {
        "AC-WIDGET-001": (
            "R-WIDGET-001",
            [
                'Given a payload is "hello"',
                'When make_widget is invoked with {"name": payload, "size": 3}',
                'Then name equals "hello"',
            ],
        ),
        "AC-WIDGET-002": (
            "R-WIDGET-002",
            [
                'Given a count is 5',
                'When make_widget is invoked with ["w2", count]',
                "Then size equals 5",
            ],
        ),
        "AC-WIDGET-003": (
            "R-WIDGET-003",
            [
                'When make_widget is invoked with {"name": "n", "size": 1}',
                'Then tags equals {"b": 2, "a": [1, true, null, 2.5], "c": "z"}',
                'Then tags[0] equals "x"',
            ],
        ),
        "AC-WIDGET-004": (
            "R-WIDGET-004",
            [
                'Given a Widget with name: "w1", size: 2, tags: ["x", "y"]',
                'When describe is invoked with {"widget": "w1"}',
                'Then length equals 2',
            ],
        ),
    }
    for aid, (covers, steps) in acceptance.items():
        body = (
            f"# {aid}\n\n"
            f"Covers: {covers}\n"
            f"Kind: compiled\n\n"
            f"{fence}gherkin\n" + "\n".join(steps) + f"\n{fence}\n"
        )
        _write(comp_dir / "acceptance" / f"{aid}.md", body)

    _write(
        comp_dir / "interface" / "library.md",
        textwrap.dedent(
            f"""\
            # Library

            {fence}
            make_widget(name: str, size: int = 1) -> dict
            describe(widget: Widget) -> str
            {fence}
            """
        ),
    )

    _write(
        comp_dir / "interface" / "data" / "Widget.md",
        textwrap.dedent(
            f"""\
            # `Widget`

            {fence}json
            {{"name": "w", "size": 1, "tags": ["a"]}}
            {fence}
            """
        ),
    )


_RUNNER = textwrap.dedent(
    """\
    import json
    import sys
    from pathlib import Path

    import criterion_compiler


    def _get(value, key, default=None):
        if isinstance(value, dict):
            return value.get(key, default)
        return getattr(value, key, default)


    repo_root = Path(sys.argv[1])
    component_id = sys.argv[2]
    slug = sys.argv[3]
    report_path = Path(sys.argv[4])

    report = criterion_compiler.compile(component_id, repo_root)
    summary = _get(report, "summary") or {}
    compiled = _get(summary, "compiled", 0) or 0
    if not compiled:
        report = criterion_compiler.compile(slug, repo_root)
        summary = _get(report, "summary") or {}

    outputs = []
    for entry in (_get(report, "outputs") or []):
        outputs.append(
            {
                "criterion_id": _get(entry, "criterion_id"),
                "status": _get(entry, "status"),
                "file": str(_get(entry, "file")),
            }
        )

    report_path.write_text(
        json.dumps(
            {
                "outputs": outputs,
                "summary": dict(summary) if isinstance(summary, dict) else {
                    "compiled": _get(summary, "compiled"),
                    "errors": _get(summary, "errors"),
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    """
)


def _module_search_root() -> str:
    mod_file = Path(criterion_compiler.__file__).resolve()
    if mod_file.name == "__init__.py":
        return str(mod_file.parent.parent)
    return str(mod_file.parent)


def _run_in_subprocess(runner: Path, repo_root: Path, report_path: Path,
                       cwd: Path, hash_seed: str) -> dict:
    env = dict(os.environ)
    path_entries = [_module_search_root()] + [p for p in sys.path if p]
    existing = env.get("PYTHONPATH")
    if existing:
        path_entries.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(path_entries)
    env["PYTHONHASHSEED"] = hash_seed

    proc = subprocess.run(
        [sys.executable, str(runner), str(repo_root), COMPONENT_ID, SLUG,
         str(report_path)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, (
        f"compile subprocess failed (rc={proc.returncode})\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    return json.loads(report_path.read_text(encoding="utf-8"))


def _snapshot(out_dir: Path) -> dict:
    files = {}
    if not out_dir.exists():
        return files
    for p in sorted(out_dir.rglob("*")):
        if p.is_file():
            files[p.relative_to(out_dir).as_posix()] = p.read_bytes()
    return files


def test_ac_compile_003_two_process_runs_are_byte_identical(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    runner = scripts / "run_compile.py"
    runner.write_text(_RUNNER, encoding="utf-8")

    cwd1 = tmp_path / "cwd1"
    cwd2 = tmp_path / "cwd2"
    cwd1.mkdir()
    cwd2.mkdir()

    out_dir = repo_root / "verification" / SLUG / "compiled"

    # Run 1
    report1 = _run_in_subprocess(
        runner, repo_root, tmp_path / "report1.json", cwd1, "1"
    )
    snap1 = _snapshot(out_dir)

    # Clear outputs so run 2 must regenerate them from scratch.
    if out_dir.exists():
        shutil.rmtree(out_dir)

    # Run 2, separate process, different hash seed and cwd.
    report2 = _run_in_subprocess(
        runner, repo_root, tmp_path / "report2.json", cwd2, "2"
    )
    snap2 = _snapshot(out_dir)

    compiled1 = [o for o in report1["outputs"] if o.get("status") == "compiled"]
    compiled2 = [o for o in report2["outputs"] if o.get("status") == "compiled"]
    assert compiled1, f"fixture compiled nothing in run 1: {report1}"
    assert compiled2, f"fixture compiled nothing in run 2: {report2}"

    # Both runs report the same set of outcomes.
    key = lambda o: (str(o.get("criterion_id")), str(o.get("status")), str(o.get("file")))
    assert sorted(map(key, report1["outputs"])) == sorted(map(key, report2["outputs"]))

    # Every compiled output file actually exists after each run.
    assert snap1, "run 1 wrote no output files"
    assert snap2, "run 2 wrote no output files"
    for o in compiled1:
        assert Path(o["file"]).name in {Path(k).name for k in snap1}, o
    for o in compiled2:
        assert Path(o["file"]).name in {Path(k).name for k in snap2}, o

    # Same set of files, byte-identical contents.
    assert sorted(snap1) == sorted(snap2)
    for name in snap1:
        assert snap1[name] == snap2[name], (
            f"output file {name!r} differs between runs:\n"
            f"--- run 1 ---\n{snap1[name].decode('utf-8', 'replace')}\n"
            f"--- run 2 ---\n{snap2[name].decode('utf-8', 'replace')}"
        )