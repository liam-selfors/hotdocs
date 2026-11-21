# hotdocs-criterion: sha256:6970d0cfbaee407fabb74aff63d50d88bb67b6cc54c41019eae250cf25fcf03d
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import review_packet_builder


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _verification_report(component_id, req_id, ac_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": ac_id, "covers": req_id, "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {req_id: "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "0" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "pass",
    }


def _build_component(repo_root, slug, upper):
    comp_id = "comp-" + slug
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + upper.capitalize() + " fixture component\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + comp_id + "\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        base / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** — The component MUST work.\n",
    )
    _write(
        base / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\nCovers: " + req_id + "\nKind: compiled\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "legacy" / slug / "__init__.py", "")
    return comp_id, req_id, ac_id


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
    )
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        env=env,
    )


def test_provenance_hit_status_reflects_each_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    foo_id, foo_req, foo_ac = _build_component(repo_root, "foo", "FOO")
    bar_id, bar_req, bar_ac = _build_component(repo_root, "bar", "BAR")

    hit_result = {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(foo_id, foo_req, foo_ac),
        "license_scan": {"blocked": False, "findings": []},
        "secret_scan": {"flagged": False, "findings": []},
    }
    miss_result = {
        "hit": False,
        "reason": "spec_bundle_hash differs",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
    report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {foo_id: hit_result, bar_id: miss_result},
        "capabilities": {},
        "not_ready_reasons": [
            bar_id + ": no provenance for current spec state — run hotdocs generate " + bar_id
        ],
    }

    log_path = tmp_path / "tracker_calls.log"
    tracker_src = (
        "import copy\n"
        "\n"
        "REPORT = " + repr(report) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    result = copy.deepcopy(REPORT)\n"
        "    result['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return result\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        tracker_src,
    )

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "fixture")

    changed_ids = [foo_id, bar_id, foo_req, bar_req]
    packet = review_packet_builder.build_review_packet(changed_ids, repo_root)

    assert log_path.is_file(), "provenance-tracker stand-in was never called"
    assert "check_readiness" in log_path.read_text(encoding="utf-8").splitlines()

    status = field(packet, "provenance_hit_status")
    assert foo_id in status, "provenance hit status missing for " + foo_id
    assert bar_id in status, "provenance hit status missing for " + bar_id
    assert status[foo_id] is True
    assert status[bar_id] is False