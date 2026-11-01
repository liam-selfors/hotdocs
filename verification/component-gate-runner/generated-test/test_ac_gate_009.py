import contextlib
import io
import json
import os
import textwrap
from pathlib import Path

import component_gate_runner


def _component_md() -> str:
    return textwrap.dedent("""\
        ---
        id: comp-foo
        title: Foo
        status: ratified
        owners: [lselfors@gmail.com]
        sealed: false
        last_ratified_commit: "0000000"
        ---

        # comp-foo

        Purpose: fixture component for AC-GATE-009.
        """)


def _provenance_checker_src() -> str:
    return textwrap.dedent("""\
        import json
        import os


        class _Key:
            spec_bundle_hash = "sha256:deadbeef"
            gate_versions = {
                "compiler": "criterion-compiler@1.0.0",
                "generated_test": "generated_test@1.0.0",
                "verifier": "verifier-orchestrator@2.0.0",
                "license_scanner": "license_scanner@3.1.0",
                "secret_scanner": "secret_scanner@0.0.0",
            }


        def _log(record):
            path = os.environ.get("GATE_TEST_CALL_LOG")
            if path:
                with open(path, "a") as f:
                    f.write(json.dumps(record) + "\\n")


        def current_provenance_key(component_id, repo_root):
            _log({"dep": "provenance-checker.current_provenance_key"})
            return _Key()


        def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
            _log({"dep": "provenance-checker.check_provenance"})
            return {
                "hit": False,
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            }
        """)


def _assembler_src() -> str:
    return textwrap.dedent("""\
        import json
        import os


        def _log(record):
            path = os.environ.get("GATE_TEST_CALL_LOG")
            if path:
                with open(path, "a") as f:
                    f.write(json.dumps(record) + "\\n")


        def assemble(component_id, repo_root, mode="cold"):
            _log({"dep": "spec-bundle-assembler.assemble"})
            return {
                "component_id": component_id,
                "spec_bundle_hash": "sha256:deadbeef",
                "spec": "spec text",
                "interface": "interface text",
                "constraints": "constraints text",
                "dependency_interfaces": {},
                "dependency_context": {},
                "dependency_usage": {},
                "vars": {},
                "glossary": "glossary text",
                "hint_code": None,
            }
        """)


def _generator_src(mode: str) -> str:
    if mode == "success":
        return textwrap.dedent("""\
            import json
            import os


            def _log(record):
                path = os.environ.get("GATE_TEST_CALL_LOG")
                if path:
                    with open(path, "a") as f:
                        f.write(json.dumps(record) + "\\n")


            def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
                _log({
                    "dep": "generator.generate",
                    "model": model,
                    "retry_feedback": retry_feedback,
                })
                return {
                    "component_id": "comp-foo",
                    "spec_bundle_hash": "sha256:deadbeef",
                    "model": model,
                    "prompt_version": "v1",
                    "cache_hit": False,
                    "files": {"foo.py": "print('hi')"},
                    "model_call_error": None,
                    "refused": None,
                    "retry_feedback": retry_feedback,
                }
            """)
    return textwrap.dedent("""\
        import json
        import os


        def _log(record):
            path = os.environ.get("GATE_TEST_CALL_LOG")
            if path:
                with open(path, "a") as f:
                    f.write(json.dumps(record) + "\\n")


        def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
            _log({
                "dep": "generator.generate",
                "model": model,
                "retry_feedback": retry_feedback,
            })
            return {
                "component_id": "comp-foo",
                "spec_bundle_hash": "sha256:deadbeef",
                "model": model,
                "prompt_version": "v1",
                "cache_hit": False,
                "files": {},
                "model_call_error": {"category": "network", "message": "boom"},
                "refused": None,
                "retry_feedback": retry_feedback,
            }
        """)


def _verifier_src() -> str:
    return textwrap.dedent("""\
        import json
        import os


        def _log(record):
            path = os.environ.get("GATE_TEST_CALL_LOG")
            if path:
                with open(path, "a") as f:
                    f.write(json.dumps(record) + "\\n")


        def verify(component_id, repo_root, judge=None, test_author=None):
            _log({"dep": "verifier-orchestrator.verify"})
            return {
                "component_id": component_id,
                "criteria": [],
                "requirement_results": {},
                "interface_drift": False,
                "mutation_score": 1.0,
                "overall": "pass",
            }
        """)


def _license_scanner_src() -> str:
    return textwrap.dedent("""\
        import json
        import os


        def _log(record):
            path = os.environ.get("GATE_TEST_CALL_LOG")
            if path:
                with open(path, "a") as f:
                    f.write(json.dumps(record) + "\\n")


        def scan(component_id, repo_root):
            _log({"dep": "license-scanner.scan"})
            return {
                "component_id": component_id,
                "gate_version": "license_scanner@3.1.0",
                "similarity_score": 0.0,
                "block_threshold": 0.70,
                "blocked": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            }
        """)


def _secret_scanner_src() -> str:
    return textwrap.dedent("""\
        import json
        import os


        def _log(record):
            path = os.environ.get("GATE_TEST_CALL_LOG")
            if path:
                with open(path, "a") as f:
                    f.write(json.dumps(record) + "\\n")


        def scan(repo_root):
            _log({"dep": "secret-scanner.scan"})
            return {
                "scope": "full",
                "gate_version": "secret_scanner@2.0.0",
                "flagged": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            }
        """)


