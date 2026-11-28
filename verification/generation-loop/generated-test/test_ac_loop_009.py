# hotdocs-criterion: sha256:fa5194a2f04e369791acf476ed5939387593f1e1d2b724704766b2c71cabc16d
import sys
from pathlib import Path

import generation_loop


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _log_helper(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(name):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(name + '\\n')\n"
        "\n"
    )


def _write(path, source):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _generation_result(files, model_call_error):
    return {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "m",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": files,
        "model_call_error": model_call_error,
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def _write_generator(repo_root, log_path, result):
    source = (
        _log_helper(log_path)
        + "RESULT = " + repr(result) + "\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    _log('generate')\n"
        "    return dict(RESULT)\n"
        "\n"
        "def commit_cache(result, repo_root=None):\n"
        "    _log('commit_cache')\n"
        "    return None\n"
    )
    _write(repo_root / "gen" / "generator" / "generator.py", source)


def _write_agentic_generator(repo_root, log_path):
    source = (
        _log_helper(log_path)
        + "def generate_agentic(bundle, model, retry_feedback=None, *, repo_root=None,\n"
        "                     allow_unisolated_exec=False, max_turns=40, max_tool_calls=120,\n"
        "                     wall_seconds=1800.0, claude_command='claude'):\n"
        "    _log('generate_agentic')\n"
        "    raise RuntimeError('agentic generation must not run in single mode')\n"
    )
    _write(repo_root / "gen" / "agentic-generator" / "agentic_generator.py", source)


def _write_surface_checker(repo_root, log_path):
    source = (
        _log_helper(log_path)
        + "GATE_VERSION = 'surface-checker@1.2.0'\n"
        "\n"
        "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    _log('check_surface')\n"
        "    return " + repr({"ok": True, "findings": []}) + "\n"
    )
    _write(repo_root / "gen" / "surface-checker" / "surface_checker.py", source)


def _write_verifier(repo_root, log_path):
    report = {
        "component_id": "comp-widget",
        "criteria": [
            {
                "id": "AC-W-001",
                "covers": "R-W-1",
                "kind": "generated-test",
                "result": "fail",
                "failure_origin": "environment",
                "failure_detail": {"message": "javascript needs node >= 24"},
            },
            {
                "id": "AC-W-002",
                "covers": "R-W-2",
                "kind": "generated-test",
                "result": "fail",
                "failure_origin": "implementation",
                "failure_detail": {"message": "assertion failed"},
            },
        ],
        "requirement_results": {"R-W-1": "fail", "R-W-2": "fail"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "fail",
    }
    source = (
        _log_helper(log_path)
        + "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify')\n"
        "    return dict(REPORT)\n"
    )
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        source,
    )


def _write_closure_deps(repo_root, log_path):
    author_result = {
        "component_id": "comp-widget",
        "criterion_id": "AC-W-001",
        "model": "m",
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": None,
        "model_call_error": {"category": "network", "message": "unused"},
        "repair_attempts": 0,
        "probe_findings": [],
    }
    source = (
        _log_helper(log_path)
        + "GATE_VERSION = 'generated_test@3.0.0'\n"
        "RESULT = " + repr(author_result) + "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    _log('author_test')\n"
        "    return dict(RESULT)\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", source)
    response = {
        "text": "pass",
        "model": "m",
        "backend": "mock",
        "model_call_error": None,
    }
    source = (
        _log_helper(log_path)
        + "RESPONSE = " + repr(response) + "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log('complete')\n"
        "    return dict(RESPONSE)\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", source)


def _build(repo_root, log_path, generation_result):
    _write_generator(repo_root, log_path, generation_result)
    _write_agentic_generator(repo_root, log_path)
    _write_surface_checker(repo_root, log_path)
    _write_verifier(repo_root, log_path)
    _write_closure_deps(repo_root, log_path)


def _calls(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def _bundle():
    return {"component_id": "comp-widget", "spec_bundle_hash": "sha256:" + "0" * 64}


def test_environment_failure_origin_in_verification_stops_loop(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build(repo_root, log_path, _generation_result({"widget.py": "X = 1"}, None))

    result = generation_loop.run_attempts(
        "comp-widget", _bundle(), repo_root, "m", max_attempts=3
    )

    calls = _calls(log_path)
    assert calls.count("generate") == 1
    assert calls.count("verify") == 1
    assert "commit_cache" not in calls
    assert "generate_agentic" not in calls

    attempts = field(result, "attempts")
    assert len(attempts) == 1
    attempt = attempts[0]
    assert field(attempt, "outcome") == "verification_failed"
    assert field(attempt, "failed_requirements") == ["R-W-2"]
    assert field(result, "passed") is False
    assert field(result, "stop_reason") == "environment"


def test_environment_generation_error_stops_loop(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build(
        repo_root,
        log_path,
        _generation_result(
            {},
            {"category": "environment", "message": "javascript needs node >= 24"},
        ),
    )

    result = generation_loop.run_attempts(
        "comp-widget", _bundle(), repo_root, "m", max_attempts=3
    )

    calls = _calls(log_path)
    assert calls.count("generate") == 1
    assert "verify" not in calls
    assert "commit_cache" not in calls

    attempts = field(result, "attempts")
    assert len(attempts) == 1
    assert field(attempts[0], "outcome") == "generation_failed"
    assert field(result, "stop_reason") == "environment"