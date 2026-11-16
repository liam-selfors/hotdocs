import json
from pathlib import Path

import pytest

import spec_completeness_assistant


# ---------------------------------------------------------------------------
# Synthetic corpus (written verbatim, no dedent over interpolated text)
# ---------------------------------------------------------------------------

GLOSSARY_MD = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

COMPONENT_MD = (
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
    "Foo doubles a number.\n"
)

REQ_MD = "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"

AC_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

LIBRARY_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"


# ---------------------------------------------------------------------------
# Fake dependency modules
# ---------------------------------------------------------------------------

COMMON = '''import json
from pathlib import Path


class _AttrDict(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _log(record):
    with open(__LOG__, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")
'''

LINTER_SRC = COMMON + '''

SEVERITY = __SEVERITY__


class LintReport(dict):
    def __init__(self, findings):
        super().__init__()
        self["findings"] = findings
        self["summary"] = {
            "hard_failures": sum(1 for f in findings if f["severity"] == "fail"),
            "warnings": sum(1 for f in findings if f["severity"] == "warn"),
            "skipped": sum(1 for f in findings if f["severity"] == "skipped"),
        }

    @property
    def findings(self):
        return self["findings"]

    @property
    def hard_failures(self):
        return self["summary"]["hard_failures"]

    @property
    def warnings(self):
        return self["summary"]["warnings"]

    @property
    def skipped(self):
        return self["summary"]["skipped"]

    def to_json(self):
        return {
            "findings": [dict(f) for f in self["findings"]],
            "summary": dict(self["summary"]),
        }


def lint(paths, repo_root, strict=False, judge=None):
    _log({"fn": "lint"})
    finding = _AttrDict(
        rule_id="R-LINT-012",
        severity=SEVERITY,
        file="specs/components/foo/component.md",
        line=3,
        message="title should be more descriptive",
    )
    return LintReport([finding])
'''

IMPACT_SRC = COMMON + '''

def compute_blast_radius(changed_ids, repo_root):
    _log({"fn": "compute_blast_radius", "changed_ids": list(changed_ids)})
    return _AttrDict(
        impacted=[_AttrDict(component_id="comp-foo", reason="direct", via=None)],
        precondition_error=None,
    )
'''

ASSEMBLER_SRC = COMMON + '''

def assemble(component_id, repo_root, mode="cold"):
    _log({"fn": "assemble", "component_id": component_id, "mode": mode})
    hint = {"foo.py": "def foo(x):\\n    return 2 * x\\n"} if mode == "hint" else None
    return _AttrDict(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="- **Foo** - a test term.",
        hint_code=hint,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log({"fn": "assemble_criterion"})
    return _AttrDict(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="Given x = 2",
        requirement_text="foo(x) MUST return 2 * x.",
        interface="foo(x: int) -> int",
        glossary="- **Foo** - a test term.",
        dependency_interfaces={},
    )
'''

GENERATOR_SRC = COMMON + '''

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log({"fn": "generate", "model": model})
    h = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else getattr(bundle, "spec_bundle_hash")
    cid = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id")
    return _AttrDict(
        component_id=cid,
        spec_bundle_hash=h,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "def foo(x):\\n    return 2 * x\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''

LLM_SRC = COMMON + '''

COMPLETENESS = json.dumps({"completeness_score": 0.7, "completeness_rationale": "AC missing"})
REDUNDANCY = json.dumps({"redundancy_flags": []})


def _count():
    p = Path(__LOG__)
    if not p.is_file():
        return 0
    return sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip())


def complete(prompt, model, *, backend=None, **params):
    index = _count()
    _log({"fn": "complete", "model": model})
    text = COMPLETENESS if index % 2 == 0 else REDUNDANCY
    return {"text": text, "model": model, "backend": "fake", "model_call_error": None}


def parse_model(model):
    return (None, model)
