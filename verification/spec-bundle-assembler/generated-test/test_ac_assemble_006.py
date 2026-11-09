import hashlib
import json
import tempfile
from pathlib import Path

import spec_bundle_assembler


def _write_corpus(repo_root: Path) -> None:
    glossary = repo_root / "specs" / "glossary.md"
    glossary.parent.mkdir(parents=True, exist_ok=True)
    glossary.write_text(
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
        encoding="utf-8",
    )

    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
        encoding="utf-8",
    )

    req_dir = comp_dir / "requirements"
    req_dir.mkdir(parents=True, exist_ok=True)
    (req_dir / "R-FOO-001.md").write_text(
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
        encoding="utf-8",
    )

    acc_dir = comp_dir / "acceptance"
    acc_dir.mkdir(parents=True, exist_ok=True)
    (acc_dir / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
        encoding="utf-8",
    )

    iface_dir = comp_dir / "interface"
    iface_dir.mkdir(parents=True, exist_ok=True)
    (iface_dir / "library.md").write_text(
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n",
        encoding="utf-8",
    )

    (comp_dir / "constraints.md").write_text(
        "# Constraints\n"
        "\n"
        "None.\n",
        encoding="utf-8",
    )


def _get_field(bundle, name, default=None):
    if isinstance(bundle, dict):
        return bundle.get(name, default)
    return getattr(bundle, name, default)


def _canonical_dict(bundle):
    fields = [
        "component_id",
        "spec_bundle_hash",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
        "hint_code",
    ]
    result = {}
    for field in fields:
        value = _get_field(bundle, field)
        if isinstance(value, dict):
            result[field] = dict(sorted(value.items()))
        else:
            result[field] = value
    return result


def test_assemble_is_deterministic_across_two_runs():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _write_corpus(repo_root)

        bundle_first = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
        bundle_second = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

        first_dict = _canonical_dict(bundle_first)
        second_dict = _canonical_dict(bundle_second)

        assert first_dict == second_dict

        first_bytes = json.dumps(first_dict, sort_keys=True).encode("utf-8")
        second_bytes = json.dumps(second_dict, sort_keys=True).encode("utf-8")

        assert first_bytes == second_bytes

        first_digest = hashlib.sha256(first_bytes).hexdigest()
        second_digest = hashlib.sha256(second_bytes).hexdigest()

        assert first_digest == second_digest

        assert _get_field(bundle_first, "spec_bundle_hash")
        assert _get_field(bundle_first, "spec_bundle_hash") == _get_field(bundle_second, "spec_bundle_hash")