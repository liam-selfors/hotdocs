import json
from pathlib import Path

import hotdocs_cli


ROWS = [
    (["lint"], "gen/spec-linter", "spec_linter", 1),
    (["impact"], "gen/impact-analyzer", "impact_analyzer", 1),
    (["assemble"], "gen/spec-bundle-assembler", "spec_bundle_assembler", 1),
    (["compile-criteria"], "pipeline/criterion-compiler", "criterion_compiler", 1),
    (["author-test"], "gen/test-author", "test_author", 0),
    (["verify-component"], "gen/verifier-orchestrator", "verifier_orchestrator", 1),
    (["generate"], "gen/component-gate-runner", "component_gate_runner", 0),
    (["verify"], "gen/provenance-tracker", "provenance_tracker", 0),
    (["track", "feedback"], "gen/provenance-tracker", "provenance_tracker", 0),
    (["track", "ui", "build"], "gen/provenance-tracker-ui", "provenance_tracker_ui", 0),
    (["provenance", "check"], "gen/provenance-checker", "provenance_checker", 1),
    (["provenance", "write"], "gen/provenance-writer", "provenance_writer", 0),
    (["license-scan"], "gen/license-scanner", "license_scanner", 1),
    (["secret-scan"], "gen/secret-scanner", "secret_scanner", 1),
    (["review-packet", "build"], "gen/review-packet-builder", "review_packet_builder", 0),
    (["decision-drift"], "gen/decision-drift-detector", "decision_drift_detector", 0),
    (["decision-impact"], "gen/decision-drift-detector", "decision_drift_detector", 0),
    (["docs-site", "build"], "gen/docs-site-renderer", "docs_site_renderer.cli", 2),
    (["corpus-graph", "build"], "gen/corpus-graph-builder", "corpus_graph_builder.cli", 1),
    (["assist"], "gen/spec-completeness-assistant", "spec_completeness_assistant", 1),
]


def _marker_path(markers_dir: Path, dir_rel: str, module_name: str) -> Path:
    safe = f"{dir_rel}__{module_name}".replace("/", "_").replace(".", "_")
    return markers_dir / f"{safe}.marker"


def _write_fake_module(gen_root: Path, dir_rel: str, module_name: str,
                        calls_log: Path, marker_path: Path) -> None:
    full_dir = gen_root / dir_rel
    if "." in module_name:
        pkg, sub = module_name.split(".", 1)
        pkg_dir = full_dir / pkg
        pkg_dir.mkdir(parents=True, exist_ok=True)
        init_file = pkg_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("")
        target = pkg_dir / f"{sub}.py"
    else:
        full_dir.mkdir(parents=True, exist_ok=True)
        target = full_dir / f"{module_name}.py"

    calls_log_literal = repr(str(calls_log))
    marker_literal = repr(str(marker_path))
    source = (
        "import json\n\n"
        "def main(argv):\n"
        f"    with open({calls_log_literal}, 'a') as f:\n"
        "        f.write(json.dumps(argv) + '\\n')\n"
        f"    with open({marker_literal}, 'a') as f:\n"
        "        f.write('1\\n')\n"
        "    return 7\n"
    )
    target.write_text(source)


def _read_lines(path: Path):
    if not path.exists():
        return []
    return path.read_text().splitlines()


def _marker_count(path: Path) -> int:
    return len(_read_lines(path))