def _provenance_tracker_src() -> str:
    return textwrap.dedent("""\
        import json
        import os


        def _log(record):
            path = os.environ.get("GATE_TEST_CALL_LOG")
            if path:
                with open(path, "a") as f:
                    f.write(json.dumps(record) + "\\n")


        def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
            _log({"dep": "provenance-tracker.write_attempt_record"})
            return {
                "attempt_id": "2026-01-01T00:00:00Z-abc123",
                "component_id": component_id,
                "timestamp": "2026-01-01T00:00:00Z",
                "spec_bundle_hash": spec_bundle_hash,
                "generation": {},
                "verification": None,
            }
        """)


def _provenance_writer_src() -> str:
    return textwrap.dedent("""\
        import json
        import os


        def _log(record):
            path = os.environ.get("GATE_TEST_CALL_LOG")
            if path:
                with open(path, "a") as f:
                    f.write(json.dumps(record) + "\\n")


        def write_provenance(component_id, inputs, repo_root):
            _log({"dep": "provenance-writer.write_provenance"})
            return None
        """)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_repo(repo_root: Path, generator_mode: str) -> Path:
    _write(repo_root / "specs" / "components" / "foo" / "component.md", _component_md())
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", _provenance_checker_src())
    _write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", _assembler_src())
    _write(repo_root / "gen" / "generator" / "generator.py", _generator_src(generator_mode))
    _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", _verifier_src())
    _write(repo_root / "gen" / "license-scanner" / "license_scanner.py", _license_scanner_src())
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", _secret_scanner_src())
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", _provenance_tracker_src())
    _write(repo_root / "gen" / "provenance-writer" / "provenance_writer.py", _provenance_writer_src())
    return repo_root


@contextlib.contextmanager
def _call_log_env(path: Path):
    old = os.environ.get("GATE_TEST_CALL_LOG")
    os.environ["GATE_TEST_CALL_LOG"] = str(path)
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("GATE_TEST_CALL_LOG", None)
        else:
            os.environ["GATE_TEST_CALL_LOG"] = old


def _run_main(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            result = component_gate_runner.main(argv)
        except SystemExit as exc:
            code = exc.code
        else:
            code = result
    return code, buf.getvalue()


def _read_call_log(path: Path):
    if not path.exists():
        return []
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def test_generate_json_pass_reports_unblocked_and_forwards_model_and_retry_feedback(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", "success")
    call_log = tmp_path / "calls.jsonl"
    with _call_log_env(call_log):
        code, output = _run_main([
            "generate", "comp-foo", "--model=m", "--seed=2",
            "--retry-feedback=R-FOO-001,R-FOO-002",
            "--repo-root=" + str(repo_root), "--format=json",
        ])

    assert code == 0
    result = json.loads(output)
    assert result["blocked"] is False

    gen_calls = [c for c in _read_call_log(call_log) if c["dep"] == "generator.generate"]
    assert len(gen_calls) == 1
    assert gen_calls[0]["model"] == "m"
    assert gen_calls[0]["retry_feedback"] == ["R-FOO-001", "R-FOO-002"]


def test_generate_text_pass_with_space_separated_flags(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", "success")
    call_log = tmp_path / "calls.jsonl"
    with _call_log_env(call_log):
        code, output = _run_main([
            "generate", "comp-foo", "--model", "m",
            "--repo-root", str(repo_root), "--format", "text",
        ])

    assert code == 0
    assert "comp-foo" in output
    assert "passed" in output


def test_generate_model_call_error_exits_1(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", "error")
    call_log = tmp_path / "calls.jsonl"
    with _call_log_env(call_log):
        code, _output = _run_main([
            "generate", "comp-foo", "--model=m",
            "--repo-root=" + str(repo_root), "--format=json",
        ])

    assert code == 1


def test_generate_usage_errors_exit_2_before_calling_any_dependency(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", "success")
    bad_argvs = [
        ["generate", "comp-foo", "--repo-root=" + str(repo_root), "--format=json"],
        ["generate", "comp-nope", "--model=m", "--repo-root=" + str(repo_root)],
        ["generate", "comp-foo", "--model=m", "--seed=x", "--repo-root=" + str(repo_root)],
        ["generate", "comp-foo", "--model=m", "--format=bogus", "--repo-root=" + str(repo_root)],
        ["generate", "comp-foo", "--model=m", "--totally-unknown=1", "--repo-root=" + str(repo_root)],
        ["build", "comp-foo", "--model=m"],
        ["generate", "comp-foo", "--repo-root=" + str(repo_root), "--model"],
    ]
    for index, argv in enumerate(bad_argvs):
        call_log = tmp_path / f"calls_{index}.jsonl"
        with _call_log_env(call_log):
            code, _output = _run_main(argv)
        assert code == 2, f"expected exit 2 for argv={argv!r}, got {code!r}"
        assert _read_call_log(call_log) == [], f"a dependency was called for argv={argv!r}"