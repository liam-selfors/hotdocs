# hotdocs-criterion: sha256:eb1a729b9c04922f5547aefbc9fff993e9f5a126fd240b30d5d2a8740ed88ca6
import spec_completeness_assistant

import os
from pathlib import Path


EXPECTED_FIELDS = [
    "lint_findings",
    "halted",
    "predicted_blast_radius",
    "criterion_reviews",
    "completeness_score",
    "completeness_rationale",
    "redundancy_flags",
    "degraded",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_corpus(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** - The foo component MUST return 1.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "Given foo, when called, then it returns 1.\n",
    )


def build_fakes(repo_root, log_path):
    log = repr(str(log_path))
    log_fn = (
        "def _log(line):\n"
        "    with open(" + log + ", 'a') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
    )

    write(
        repo_root / "gen" / "spec-linter" / "spec_linter.py",
        log_fn
        + "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    _log('lint')\n"
        "    return {'findings': [], 'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0}}\n",
    )

    write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        log_fn
        + "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log('compute_blast_radius')\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': 'comp-foo', 'reason': 'direct', 'via': None},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n",
    )

    write(
        repo_root / "gen" / "spec-reviewer" / "spec_reviewer.py",
        log_fn
        + "class _Report:\n"
        "    def __init__(self, targets):\n"
        "        self._data = {\n"
        "            'targets': list(targets),\n"
        "            'criteria_checked': ['AC-FOO-001'],\n"
        "            'findings': [],\n"
        "            'gaps': [],\n"
        "            'writable': {'AC-FOO-001': None},\n"
        "            'lint_findings': [],\n"
        "            'proposals': [],\n"
        "            'degraded': True,\n"
        "        }\n"
        "    def __getitem__(self, key):\n"
        "        return self._data[key]\n"
        "    def __getattr__(self, name):\n"
        "        data = self.__dict__.get('_data', {})\n"
        "        if name in data:\n"
        "            return data[name]\n"
        "        raise AttributeError(name)\n"
        "    def to_dict(self):\n"
        "        return dict(self._data)\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        "    _log('check')\n"
        "    return _Report(targets)\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    _log('glossary_judge')\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    return judge\n",
    )

    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        log_fn
        + "def complete(prompt, model, backend=None, **params):\n"
        "    _log('complete')\n"
        "    return {\n"
        "        'text': None,\n"
        "        'model': model,\n"
        "        'backend': 'mock',\n"
        "        'model_call_error': {'category': 'network', 'message': 'fake'},\n"
        "    }\n",
    )


def snapshot(repo_root):
    result = {}
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            p = Path(dirpath) / name
            rel = p.relative_to(repo_root)
            if "__pycache__" in rel.parts:
                continue
            result[rel.as_posix()] = p.read_bytes()
    return result


def test_ac_assist_008_to_dict_holds_every_field_and_no_file_changes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    build_corpus(repo_root)
    build_fakes(repo_root, log_path)

    before = snapshot(repo_root)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    data = report.to_dict()
    assert isinstance(data, dict)
    for name in EXPECTED_FIELDS:
        assert name in data, "to_dict() is missing field " + repr(name)

    # The fakes were the dependencies used.
    calls = log_path.read_text().splitlines() if log_path.exists() else []
    assert "lint" in calls
    assert "compute_blast_radius" in calls

    after = snapshot(repo_root)
    assert sorted(after.keys()) == sorted(before.keys())
    for rel, content in before.items():
        assert after[rel] == content, "file changed under repo_root: " + rel