def test_dispatch_strips_and_routes_every_row(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    calls_log = project / "calls.log"
    markers_dir = project / "markers"
    markers_dir.mkdir()

    unique_pairs = []
    seen = set()
    for _, dir_rel, module_name, _ in ROWS:
        key = (dir_rel, module_name)
        if key not in seen:
            seen.add(key)
            unique_pairs.append(key)

    for dir_rel, module_name in unique_pairs:
        marker_path = _marker_path(markers_dir, dir_rel, module_name)
        _write_fake_module(project, dir_rel, module_name, calls_log, marker_path)

    for words, dir_rel, module_name, strip in ROWS:
        target_key = (dir_rel, module_name)
        before_markers = {
            k: _marker_count(_marker_path(markers_dir, *k)) for k in unique_pairs
        }
        before_calls = _read_lines(calls_log)

        argv = list(words) + ["x", "--flag", f"--repo-root={project}"]
        code = hotdocs_cli.main(argv)

        after_markers = {
            k: _marker_count(_marker_path(markers_dir, *k)) for k in unique_pairs
        }
        after_calls = _read_lines(calls_log)

        assert code == 7

        for k in unique_pairs:
            expected_delta = 1 if k == target_key else 0
            assert after_markers[k] == before_markers[k] + expected_delta, (
                f"verb {words!r} marker mismatch for {k}: "
                f"before={before_markers[k]} after={after_markers[k]}"
            )

        assert len(after_calls) == len(before_calls) + 1
        expected_tokens = argv[strip:]
        assert json.loads(after_calls[-1]) == expected_tokens


def test_system_exit_codes_are_caught_and_translated(tmp_path):
    project = tmp_path / "project2"
    project.mkdir()
    gen_dir = project / "gen" / "spec-linter"
    gen_dir.mkdir(parents=True)
    state_path = project / "state.txt"
    module_path = gen_dir / "spec_linter.py"

    state_literal = repr(str(state_path))
    source = (
        "import os\n\n"
        f"_STATE = {state_literal}\n\n"
        "def main(argv):\n"
        "    n = 0\n"
        "    if os.path.exists(_STATE):\n"
        "        n = int(open(_STATE).read().strip())\n"
        "    with open(_STATE, 'w') as f:\n"
        "        f.write(str(n + 1))\n"
        "    if n == 0:\n"
        "        raise SystemExit(3)\n"
        "    elif n == 1:\n"
        "        raise SystemExit(None)\n"
        "    else:\n"
        "        raise SystemExit('boom')\n"
    )
    module_path.write_text(source)

    argv = ["lint", "x", "--flag", f"--repo-root={project}"]

    code1 = hotdocs_cli.main(argv)
    code2 = hotdocs_cli.main(argv)
    code3 = hotdocs_cli.main(argv)

    assert code1 == 3
    assert code2 == 0
    assert code3 == 1


def test_fresh_module_per_repo_root_does_not_leak_between_projects(tmp_path):
    project_a = tmp_path / "proj_a"
    project_b = tmp_path / "proj_b"
    project_a.mkdir()
    project_b.mkdir()

    log_a = project_a / "calls.log"
    log_b = project_b / "calls.log"

    gen_a = project_a / "gen" / "spec-linter"
    gen_a.mkdir(parents=True)
    log_a_literal = repr(str(log_a))
    (gen_a / "spec_linter.py").write_text(
        "import json\n\n"
        "def main(argv):\n"
        f"    with open({log_a_literal}, 'a') as f:\n"
        "        f.write(json.dumps(argv) + '\\n')\n"
        "    return 11\n"
    )

    gen_b = project_b / "gen" / "spec-linter"
    gen_b.mkdir(parents=True)
    log_b_literal = repr(str(log_b))
    (gen_b / "spec_linter.py").write_text(
        "import json\n\n"
        "def main(argv):\n"
        f"    with open({log_b_literal}, 'a') as f:\n"
        "        f.write(json.dumps(argv) + '\\n')\n"
        "    return 55\n"
    )

    argv_a = ["lint", "x", f"--repo-root={project_a}"]
    argv_b = ["lint", "x", f"--repo-root={project_b}"]

    code_a = hotdocs_cli.main(argv_a)
    code_b = hotdocs_cli.main(argv_b)

    assert code_a == 11
    assert code_b == 55
    assert _read_lines(log_a) == [json.dumps(argv_a[1:])]
    assert _read_lines(log_b) == [json.dumps(argv_b[1:])]