import review_packet_builder

import dataclasses
import json
import os
import subprocess
from pathlib import Path


# Distinctive tokens that appear ONLY inside generated code (never in specs,
# never in the provenance-tracker stand-in). If any of them shows up anywhere
# in the packet, generated-code diff content leaked into it.
OLD_TAG = "OLDGENQXW7"
NEW_TAG = "NEWGENZVK4"
WIP_TAG = "WIPGENKMR2"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _plain(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _plain(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(v) for v in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dict__"):
        return _plain(vars(value))
    return str(value)


def _git(repo_root, *args):
    env = dict(os.environ)
    env.setdefault("GIT_CONFIG_NOSYSTEM", "1")
    subprocess.run(
        [
            "git",
            "-c", "user.name=Test User",
            "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false",
            "-c", "init.defaultBranch=main",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        env=env,
    )


def _gen_code(tag, n=80):
    lines = [
        f'"""Generated module body {tag}."""',
        "",
        f"# {tag} generated header comment",
        "",
    ]
    for i in range(n):
        lines.append(f"def {tag}_func_{i}(x):")
        lines.append(f"    # {tag} step {i}")
        lines.append(f"    return x * {i} + len('{tag}_literal_{i}')")
        lines.append("")
    return "\n".join(lines) + "\n"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_specs(repo_root, requirement_text):
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A small fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n" + requirement_text + "\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a foo\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")


def _verify_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [
                        {
                            "id": "AC-FOO-001",
                            "covers": "R-FOO-001",
                            "kind": "generated-test",
                            "result": "pass",
                        }
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def _write_provenance_stand_in(repo_root):
    report_literal = repr(_verify_report())
    source = (
        "import copy\n"
        "\n"
        "_REPORT = " + report_literal + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        source,
    )


def _build_fixture(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init")

    # Base state: original spec + original generated code.
    _write_specs(repo_root, "The foo MUST return a number.")
    _write(repo_root / "gen" / "foo" / "foo.py", _gen_code(OLD_TAG))
    _write_provenance_stand_in(repo_root)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "base")
    _git(repo_root, "branch", "-M", "main")

    # PR branch: spec changed, generated code rewritten substantially.
    _git(repo_root, "checkout", "-b", "feature")
    _write_specs(repo_root, "The foo MUST return a number, doubled on request.")
    _write(repo_root / "gen" / "foo" / "foo.py", _gen_code(NEW_TAG, n=120))
    _write(repo_root / "gen" / "foo" / "extra_helpers.py", _gen_code(NEW_TAG + "_x", n=40))
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "change foo")

    # Uncommitted working-tree change as well, so the generated-code change
    # is visible whichever diff base the builder uses.
    _write_specs(repo_root, "The foo MUST return a number, tripled on request.")
    _write(repo_root / "gen" / "foo" / "foo.py", _gen_code(WIP_TAG, n=100))

    return repo_root


def test_packet_contains_no_generated_code_diff(tmp_path):
    repo_root = _build_fixture(tmp_path)

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001"], repo_root
    )

    # Sanity: it is a ReviewPacket-shaped value.
    spec_diff = field(packet, "spec_diff")
    assert isinstance(spec_diff, str)

    plain = _plain(packet)
    serialized = json.dumps(plain, sort_keys=True, default=str)
    blob = serialized + "\n" + spec_diff

    for tag in (OLD_TAG, NEW_TAG, WIP_TAG):
        assert tag not in blob, (
            f"generated-code content ({tag}) leaked into the review packet"
        )

    # No unified-diff hunks/headers targeting generated code either.
    for header in (
        "a/gen/foo/foo.py",
        "b/gen/foo/foo.py",
        "--- gen/foo/foo.py",
        "+++ gen/foo/foo.py",
        "b/gen/foo/extra_helpers.py",
        "+++ gen/foo/extra_helpers.py",
    ):
        assert header not in blob, (
            f"generated-code diff header {header!r} found in the review packet"
        )