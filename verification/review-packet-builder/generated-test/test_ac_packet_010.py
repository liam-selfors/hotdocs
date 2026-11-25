# hotdocs-criterion: sha256:d51c347f162e5c69be4a53951227ac9042bfc013d88937a0101fa7d5c84a007c
import dataclasses
import json
import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PACKET_FIELDS = [
    "spec_diff",
    "changed_requirements",
    "regenerated_components",
    "verification_results",
    "compliance_flags",
    "provenance_hit_status",
    "capability_scenarios",
    "exemption_changes",
    "residual_risk",
]


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
    return repr(value)


def git(repo_root, *args):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "Test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "Test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.invalid"
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        env=env,
    )


def gen_code(tag, count):
    lines = ["# generated module " + tag]
    for i in range(count):
        lines.append(
            "def gencode_" + tag + "_func_" + str(i) + "():\n"
            "    return 'GENCODEMARKER_" + tag + "_VALUE_" + str(i) + "'\n"
        )
    return "\n".join(lines) + "\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def component_md():
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n"
    )


def requirement_text(version):
    return (
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** - The foo component MUST do thing version " + version + ".\n"
    )


def acceptance_text():
    return (
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: llm-judge\n"
        "\n"
        "Given foo\nWhen it runs\nThen it does the thing\n"
    )


def verify_report():
    verification = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "llm-judge",
             "result": "pass", "rationale": None},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
    }
    secret = {
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
    license_scan = {"blocked": False, "matches": []}
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification,
                "license_scan": license_scan,
                "secret_scan": secret,
            }
        },
        "capabilities": {},
        "secret_scan": secret,
        "not_ready_reasons": [],
    }


def write_standin(repo_root, log_path):
    src = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return " + repr(verify_report()) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", src)


def test_ac_packet_010_no_generated_code_diff(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "standin.log"

    git(repo_root, "init", "-q")

    comp_dir = repo_root / "specs" / "components" / "foo"
    write(comp_dir / "component.md", component_md())
    write(comp_dir / "requirements" / "R-FOO-001.md", requirement_text("one"))
    write(comp_dir / "acceptance" / "AC-FOO-001.md", acceptance_text())
    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "gen" / "foo" / "foo.py", gen_code("OLDA", 40))
    write_standin(repo_root, log_path)
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "initial")

    # Second commit: spec change plus a substantial generated-code rewrite.
    write(comp_dir / "requirements" / "R-FOO-001.md", requirement_text("two"))
    write(repo_root / "gen" / "foo" / "foo.py", gen_code("MIDB", 40))
    write(repo_root / "gen" / "foo" / "extra.py", gen_code("EXTRAC", 20))
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "regenerate")

    # Working-tree changes too, so whichever base the builder diffs against
    # there is substantial generated-code change visible.
    write(comp_dir / "requirements" / "R-FOO-001.md", requirement_text("three"))
    write(repo_root / "gen" / "foo" / "foo.py", gen_code("NEWD", 40))

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001"], repo_root
    )

    plain = {name: to_plain(field(packet, name)) for name in PACKET_FIELDS}
    whole = json.dumps(plain, sort_keys=True, default=repr)
    if isinstance(packet, dict):
        whole += json.dumps(to_plain(packet), sort_keys=True, default=repr)
    else:
        whole += json.dumps(to_plain(packet), sort_keys=True, default=repr)

    for tag in ("OLDA", "MIDB", "EXTRAC", "NEWD"):
        assert "GENCODEMARKER_" + tag not in whole, tag
        assert "gencode_" + tag not in whole, tag
        assert "generated module " + tag not in whole, tag
    assert "GENCODEMARKER" not in whole
    assert "gencode_" not in whole

    spec_diff = field(packet, "spec_diff")
    spec_diff_text = spec_diff if isinstance(spec_diff, str) else json.dumps(to_plain(spec_diff), default=repr)
    assert "gen/foo/" not in spec_diff_text
    assert "+++ b/gen/" not in whole
    assert "--- a/gen/" not in whole
    assert "diff --git a/gen/" not in whole