# hotdocs-criterion: sha256:f3c66d10c59aeb1107495127b46941c16fa83e73e1c38d1aa669ceeac531c38b
import dataclasses
import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def to_plain(value):
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_plain(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dict__"):
        return {k: to_plain(v) for k, v in vars(value).items() if not k.startswith("__")}
    return repr(value)


def flatten_text(value):
    plain = to_plain(value)
    parts = []

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                parts.append(str(k))
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        else:
            parts.append(str(v))

    walk(plain)
    parts.append(repr(plain))
    return "\n".join(parts)


def git(repo_root, *args):
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    })
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"] + list(args),
        cwd=str(repo_root), env=env, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def generated_code(version, count):
    markers = []
    lines = ["# generated code version " + version + "\n"]
    for i in range(count):
        marker = "GENMARK_" + version + "_" + str(i) + "_zq7x"
        markers.append(marker)
        lines.append("def " + marker.lower() + "_fn(x):\n")
        lines.append("    " + marker + " = x * " + str(i + 1) + "\n")
        lines.append("    return " + marker + "\n")
        lines.append("\n")
    return "".join(lines), markers


def component_md(title):
    return (
        "---\n"
        "id: comp-foo\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n\n"
        "# Foo\n\nThe foo component.\n"
    )


def requirement_md(text):
    return "# R-FOO-001\n\n**R-FOO-001** — " + text + "\n"


ACCEPTANCE_MD = (
    "# AC-FOO-001\n\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n\n"
    "```gherkin\n"
    "Given foo\n"
    "When it runs\n"
    "Then it works\n"
    "```\n"
)

INTERFACE_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"


def tracker_source():
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "0" * 64,
                    "versions": {"python": "3.12.4"}, "lockfile_sha256": None}],
        "overall": "pass",
    }
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report,
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }
    return (
        "REPORT = " + repr(report) + "\n\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    import copy\n"
        "    result = copy.deepcopy(REPORT)\n"
        "    result['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return result\n\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def test_ac_packet_010_no_generated_code_diff_in_packet(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git(repo_root, "init")

    comp_dir = repo_root / "specs" / "components" / "foo"
    gen_file = repo_root / "gen" / "foo" / "foo.py"
    write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", tracker_source())

    # Commit 1: original spec and generated code.
    v1_code, v1_markers = generated_code("v1", 15)
    write(comp_dir / "component.md", component_md("Foo"))
    write(comp_dir / "requirements" / "R-FOO-001.md", requirement_md("Foo MUST return x."))
    write(comp_dir / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    write(comp_dir / "interface" / "library.md", INTERFACE_MD)
    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    write(gen_file, v1_code)
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-m", "initial")

    # Commit 2: spec changed and generated code rewritten substantially.
    v2_code, v2_markers = generated_code("v2", 25)
    write(comp_dir / "requirements" / "R-FOO-001.md", requirement_md("Foo MUST return twice x."))
    write(gen_file, v2_code)
    write(repo_root / "gen" / "foo" / "extra_generated.py", generated_code("v2extra", 10)[0])
    v2extra_markers = generated_code("v2extra", 10)[1]
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-m", "change foo")

    # Working tree: further substantial uncommitted change to generated code and spec.
    v3_code, v3_markers = generated_code("v3", 20)
    write(comp_dir / "requirements" / "R-FOO-001.md", requirement_md("Foo MUST return thrice x."))
    write(gen_file, v3_code)

    all_markers = v1_markers + v2_markers + v2extra_markers + v3_markers

    packet = review_packet_builder.build_review_packet(["comp-foo", "R-FOO-001"], repo_root)

    spec_diff = field(packet, "spec_diff")
    assert isinstance(spec_diff, str)

    text = flatten_text(packet)
    leaked = [m for m in all_markers if m in text or m.lower() in text]
    assert leaked == [], "generated-code diff content found in packet: " + repr(leaked[:5])
    assert "generated code version" not in text