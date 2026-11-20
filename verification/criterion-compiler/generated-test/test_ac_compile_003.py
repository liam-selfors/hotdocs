# hotdocs-criterion: sha256:1b3c40d6cde1ff40778610023a8afad9429900fb2fcc2b07cadfafd8a0fb7839
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import criterion_compiler


SLUG = "widget"
COMPONENT_ID = "comp-widget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [widget-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/widget/\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A tiny fixture component used to exercise criterion compilation.\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    _write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — `greet` MUST greet by name.\n",
    )
    _write(
        comp / "requirements" / "R-WIDGET-002.md",
        "# R-WIDGET-002\n\n**R-WIDGET-002** — `greet` MUST honor punctuation.\n",
    )
    _write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a payload is \"hello\"\n"
        "When greet is invoked with {\"name\": payload}\n"
        "Then value equals \"hello!\"\n"
        "```\n",
    )
    _write(
        comp / "acceptance" / "AC-WIDGET-002.md",
        "# AC-WIDGET-002\n"
        "\n"
        "Covers: R-WIDGET-002\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a Thing with label: \"box\", count: 3\n"
        "Given a mark is \"?\"\n"
        "When greet is invoked with {\"punctuation\": mark, \"name\": \"zed\"}\n"
        "Then meta equals {\"b\": 1, \"a\": [1, true, null], \"c\": \"x\"}\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "greet(name: str, punctuation: str = \"!\") -> str\n"
        "```\n",
    )
    _write(
        comp / "interface" / "data" / "Thing.md",
        "# `Thing`\n"
        "\n"
        "```json\n"
        "{\"label\": \"box\", \"count\": 1}\n"
        "```\n",
    )


RUNNER_SOURCE = (
    "import json\n"
    "import sys\n"
    "from pathlib import Path\n"
    "import criterion_compiler\n"
    "\n"
    "def field(value, name):\n"
    "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
    "\n"
    "repo_root = Path(sys.argv[1])\n"
    "out = Path(sys.argv[2])\n"
    "for cid in sys.argv[3:]:\n"
    "    try:\n"
    "        report = criterion_compiler.compile(cid, repo_root, target='pytest', out_dir=out)\n"
    "    except Exception:\n"
    "        continue\n"
    "    summary = field(report, 'summary')\n"
    "    if summary.get('compiled', 0) >= 1:\n"
    "        print(json.dumps(summary, sort_keys=True))\n"
    "        sys.exit(0)\n"
    "sys.exit(3)\n"
)


def _module_search_dir():
    path = Path(criterion_compiler.__file__).resolve()
    if path.name == "__init__.py":
        return path.parent.parent
    return path.parent


def _run_in_subprocess(script, repo_root, out_dir, hash_seed):
    env = dict(os.environ)
    entries = [str(_module_search_dir())] + [p for p in sys.path if p]
    env["PYTHONPATH"] = os.pathsep.join(entries)
    env["PYTHONHASHSEED"] = hash_seed
    proc = subprocess.run(
        [sys.executable, str(script), str(repo_root), str(out_dir), COMPONENT_ID, SLUG],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, (
        "compile run failed in subprocess: rc=" + repr(proc.returncode)
        + " stdout=" + repr(proc.stdout) + " stderr=" + repr(proc.stderr)
    )
    return proc.stdout


def _snapshot(out_dir):
    files = {}
    for p in sorted(out_dir.rglob("*")):
        if p.is_file():
            files[p.relative_to(out_dir).as_posix()] = p.read_bytes()
    return files


def test_two_separate_process_runs_produce_byte_identical_output(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    script = script_dir / "run_compile.py"
    script.write_text(RUNNER_SOURCE, encoding="utf-8")

    out_dir = repo_root / "out"

    _run_in_subprocess(script, repo_root, out_dir, "1")
    first = _snapshot(out_dir)
    shutil.rmtree(out_dir)

    _run_in_subprocess(script, repo_root, out_dir, "2")
    second = _snapshot(out_dir)

    assert first, "first run produced no output files"
    assert sorted(first) == sorted(second), (
        "output file sets differ: " + repr(sorted(first)) + " vs " + repr(sorted(second))
    )
    for name in first:
        assert first[name] == second[name], "output file differs between runs: " + repr(name)