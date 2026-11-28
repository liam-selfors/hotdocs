# hotdocs-criterion: sha256:b90653681e45e72423419bfedb1141550a6b501e316ce306e82afbdd17db699c
import json
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    for slug, prefix in (("alpha", "ALPHA"), ("beta", "BETA")):
        base = repo_root / "specs" / "components" / slug
        _write(
            base / "component.md",
            "---\n"
            "id: comp-" + slug + "\n"
            "title: " + slug.capitalize() + "\n"
            "status: draft\n"
            "owners: [test-team]\n"
            "depends_on: []\n"
            "sealed: true\n"
            "source_path: legacy/" + slug + "/\n"
            "---\n\n"
            "# " + slug.capitalize() + "\n\n"
            "A fixture component.\n",
        )
        rid = "R-" + prefix + "-001"
        aid = "AC-" + prefix + "-001"
        _write(
            base / "requirements" / (rid + ".md"),
            "# " + rid + "\n\n"
            "**" + rid + "** — MUST do the " + slug + " thing.\n",
        )
        _write(
            base / "acceptance" / (aid + ".md"),
            "# " + aid + "\n\n"
            "Covers: " + rid + "\n"
            "Kind: generated-test\n\n"
            "```gherkin\n"
            "Given a thing\n"
            "When it runs\n"
            "Then the " + slug + " thing is done\n"
            "```\n",
        )


def _write_fakes(repo_root, log_path):
    log = repr(str(log_path))
    log_helper = (
        "import json\n"
        "def _log(entry):\n"
        "    with open(" + log + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
    )

    linter_src = (
        log_helper
        + "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    _log({'call': 'lint'})\n"
        "    return {'findings': [], 'summary': "
        "{'hard_failures': 0, 'warnings': 0, 'skipped': 0}}\n"
    )
    _write(repo_root / "gen" / "spec-linter" / "spec_linter.py", linter_src)

    impacted = [
        {"component_id": "comp-alpha", "reason": "direct", "via": None,
         "guarantee_ids": None},
        {"component_id": "comp-beta", "reason": "transitive-interface",
         "via": "comp-alpha", "guarantee_ids": None},
    ]
    impact_src = (
        log_helper
        + "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log({'call': 'compute_blast_radius', 'changed_ids': list(changed_ids)})\n"
        "    return {'impacted': " + repr(impacted) + ", "
        "'precondition_error': None}\n"
    )
    _write(repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py", impact_src)

    reviewer_src = (
        log_helper
        + "class _Report:\n"
        "    def __init__(self, targets):\n"
        "        self.targets = list(targets)\n"
        "        self.criteria_checked = []\n"
        "        self.findings = []\n"
        "        self.gaps = []\n"
        "        self.writable = {}\n"
        "        self.lint_findings = []\n"
        "        self.proposals = []\n"
        "        self.degraded = True\n"
        "    def __getitem__(self, key):\n"
        "        return self.to_dict()[key]\n"
        "    def to_dict(self):\n"
        "        return {'targets': list(self.targets),\n"
        "                'criteria_checked': list(self.criteria_checked),\n"
        "                'findings': list(self.findings),\n"
        "                'gaps': list(self.gaps),\n"
        "                'writable': dict(self.writable),\n"
        "                'lint_findings': list(self.lint_findings),\n"
        "                'proposals': list(self.proposals),\n"
        "                'degraded': self.degraded}\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, "
        "write_proposals=False):\n"
        "    _log({'call': 'check', 'targets': list(targets)})\n"
        "    return _Report(targets)\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    _log({'call': 'glossary_judge'})\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    return judge\n"
    )
    _write(repo_root / "gen" / "spec-reviewer" / "spec_reviewer.py", reviewer_src)

    endpoint_src = (
        log_helper
        + "def complete(prompt, model, backend=None, **params):\n"
        "    _log({'call': 'complete'})\n"
        "    return {'text': " + repr(json.dumps(
            {"completeness_score": 1.0, "completeness_rationale": "ok"})) + ", "
        "'model': model, 'backend': 'mock', 'model_call_error': None}\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


def _read_log(log_path):
    if not log_path.is_file():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_assist_002_predicted_blast_radius_lists_impacted_components(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    _build_corpus(repo_root)
    _write_fakes(repo_root, log_path)

    report = spec_completeness_assistant.assist(["R-ALPHA-001"], repo_root)

    calls = _read_log(log_path)
    blast_calls = [c for c in calls if c["call"] == "compute_blast_radius"]
    assert len(blast_calls) == 1, calls
    assert blast_calls[0]["changed_ids"] == ["R-ALPHA-001"]

    assert field(report, "halted") is False
    assert list(field(report, "predicted_blast_radius")) == ["comp-alpha", "comp-beta"]
    assert report.to_dict()["predicted_blast_radius"] == ["comp-alpha", "comp-beta"]