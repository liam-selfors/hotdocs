# hotdocs-criterion: sha256:839146310d1de30d815802605b40b50831bc31d059c6f455da41d695edf76668
import dataclasses
import json
import subprocess
from pathlib import Path

import review_packet_builder


OLD_MARKER = "QZXOLDGENCODEMARKER"
NEW_MARKER = "QZXNEWGENCODEMARKER"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def to_plain(value):
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_plain(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_plain(dataclasses.asdict(value))
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dict__"):
        return to_plain(vars(value))
    return str(value)


def git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root), check=True, capture_output=True, text=True,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def component_md():
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [foo-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does foo things.\n"
    )


def requirement_md(text):
    return "# R-FOO-001\n\n**R-FOO-001** — " + text + "\n"


def acceptance_md():
    return (
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "When foo runs\n"
        "Then foo returns a value\n"
        "```\n"
    )


def old_gen_code():
    lines = ["# " + OLD_MARKER + " module header\n"]
    for i in range(30):
        lines.append("def old_fn_" + str(i) + "():\n")
        lines.append("    return " + repr(OLD_MARKER + "_" + str(i)) + "\n\n")
    return "".join(lines)


def new_gen_code():
    lines = ["# " + NEW_MARKER + " module header, fully rewritten\n"]
    lines.append("class " + NEW_MARKER + "Engine:\n")
    for i in range(40):
        lines.append("    def new_method_" + str(i) + "(self, x):\n")
        lines.append("        return (x, " + repr(NEW_MARKER + "_" + str(i)) + ")\n\n")
    return "".join(lines)


def verify_report():
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }
    license_scan = {
        "blocked": False,
        "matches": [],
        "gate_version": "license_scanner@1.0.0",
        "cache_hit": False,
    }
    secret_scan = {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report,
                "license_scan": license_scan,
                "secret_scan": secret_scan,
            }
        },
        "capabilities": {},
        "secret_scan": secret_scan,
        "not_ready_reasons": [],
    }


def tracker_source(log_path):
    return (
        "import os\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(verify_report()) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    import copy\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    )


def test_packet_contains_no_generated_code_diff(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker.log"

    git(repo_root, "init")
    git(repo_root, "symbolic-ref", "HEAD", "refs/heads/main")

    comp_dir = repo_root / "specs" / "components" / "foo"
    write(comp_dir / "component.md", component_md())
    write(comp_dir / "requirements" / "R-FOO-001.md",
          requirement_md("Foo MUST return a value."))
    write(comp_dir / "acceptance" / "AC-FOO-001.md", acceptance_md())
    write(repo_root / "legacy" / "foo" / "README.md", "legacy foo\n")
    write(repo_root / "gen" / "foo" / "foo.py", old_gen_code())
    write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
          tracker_source(log_path))

    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-m", "base")

    git(repo_root, "checkout", "-b", "feature")
    write(comp_dir / "requirements" / "R-FOO-001.md",
          requirement_md("Foo MUST return a value and MUST log each call."))
    write(repo_root / "gen" / "foo" / "foo.py", new_gen_code())
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-m", "change foo spec and regenerate")

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001"], repo_root
    )

    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text()

    # The packet is a real packet: it carries a spec diff field.
    field(packet, "spec_diff")

    plain = to_plain(packet)
    serialized = json.dumps(plain, default=str, ensure_ascii=False)
    texts = [serialized, repr(packet), repr(plain)]

    for text in texts:
        assert OLD_MARKER not in text
        assert NEW_MARKER not in text
        assert "old_fn_" not in text
        assert "new_method_" not in text
        assert "a/gen/foo/foo.py" not in text
        assert "b/gen/foo/foo.py" not in text