'''


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fake(root, logs, slug, module, template, **subs):
    log = logs / (module + ".log")
    src = template.replace("__LOG__", repr(str(log)))
    for key, value in subs.items():
        src = src.replace(key, value)
    _write(root / "gen" / slug / (module + ".py"), src)
    return log


def make_repo(base, name, severity="warn", with_model=False):
    root = base / name
    logs = base / (name + "-logs")
    root.mkdir(parents=True)
    logs.mkdir(parents=True)

    _write(root / "specs" / "glossary.md", GLOSSARY_MD)
    comp = root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQ_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)

    _fake(root, logs, "spec-linter", "spec_linter", LINTER_SRC,
          __SEVERITY__=repr(severity))
    _fake(root, logs, "impact-analyzer", "impact_analyzer", IMPACT_SRC)
    _fake(root, logs, "spec-bundle-assembler", "spec_bundle_assembler", ASSEMBLER_SRC)
    llm_log = None
    if with_model:
        _fake(root, logs, "generator", "generator", GENERATOR_SRC)
        llm_log = _fake(root, logs, "llm-endpoint", "llm_endpoint", LLM_SRC)
    return root, llm_log


def run(argv):
    try:
        return spec_completeness_assistant.main(argv)
    except SystemExit as exc:
        return exc.code


def parse_json(out):
    text = out.strip()
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        return json.loads(text[start:end + 1])


def read_log(path):
    if path is None or not Path(path).is_file():
        return []
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.fixture(autouse=True)
def _cwd(tmp_path, monkeypatch):
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_json_degraded(tmp_path, capsys):
    root, _ = make_repo(tmp_path, "repo")
    rc = run(["--changed=R-FOO-001", f"--repo-root={root}", "--format=json"])
    out = capsys.readouterr().out
    assert rc == 0
    report = parse_json(out)
    assert report["predicted_blast_radius"] == ["comp-foo"]
    assert report["degraded"] is True


def test_text_degraded_space_separated_flags(tmp_path, capsys):
    root, _ = make_repo(tmp_path, "repo")
    rc = run(["--changed", "R-FOO-001", "--repo-root", str(root), "--format", "text"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "R-LINT-012" in out
    assert "comp-foo" in out


def test_model_json(tmp_path, capsys):
    root, llm_log = make_repo(tmp_path, "repo", with_model=True)
    rc = run(["--changed=R-FOO-001", f"--repo-root={root}",
              "--model=fake-model", "--format=json"])
    out = capsys.readouterr().out
    assert rc == 0
    calls = [c for c in read_log(llm_log) if c.get("fn") == "complete"]
    assert len(calls) >= 1
    assert all(c["model"] == "fake-model" for c in calls)
    report = parse_json(out)
    assert report["degraded"] is False
    assert report["completeness_score"] == pytest.approx(0.7)


def test_model_text(tmp_path, capsys):
    root, llm_log = make_repo(tmp_path, "repo", with_model=True)
    rc = run(["--changed=R-FOO-001", f"--repo-root={root}",
              "--model=fake-model", "--format=text"])
    out = capsys.readouterr().out
    assert rc == 0
    calls = [c for c in read_log(llm_log) if c.get("fn") == "complete"]
    assert len(calls) >= 1
    assert all(c["model"] == "fake-model" for c in calls)
    assert "0.7" in out


def test_fail_finding_returns_1(tmp_path, capsys):
    root, _ = make_repo(tmp_path, "repo", severity="fail")
    rc = run(["--changed=R-FOO-001", f"--repo-root={root}", "--format=json"])
    capsys.readouterr()
    assert rc == 1


def test_fail_finding_returns_1_text(tmp_path, capsys):
    root, _ = make_repo(tmp_path, "repo", severity="fail")
    rc = run(["--changed", "R-FOO-001", "--repo-root", str(root)])
    capsys.readouterr()
    assert rc == 1


@pytest.mark.parametrize(
    "argv_builder",
    [
        lambda r: [],
        lambda r: ["serve", "--changed=R-FOO-001"],
        lambda r: ["serve", "--changed=R-FOO-001", f"--repo-root={r}"],
        lambda r: [f"--repo-root={r}", "--format=json"],
        lambda r: ["--changed=R-FOO-001", f"--repo-root={r}", "--format=bogus"],
        lambda r: ["--changed=R-FOO-001", f"--repo-root={r}", "--bogus"],
        lambda r: ["--changed=R-FOO-001", f"--repo-root={r}", "--bogus=1"],
        lambda r: [f"--repo-root={r}", "--changed"],
        lambda r: ["--changed"],
    ],
    ids=[
        "empty",
        "stray-word",
        "stray-word-with-root",
        "no-changed",
        "bad-format",
        "unknown-flag",
        "unknown-flag-with-value",
        "changed-last-no-value",
        "changed-only-no-value",
    ],
)
def test_usage_errors_return_2(tmp_path, capsys, argv_builder):
    root, _ = make_repo(tmp_path, "repo")
    rc = run(argv_builder(str(root)))
    capsys.readouterr()
    assert rc == 2